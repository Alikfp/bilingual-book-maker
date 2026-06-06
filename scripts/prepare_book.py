#!/usr/bin/env python3
"""Split source text into sentences, translate via LLM, write book.json."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# Abbreviations that should not end a sentence (French).
FR_ABBREV = re.compile(
    r"\b(M\.|Mme|Mlle|Dr|Prof|etc|vol|chap|p|pp|av|apr|env|ex|cf|ibid|art|n|no|nos|st|ste|s\.|c\.-à-d)\.\s*$",
    re.IGNORECASE,
)

# Load environment variables from .env file
def load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def read_text(source: Path) -> str:
    suffix = source.suffix.lower()
    if suffix == ".txt":
        return source.read_text(encoding="utf-8")
    if suffix == ".epub":
        try:
            import ebooklib
            from ebooklib import epub
            from bs4 import BeautifulSoup
        except ImportError as exc:
            raise SystemExit("Install epub support: pip install ebooklib beautifulsoup4") from exc
        book = epub.read_epub(str(source))
        parts = []
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), "html.parser")
                text = soup.get_text(separator="\n")
                if text.strip():
                    parts.append(text)
        return "\n\n".join(parts)
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
        raise SystemExit(
            f"Translation ID mismatch. Missing: {sorted(missing)}. Extra: {sorted(extra)}"
        )
    translations.update(new_translations)
    return translations


def update_catalog(slug: str) -> None:
    catalog_path = ROOT / "books" / "catalog.json"
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog = {"books": []}
    if catalog_path.exists():
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    books = catalog.setdefault("books", [])
    if slug not in books:
        books.append(slug)
        catalog_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")


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
    update_catalog(slug)
    return out_path


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Prepare a bilingual book via LLM translation")
    parser.add_argument("source", type=Path, help="Path to book.txt or book.epub")
    parser.add_argument("--slug", help="Book id / folder name (default: source parent dir name)")
    parser.add_argument("--title")
    parser.add_argument("--author")
    parser.add_argument("--language", default=None)
    parser.add_argument("--translation-language", default=None)
    parser.add_argument("--chapter", default=None)
    parser.add_argument("--window-size", type=int, default=15)
    parser.add_argument("--context", type=int, default=3, help="Context sentences before/after window")
    parser.add_argument("--from-id", type=int, default=1, dest="from_id")
    parser.add_argument("--to-id", type=int, default=None, dest="to_id")
    parser.add_argument("--dry-run", action="store_true", help="Split only, no LLM calls")
    parser.add_argument("--model", default=os.environ.get("MODEL", "gpt-4o-mini"))
    args = parser.parse_args()

    source = args.source.resolve()
    if not source.exists():
        raise SystemExit(f"Source not found: {source}")

    source_dir = source.parent
    slug = args.slug or re.sub(r"[^a-z0-9-]", "-", source_dir.name.lower()).strip("-")
    manifest = load_manifest(source_dir, args)

    text = read_text(source)
    raw_sentences = split_sentences(text)
    sentences = [{"id": i + 1, "original": s} for i, s in enumerate(raw_sentences)]

    state_path = source_dir / ".prepare_state.json"
    translations: dict[int, str] = {}
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        translations = {int(k): v for k, v in state.get("translations", {}).items()}

    from_idx = max(0, args.from_id - 1)
    to_idx = len(sentences) if args.to_id is None else min(args.to_id, len(sentences))

    print(f"Book: {manifest['title']} ({len(sentences)} sentences)")
    print(f"Translating sentences {from_idx + 1}–{to_idx}")

    if args.dry_run:
        for s in sentences[from_idx:to_idx][:5]:
            print(f"  [{s['id']}] {s['original'][:80]}…")
        print("  …")
        return

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Set OPENAI_API_KEY in .env or environment")

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    window = args.window_size

    idx = from_idx
    while idx < to_idx:
        end = min(idx + window, to_idx)
        print(f"  Window {sentences[idx]['id']}–{sentences[end - 1]['id']} …", flush=True)
        translations = translate_window(
            manifest,
            sentences,
            idx,
            end,
            translations,
            model=args.model,
            base_url=base_url,
            api_key=api_key,
            context_before=args.context,
            context_after=args.context,
        )
        state_path.write_text(
            json.dumps({"translations": translations}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        idx = end

    out = write_book_json(slug, manifest, sentences, translations)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
