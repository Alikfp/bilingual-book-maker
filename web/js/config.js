// Absolute /books avoids broken relative resolution with hash routes and missing trailing slashes.
export const BOOKS_BASE = location.pathname.includes("/web") ? "/books" : "./books";

export const MODES = {
  STUDY: "study",
  COMFORT: "comfort",
  LISTEN: "listen",
};

export const MODE_LABELS = {
  study: "Study",
  comfort: "Comfort",
  listen: "Listen",
};
