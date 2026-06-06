#!/usr/bin/env python3
"""Unified CLI for adding and extending bilingual books."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import book_common as bc
from generate_audio import generate_range
from prepare_book import run_translation


def cmd_init(args: argparse.Namespace) -> None:
    slug = bc.resolve_slug(args.slug)
    src = bc.source_dir(slug)
    out = bc.book_dir(slug)

    if src.exists() and not args.force:
        raise SystemExit(f"Source already exists: {src}\nUse --force to overwrite scaffold.")

    src.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)

    source_input = args.epub or args.txt
    if not source_input:
        raise SystemExit("Provide --epub or --txt with the source file path.")

    source_input = Path(source_input).expanduser().resolve()
    if not source_input.exists():
        raise SystemExit(f"Source file not found: {source_input}")

    dest_name = "book.epub" if source_input.suffix.lower() == ".epub" else "book.txt"
    shutil.copy2(source_input, src / dest_name)

    title = args.title or bc.guess_title(slug)
    manifest = {
        "title": title,
        "author": args.author or "",
        "language": args.language or "fr",
        "translationLanguage": args.translation_language or "en",
        "notes": "",
        "characterNames": [],
    }

    cover_name = None
    if dest_name == "book.epub":
        cover_path = out / "cover.jpg"
        if bc.extract_epub_cover(src / dest_name, cover_path):
            cover_name = "cover.jpg"
            manifest["cover"] = cover_name
            print(f"Cover: {cover_path}")

    (src / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    bc.update_catalog_entry(slug)
    print(f"Created source: {src}")
    print(f"Output dir:     {out}")
    print(f"Edit notes:     {src / 'manifest.json'}")
    print(f"Next:           python scripts/book.py continue {slug}")


def cmd_split(args: argparse.Namespace) -> None:
    slug = bc.resolve_slug(args.slug)
    src = bc.source_dir(slug)
    source = bc.find_source_file(src)
    if source is None:
        raise SystemExit(f"No source file in {src}")

    sentences = bc.load_sentences_cache(src, source, re_split=args.re_split)
    print(f"Book: {slug}")
    print(f"Sentences: {len(sentences)}")
    print(f"Cache: {src / bc.SENTENCES_CACHE}")
    for s in sentences[:5]:
        print(f"  [{s['id']}] {s['original'][:80]}…")
    if len(sentences) > 5:
        print("  …")


def _format_pct(done: int, total: int) -> str:
    if total == 0:
        return "0%"
    return f"{round((done / total) * 100)}%"


def cmd_status(args: argparse.Namespace) -> None:
    slug = bc.resolve_slug(args.slug)
    p = bc.get_progress(slug)

    print(f"Book: {p['title']}")
    if p["author"]:
        print(f"Author: {p['author']}")
    print(f"Slug: {slug}")
    print()
    print(f"Sentences:   {p['total']}")
    print(f"Translated:  {p['translated']} ({_format_pct(p['translated'], p['total'])})")
    print(f"Audio:       {p['audio']} ({_format_pct(p['audio'], p['total'])})")
    print(f"Ready:       {'yes' if p['ready'] else 'no'}")
    print()

    if p["ready"]:
        print("Next: python scripts/book.py deploy")
    elif not p["has_source"]:
        print("No source folder. Run: python scripts/book.py init <slug> --epub <file>")
    elif p["total"] == 0:
        print("Next: python scripts/book.py split " + slug)
    else:
        print("Next: python scripts/book.py continue " + slug)


def cmd_translate(args: argparse.Namespace) -> None:
    slug = bc.resolve_slug(args.slug)
    limit = None if args.all else (args.batch or bc.default_batch_size())
    from_id = None if args.all else None

    if args.from_id is not None:
        from_id = args.from_id

    result = run_translation(
        slug,
        from_id=from_id,
        to_id=args.to_id,
        limit=limit,
        re_split=args.re_split,
        dry_run=args.dry_run,
    )
    bc.update_catalog_entry(slug)

    if result.get("translated", 0) == 0 and not result.get("dry_run"):
        print("Nothing to translate — book may already be complete.")


def cmd_audio(args: argparse.Namespace) -> None:
    slug = bc.resolve_slug(args.slug)
    out = bc.book_dir(slug)
    p = bc.get_progress(slug)

    from_id = args.from_id
    to_id = args.to_id

    if from_id is None:
        from_id = p["next_audio_id"] or 1
    if to_id is None:
        translations = bc.load_translations(bc.source_dir(slug))
        if not translations:
            book = bc.load_book_json(slug)
            if book:
                translated_ids = [s["id"] for s in book["sentences"] if s.get("translation")]
                to_id = max(translated_ids) if translated_ids else from_id
            else:
                to_id = from_id
        else:
            to_id = max(translations)

    generate_range(
        out,
        from_id=from_id,
        to_id=to_id,
        backend_name=args.backend,
        voice=args.voice,
        force=args.force,
    )


def cmd_continue(args: argparse.Namespace) -> None:
    slug = bc.resolve_slug(args.slug)
    batch = args.batch or bc.default_batch_size()

    p = bc.get_progress(slug)
    if p["total"] == 0:
        cmd_split(argparse.Namespace(slug=slug, re_split=False))

    p = bc.get_progress(slug)
    if p["ready"]:
        print(f"{p['title']} is complete.")
        print("Next: python scripts/book.py deploy")
        return

    translate_from = p["next_translate_id"]
    if translate_from is not None:
        result = run_translation(slug, from_id=translate_from, limit=batch)
        bc.update_catalog_entry(slug)
        if result.get("translated", 0) > 0:
            audio_from = result["from_id"]
            audio_to = result["to_id"]
            print(f"\nGenerating audio {audio_from}–{audio_to}…")
            generate_range(bc.book_dir(slug), from_id=audio_from, to_id=audio_to)
            bc.update_catalog_entry(slug)
    else:
        p = bc.get_progress(slug)
        if p["next_audio_id"] is not None:
            print("Translations complete. Generating missing audio…")
            translations = bc.load_translations(bc.source_dir(slug))
            to_id = max(translations) if translations else p["audio"]
            generate_range(bc.book_dir(slug), from_id=p["next_audio_id"], to_id=to_id)
            bc.update_catalog_entry(slug)
        else:
            print("Nothing to do — book is complete.")
            print("Next: python scripts/book.py deploy")
            return

    p = bc.get_progress(slug)
    print()
    print(f"Progress: {p['translated']}/{p['total']} translated, {p['audio']}/{p['total']} audio")
    if p["ready"]:
        print("Next: python scripts/book.py deploy")
    else:
        print(f"Next: python scripts/book.py continue {slug}")


def cmd_deploy(args: argparse.Namespace) -> None:
    bc.load_dotenv()
    remote = args.remote or os.environ.get("LIGHTSAIL_HOST")
    key = args.key or os.environ.get("LIGHTSAIL_KEY")

    if not remote:
        raise SystemExit(
            "Set LIGHTSAIL_HOST in .env or pass remote user@IP.\n"
            "Example: python scripts/book.py deploy ubuntu@13.239.132.197 --key ./key.pem"
        )

    script = bc.ROOT / "deploy" / "sync-to-lightsail.sh"
    cmd = [str(script), remote]
    if key:
        cmd.append(key)
    subprocess.run(cmd, check=True)


def cmd_refresh_catalog(_args: argparse.Namespace) -> None:
    bc.refresh_all_catalog_entries()
    print(f"Updated {bc.CATALOG_PATH}")


def main() -> None:
    bc.load_dotenv()

    parser = argparse.ArgumentParser(
        description="Add and extend bilingual books",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Routine workflow:
  python scripts/book.py init my-novel --epub ~/Downloads/novel.epub
  python scripts/book.py continue my-novel    # repeat until done
  python scripts/book.py deploy
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Scaffold a new book from EPUB or TXT")
    p_init.add_argument("slug", help="Book id (folder name), e.g. le-petit-prince")
    p_init.add_argument("--epub", type=Path, help="Path to source EPUB")
    p_init.add_argument("--txt", type=Path, help="Path to source TXT")
    p_init.add_argument("--title", help="Book title (default: derived from slug)")
    p_init.add_argument("--author", default="")
    p_init.add_argument("--language", default="fr")
    p_init.add_argument("--translation-language", default="en")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing scaffold")
    p_init.set_defaults(func=cmd_init)

    p_split = sub.add_parser("split", help="Split source into sentences and cache")
    p_split.add_argument("slug")
    p_split.add_argument("--re-split", action="store_true", help="Ignore cache and re-split")
    p_split.set_defaults(func=cmd_split)

    p_status = sub.add_parser("status", help="Show progress and next step")
    p_status.add_argument("slug")
    p_status.set_defaults(func=cmd_status)

    for name, help_text, run in [
        ("translate", "Translate the next batch (or --all)", cmd_translate),
        ("audio", "Generate audio for translated sentences", cmd_audio),
        ("continue", "Translate next batch + generate audio (main routine)", cmd_continue),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("slug")
        p.add_argument("--batch", type=int, help=f"Batch size (default: {bc.default_batch_size()})")
        if name == "translate":
            p.add_argument("--all", action="store_true", help="Translate all remaining sentences")
            p.add_argument("--from-id", type=int, default=None)
            p.add_argument("--to-id", type=int, default=None)
            p.add_argument("--re-split", action="store_true")
            p.add_argument("--dry-run", action="store_true")
        if name == "audio":
            p.add_argument("--from-id", type=int, default=None)
            p.add_argument("--to-id", type=int, default=None)
            p.add_argument("--backend", choices=["edge", "openai", "elevenlabs", "gtts"])
            p.add_argument("--voice")
            p.add_argument("--force", action="store_true")
        p.set_defaults(func=run)

    p_deploy = sub.add_parser("deploy", help="Sync web/ + books/ to Lightsail")
    p_deploy.add_argument("remote", nargs="?", help="user@IP (or LIGHTSAIL_HOST in .env)")
    p_deploy.add_argument("--key", help="SSH key path (or LIGHTSAIL_KEY in .env)")
    p_deploy.set_defaults(func=cmd_deploy)

    p_refresh = sub.add_parser("refresh-catalog", help="Rebuild catalog metadata from all books")
    p_refresh.set_defaults(func=cmd_refresh_catalog)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
