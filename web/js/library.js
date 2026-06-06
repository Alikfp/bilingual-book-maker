import { MODE_LABELS, MODES } from "./config.js";
import {
  fetchBook,
  fetchCatalog,
  bookStats,
  coverUrl,
  indexForId,
} from "./books.js";
import { getProgress, getLastOpened, getTheme, setTheme, getFontScale, setFontScale } from "./storage.js";
import { escapeHtml } from "./util.js";

function progressBar(pct) {
  return `<div class="progress-track" aria-hidden="true"><div class="progress-fill" style="width:${pct}%"></div></div>`;
}

function bookCoverHtml(slug, cover, large = false) {
  const cls = large ? "book-cover book-cover-lg" : "book-cover";
  if (cover) {
    return `<img class="${cls}" src="${cover}" alt="">`;
  }
  return `<div class="${cls} placeholder" aria-hidden="true">📖</div>`;
}

function readyLabel(stats) {
  if (stats.partial) {
    return `${stats.ready.toLocaleString()} of ${stats.total.toLocaleString()} ready`;
  }
  return `${stats.total.toLocaleString()} sentences`;
}

export async function renderLibrary(app, { onOpenBook }) {
  app.innerHTML = `
    <header class="library-header">
      <div class="library-header-row">
        <div>
          <h1>Bilingual Reader</h1>
          <p>One sentence at a time</p>
        </div>
        <div class="library-actions">
          <button type="button" class="icon-btn" id="btn-font-down" aria-label="Smaller text">A−</button>
          <button type="button" class="icon-btn" id="btn-font-up" aria-label="Larger text">A+</button>
          <button type="button" class="icon-btn" id="btn-theme" aria-label="Toggle theme">◐</button>
        </div>
      </div>
    </header>
    <div class="book-list" id="book-list">Loading…</div>
  `;

  bindLibrarySettings(app);

  const catalog = await fetchCatalog();
  const list = app.querySelector("#book-list");

  if (catalog.length === 0) {
    list.innerHTML = '<div class="empty-state">No books yet.<br>Run prepare_book.py to add one.</div>';
    return;
  }

  const entries = await Promise.all(
    catalog.map(async (slug) => {
      const book = await fetchBook(slug);
      const progress = getProgress(slug);
      const stats = bookStats(book, progress);
      return { slug, book, progress, stats, cover: coverUrl(slug, book.cover) };
    })
  );

  const lastOpened = getLastOpened()?.slug;
  const continueEntry =
    entries.find((e) => e.slug === lastOpened) ||
    entries.reduce((a, b) => (a.stats.idx >= b.stats.idx ? a : b), entries[0]);

  const hero = continueEntry
    ? `
      <section class="continue-card">
        <p class="continue-label">Continue reading</p>
        <button type="button" class="continue-inner" data-slug="${escapeHtml(continueEntry.slug)}" data-id="${continueEntry.progress}">
          ${bookCoverHtml(continueEntry.slug, continueEntry.cover, true)}
          <div class="continue-info">
            <h2>${escapeHtml(continueEntry.book.title)}</h2>
            <p class="author">${escapeHtml(continueEntry.book.author || "")}</p>
            <p class="meta">Sentence ${continueEntry.progress} · ${continueEntry.stats.readPct}% through book</p>
            ${progressBar(continueEntry.stats.readPct)}
            <p class="ready-meta">${readyLabel(continueEntry.stats)}</p>
          </div>
        </button>
      </section>
      <h2 class="section-label">Library</h2>
    `
    : "";

  const cards = entries
    .map(({ slug, book, progress, stats, cover }) => `
        <button type="button" class="book-card" data-slug="${escapeHtml(slug)}" data-id="${progress}">
          ${bookCoverHtml(slug, cover)}
          <div class="book-info">
            <h2>${escapeHtml(book.title)}</h2>
            <p class="author">${escapeHtml(book.author || "")}</p>
            <p class="meta">Sentence ${progress} · ${stats.readPct}%</p>
            ${progressBar(stats.partial ? stats.readyPct : stats.readPct)}
            <p class="ready-meta">${readyLabel(stats)}</p>
          </div>
        </button>
      `)
    .join("");

  list.innerHTML = hero + cards;

  list.querySelectorAll("[data-slug]").forEach((btn) => {
    btn.addEventListener("click", () => {
      onOpenBook(btn.dataset.slug, parseInt(btn.dataset.id, 10));
    });
  });
}

function bindLibrarySettings(app) {
  app.querySelector("#btn-font-down")?.addEventListener("click", () => {
    setFontScale(Math.max(-1, getFontScale() - 1));
  });
  app.querySelector("#btn-font-up")?.addEventListener("click", () => {
    setFontScale(Math.min(1, getFontScale() + 1));
  });

  app.querySelector("#btn-theme")?.addEventListener("click", () => {
    const order = ["auto", "light", "dark"];
    const current = getTheme();
    setTheme(order[(order.indexOf(current) + 1) % order.length]);
  });
}

export function renderLibraryError(app, message) {
  app.innerHTML = `<div class="error-banner">${escapeHtml(message)}</div>`;
}
