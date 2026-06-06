# Legacy

Early experiments and manually prepared book data from before the current app. Nothing here is used by the reader in `web/` — kept for reference.

| Path | What it is |
|------|------------|
| `the-stranger/` | Hand-prepared *L'Étranger* — sentences.json, per-book HTML player, audio, PDFs |
| `in-search-of-lost-time/` | Proust opening — sentences.json, HTML player, audio |
| `publications/` | Exported bilingual PDF/DOCX |
| `french_sentences.json` | Flat French sentence map (Proust excerpt) |
| `audio_generatro.ipynb` | Original gTTS notebook |

The current sample book in `books/letranger/` was built from `the-stranger/sentences.json`. Its audio folder symlinks to `legacy/the-stranger/audio/`.
