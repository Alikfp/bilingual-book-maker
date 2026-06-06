// ../books when served from /web/; ./books when app files are at site root
const BOOKS_BASE = location.pathname.includes("/web") ? "../books" : "./books";
const PROGRESS_KEY = "bilingual-reader-progress";
const SHOW_TRANSLATION_KEY = "bilingual-reader-show-translation";

const app = document.getElementById("app");
const audioPlayer = document.getElementById("audio-player");

let catalog = [];
let currentBook = null;
let currentIndex = 0;
let showTranslation = localStorage.getItem(SHOW_TRANSLATION_KEY) !== "false";

function parseRoute() {
  const hash = location.hash.replace(/^#/, "") || "/";
  const parts = hash.split("/").filter(Boolean);
  if (parts.length === 0) return { view: "library" };
  return {
    view: "reader",
    slug: parts[0],
    sentenceId: parts[1] ? parseInt(parts[1], 10) : null,
  };
}

function navigate(hash) {
  if (location.hash !== hash) location.hash = hash;
  else render();
}

window.addEventListener("hashchange", render);

function loadProgress() {
  try {
    return JSON.parse(localStorage.getItem(PROGRESS_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveProgress(slug, sentenceId) {
  const progress = loadProgress();
  progress[slug] = sentenceId;
  localStorage.setItem(PROGRESS_KEY, JSON.stringify(progress));
}

function getProgress(slug) {
  return loadProgress()[slug] || 1;
}

async function fetchCatalog() {
  const res = await fetch(`${BOOKS_BASE}/catalog.json`);
  if (!res.ok) throw new Error("Could not load book catalog");
  const data = await res.json();
  return data.books || [];
}

async function fetchBook(slug) {
  const res = await fetch(`${BOOKS_BASE}/${slug}/book.json`);
  if (!res.ok) throw new Error(`Could not load book: ${slug}`);
  return res.json();
}

function hasTranslations(book) {
  return book.sentences.some((s) => s.translation);
}

function indexForId(book, id) {
  const idx = book.sentences.findIndex((s) => s.id === id);
  return idx >= 0 ? idx : 0;
}

function coverUrl(slug, cover) {
  return cover ? `${BOOKS_BASE}/${slug}/${cover}` : null;
}

function audioUrl(slug, id) {
  return `${BOOKS_BASE}/${slug}/audio/sentence_${id}.mp3`;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function playCurrentAudio() {
  if (!currentBook) return;
  const sentence = currentBook.sentences[currentIndex];
  if (!sentence) return;
  audioPlayer.src = audioUrl(currentBook.id, sentence.id);
  audioPlayer.load();
  audioPlayer.play().catch(() => {});
}

function repeatAudio() {
  audioPlayer.currentTime = 0;
  audioPlayer.play().catch(() => {});
}

function goToIndex(index) {
  if (!currentBook) return;
  const max = currentBook.sentences.length - 1;
  currentIndex = Math.max(0, Math.min(index, max));
  const sentence = currentBook.sentences[currentIndex];
  saveProgress(currentBook.id, sentence.id);
  renderReaderContent();
  updateNavButtons();
  updateProgressBadge();
  playCurrentAudio();
  history.replaceState(null, "", `#/${currentBook.id}/${sentence.id}`);
}

function goRelative(delta) {
  goToIndex(currentIndex + delta);
}

function toggleTranslation() {
  if (!currentBook || !hasTranslations(currentBook)) return;
  showTranslation = !showTranslation;
  localStorage.setItem(SHOW_TRANSLATION_KEY, showTranslation);
  renderReaderContent();
  updateTranslationButton();
}

let touchStartX = 0;
let touchStartY = 0;

function setupSwipe(el) {
  el.addEventListener(
    "touchstart",
    (e) => {
      touchStartX = e.changedTouches[0].screenX;
      touchStartY = e.changedTouches[0].screenY;
    },
    { passive: true }
  );

  el.addEventListener(
    "touchend",
    (e) => {
      const dx = e.changedTouches[0].screenX - touchStartX;
      const dy = e.changedTouches[0].screenY - touchStartY;
      if (Math.abs(dx) < 50 || Math.abs(dx) < Math.abs(dy)) return;
      goRelative(dx < 0 ? 1 : -1);
    },
    { passive: true }
  );
}

function renderError(message) {
  app.innerHTML = `<div class="error-banner">${escapeHtml(message)}</div>`;
}

async function renderLibrary() {
  app.innerHTML = `
    <div class="library-header">
      <h1>Bilingual Reader</h1>
      <p>Read one sentence at a time with audio</p>
    </div>
    <div class="book-list" id="book-list">Loading…</div>
  `;

  try {
    catalog = await fetchCatalog();
    const list = document.getElementById("book-list");
    if (catalog.length === 0) {
      list.innerHTML =
        '<div class="empty-state">No books yet.<br>Run prepare_book.py to add one.</div>';
      return;
    }

    const cards = await Promise.all(
      catalog.map(async (slug) => {
        const book = await fetchBook(slug);
        const progress = getProgress(slug);
        const total = book.sentences.length;
        const idx = indexForId(book, progress);
        const pct = total ? Math.round(((idx + 1) / total) * 100) : 0;
        const cover = coverUrl(slug, book.cover);

        return `
          <button class="book-card" data-slug="${escapeHtml(slug)}">
            ${
              cover
                ? `<img class="book-cover" src="${cover}" alt="">`
                : '<div class="book-cover placeholder">📖</div>'
            }
            <div class="book-info">
              <h2>${escapeHtml(book.title)}</h2>
              <p class="author">${escapeHtml(book.author || "")}</p>
              <p class="progress">${pct}% · sentence ${progress} of ${total}</p>
            </div>
          </button>
        `;
      })
    );

    list.innerHTML = cards.join("");
    list.querySelectorAll(".book-card").forEach((btn) => {
      btn.addEventListener("click", () => {
        navigate(`#/${btn.dataset.slug}/${getProgress(btn.dataset.slug)}`);
      });
    });
  } catch (err) {
    renderError(err.message);
  }
}

function renderReaderContent() {
  const content = document.getElementById("reader-content");
  if (!content || !currentBook) return;

  const sentence = currentBook.sentences[currentIndex];
  const canTranslate = hasTranslations(currentBook);

  content.innerHTML = `
    <p class="sentence-original">${escapeHtml(sentence.original)}</p>
    ${
      canTranslate
        ? `<p class="sentence-translation${showTranslation ? "" : " hidden"}">${escapeHtml(sentence.translation || "")}</p>`
        : '<p class="no-translation-hint">No translation available for this book.</p>'
    }
  `;
}

function updateTranslationButton() {
  const btn = document.getElementById("btn-translate");
  if (!btn) return;
  const canTranslate = currentBook && hasTranslations(currentBook);
  btn.disabled = !canTranslate;
  btn.classList.toggle("active", showTranslation && canTranslate);
}

function updateNavButtons() {
  const prev = document.getElementById("btn-prev");
  const next = document.getElementById("btn-next");
  if (!prev || !next || !currentBook) return;
  prev.disabled = currentIndex <= 0;
  next.disabled = currentIndex >= currentBook.sentences.length - 1;
}

function updateProgressBadge() {
  const badge = document.getElementById("progress-badge");
  if (badge && currentBook) {
    badge.textContent = `${currentIndex + 1} / ${currentBook.sentences.length}`;
  }
}

async function renderReader(slug, sentenceId) {
  try {
    if (!currentBook || currentBook.id !== slug) {
      currentBook = await fetchBook(slug);
    }

    const savedId = sentenceId || getProgress(slug);
    currentIndex = indexForId(currentBook, savedId);
    const sentence = currentBook.sentences[currentIndex];
    saveProgress(slug, sentence.id);

    app.innerHTML = `
      <div class="reader-view">
        <header class="reader-top">
          <button class="back-btn" id="btn-back" aria-label="Back">←</button>
          <div class="reader-title">
            <h1>${escapeHtml(currentBook.title)}</h1>
            <p>${escapeHtml(currentBook.author || "")}</p>
          </div>
          <span class="progress-badge" id="progress-badge">${currentIndex + 1} / ${currentBook.sentences.length}</span>
        </header>
        <div class="reader-content" id="reader-content"></div>
        <nav class="reader-toolbar reader-toolbar-main">
          <button class="toolbar-btn" id="btn-prev" aria-label="Previous">
            <span class="icon">◀</span><span>Prev</span>
          </button>
          <button class="toolbar-btn primary" id="btn-play" aria-label="Play">
            <span class="icon">▶</span><span>Play</span>
          </button>
          <button class="toolbar-btn" id="btn-repeat" aria-label="Repeat">
            <span class="icon">↻</span><span>Repeat</span>
          </button>
          <button class="toolbar-btn" id="btn-next" aria-label="Next">
            <span class="icon">▶</span><span>Next</span>
          </button>
          <button class="toolbar-btn" id="btn-translate" aria-label="Toggle translation">
            <span class="icon">A/a</span><span>English</span>
          </button>
        </nav>
      </div>
    `;

    renderReaderContent();
    updateTranslationButton();
    updateNavButtons();
    setupSwipe(document.getElementById("reader-content"));

    document.getElementById("btn-back").addEventListener("click", () => navigate("#/"));
    document.getElementById("btn-prev").addEventListener("click", () => goRelative(-1));
    document.getElementById("btn-next").addEventListener("click", () => goRelative(1));
    document.getElementById("btn-play").addEventListener("click", playCurrentAudio);
    document.getElementById("btn-repeat").addEventListener("click", repeatAudio);
    document.getElementById("btn-translate").addEventListener("click", toggleTranslation);

    playCurrentAudio();

    if (sentenceId !== sentence.id) {
      history.replaceState(null, "", `#/${slug}/${sentence.id}`);
    }
  } catch (err) {
    renderError(err.message);
  }
}

async function render() {
  const route = parseRoute();
  if (route.view === "library") {
    currentBook = null;
    await renderLibrary();
    return;
  }
  await renderReader(route.slug, route.sentenceId);
}

render();
