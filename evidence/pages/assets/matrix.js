// Feature-matrix page: toggles and row/column highlight. No framework.
(function () {
  function init() {
    var table = document.querySelector(".ev-matrix");
    if (!table) return;
    var prop = document.getElementById("ev-show-proposed");
    var fig = document.getElementById("ev-only-figure");
    if (!prop || !fig) return;   // other tables (the coverage page) reuse .ev-matrix without the toggles
    function apply() {
      table.classList.toggle("ev-hide-prop", !prop.checked);
      table.classList.toggle("ev-only-fig", fig.checked);
    }
    prop.addEventListener("change", apply);
    fig.addEventListener("change", apply);
    apply();
    table.addEventListener("mouseover", function (e) {
      var td = e.target.closest("td[data-col], th[data-col]");
      table.querySelectorAll(".ev-hl").forEach(function (x) { x.classList.remove("ev-hl"); });
      if (!td) return;
      table.querySelectorAll('[data-col="' + td.dataset.col + '"]').forEach(function (x) { x.classList.add("ev-hl"); });
    });
  }
  // Material's instant navigation exposes document$; plain loads use DOMContentLoaded.
  if (window.document$) window.document$.subscribe(init);
  else document.addEventListener("DOMContentLoaded", init);
})();
