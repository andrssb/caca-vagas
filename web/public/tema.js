// Carregado no <head>, antes do CSS pintar: aplica o tema salvo sem piscar.
(function () {
  var tema = null;
  try { tema = localStorage.getItem("cv_tema"); } catch (e) {}
  if (tema === "claro" || tema === "escuro") document.documentElement.dataset.theme = tema === "claro" ? "light" : "dark";
})();
