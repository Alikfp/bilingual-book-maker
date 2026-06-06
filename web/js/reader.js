import { MODES, MODE_LABELS } from "./config.js";
import {
  audioUrl,
  bookStats,
  fetchBook,
  indexForId,
  isSentenceReady,
} from "./books.js";
import {
  getReadingMode,
  cycleReadingMode,
  saveProgress,
} from "./storage.js";
import { chapterLabel, escapeHtml, prefersReducedMotion } from "./util.js";

export function createReader(app, audio) {
  let book = null;
  let index = 0;
  let peeking = false;
  let navigateFn = () => {};

  const els = {};

  function sentence() {
    return book?.sentences[index];
  }

  function stats() {
    return book ? bookStats(book, sentence()?.id) : null;
  }

  function shouldShowTranslation() {
    const mode = getReadingMode();
    if (mode === MODES.COMFORT) return true;
    if (mode === MODES.STUDY) return peeking;
    return false;
  }

  function shouldAutoPlay() {
    return getReadingMode() === MODES.LISTEN;
  }

  function translationHtml(s) {
    if (!s.translation) {
      return `<p class="sentence-hint">Translation not ready yet.</p>`;
    }
    const visible = shouldShowTranslation();
    return `<p class="sentence-translation${visible ? " is-visible" : ""}">${escapeHtml(s.translation)}</p>`;
  }

  function statusHtml(s) {
    if (!isSentenceReady(s)) {
      return `<p class="sentence-hint">This sentence is not prepared yet.</p>`;
    }
    if (audio.state === "error") {
      return `<p class="sentence-hint">Audio not available.</p>`;
    }
    if (getReadingMode() === MODES.STUDY && !peeking) {
      return `<p class="sentence-hint study-hint">Tap sentence to peek at English</p>`;
    }
    return "";
  }

  function updateContent(direction = 0) {
    const content = els.content;
    if (!content || !book) return;

    const s = sentence();
    const chapter = chapterLabel(s.original);

    const apply = () => {
      content.innerHTML = `
        <article class="sentence-card">
          ${chapter ? `<p class="chapter-label">${escapeHtml(chapter)}</p>` : ""}
          <p class="sentence-original${audio.state === "playing" ? " is-speaking" : ""}">${escapeHtml(s.original)}</p>
          ${translationHtml(s)}
          ${statusHtml(s)}
        </article>
      `;
      bindSentencePeek(content);
    };

    if (prefersReducedMotion() || !content.classList.contains("is-ready") || direction === 0) {
      apply();
      content.classList.add("is-ready");
      return;
    }

    content.classList.remove("is-ready");
    content.classList.add("is-changing");
    if (direction > 0) content.classList.add("dir-next");
    else if (direction < 0) content.classList.add("dir-prev");
    window.setTimeout(() => {
      apply();
      content.classList.remove("dir-next", "dir-prev", "is-changing");
      requestAnimationFrame(() => content.classList.add("is-ready"));
    }, 140);
  }

  function bindSentencePeek(content) {
    const card = content.querySelector(".sentence-card");
    if (!card || getReadingMode() !== MODES.STUDY) return;

    const showPeek = () => {
      peeking = true;
      updateContent();
    };
    const hidePeek = () => {
      peeking = false;
      updateContent();
    };

    card.addEventListener("click", () => {
      peeking = !peeking;
      updateContent();
    });
  }

  function updateChrome() {
    const s = sentence();
    if (!s || !book) return;

    els.badge.textContent = `${index + 1} / ${book.sentences.length}`;
    els.barFill.style.width = `${stats().readPct}%`;

    const st = stats();
    if (st.partial) {
      els.readyMeta.textContent = `${st.ready.toLocaleString()} of ${st.total.toLocaleString()} prepared`;
      els.readyMeta.hidden = false;
    } else {
      els.readyMeta.hidden = true;
    }

    els.modeBtn.textContent = MODE_LABELS[getReadingMode()];
    els.modeBtn.classList.toggle("active", getReadingMode() !== MODES.STUDY);

    els.prev.disabled = index <= 0;
    const nextSentence = book.sentences[index + 1];
    const atEnd = index >= book.sentences.length - 1;
    const nextBlocked = st.partial && nextSentence && !isSentenceReady(nextSentence);
    els.next.disabled = atEnd || nextBlocked;

    updatePlayButton();
    updateContent();
  }

  function updatePlayButton() {
    const labels = { idle: "Play", loading: "…", playing: "Pause", paused: "Play", error: "—" };
    const icons = { idle: "▶", loading: "◌", playing: "⏸", paused: "▶", error: "✕" };
    els.playLabel.textContent = labels[audio.state] || "Play";
    els.playIcon.textContent = icons[audio.state] || "▶";
    els.play.classList.toggle("is-playing", audio.state === "playing");
    els.play.disabled = audio.state === "error" || !isSentenceReady(sentence());
  }

  function loadAudio() {
    const s = sentence();
    if (!book || !s || !isSentenceReady(s)) {
      audio.load(null);
      return;
    }
    audio.load(new URL(audioUrl(book.id, s.id), location.href).href);
    if (shouldAutoPlay()) {
      audio.play();
    }
  }

  function goTo(nextIndex, direction) {
    if (!book) return;
    const max = book.sentences.length - 1;
    index = Math.max(0, Math.min(nextIndex, max));
    peeking = false;

    const s = sentence();
    saveProgress(book.id, s.id);
    history.replaceState(null, "", `#/${book.id}/${s.id}`);

    loadAudio();
    updateContent(direction);
    updateChrome();
  }

  function goRelative(delta) {
    goTo(index + delta, delta);
  }

  function bindSwipe(el) {
    let startX = 0;
    let startY = 0;

    el.addEventListener(
      "touchstart",
      (e) => {
        startX = e.changedTouches[0].screenX;
        startY = e.changedTouches[0].screenY;
      },
      { passive: true }
    );

    el.addEventListener(
      "touchend",
      (e) => {
        const dx = e.changedTouches[0].screenX - startX;
        const dy = e.changedTouches[0].screenY - startY;
        if (Math.abs(dx) < 50 || Math.abs(dx) < Math.abs(dy)) return;
        goRelative(dx < 0 ? 1 : -1);
      },
      { passive: true }
    );
  }

  function bindLongPressRepeat() {
    let timer;
    const start = () => {
      timer = window.setTimeout(() => audio.repeat(), 450);
    };
    const cancel = () => window.clearTimeout(timer);

    els.play.addEventListener("touchstart", start, { passive: true });
    els.play.addEventListener("touchend", cancel);
    els.play.addEventListener("touchcancel", cancel);
    els.play.addEventListener("mousedown", start);
    els.play.addEventListener("mouseup", cancel);
    els.play.addEventListener("mouseleave", cancel);
  }

  function mountShell() {
    app.innerHTML = `
      <div class="reader-view mode-${getReadingMode()}">
        <header class="reader-top">
          <button type="button" class="back-btn" id="btn-back" aria-label="Back">←</button>
          <div class="reader-title">
            <h1 id="reader-title"></h1>
            <p id="reader-author"></p>
          </div>
          <button type="button" class="mode-chip" id="btn-mode"></button>
        </header>
        <div class="reader-progress">
          <div class="progress-track"><div class="progress-fill" id="reader-bar"></div></div>
          <span class="progress-badge" id="progress-badge"></span>
        </div>
        <p class="ready-meta reader-ready" id="reader-ready" hidden></p>
        <main class="reader-content is-ready" id="reader-content"></main>
        <nav class="reader-toolbar" aria-label="Reader controls">
          <button type="button" class="toolbar-btn" id="btn-prev" aria-label="Previous sentence">
            <span class="icon">◀</span>
          </button>
          <button type="button" class="toolbar-btn toolbar-btn-play" id="btn-play" aria-label="Play or pause">
            <span class="icon" id="play-icon">▶</span>
            <span class="label" id="play-label">Play</span>
          </button>
          <button type="button" class="toolbar-btn" id="btn-next" aria-label="Next sentence">
            <span class="icon">▶</span>
          </button>
        </nav>
      </div>
    `;

    els.content = app.querySelector("#reader-content");
    els.badge = app.querySelector("#progress-badge");
    els.barFill = app.querySelector("#reader-bar");
    els.readyMeta = app.querySelector("#reader-ready");
    els.modeBtn = app.querySelector("#btn-mode");
    els.play = app.querySelector("#btn-play");
    els.playIcon = app.querySelector("#play-icon");
    els.playLabel = app.querySelector("#play-label");
    els.prev = app.querySelector("#btn-prev");
    els.next = app.querySelector("#btn-next");

    app.querySelector("#reader-title").textContent = book.title;
    app.querySelector("#reader-author").textContent = book.author || "";

    app.querySelector("#btn-back").addEventListener("click", () => navigateFn("#/"));
    els.prev.addEventListener("click", () => goRelative(-1));
    els.next.addEventListener("click", () => goRelative(1));
    els.play.addEventListener("click", () => {
      if (audio.state === "playing") audio.pause();
      else audio.play();
    });
    els.modeBtn.addEventListener("click", () => {
      cycleReadingMode();
      peeking = false;
      app.querySelector(".reader-view").className = `reader-view mode-${getReadingMode()}`;
      updateChrome();
      if (shouldAutoPlay()) audio.play();
    });

    bindSwipe(els.content);
    bindLongPressRepeat();
    audio.onChange(() => {
      updatePlayButton();
      const original = els.content?.querySelector(".sentence-original");
      original?.classList.toggle("is-speaking", audio.state === "playing");
    });
  }

  return {
    setNavigate(fn) {
      navigateFn = fn;
    },

    async open(slug, sentenceId) {
      if (!book || book.id !== slug) {
        book = await fetchBook(slug);
      }

      if (!app.querySelector("#reader-content")) {
        mountShell();
      } else {
        app.querySelector("#reader-title").textContent = book.title;
        app.querySelector("#reader-author").textContent = book.author || "";
        app.querySelector(".reader-view").className = `reader-view mode-${getReadingMode()}`;
      }

      index = indexForId(book, sentenceId || 1);
      peeking = false;
      saveProgress(slug, sentence().id);
      loadAudio();
      updateContent();
      updateChrome();
    },

    destroy() {
      book = null;
      index = 0;
      peeking = false;
      for (const key of Object.keys(els)) delete els[key];
    },
  };
}

export function renderReaderError(app, message) {
  app.innerHTML = `<div class="error-banner">${escapeHtml(message)}</div>`;
}
