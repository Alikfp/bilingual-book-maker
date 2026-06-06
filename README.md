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
  book.txt          ← original text (.txt or .epub)
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
python scripts/prepare_book.py sources/my-book/book.txt --dry-run

# Translate the full book
python scripts/prepare_book.py sources/my-book/book.txt --slug my-book

# Fix a bad stretch only
python scripts/prepare_book.py sources/my-book/book.txt --from-id 40 --to-id 60
```

Output lands in `books/my-book/book.json`. Translation progress is saved in `sources/my-book/.prepare_state.json` — safe to stop and resume.

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

Creates `books/my-book/audio/sentence_1.mp3`, etc.

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

## Read from anywhere (iPad over the internet)

Manual prep on your Mac, then deploy so you don't need same Wi‑Fi:

- **[DEPLOY.md](DEPLOY.md)** — Cloudflare Tunnel (easiest: books stay on Mac, public URL) or static hosting (Cloudflare Pages / VPS)

Quick tunnel test:

```bash
python3 -m http.server 8080
cloudflared tunnel --url http://localhost:8080
# Open https://….trycloudflare.com/web/ on iPad
```

---

## Legacy

Pre-app experiments (manual sentence files, old HTML players, PDF exports) live in [`legacy/`](legacy/). See [`legacy/README.md`](legacy/README.md).
