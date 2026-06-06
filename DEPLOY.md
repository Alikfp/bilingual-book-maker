# Deploying for access from anywhere

The reader is static files. Your prepared `books/` folder (JSON + MP3s) must be served alongside `web/`. There is no backend at read time.

Two practical approaches:

| Approach | Books live on | Best when |
|----------|---------------|-----------|
| **Cloudflare Tunnel** | Your Mac | Personal use, large audio libraries, prep locally |
| **Static host** (Cloudflare Pages, etc.) | The cloud | Mac can be off; you upload books after prep |

---

## Option A — Cloudflare Tunnel (recommended)

Books stay on your Mac. You get a public HTTPS URL. No need to upload gigabytes of MP3s.

### 1. Prepare books locally (as usual)

```bash
python scripts/prepare_book.py sources/my-book/book.txt
python scripts/generate_audio.py books/my-book/
```

### 2. Install cloudflared

```bash
brew install cloudflared
```

### 3. Start the local server

```bash
cd bilingual-book-maker
python3 -m http.server 8080
```

### 4. Open a tunnel (one-off quick test)

```bash
cloudflared tunnel --url http://localhost:8080
```

Copy the `https://….trycloudflare.com` URL → open `https://….trycloudflare.com/web/` on your iPad from anywhere.

### 5. Permanent tunnel (optional)

1. [Create a free Cloudflare account](https://dash.cloudflare.com)
2. Add your domain (or use a subdomain)
3. Follow [Cloudflare Tunnel docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) to create a named tunnel pointing to `http://localhost:8080`
4. Run tunnel as a service so it survives reboots

**Pros:** No code changes, books never leave your machine, free tier.  
**Cons:** Mac must be on (or use a small always-on device / VPS to host files instead).

---

## Option B — Static hosting (Cloudflare Pages)

Host `web/` + `books/` in the cloud. Works when your Mac is off.

### Folder layout on the host

```
/
  web/           ← reader app
  books/         ← prepared books (not in git by default)
  index.html     ← redirect to web/ (optional)
```

The app detects `/web` in the URL and loads books from `../books`.

### Deploy with Wrangler

```bash
npm install -g wrangler
wrangler pages project create bilingual-reader

# From project root — includes web/ and books/
wrangler pages deploy . --project-name=bilingual-reader
```

**Important:** `books/` and `*.mp3` are gitignored. You must deploy from your local disk (which has the prepared books), not from GitHub alone.

### Size limits

- One book like *L'Étranger* (~130 sentences): ~5–15 MB audio
- Full novel (~4000 sentences): ~150–400 MB audio
- Cloudflare Pages free tier: 20,000 files, 25 MB max per file — fine for MP3s

After each new book:

```bash
python scripts/prepare_book.py ...
python scripts/generate_audio.py ...
wrangler pages deploy . --project-name=bilingual-reader
```

### Optional: protect with Cloudflare Access

Free tier can add email OTP or Google login so your library isn’t public to the whole internet.

---

## Option C — Small VPS (DigitalOcean, Hetzner, etc.)

```bash
# On the server
sudo apt install nginx
```

Copy project to `/var/www/bilingual-book-maker/`, nginx config:

```nginx
server {
    listen 80;
    server_name books.example.com;
    root /var/www/bilingual-book-maker;
    index index.html;
}
```

Add HTTPS with Certbot. Sync books from your Mac:

```bash
rsync -av books/ user@server:/var/www/bilingual-book-maker/books/
rsync -av web/ user@server:/var/www/bilingual-book-maker/web/
```

---

## iPad usage after deploy

| Deploy | URL |
|--------|-----|
| Tunnel / VPS / Pages | `https://your-domain/web/` |
| Local Wi‑Fi only | `http://192.168.x.x:8080/web/` |

Safari → Share → **Add to Home Screen** for an app-like icon.

---

## What is not deployed

- `scripts/` — run on your Mac only
- `sources/` — raw input + LLM state
- `.env` — never upload (API keys)

Prep stays local. Only `books/` + `web/` need to be reachable by the browser.
