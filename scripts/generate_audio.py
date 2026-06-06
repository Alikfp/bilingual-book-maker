#!/usr/bin/env python3
"""Generate MP3 audio files for a prepared book.json."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import book_common as bc

ROOT = bc.ROOT

# Allow `from tts_backends import ...` when run as scripts/generate_audio.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tts_backends import BACKENDS, get_backend  # noqa: E402

load_dotenv = bc.load_dotenv


def generate_range(
    book_path: Path,
    *,
    from_id: int = 1,
    to_id: int | None = None,
    backend_name: str | None = None,
    voice: str | None = None,
    force: bool = False,
) -> dict:
    """Generate MP3s for a sentence id range. Returns summary dict."""
    book_path = book_path.resolve()
    if book_path.is_dir():
        book_json = book_path / "book.json"
        book_dir = book_path
    else:
        book_json = book_path
        book_dir = book_path.parent

    if not book_json.exists():
        raise SystemExit(f"Not found: {book_json}")

    backend_kwargs = {}
    if voice:
        backend_kwargs["voice"] = voice

    backend_name = backend_name or os.environ.get("TTS_BACKEND", "edge")
    backend = get_backend(backend_name, **backend_kwargs)
    print(f"Backend: {backend.name}")

    book = json.loads(book_json.read_text(encoding="utf-8"))
    lang = book.get("language", "fr")
    audio_dir = book_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    sentences = book.get("sentences", [])
    max_id = max((s["id"] for s in sentences), default=0)
    to_id = to_id or max_id

    created = skipped = 0
    first_created = last_created = None
    for sentence in sentences:
        sid = sentence["id"]
        if sid < from_id or sid > to_id:
            continue

        out_file = audio_dir / f"sentence_{sid}.mp3"
        if out_file.exists() and not force:
            skipped += 1
            continue

        text = sentence.get("original", "").strip()
        if not text:
            continue

        print(f"  [{sid}/{len(sentences)}] {text[:60]}…", flush=True)
        backend.synthesize(text, lang, out_file)
        created += 1
        first_created = first_created or sid
        last_created = sid

    print(f"Done: {created} created, {skipped} skipped")
    slug = book_dir.name
    bc.update_catalog_entry(slug)
    return {
        "slug": slug,
        "created": created,
        "skipped": skipped,
        "from_id": from_id,
        "to_id": to_id,
        "first_created": first_created,
        "last_created": last_created,
    }


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Generate TTS audio for a book",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Backends (best → basic):
  edge        Microsoft neural voices — free, no API key (default)
  openai      OpenAI tts-1-hd — natural, uses OPENAI_API_KEY
  elevenlabs  ElevenLabs — most expressive, needs ELEVENLABS_API_KEY + VOICE_ID
  gtts        Google Translate TTS — legacy, robotic

Examples:
  python scripts/generate_audio.py books/letranger/
  python scripts/generate_audio.py books/letranger/ --backend openai --voice onyx
  python scripts/generate_audio.py books/letranger/ --backend edge --voice fr-FR-DeniseNeural
  edge-tts --list-voices | grep fr-FR
        """,
    )
    parser.add_argument("book", type=Path, help="Book directory or book.json path")
    parser.add_argument(
        "--backend",
        choices=list(BACKENDS),
        default=os.environ.get("TTS_BACKEND", "edge"),
        help="TTS provider (default: edge)",
    )
    parser.add_argument("--voice", help="Voice ID/name (backend-specific)")
    parser.add_argument("--force", action="store_true", help="Regenerate existing files")
    parser.add_argument("--from-id", type=int, default=1, dest="from_id")
    parser.add_argument("--to-id", type=int, default=None, dest="to_id")
    args = parser.parse_args()

    generate_range(
        args.book,
        from_id=args.from_id,
        to_id=args.to_id,
        backend_name=args.backend,
        voice=args.voice,
        force=args.force,
    )


if __name__ == "__main__":
    main()
