(function () {
  "use strict";

  const form = document.getElementById("film-picker");
  const input = document.getElementById("film-input");
  const error = document.getElementById("picker-error");
  if (!form || !input) {
    return;
  }

  const ids = new Map();
  document.querySelectorAll("#film-options option").forEach(function (option) {
    ids.set(option.value.toLowerCase(), option.dataset.id);
  });

  function resolve(text) {
    const query = text.trim().toLowerCase();
    if (!query) {
      return null;
    }
    if (ids.has(query)) {
      return ids.get(query);
    }
    // Digitazione parziale: accetta solo se il titolo corrisponde a un unico film.
    const matches = [...ids.entries()].filter(function (entry) {
      return entry[0].startsWith(query);
    });
    return matches.length === 1 ? matches[0][1] : null;
  }

  input.addEventListener("input", function () {
    error.textContent = "";
  });

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    const id = resolve(input.value);
    if (!id) {
      error.textContent = input.value.trim()
        ? "Nessun film univoco con questo titolo: scegline uno dall'elenco."
        : "Scrivi il titolo di un film.";
      input.focus();
      return;
    }
    window.location.href = "/recommendations/" + encodeURIComponent(id);
  });
})();
