import { BOOKS_BASE } from "./config.js";

export function indexForId(book, id) {
  const idx = book.sentences.findIndex((s) => s.id === id);
  return idx >= 0 ? idx : 0;
}

export function coverUrl(slug, cover) {
  const file = cover || "cover.jpg";
  return `${BOOKS_BASE}/${slug}/${file}`;
}

export function audioUrl(slug, id) {
  return `${BOOKS_BASE}/${slug}/audio/sentence_${id}.mp3`;
}

export function normalizeCatalogEntry(entry) {
  if (typeof entry === "string") {
    return { id: entry, slug: entry, cover: "cover.jpg" };
  }
  const slug = entry.id || entry.slug;
  return { ...entry, slug, cover: entry.cover || "cover.jpg" };
}

export async function fetchCatalog() {
  const res = await fetch(`${BOOKS_BASE}/catalog.json`);
  if (!res.ok) throw new Error("Could not load book catalog");
  const data = await res.json();
  return (data.books || []).map(normalizeCatalogEntry);
}

export async function fetchBook(slug) {
  const res = await fetch(`${BOOKS_BASE}/${slug}/book.json`);
  if (!res.ok) throw new Error(`Could not load book: ${slug}`);
  return res.json();
}

export function bookStats(book, progressId) {
  const total = book.sentences.length;
  const ready = book.sentences.filter((s) => s.translation).length;
  const idx = indexForId(book, progressId);
  const readPct = total ? Math.round(((idx + 1) / total) * 100) : 0;
  const readyPct = total ? Math.round((ready / total) * 100) : 0;
  const partial = ready > 0 && ready < total;
  const lastReadyIndex = (() => {
    for (let i = book.sentences.length - 1; i >= 0; i--) {
      if (book.sentences[i].translation) return i;
    }
    return -1;
  })();

  return { total, ready, readPct, readyPct, partial, lastReadyIndex, idx };
}

export function catalogStats(entry, progressId) {
  const total = entry.totalSentences || 0;
  const ready = entry.translatedSentences || 0;
  const readPct = total ? Math.round((progressId / total) * 100) : 0;
  const readyPct = total ? Math.round((ready / total) * 100) : 0;
  const partial = ready > 0 && ready < total;
  return { total, ready, readPct, readyPct, partial, idx: Math.max(0, progressId - 1) };
}

export function isSentenceReady(sentence) {
  return Boolean(sentence?.translation);
}
