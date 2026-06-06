# Bilingual Book Maker

Read books in a foreign language **one sentence at a time** — with audio, an English translation toggle, and iOS Look Up for individual words. Built for personal use on iPhone and iPad.

---

## How it works

```
Source text (TXT/EPUB)
        ↓
  book.py continue       ← translate batch + generate audio
        ↓
  book.json + audio      ← neural TTS reads each sentence aloud
        ↓
  web/ reader app        ← read on phone or tablet
```

You prepare books once on your Mac. The reader runs offline from static files — no API calls while reading.

---

## Read a book (5 minutes)

**1. Start the server** (from the project root):

```bash
python3 -m http.server 8080
```

**2. Open the app**

| Device | URL |
|--------|-----|
| Mac | http://localhost:8080/web/ |
| iPhone / iPad (same Wi‑Fi) | `http://<your-mac-ip>:8080/web/` |

**3. Pick a book and read**

Tap a book → read one sentence → play audio → swipe or tap Next → toggle English when needed.

Progress is saved automatically in the browser.

---

## Book workflow

One routine for adding and extending books. Run from the project root with your venv active.

### 1. One-time setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set OPENAI_API_KEY
```

### 2. Add a new book

```bash
python scripts/book.py init my-book --epub ~/Downloads/novel.epub
```

This creates `sources/my-book/` (source + manifest template), extracts a cover if possible, and registers the book in `books/catalog.json`.

Optionally edit `sources/my-book/manifest.json` — add `notes` and `characterNames` to guide the LLM:

```json
{
  "title": "L'Étranger",
  "author": "Albert Camus",
  "language": "fr",
  "translationLanguage": "en",
  "notes": "First-person, detached tone. Keep 'maman' not 'mother'.",
  "characterNames": ["Meursault", "Marie"]
}
```

### 3. Translate + audio (repeat)

```bash
python scripts/book.py continue my-book
```

Each run translates the next batch (default 30 sentences), generates matching audio, and updates the catalog. Safe to stop and resume anytime.

```bash
python scripts/book.py status my-book   # see progress + next step
```

Or with Make:

```bash
make continue BOOK=my-book
make status BOOK=my-book
```

### 4. Read it

Refresh the app — your book appears in the library with translation progress.

### 5. Deploy (if using Lightsail)

```bash
python scripts/book.py deploy ubuntu@YOUR_IP --key ./your-key.pem
```

Or set `LIGHTSAIL_HOST` and `LIGHTSAIL_KEY` in `.env`, then `make deploy`.

---

### Cost estimate

```bash
python scripts/estimate_cost.py sources/my-book/book.epub
```

Rough guide with defaults (`gpt-4o-mini`, 15-sentence windows):

| Scope | Sentences | Est. cost |
|-------|-----------|-----------|
| Sample book (`books/letranger/`) | 130 | under $0.01 |
| Full novel (~36,000 words) | ~4,000 | **~$0.10–0.30** |
| Long novel (~100,000 words) | ~12,000 | **~$0.50–1.50** |

Audio via Edge TTS is free.

---

## Advanced (low-level scripts)

For fine-grained control, use the underlying scripts directly:

```bash
# Split only (no API calls)
python scripts/book.py split my-book

# Translate with explicit range
python scripts/prepare_book.py sources/my-book/book.epub --from-id 40 --to-id 60

# Re-split after source text changed
python scripts/prepare_book.py sources/my-book/book.epub --re-split

# Audio with a specific backend
python scripts/generate_audio.py books/my-book/ --backend openai --voice onyx
```

| TTS backend | Quality | Cost | API key |
|-------------|---------|------|---------|
| **edge** (default) | Good neural | Free | None |
| **openai** | Very natural | ~$15 / 1M chars | `OPENAI_API_KEY` |
| **elevenlabs** | Best / expressive | Paid | `ELEVENLABS_API_KEY` |

---

## Project layout

```
web/                        Reader app (open this in the browser)
books/
  catalog.json              Index of available books
  {slug}/
    book.json               Sentences + translations
    audio/                  MP3 files
    cover.jpg               Optional cover image

scripts/
  book.py                   Unified CLI (init / continue / status / deploy)
  prepare_book.py           Split text + LLM translate
  generate_audio.py         Text-to-speech (edge / openai / elevenlabs)
  tts_backends.py           TTS provider implementations
  prompts/                  LLM prompt templates

sources/{slug}/             Input (not deployed)
  book.epub or book.txt
  manifest.json
  .sentences.json           Cached sentence splits
  .prepare_state.json       Translation checkpoint

legacy/                     Old experiments (not used by the app)
```

---

## Reader features

- **Library** with reading progress per book
- **One sentence at a time** — large, selectable text (long-press a word on iOS for Look Up)
- **Translation toggle** — show/hide English
- **Audio** — play and repeat the current sentence
- **Navigation** — prev/next buttons or swipe left/right
- **Resume** — picks up where you left off

---

## Tips

- **iPhone home screen:** Safari → Share → Add to Home Screen (basic PWA support via `web/manifest.json`)
- **Long books:** run `python scripts/book.py continue <slug>` repeatedly; batch size defaults to 30 (set `BATCH_SIZE` in `.env`)
- **Tune translation quality:** edit `scripts/prompts/system.txt` or add detail to `manifest.json` → `notes`
- **Sample book:** `books/letranger/` (*L'Étranger*, 130 sentences) ships ready to read

---

## Read from anywhere (iPhone / iPad over the internet)

1. **[Test locally first](DEPLOY.md#part-1-test-on-iphone-locally)** — same Wi‑Fi, `http://<mac-ip>:8080/web/`
2. **[Deploy on AWS Lightsail](DEPLOY.md#part-2-deploy-on-aws-lightsail)** — step-by-step with nginx

Full guide: **[DEPLOY.md](DEPLOY.md)**

---

## Legacy

Pre-app experiments (manual sentence files, old HTML players, PDF exports) live in [`legacy/`](legacy/). See [`legacy/README.md`](legacy/README.md).
