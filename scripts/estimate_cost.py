#!/usr/bin/env python3
"""Estimate LLM translation cost for a book before running prepare_book.py."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# USD per 1M tokens (check openai.com/pricing — these are approximate)
MODEL_PRICING = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1": (2.00, 8.00),
}

WINDOW_DEFAULT = 15
CONTEXT_DEFAULT = 5
SYSTEM_TOKENS = 450
USER_HEADER_TOKENS = 120
PRIOR_TRANSLATION_TOKENS = 125  # ~5 prior sentences
OUTPUT_TOKENS_PER_SENTENCE = 25


def load_sentences(source: Path) -> list[str]:
    if source.suffix == ".json":
        data = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [s.get("original", "") for s in data]
        if "sentences" in data:
            return [s["original"] for s in data["sentences"]]
        raise SystemExit("Unrecognised JSON shape")
    # Import splitter from prepare_book
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from prepare_book import read_text, split_sentences  # noqa: E402

    return split_sentences(read_text(source))


def estimate(sentences: list[str], window: int, context: int) -> dict:
    if not sentences:
        raise SystemExit("No sentences found")

    total_chars = sum(len(s) for s in sentences)
    avg_chars = total_chars / len(sentences)
    avg_tokens_in = avg_chars / 4  # rough for French

    n = len(sentences)
    windows = (n + window - 1) // window
    sentences_in_prompt = window + 2 * context

    input_per_window = (
        SYSTEM_TOKENS
        + USER_HEADER_TOKENS
        + PRIOR_TRANSLATION_TOKENS
        + sentences_in_prompt * avg_tokens_in
    )
    output_per_window = window * OUTPUT_TOKENS_PER_SENTENCE

    total_input = windows * input_per_window
    total_output = windows * output_per_window

    return {
        "sentences": n,
        "characters": total_chars,
        "words_approx": sum(len(s.split()) for s in sentences),
        "windows": windows,
        "window_size": window,
        "context": context,
        "input_tokens": int(total_input),
        "output_tokens": int(total_output),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate translation API cost")
    parser.add_argument("source", type=Path, help="book.txt, .epub, or book.json")
    parser.add_argument("--window-size", type=int, default=WINDOW_DEFAULT)
    parser.add_argument("--context", type=int, default=CONTEXT_DEFAULT)
    args = parser.parse_args()

    sentences = load_sentences(args.source.resolve())
    stats = estimate(sentences, args.window_size, args.context)

    print(f"Sentences:     {stats['sentences']:,}")
    print(f"Characters:    {stats['characters']:,}")
    print(f"Words (approx):{stats['words_approx']:,}")
    print(f"API windows:   {stats['windows']} ({stats['window_size']} translate + {stats['context']} context each side)")
    print(f"Input tokens:  ~{stats['input_tokens']:,}")
    print(f"Output tokens: ~{stats['output_tokens']:,}")
    print()
    print("Estimated cost (translation only):")

    for model, (pin, pout) in MODEL_PRICING.items():
        cost = stats["input_tokens"] * pin / 1e6 + stats["output_tokens"] * pout / 1e6
        print(f"  {model:14} ~${cost:.2f}")

    print()
    print("Note: actual cost varies with sentence length, retries, and pricing changes.")


if __name__ == "__main__":
    main()
