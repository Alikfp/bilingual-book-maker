#!/usr/bin/env python3
"""Split source text into sentences, translate via LLM, write book.json."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

import book_common as bc

ROOT = bc.ROOT
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# Abbreviations that should not end a sentence (French).
FR_ABBREV = re.compile(
    r"\b(M\.|Mme|Mlle|Dr|Prof|etc|vol|chap|p|pp|av|apr|env|ex|cf|ibid|art|n|no|nos|st|ste|s\.|c\.-à-d)\.\s*$",
    re.IGNORECASE,
)

# OCR / scan artifacts and other non-prose lines the LLM often skips.
PAGE_MARKER = re.compile(r"Page\s+\d+\s*$", re.IGNORECASE)
CHAPTER_NUMBER = re.compile(r"^\d+\.\s*$")

load_dotenv = bc.load_dotenv


def read_epub_text(source: Path) -> str:
    try:
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise SystemExit("Install epub support: pip install ebooklib beautifulsoup4") from exc

    book = epub.read_epub(str(source))
    parts: list[str] = []
    seen: set[str] = set()

    def append_document(item) -> None:
        item_id = item.get_id()
        if item_id in seen:
            return
        seen.add(item_id)
        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = soup.get_text(separator="\n")
        if text.strip():
            parts.append(text)

    # Spine order matches reading order; get_items() is manifest order (often wrong).
    for item_id, linear in book.spine:
        if linear == "no":
            continue
        item = book.get_item_with_id(item_id)
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        append_document(item)

    if not parts:
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                append_document(item)

    return "\n\n".join(parts)


def read_text(source: Path) -> str:
    suffix = source.suffix.lower()
    if suffix == ".txt":
        return source.read_text(encoding="utf-8")
    if suffix == ".epub":
        return read_epub_text(source)
    raise SystemExit(f"Unsupported format: {suffix} (use .txt or .epub)")


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    """French-oriented sentence splitter."""
    text = normalize_whitespace(text)
    paragraphs = re.split(r"\n\s*\n", text)
    sentences: list[str] = []

    for para in paragraphs:
        para = para.replace("\n", " ").strip()
        if not para:
            continue
        # Split on sentence-ending punctuation followed by space and uppercase/quote/number
        parts = re.split(r"(?<=[.!?…])\s+(?=[«\"'A-ZÀÂÄÉÈÊËÏÎÔÙÛÜŸ0-9])", para)
        buffer = ""
        for part in parts:
            candidate = f"{buffer} {part}".strip() if buffer else part.strip()
            if FR_ABBREV.search(candidate) or re.search(r"[;,:]\s*$", candidate):
                buffer = candidate
                continue
            if candidate:
                sentences.append(candidate)
            buffer = ""
        if buffer.strip():
            sentences.append(buffer.strip())

    return [s for s in sentences if len(s.strip()) > 1]


def load_manifest(source_dir: Path, args: argparse.Namespace) -> dict:
    manifest_path = source_dir / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    overrides = {
        "title": args.title,
        "author": args.author,
        "language": args.language,
        "translationLanguage": args.translation_language,
        "chapter": args.chapter,
    }
    for key, value in overrides.items():
        if value is not None:
            manifest[key if key != "translation_language" else "translationLanguage"] = value

    required = ["title", "language", "translationLanguage"]
    missing = [k for k in required if not manifest.get(k)]
    if missing:
        raise SystemExit(
            f"Missing manifest fields {missing}. "
            f"Create {manifest_path} or pass --title --language --translation-language"
        )
    return manifest


def load_template(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def format_system_prompt(manifest: dict) -> str:
    template = load_template("system.txt")
    characters = manifest.get("characterNames") or []
    if isinstance(characters, list):
        characters = ", ".join(characters)
    return template.format(
        title=manifest.get("title", ""),
        author=manifest.get("author", "Unknown"),
        language=manifest.get("language", ""),
        translationLanguage=manifest.get("translationLanguage", ""),
        year=manifest.get("year", "unknown"),
        genre=manifest.get("genre", "literary fiction"),
        translationStyle=manifest.get("translationStyle", "natural literary English"),
        notes=manifest.get("notes", "none"),
        characterNames=characters or "none",
    )


def format_prior_translations(translations: dict[int, str], count: int = 5) -> str:
    if not translations:
        return "(none yet — this is the start of the book)"
    items = sorted(translations.items())[-count:]
    lines = []
    for sid, trans in items:
        lines.append(f"  id={sid}: {trans}")
    return "\n".join(lines)


def build_window_block(
    sentences: list[dict],
    start_idx: int,
    end_idx: int,
    context_before: int,
    context_after: int,
) -> str:
    lines = []
    ctx_start = max(0, start_idx - context_before)
    ctx_end = min(len(sentences), end_idx + context_after)

    for i in range(ctx_start, ctx_end):
        sid = sentences[i]["id"]
        tag = "TRANSLATE" if start_idx <= i < end_idx else "CONTEXT"
        lines.append(f"[{tag}] id={sid}: {sentences[i]['original']}")
    return "\n".join(lines)


def call_llm(system: str, user: str, model: str, base_url: str, api_key: str) -> dict:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"LLM API error {exc.code}: {detail}") from exc

    content = body["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    if "translations" in parsed:
        return parsed
    if isinstance(parsed, list):
        return {"translations": parsed}
    raise SystemExit(f"Unexpected LLM response shape: {content[:200]}")


def auto_translation(original: str) -> str | None:
    """Return a pass-through translation for non-prose lines, or None."""
    text = original.strip()
    if not text:
        return None
    if PAGE_MARKER.search(text) or CHAPTER_NUMBER.fullmatch(text):
        return text
    return None


def fill_auto_translations(
    sentences: list[dict],
    missing_ids: set[int],
    into: dict[int, str],
) -> set[int]:
    by_id = {s["id"]: s for s in sentences}
    still_missing: set[int] = set()
    for sid in missing_ids:
        sentence = by_id.get(sid)
        if sentence is None:
            still_missing.add(sid)
            continue
        auto = auto_translation(sentence["original"])
        if auto is not None:
            into[sid] = auto
        else:
            still_missing.add(sid)
    return still_missing


def translate_window(
    manifest: dict,
    sentences: list[dict],
    start_idx: int,
    end_idx: int,
    translations: dict[int, str],
    *,
    model: str,
    base_url: str,
    api_key: str,
    context_before: int,
    context_after: int,
    _allow_retry: bool = True,
) -> dict[int, str]:
    system = format_system_prompt(manifest)
    user_template = load_template("user_window.txt")

    start_id = sentences[start_idx]["id"]
    end_id = sentences[end_idx - 1]["id"]
    total = len(sentences)
    percent = round((end_idx / total) * 100)

    user = user_template.format(
        startId=start_id,
        endId=end_id,
        totalSentences=total,
        percent=percent,
        chapter=manifest.get("chapter", "unknown"),
        priorTranslations=format_prior_translations(translations),
        sentenceBlock=build_window_block(
            sentences, start_idx, end_idx, context_before, context_after
        ),
    )

    result = call_llm(system, user, model, base_url, api_key)
    new_translations = {}
    for item in result["translations"]:
        sid = int(item["id"])
        new_translations[sid] = item["translation"].strip()

    expected_ids = {sentences[i]["id"] for i in range(start_idx, end_idx)}
    got_ids = set(new_translations)
    if expected_ids != got_ids:
        missing = expected_ids - got_ids
        extra = got_ids - expected_ids
        if extra:
            raise SystemExit(
                f"Translation ID mismatch. Missing: {sorted(missing)}. Extra: {sorted(extra)}"
            )
        missing = fill_auto_translations(sentences, missing, new_translations)
        if missing and _allow_retry:
            retry_indices = [
                i for i in range(start_idx, end_idx) if sentences[i]["id"] in missing
            ]
            print(
                f"  Retrying missing ids {sorted(missing)} …",
                flush=True,
            )
            return translate_window(
                manifest,
                sentences,
                min(retry_indices),
                max(retry_indices) + 1,
                translations | new_translations,
                model=model,
                base_url=base_url,
                api_key=api_key,
                context_before=context_before,
                context_after=context_after,
                _allow_retry=False,
            )
        if missing:
            raise SystemExit(
                f"Translation ID mismatch. Missing: {sorted(missing)}. Extra: []"
            )
    translations.update(new_translations)
    return translations


resolve_slug = bc.resolve_slug


def write_book_json(slug: str, manifest: dict, sentences: list[dict], translations: dict[int, str]) -> Path:
    book_dir = ROOT / "books" / slug
    book_dir.mkdir(parents=True, exist_ok=True)

    book = {
        "id": slug,
        "title": manifest["title"],
        "author": manifest.get("author", ""),
        "language": manifest["language"],
        "translationLanguage": manifest["translationLanguage"],
        "source": "llm",
        "cover": manifest.get("cover"),
        "sentences": [
            {
                "id": s["id"],
                "original": s["original"],
                "translation": translations.get(s["id"]),
            }
            for s in sentences
        ],
    }
    if not book["cover"]:
        book.pop("cover", None)

    out_path = book_dir / "book.json"
    out_path.write_text(json.dumps(book, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bc.update_catalog_entry(slug)
    return out_path


def run_translation(
    slug: str,
    *,
    src_dir: Path | None = None,
    from_id: int | None = None,
    to_id: int | None = None,
    limit: int | None = None,
    re_split: bool = False,
    dry_run: bool = False,
    window_size: int = 15,
    context: int = 5,
    model: str | None = None,
) -> dict:
    """Translate a batch (or all) sentences for a book slug. Returns run summary."""
    load_dotenv()

    src_dir = src_dir or bc.source_dir(slug)
    source = bc.find_source_file(src_dir)
    if source is None:
        raise SystemExit(f"No source file in {src_dir} (expected book.epub or book.txt)")

    manifest = bc.load_manifest_dict(src_dir)
    sentences = bc.load_sentences_cache(src_dir, source, re_split=re_split)
    translations = bc.load_translations(src_dir)

    total = len(sentences)
    start_id = from_id or bc.next_untranslated_id(translations, total) or 1
    if start_id < 1 or start_id > total:
        return {"slug": slug, "translated": 0, "from_id": start_id, "to_id": start_id, "complete": True}

    from_idx = start_id - 1
    if limit is not None:
        to_idx = min(from_idx + limit, total)
    elif to_id is not None:
        to_idx = min(to_id, total)
    else:
        to_idx = total

    end_id = sentences[to_idx - 1]["id"] if to_idx > from_idx else start_id
    print(f"Book: {manifest['title']} ({total} sentences total)")
    print(f"This run: translate ids {start_id}–{end_id} ({to_idx - from_idx} sentences)")

    if dry_run:
        for s in sentences[from_idx:to_idx][:5]:
            print(f"  [{s['id']}] {s['original'][:80]}…")
        print("  …")
        return {"slug": slug, "translated": 0, "from_id": start_id, "to_id": end_id, "dry_run": True}

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Set OPENAI_API_KEY in .env or environment")

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = model or os.environ.get("MODEL", "gpt-4o-mini")

    idx = from_idx
    while idx < to_idx:
        end = min(idx + window_size, to_idx)
        print(f"  Window {sentences[idx]['id']}–{sentences[end - 1]['id']} …", flush=True)
        translations = translate_window(
            manifest,
            sentences,
            idx,
            end,
            translations,
            model=model,
            base_url=base_url,
            api_key=api_key,
            context_before=context,
            context_after=context,
        )
        bc.save_translations(src_dir, translations)
        idx = end

    out = write_book_json(slug, manifest, sentences, translations)
    print(f"Wrote {out}")
    return {
        "slug": slug,
        "translated": to_idx - from_idx,
        "from_id": start_id,
        "to_id": end_id,
        "complete": end_id >= total,
        "book_path": out,
    }


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Prepare a bilingual book via LLM translation")
    parser.add_argument("source", type=Path, help="Path to book.txt or book.epub")
    parser.add_argument("--title")
    parser.add_argument("--author")
    parser.add_argument("--language", default=None)
    parser.add_argument("--translation-language", default=None)
    parser.add_argument("--chapter", default=None)
    parser.add_argument("--window-size", type=int, default=15)
    parser.add_argument("--context", type=int, default=5, help="Context sentences before/after window")
    parser.add_argument("--from-id", type=int, default=1, dest="from_id", help="First sentence id to translate")
    parser.add_argument(
        "--to-id",
        type=int,
        default=None,
        dest="to_id",
        help="Last sentence id to translate (inclusive). Ignored if --limit is set.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max sentences to translate in this run (from --from-id). E.g. --limit 30 for the first batch.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Split only, no LLM calls")
    parser.add_argument("--re-split", action="store_true", help="Ignore sentence cache and re-split source")
    parser.add_argument("--model", default=os.environ.get("MODEL", "gpt-4o-mini"))
    args = parser.parse_args()

    source = args.source.resolve()
    if not source.exists():
        raise SystemExit(f"Source not found: {source}")

    source_dir = source.parent
    slug = resolve_slug(source_dir)

    if args.title or args.author or args.language or args.translation_language or args.chapter:
        load_manifest(source_dir, args)

    result = run_translation(
        slug,
        src_dir=source_dir,
        from_id=args.from_id,
        to_id=args.to_id,
        limit=args.limit,
        re_split=args.re_split,
        dry_run=args.dry_run,
        window_size=args.window_size,
        context=args.context,
        model=args.model,
    )
    if result.get("dry_run"):
        return
    if result.get("translated", 0) > 0:
        print(f"Catalog: books/catalog.json (slug {slug!r})")
        print(f"Next: python scripts/generate_audio.py books/{slug}/ --to-id {result['to_id']}")


if __name__ == "__main__":
    main()
