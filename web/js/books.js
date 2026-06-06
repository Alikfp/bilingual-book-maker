import { BOOKS_BASE } from "./config.js";

export function indexForId(book, id) {
  const idx = book.sentences.findIndex((s) => s.id === id);
  return idx >= 0 ? idx : 0;
}

export function coverUrl(slug, cover) {
  return cover ? `${BOOKS_BASE}/${slug}/${cover}` : null;
}

export function audioUrl(slug, id) {
  return `${BOOKS_BASE}/${slug}/audio/sentence_${id}.mp3`;
}

export async function fetchCatalog() {
  const res = await fetch(`${BOOKS_BASE}/catalog.json`);
  if (!res.ok) throw new Error("Could not load book catalog");
  const data = await res.json();
  return data.books || [];
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

export function isSentenceReady(sentence) {
  return Boolean(sentence?.translation);
}
