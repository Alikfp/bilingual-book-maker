import { applyPreferences } from "./js/storage.js";
import { renderLibrary, renderLibraryError } from "./js/library.js";
import { createReader, renderReaderError } from "./js/reader.js";
import { createAudioController } from "./js/audio.js";

const app = document.getElementById("app");
const audioPlayer = document.getElementById("audio-player");
const audio = createAudioController(audioPlayer);
const reader = createReader(app, audio);

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

reader.setNavigate(navigate);
window.addEventListener("hashchange", render);

async function render() {
  const route = parseRoute();

  if (route.view === "library") {
    reader.destroy();
    try {
      await renderLibrary(app, {
        onOpenBook: (slug, id) => navigate(`#/${slug}/${id}`),
      });
    } catch (err) {
      renderLibraryError(app, err.message);
    }
    return;
  }

  try {
    await reader.open(route.slug, route.sentenceId);
  } catch (err) {
    renderReaderError(app, err.message);
  }
}

applyPreferences();
render();
