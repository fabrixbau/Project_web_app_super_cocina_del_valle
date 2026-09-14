(() => {
  if (window.location.pathname !== "/app/pedidos/") return;

  const params = new URLSearchParams(window.location.search);
  const choice = params.get("x20_layout");
  if (choice === "1" || choice === "0") {
    try { window.localStorage.setItem("yeemovil-x20-layout", choice); } catch (_) { /* Storage may be disabled. */ }
  }
  let saved = choice === "1" || choice === "0" ? choice : null;
  if (saved === null) {
    try { saved = window.localStorage.getItem("yeemovil-x20-layout"); } catch (_) { /* Storage may be disabled. */ }
  }
  const modelMatches = /Android/i.test(navigator.userAgent)
    && /(?:^|[;(\s])X20(?:$|[);\s/])/i.test(navigator.userAgent)
    && Math.min(window.screen.width, window.screen.height) >= 600;
  document.documentElement.classList.toggle("yeemovil-x20", saved === "1" || (saved !== "0" && modelMatches));
})();
