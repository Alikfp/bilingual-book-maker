import { MODES } from "./config.js";

const AUDIO_SPEEDS = [0.75, 1, 1.25, 1.5];

const FONT_STEPS = [-1, 0, 1];

const KEYS = {
  progress: "bilingual-reader-progress",
  lastOpened: "bilingual-reader-last-opened",
  readingMode: "bilingual-reader-mode",
  theme: "bilingual-reader-theme",
  fontScale: "bilingual-reader-font-scale",
  audioSpeed: "bilingual-reader-audio-speed",
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
  const clamped = Math.max(-1, Math.min(1, step));
  localStorage.setItem(KEYS.fontScale, String(clamped));
  applyFontScale(clamped);
}

export function cycleFontScale() {
  const idx = FONT_STEPS.indexOf(getFontScale());
  const next = FONT_STEPS[(idx + 1) % FONT_STEPS.length];
  setFontScale(next);
  return next;
}

export function formatFontScale(step) {
  return { [-1]: "S", 0: "M", 1: "L" }[step] || "M";
}

export function getAudioSpeed() {
  const raw = parseFloat(localStorage.getItem(KEYS.audioSpeed) || "1");
  return AUDIO_SPEEDS.includes(raw) ? raw : 1;
}

export function setAudioSpeed(speed) {
  if (!AUDIO_SPEEDS.includes(speed)) return;
  localStorage.setItem(KEYS.audioSpeed, String(speed));
}

export function cycleAudioSpeed() {
  const idx = AUDIO_SPEEDS.indexOf(getAudioSpeed());
  const next = AUDIO_SPEEDS[(idx + 1) % AUDIO_SPEEDS.length];
  setAudioSpeed(next);
  return next;
}

export function formatAudioSpeed(speed) {
  return speed === 1 ? "1×" : `${speed}×`;
}

export function applyPreferences() {
  applyTheme(getTheme());
  applyFontScale(getFontScale());
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
}

function applyFontScale(step) {
  const scales = [0.88, 1, 1.2];
  document.documentElement.style.setProperty("--font-scale", String(scales[step + 1]));
}
