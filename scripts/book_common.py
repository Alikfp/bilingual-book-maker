"""Shared helpers for book preparation and the book CLI."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = ROOT / "sources"
BOOKS_DIR = ROOT / "books"
CATALOG_PATH = BOOKS_DIR / "catalog.json"
SENTENCES_CACHE = ".sentences.json"
STATE_FILE = ".prepare_state.json"


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


def resolve_slug(name: str | Path) -> str:
    if isinstance(name, Path):
        name = name.name
    return re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-")


def source_dir(slug: str) -> Path:
    return SOURCES_DIR / slug


def book_dir(slug: str) -> Path:
    return BOOKS_DIR / slug


def find_source_file(src_dir: Path) -> Path | None:
    for name in ("book.epub", "book.txt"):
        path = src_dir / name
        if path.exists():
            return path
    for path in sorted(src_dir.glob("*.epub")) + sorted(src_dir.glob("*.txt")):
        return path
    return None


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def guess_title(slug: str) -> str:
    return " ".join(word.capitalize() for word in slug.replace("-", " ").split())


def load_manifest_dict(src_dir: Path, overrides: dict | None = None) -> dict:
    manifest_path = src_dir / "manifest.json"
    manifest: dict = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if overrides:
        for key, value in overrides.items():
            if value is not None:
                manifest[key] = value

    required = ["title", "language", "translationLanguage"]
    missing = [k for k in required if not manifest.get(k)]
    if missing:
        raise SystemExit(
            f"Missing manifest fields {missing}. Edit {manifest_path} or pass overrides."
        )
    return manifest


def load_translations(src_dir: Path) -> dict[int, str]:
    state_path = src_dir / STATE_FILE
    if not state_path.exists():
        return {}
    state = json.loads(state_path.read_text(encoding="utf-8"))
    return {int(k): v for k, v in state.get("translations", {}).items()}


def save_translations(src_dir: Path, translations: dict[int, str]) -> None:
    state_path = src_dir / STATE_FILE
    payload = {"translations": {str(k): v for k, v in sorted(translations.items())}}
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def count_audio(out_dir: Path) -> int:
    audio_dir = out_dir / "audio"
    if not audio_dir.is_dir():
        return 0
    return sum(1 for p in audio_dir.glob("sentence_*.mp3") if p.is_file())


def load_book_json(slug: str) -> dict | None:
    path = book_dir(slug) / "book.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def count_translated_from_book(book: dict | None) -> int:
    if not book:
        return 0
    return sum(1 for s in book.get("sentences", []) if s.get("translation"))


def total_sentences_from_cache(src_dir: Path) -> int:
    cache_path = src_dir / SENTENCES_CACHE
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        return len(cache.get("sentences", []))
    book = load_book_json(resolve_slug(src_dir.name))
    if book:
        return len(book.get("sentences", []))
    return 0


def next_untranslated_id(translations: dict[int, str], total: int) -> int | None:
    for sid in range(1, total + 1):
        if sid not in translations:
            return sid
    return None


def next_missing_audio_id(out_dir: Path, translated_ids: set[int]) -> int | None:
    for sid in sorted(translated_ids):
        if not (out_dir / "audio" / f"sentence_{sid}.mp3").exists():
            return sid
    return None


def get_progress(slug: str) -> dict:
    src = source_dir(slug)
    out = book_dir(slug)
    manifest_path = src / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    book = load_book_json(slug)
    translations = load_translations(src) if src.exists() else {}
    if not translations and book:
        translations = {
            s["id"]: s["translation"]
            for s in book.get("sentences", [])
            if s.get("translation")
        }

    total = 0
    cache_path = src / SENTENCES_CACHE
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        total = len(cache.get("sentences", []))
    elif book:
        total = len(book.get("sentences", []))

    translated = len(translations) if translations else count_translated_from_book(book)
    audio = count_audio(out)
    ready = total > 0 and translated >= total and audio >= total
    next_translate = next_untranslated_id(translations, total) if total else None
    next_audio = next_missing_audio_id(out, set(translations)) if translations else None

    title = manifest.get("title") or (book or {}).get("title") or guess_title(slug)
    author = manifest.get("author") or (book or {}).get("author") or ""
    cover = manifest.get("cover") or (book or {}).get("cover")

    return {
        "slug": slug,
        "title": title,
        "author": author,
        "cover": cover,
        "total": total,
        "translated": translated,
        "audio": audio,
        "ready": ready,
        "next_translate_id": next_translate,
        "next_audio_id": next_audio,
        "has_source": src.exists() and find_source_file(src) is not None,
    }


def catalog_entry_from_progress(progress: dict) -> dict:
    return {
        "id": progress["slug"],
        "title": progress["title"],
        "author": progress["author"],
        "cover": progress.get("cover"),
        "totalSentences": progress["total"],
        "translatedSentences": progress["translated"],
        "audioSentences": progress["audio"],
        "ready": progress["ready"],
    }


def read_catalog() -> dict:
    if not CATALOG_PATH.exists():
        return {"books": []}
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def catalog_slug(entry) -> str:
    if isinstance(entry, str):
        return entry
    return entry.get("id") or entry.get("slug") or ""


def update_catalog_entry(slug: str) -> None:
    progress = get_progress(slug)
    if progress["total"] == 0 and not progress["has_source"]:
        book = load_book_json(slug)
        if not book:
            return
        progress["total"] = len(book.get("sentences", []))
        progress["translated"] = count_translated_from_book(book)
        progress["audio"] = count_audio(book_dir(slug))
        progress["ready"] = progress["translated"] >= progress["total"] and progress["audio"] >= progress["total"]
        progress["title"] = book.get("title", progress["title"])
        progress["author"] = book.get("author", "")
        progress["cover"] = book.get("cover")

    catalog = read_catalog()
    books = catalog.setdefault("books", [])
    entry = catalog_entry_from_progress(progress)

    replaced = False
    for i, item in enumerate(books):
        if catalog_slug(item) == slug:
            books[i] = entry
            replaced = True
            break
    if not replaced:
        books.append(entry)

    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def refresh_all_catalog_entries() -> None:
    catalog = read_catalog()
    slugs = {catalog_slug(item) for item in catalog.get("books", []) if catalog_slug(item)}
    for slug in sorted(slugs):
        update_catalog_entry(slug)


def save_sentences_cache(src_dir: Path, source_path: Path, sentences: list[dict]) -> Path:
    cache_path = src_dir / SENTENCES_CACHE
    payload = {
        "sourceHash": file_hash(source_path),
        "sourceFile": source_path.name,
        "splitAt": datetime.now(timezone.utc).isoformat(),
        "sentences": sentences,
    }
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cache_path


def load_sentences_cache(src_dir: Path, source_path: Path, *, re_split: bool = False):
    from prepare_book import read_text, split_sentences

    cache_path = src_dir / SENTENCES_CACHE
    current_hash = file_hash(source_path)

    if cache_path.exists() and not re_split:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        if cache.get("sourceHash") == current_hash:
            return cache["sentences"]
        raise SystemExit(
            f"Source file changed since last split ({cache_path}).\n"
            f"Run: python scripts/book.py split {src_dir.name} --re-split"
        )

    text = read_text(source_path)
    raw = split_sentences(text)
    sentences = [{"id": i + 1, "original": s} for i, s in enumerate(raw)]
    save_sentences_cache(src_dir, source_path, sentences)
    return sentences


def extract_epub_cover(epub_path: Path, output_path: Path) -> bool:
    try:
        import ebooklib
        from ebooklib import epub
    except ImportError:
        return False

    book = epub.read_epub(str(epub_path))
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_COVER:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(item.get_content())
            return True

    for name in ("cover.jpg", "cover.jpeg", "cover.png"):
        item = book.get_item_with_id(name)
        if item is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(item.get_content())
            return True
    return False


def default_batch_size() -> int:
    return int(os.environ.get("BATCH_SIZE", "30"))
