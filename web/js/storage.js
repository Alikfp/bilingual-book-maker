import { MODES } from "./config.js";

const KEYS = {
  progress: "bilingual-reader-progress",
  lastOpened: "bilingual-reader-last-opened",
  readingMode: "bilingual-reader-mode",
  theme: "bilingual-reader-theme",
  fontScale: "bilingual-reader-font-scale",
};

function readJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

export function getProgress(slug) {
  return readJson(KEYS.progress, {})[slug] || 1;
}

export function saveProgress(slug, sentenceId) {
  const progress = readJson(KEYS.progress, {});
  progress[slug] = sentenceId;
  writeJson(KEYS.progress, progress);
  setLastOpened(slug);
}

export function setLastOpened(slug) {
  writeJson(KEYS.lastOpened, { slug, at: Date.now() });
}

export function getLastOpened() {
  return readJson(KEYS.lastOpened, null);
}

export function getReadingMode() {
  const mode = localStorage.getItem(KEYS.readingMode);
  return Object.values(MODES).includes(mode) ? mode : MODES.STUDY;
}

export function setReadingMode(mode) {
  localStorage.setItem(KEYS.readingMode, mode);
}

export function cycleReadingMode() {
  const order = [MODES.STUDY, MODES.COMFORT, MODES.LISTEN];
  const next = order[(order.indexOf(getReadingMode()) + 1) % order.length];
  setReadingMode(next);
  return next;
}

export function getTheme() {
  return localStorage.getItem(KEYS.theme) || "auto";
}

export function setTheme(theme) {
  localStorage.setItem(KEYS.theme, theme);
  applyTheme(theme);
}

export function getFontScale() {
  const n = parseInt(localStorage.getItem(KEYS.fontScale) || "0", 10);
  return Number.isFinite(n) ? Math.max(-1, Math.min(1, n)) : 0;
}

export function setFontScale(step) {
  localStorage.setItem(KEYS.fontScale, String(step));
  applyFontScale(step);
}

export function applyPreferences() {
  applyTheme(getTheme());
  applyFontScale(getFontScale());
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
}

function applyFontScale(step) {
  const scales = [0.9, 1, 1.12];
  document.documentElement.style.setProperty("--font-scale", String(scales[step + 1]));
}
