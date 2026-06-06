# Bilingual Book Maker

Read books in a foreign language **one sentence at a time** — with audio, an English translation toggle, and iOS Look Up for individual words. Built for personal use on iPhone and iPad.

---

## How it works

```
Source text (TXT/EPUB)
        ↓
  prepare_book.py        ← LLM translates sentence-by-sentence
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

## Add a new book

### 1. Create a source folder

```
sources/my-book/
  book.epub         ← or book.txt — original text
  manifest.json     ← metadata for the LLM (see below)
```

**Example `manifest.json`:**

```json
{
  "title": "L'Étranger",
  "author": "Albert Camus",
  "language": "fr",
  "translationLanguage": "en",
  "year": 1942,
  "genre": "literary fiction",
  "notes": "First-person, detached tone. Keep 'maman' not 'mother'.",
  "characterNames": ["Meursault", "Marie"],
  "translationStyle": "natural literary English"
```

`notes` and `characterNames` help the LLM stay consistent across the whole book.

### 2. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Set your API key

```bash
cp .env.example .env
```

Edit `.env`:

```
OPENAI_API_KEY=sk-...
MODEL=gpt-4o-mini
```

Works with any OpenAI-compatible API (`OPENAI_BASE_URL` optional).

### 4. Translate

```bash
# Check sentence splitting (free, no API calls)
python scripts/prepare_book.py sources/my-book/book.epub --dry-run

# First batch only — translate 30 sentences, then test in the app
python scripts/prepare_book.py sources/my-book/book.epub --limit 30

# Continue next batch (resumes from saved state)
python scripts/prepare_book.py sources/my-book/book.epub --from-id 31 --limit 30

# Translate everything remaining (from id 1, or pick up after batches)
python scripts/prepare_book.py sources/my-book/book.epub

# Fix a bad stretch only
python scripts/prepare_book.py sources/my-book/book.epub --from-id 40 --to-id 60
```

| Flag | Meaning |
|------|---------|
| `--limit 30` | Translate at most 30 sentences starting at `--from-id` (default 1) |
| `--from-id 31 --limit 30` | Sentences 31–60 (batch 2) |
| `--to-id 60` | Translate ids 1–60 inclusive (alternative to `--limit`) |
| `--dry-run` | Split EPUB/TXT and print sample sentences, no API calls |

Output always lands in `books/{folder}/book.json` where `{folder}` is the parent directory of your source file (e.g. `sources/le-petit-prince/book.epub` → `books/le-petit-prince/`). Progress is saved in `sources/{folder}/.prepare_state.json` — safe to stop and resume.

**Estimate cost before translating:**

```bash
python scripts/estimate_cost.py sources/my-book/book.txt
```

#### Translation cost (example: *L'Étranger*)

Rough guide with defaults (`gpt-4o-mini`, 15-sentence windows, **5 context sentences**):

| Scope | Sentences | API calls | Est. cost |
|-------|-----------|-----------|-----------|
| Your sample in `books/letranger/` | 130 | ~9 | under $0.01 |
| Full novel (~36,000 French words) | ~4,000 | ~270 | **~$0.10–0.30** |
| Long novel (~100,000 words) | ~12,000 | ~800 | **~$0.50–1.50** |

`gpt-4o` is roughly 15–20× more. Audio via Edge TTS is free.

### 5. Generate audio

```bash
# Default: Microsoft Edge neural voices (free, no API key)
python scripts/generate_audio.py books/my-book/

# OpenAI HD — very natural, uses your existing OPENAI_API_KEY
python scripts/generate_audio.py books/my-book/ --backend openai --voice onyx

# ElevenLabs — most audiobook-like (needs ELEVENLABS_API_KEY + ELEVENLABS_VOICE_ID)
python scripts/generate_audio.py books/my-book/ --backend elevenlabs

# Pick a French voice (edge backend)
edge-tts --list-voices | grep fr-FR
python scripts/generate_audio.py books/my-book/ --backend edge --voice fr-FR-DeniseNeural
```

Creates `books/my-book/audio/sentence_1.mp3`, etc. Match your translation batch:

```bash
# Audio for the first 30 sentences only
python scripts/generate_audio.py books/my-book/ --to-id 30
```

#### TTS backends compared

| Backend | Quality | Cost | API key | Best for |
|---------|---------|------|---------|----------|
| **edge** (default) | Good neural | Free | None | Personal use, bulk generation |
| **openai** | Very natural | ~$15 / 1M chars | `OPENAI_API_KEY` | Same key as translation |
| **elevenlabs** | Best / most expressive | Paid tiers | `ELEVENLABS_API_KEY` | Audiobook feel |
| **gtts** | Robotic | Free | None | Legacy fallback only |

Set the default in `.env`: `TTS_BACKEND=edge`

### 6. Read it

Refresh the app — your book appears in the library.

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
  prepare_book.py           Split text + LLM translate
  generate_audio.py         Text-to-speech (edge / openai / elevenlabs)
  tts_backends.py           TTS provider implementations
  prompts/                  LLM prompt templates

sources/{slug}/             Input for prepare_book.py
  book.txt
  manifest.json

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
- **Long books:** translation runs in windows of ~15 sentences; interrupt anytime and re-run the same command to continue
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
