(function () {
  "use strict";

  const picker = document.getElementById("film-picker");
  const select = document.getElementById("film-select");
  if (!picker || !select) {
    return;
  }

  picker.addEventListener("submit", function (event) {
    event.preventDefault();
    const film = select.value;
    if (!film) {
      select.focus();
      return;
    }
    window.location.href = "/recommendations/" + encodeURIComponent(film);
  });
})();
