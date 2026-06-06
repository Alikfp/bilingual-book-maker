export function createAudioController(player) {
  let state = "idle";
  let listeners = new Set();

  function setState(next) {
    state = next;
    listeners.forEach((fn) => fn(state));
  }

  function bind() {
    player.addEventListener("loadstart", () => setState("loading"));
    player.addEventListener("waiting", () => setState("loading"));
    player.addEventListener("playing", () => setState("playing"));
    player.addEventListener("pause", () => setState(player.currentTime > 0 ? "paused" : "idle"));
    player.addEventListener("ended", () => setState("idle"));
    player.addEventListener("error", () => setState("error"));
  }

  bind();

  return {
    get state() {
      return state;
    },

    onChange(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },

    load(url) {
      if (!url) {
        player.removeAttribute("src");
        setState("error");
        return;
      }
      if (player.src !== url) {
        player.src = url;
        player.load();
      }
    },

    play() {
      return player.play().catch(() => setState("error"));
    },

    pause() {
      player.pause();
    },

    toggle() {
      if (state === "playing") {
        this.pause();
      } else {
        return this.play();
      }
    },

    repeat() {
      player.currentTime = 0;
      return this.play();
    },
  };
}
