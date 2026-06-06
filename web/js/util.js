export function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

export function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

const CHAPTER_RE = /^(PREMIER CHAPITRE|CHAPITRE [IVXLCDM]+|\d+\.?)$/i;

export function chapterLabel(text) {
  const head = text.trim().split(/\s+/).slice(0, 3).join(" ");
  if (CHAPTER_RE.test(head) || CHAPTER_RE.test(text.trim().slice(0, 20))) {
    return text.trim().length <= 40 ? text.trim() : head;
  }
  return null;
}
