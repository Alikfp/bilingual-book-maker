# Deploy guide

1. **[Test on iPhone locally](#part-1-test-on-iphone-locally)** — same Wi‑Fi, no cloud (do this first)
2. **[Deploy on AWS Lightsail](#part-2-deploy-on-aws-lightsail)** — always-on server, access from anywhere
3. **[Technical background](#technical-background)** — HTTP flow, `manifest.json`, nginx
4. [Other options](#other-options) — Cloudflare Tunnel, Pages

Prep (`prepare_book.py`, `generate_audio.py`) always runs on your Mac. Only `web/` + `books/` go on the server.

---

## Part 1: Test on iPhone locally

Goal: confirm the reader works on your phone **before** paying for a server or uploading anything.

### What you need

- Mac and iPhone on the **same Wi‑Fi**
- A prepared book in `books/` (e.g. `books/letranger/`)
- Nothing deployed to the cloud yet

### Step 1 — Start the web server on your Mac

```bash
cd bilingual-book-maker
python3 -m http.server 8080
```

**What this does:** Python listens on port **8080** and serves every file in the project folder over HTTP. The iPhone will request HTML, JSON, and MP3 files from your Mac — like a tiny static website with no install step.

**Under the hood:** Python’s `http.server` is a single-process HTTP/1.0 server. For each request it maps the URL path to a file on disk (e.g. `GET /web/app.js` → `./web/app.js`) and streams bytes back with a `Content-Type` header. It is fine for development; it is not tuned for many concurrent users or production security.

Leave this terminal open. Stop with `Ctrl+C` when done.

---

### Step 2 — Find your Mac’s local IP address

```bash
ipconfig getifaddr en0
```

**What this does:** Prints your Mac’s address on Wi‑Fi (e.g. `192.168.1.42`). `en0` is usually Wi‑Fi; if empty, try `en1` or check **System Settings → Network → Wi‑Fi → Details**.

Your iPhone cannot use `localhost` — that means “the phone itself”, not your Mac.

---

### Step 3 — Open the app on your iPhone

In **Safari**, go to:

```
http://192.168.1.42:8080/web/
```

(replace with your IP from step 2)

**What this does:**

1. Safari loads `web/index.html`
2. `app.js` fetches `../books/catalog.json` → list of books
3. Tap a book → fetches `../books/letranger/book.json`
4. Play → loads `../books/letranger/audio/sentence_1.mp3`

All traffic stays on your home network. No internet required for reading (only for initial page load from Mac).

---

### Step 4 — Quick checklist on iPhone

| Check | Expected |
|-------|----------|
| Library shows *L'Étranger* | `books/catalog.json` + `book.json` load |
| French sentence visible | JSON parsed correctly |
| English toggle works | Translation shows/hides |
| Play button | MP3 loads from `books/.../audio/` |
| Swipe left/right | Next/previous sentence |
| Close Safari, reopen same URL | Progress remembered (`localStorage`) |

---

### Step 5 — Add to Home Screen (optional)

Safari → **Share** → **Add to Home Screen**

**What this does at a high level:** iOS creates a **home-screen bookmark** that launches your site in a chromeless WebView — it looks like an app icon, but it is still your web app loading from the server.

See [Web app manifest & Add to Home Screen](#web-app-manifest--add-to-home-screen) for the full technical picture.

Still points at your Mac’s IP — Mac must be on and server running (unless deployed to Lightsail).

---

### Troubleshooting local test

| Problem | Fix |
|---------|-----|
| Page won’t load | Same Wi‑Fi? Correct IP? Server running? |
| “Could not load book catalog” | Open `http://IP:8080/books/catalog.json` in Safari — should show JSON |
| No audio | Open `http://IP:8080/books/letranger/audio/sentence_1.mp3` directly |
| Mac firewall blocks phone | **System Settings → Network → Firewall** — allow incoming for Python, or temporarily disable to test |

---

## Part 2: Deploy on AWS Lightsail

Goal: a small **always-on Linux server** on the internet. Your iPhone uses **public IP or domain** from anywhere — Mac can be off.

### Architecture

```
iPhone (anywhere)
    ↓ HTTPS (optional) or HTTP
Lightsail instance (nginx)
    ├── /web/     reader app
    ├── /books/   book.json + audio/
    └── index.html
```

**nginx** replaces Python’s dev server in production. See [What nginx does](#what-nginx-does) below.

---

### Phase A — Create the Lightsail instance

#### Step A1 — Open Lightsail

Go to [AWS Lightsail console](https://lightsail.aws.amazon.com/)

**What this is:** Lightsail is AWS’s simple VPS product — a virtual Linux machine with a fixed monthly price.

---

#### Step A2 — Create instance

| Setting | Recommendation |
|---------|----------------|
| Platform | **Linux/Unix** |
| Blueprint | **OS Only → Ubuntu 22.04 or 24.04** |
| Plan | **$3.50–5/mo** (512 MB–1 GB RAM is enough for static files) |
| Name | e.g. `bilingual-reader` |

Click **Create instance**.

**What this does:** AWS boots a remote Ubuntu machine. You get SSH access and a public IP. No app is installed yet — blank server.

---

#### Step A3 — Attach a static IP

Lightsail → your instance → **Networking** → **Create static IP** → attach to this instance.

**What this does:** By default, rebooting can change your IP. A **static IP** stays the same so you can bookmark `http://3.x.x.x/web/` and optionally point a domain at it.

Note the IP (e.g. `3.120.45.67`).

---

#### Step A4 — Open HTTP in the firewall

Lightsail → instance → **Networking** tab → **IPv4 Firewall**

Add:

| Application | Protocol | Port |
|-------------|----------|------|
| HTTP | TCP | 80 |
| HTTPS | TCP | 443 |

**What this does:** Lightsail blocks all incoming ports by default. Without rule **80**, nginx would run but the internet couldn’t reach it. **443** is for HTTPS later.

---

#### Step A5 — Download SSH key

Lightsail → **Account** → **SSH keys** → download default key for your region.

Save as e.g. `~/Downloads/LightsailDefaultKey.pem`

```bash
chmod 400 ~/Downloads/LightsailDefaultKey.pem
```

**What this does:** Proves to AWS that you’re allowed to log into the server. Lightsail uses key-based SSH, not passwords.

---

### Phase B — Set up the server

#### Step B1 — SSH into the instance

```bash
ssh -i ~/Downloads/LightsailDefaultKey.pem ubuntu@3.120.45.67
```

Replace IP with your static IP. User is **`ubuntu`** on Ubuntu blueprints.

**What this does:** Opens a remote shell on the Lightsail machine. Commands now run on the server, not your Mac.

---

#### Step B2 — Install nginx

On the server:

```bash
sudo apt-get update
sudo apt-get install -y nginx
sudo mkdir -p /var/www/bilingual-book-maker
```

Or upload the project’s setup script first (after sync) and run:

```bash
sudo bash /var/www/bilingual-book-maker/deploy/lightsail-setup.sh
```

**What this does:**

- `apt-get update` — refreshes package list
- `nginx` — installs the web server
- `/var/www/bilingual-book-maker` — directory where your site files will live

---

#### Step B3 — Configure nginx

On the server, create the site config:

```bash
sudo nano /etc/nginx/sites-available/bilingual-book-maker
```

Paste the contents of [`deploy/nginx.conf`](deploy/nginx.conf) from this repo (or copy via sync in step C).

Enable it:

```bash
sudo ln -sf /etc/nginx/sites-available/bilingual-book-maker /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

**What each command does:**

| Command | Purpose |
|---------|---------|
| `sites-available` | Stores config files |
| `sites-enabled` | Symlink = “use this config” |
| Remove `default` | Stops nginx showing “Welcome to nginx” instead of your app |
| `nginx -t` | Tests config syntax before restart |
| `systemctl restart nginx` | Applies changes |

---

### Phase C — Upload your books from Mac

**Exit SSH** (`exit`) or open a **new terminal on your Mac**.

#### Step C1 — Make sync script executable (once)

```bash
cd bilingual-book-maker
chmod +x deploy/sync-to-lightsail.sh
```

#### Step C2 — Sync files

Pass your `.pem` key as the second argument (nothing is saved to `~/.ssh/config`):

```bash
chmod 400 LightsailDefaultKey-ap-southeast-2.pem
./deploy/sync-to-lightsail.sh ubuntu@13.239.132.197 ./LightsailDefaultKey-ap-southeast-2.pem
```

Or set the key for **this terminal session only**:

```bash
export LIGHTSAIL_KEY=./LightsailDefaultKey-ap-southeast-2.pem
./deploy/sync-to-lightsail.sh ubuntu@13.239.132.197
```

**What this does:** `rsync` copies only changed files over SSH. Uploads:

- `index.html` — redirect to `/web/`
- `web/` — reader app
- `books/` — JSON + MP3s (can be large)
- `deploy/` — nginx config for reference

**Does not upload:** `scripts/`, `sources/`, `.env` (API keys stay on Mac).

If you see `Permission denied` on `/var/www/...`, the script fixes that automatically. Or run once on the server:

```bash
sudo mkdir -p /var/www/bilingual-book-maker && sudo chown -R ubuntu:ubuntu /var/www/bilingual-book-maker
```

#### Step C3 — Fix permissions on server (if needed)

```bash
ssh -i ~/Downloads/LightsailDefaultKey.pem ubuntu@3.120.45.67
sudo chown -R www-data:www-data /var/www/bilingual-book-maker
sudo chmod -R a+rX /var/www/bilingual-book-maker
```

**What this does:** nginx runs as user `www-data` and must be able to read all files.

---

### Phase D — Test from iPhone (over the internet)

Turn **Wi‑Fi off** on iPhone (use cellular) to prove it’s not local.

Open Safari:

```
http://3.120.45.67/web/
```

**What this does:** Traffic goes over the internet → Lightsail → nginx → your files. Mac is not involved.

If it works: deploy succeeded.

---

### Phase E — HTTPS with a domain (recommended)

HTTP works but HTTPS is better (padlock, some iOS behaviour). You need a **domain name** (e.g. `books.yourdomain.com`) pointing at your static IP.

#### Step E1 — DNS

At your registrar, add an **A record**:

```
books.yourdomain.com  →  3.120.45.67
```

Wait a few minutes for DNS to propagate.

---

#### Step E2 — Install Certbot on the server

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d books.yourdomain.com
```

Follow prompts (email, agree to terms). Certbot edits nginx for HTTPS and auto-renewal.

**What this does:** Let’s Encrypt gives a free TLS certificate. nginx serves `https://books.yourdomain.com/web/`.

---

#### Step E3 — Update nginx `server_name`

Edit `/etc/nginx/sites-available/bilingual-book-maker`:

```nginx
server_name books.yourdomain.com;
```

Then `sudo nginx -t && sudo systemctl reload nginx`.

---

### When you add a new book

Always on your **Mac**:

```bash
python scripts/prepare_book.py sources/new-book/book.txt
python scripts/generate_audio.py books/new-book/
./deploy/sync-to-lightsail.sh ubuntu@3.120.45.67
```

Only `books/new-book/` and updated `catalog.json` need to re-sync. Refresh Safari on iPhone — new book appears.

---

### Optional — Restrict access

Lightsail has no built-in password for static sites. Options:

1. **nginx basic auth** — username/password prompt before any page
2. **Cloudflare** in front of your domain — free Access rules
3. **Security group** — only allow your home IP (breaks “read anywhere”)

For personal use, obscurity + HTTPS is often enough; add basic auth if the URL leaks.

Example basic auth on server:

```bash
sudo apt-get install apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd yourusername
```

Add inside nginx `location /` block:

```nginx
auth_basic "Private library";
auth_basic_user_file /etc/nginx/.htpasswd;
```

---

### Lightsail cost snapshot

| Item | Typical cost |
|------|----------------|
| Instance (512 MB–1 GB) | ~$3.50–5/mo |
| Static IP | Free while attached to running instance |
| Data transfer | First 1 TB/mo included on many plans |
| Domain | ~$10–15/year (optional) |
| Translation (gpt-4o-mini, full novel) | ~$0.10–0.30 one-time per book |

---

## Technical background

This section explains what happens under the hood — useful before or after you deploy.

### How the reader loads (HTTP request flow)

Every time you open the app or tap Play, the browser makes ordinary **HTTP GET** requests. There is no custom backend API.

```
1. GET /web/                    → index.html
2. GET /web/styles.css          → layout
3. GET /web/app.js              → application logic
4. GET /web/manifest.json       → PWA metadata (for install hints)
5. GET /books/catalog.json        → ["letranger"]
6. GET /books/letranger/book.json → all sentences + translations
7. GET /books/letranger/audio/sentence_42.mp3 → audio for current sentence
```

**Origin:** All URLs share the same scheme + host + port (e.g. `http://3.120.45.67`). That is one **origin**. The browser allows `app.js` to `fetch('../books/...')` because it is same-origin.

**Hash routing:** URLs like `#/letranger/42` are handled entirely in JavaScript. The server always receives `GET /web/` (or `/web/index.html`); the `#...` part is never sent to the server. Navigation between sentences does not reload the page.

**State on device:** Reading progress lives in `localStorage` under keys like `bilingual-reader-progress`. That data stays on the iPhone in Safari’s storage for that origin — it is not on the server.

---

### Web app manifest & Add to Home Screen

#### What is `web/manifest.json`?

It is a **Web App Manifest** — a JSON file that describes how the site should behave when “installed” as an app:

```json
{
  "name": "Bilingual Reader",       // full name under the icon
  "short_name": "Reader",           // label if space is tight
  "start_url": "./",                // URL opened when icon is tapped
  "display": "standalone",          // hide browser URL bar / tab UI
  "background_color": "#f5f0e8",    // splash while loading
  "theme_color": "#f5f0e8",         // status bar tint (Android; hint on iOS)
  "orientation": "portrait"
}
```

It is linked from `web/index.html`:

```html
<link rel="manifest" href="manifest.json">
```

Browsers fetch it to learn the app name, colors, and launch behaviour. **It does not contain your books or logic** — only presentation metadata.

#### iOS-specific tags (also in `index.html`)

Safari historically ignored the manifest for some features and used Apple meta tags instead:

```html
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="viewport" content="..., viewport-fit=cover">
```

- **`apple-mobile-web-app-capable`** — when launched from home screen, run in standalone mode (no Safari toolbar).
- **`viewport-fit=cover`** — layout can extend into notch / home-indicator areas; CSS uses `env(safe-area-inset-*)`.

We do **not** currently ship `apple-touch-icon` — iOS falls back to a screenshot or generic icon.

#### What happens when you tap “Add to Home Screen”

Step by step on iPhone:

1. **Safari reads the page** — already loaded `index.html`, sees `<link rel="manifest">`.
2. **Safari may fetch `manifest.json`** — reads `name`, `short_name`, `display`, etc.
3. **You confirm** — iOS prompts for icon name (defaults to `short_name` or `<title>`).
4. **iOS writes a bookmark** — a `.webclip` plist on the device pointing at the **exact URL you were viewing** (e.g. `http://192.168.1.42:8080/web/` or `https://books.example.com/web/`).
5. **Icon appears** on home screen — looks like an app.

When you **tap the icon later**:

1. iOS opens **WebKit in standalone mode** (not the full Safari app UI).
2. WebKit requests `start_url` relative to the saved URL — effectively `/web/` again.
3. Same HTTP flow as before: HTML → CSS → JS → fetch JSON → fetch MP3.
4. **`localStorage` is available** — same origin as before, so progress is restored.

#### What it is *not*

| Myth | Reality |
|------|---------|
| “Installed like App Store” | No binary on device; still a website |
| “Works offline” | **Not yet** — we have no service worker; every launch needs the server (or cached assets only if browser cached them) |
| “manifest stores books” | Only UI metadata |
| “Separate app identity” | Same origin as Safari; shares cookies/storage with Safari for that URL |

To get true offline reading later, you would add a **service worker** that caches `book.json` and MP3s — that is planned as a future step, not implemented now.

---

### What nginx does

#### Role in one sentence

**nginx** is a production **web server** (and reverse proxy): it listens on ports 80/443, accepts HTTP requests from the internet, and **returns files from disk** (or forwards to another program).

For this project, nginx only does **static file serving** — no Python, Node, or database at runtime.

#### Python dev server vs nginx

| | `python3 -m http.server` | nginx |
|--|--------------------------|--------|
| Purpose | Local development | Production |
| Concurrency | One thread; slow under load | Event-driven; handles many connections |
| Security | Minimal | Mature; easy TLS, headers, auth |
| Config | None | `nginx.conf` + site files |
| Process | Stops when you close Terminal | Runs as systemd service, survives reboot |
| MIME types | Basic | Full (`.mp3` → `audio/mpeg`, `.json` → `application/json`) |

Both do the same logical job for a static site: **`GET /path` → read file → respond**.

#### Request path on Lightsail (detailed)

```
iPhone Safari
  │  TCP connect to 3.120.45.67:443 (HTTPS) or :80 (HTTP)
  │  TLS handshake (if HTTPS) — encrypts channel
  │  HTTP: GET /web/app.js HTTP/1.1
  │        Host: books.example.com
  ▼
Lightsail firewall (allows 80/443)
  ▼
Linux kernel — delivers packet to nginx process
  ▼
nginx — reads /etc/nginx/sites-enabled/bilingual-book-maker
  │  Matches server { root /var/www/bilingual-book-maker; }
  │  Maps URI /web/app.js → /var/www/bilingual-book-maker/web/app.js
  │  Checks file exists, readable
  │  Sets headers: Content-Type: application/javascript, Content-Length, ...
  ▼
HTTP 200 + file bytes → iPhone → app.js runs
```

For **MP3**, iOS may send `Range: bytes=0-` requests for seeking; nginx supports range requests on static files by default — important for audio.

#### Key nginx concepts in our setup

| Concept | Meaning |
|---------|---------|
| **`root`** | Directory prefix for URLs. `root /var/www/bilingual-book-maker` + URI `/web/index.html` → file at `/var/www/bilingual-book-maker/web/index.html` |
| **`server` block** | Virtual host — one site config (IP/domain, root, rules) |
| **`sites-available` / `sites-enabled`** | Debian/Ubuntu pattern: store configs, enable via symlink |
| **`www-data`** | Unix user nginx uses; files must be readable by this user |
| **`systemctl`** | Starts nginx on boot, restarts after config changes |
| **`certbot --nginx`** | Obtains Let’s Encrypt cert and injects `listen 443 ssl` into config |

Our [`deploy/nginx.conf`](deploy/nginx.conf) also sets cache headers on `.mp3` and `.json` so repeat visits do less work.

#### Why not run Python on the server?

You could (`python3 -m http.server 80`), but nginx is preferred because it:

- Starts automatically on reboot
- Handles TLS termination efficiently
- Serves large MP3 libraries with less memory
- Is the standard pattern for static + TLS on VPS/Lightsail

---

## Other options

### Cloudflare Tunnel

Books stay on Mac; public URL without uploading MP3s. See previous sections in git history or run:

```bash
cloudflared tunnel --url http://localhost:8080
```

### Cloudflare Pages

Static deploy; upload entire project including `books/` from local disk.

---

## What never goes on the server

| Path | Why |
|------|-----|
| `.env` | API keys |
| `sources/` | Raw text + LLM checkpoint |
| `scripts/` | Prep tools — Mac only |
| `legacy/` | Archive |

---

## Quick reference

| Stage | URL |
|-------|-----|
| Local iPhone test | `http://192.168.x.x:8080/web/` |
| Lightsail (HTTP) | `http://STATIC_IP/web/` |
| Lightsail (HTTPS) | `https://books.yourdomain.com/web/` |
