/* NOTA TEMPORAL PARA APRENDIZAJE: Ya no hay PIN. Si el mesero preseleccionado
necesita su contraseña (primera vez hoy), se enfoca ese campo al abrir; si el
cambio es instantáneo o hay que elegir entre varios, se enfoca el selector o el
botón. Borra esta nota después de leerla. */
(() => {
  const dropdown = document.querySelector("[data-quick-switch-dropdown]");
  if (!dropdown) return;
  const password = dropdown.querySelector("[data-quick-switch-pin]");
  const select = dropdown.querySelector("[data-quick-switch-select]");
  const submit = dropdown.querySelector("[data-quick-switch-submit]");
  dropdown.addEventListener("toggle", () => {
    if (!dropdown.open) return;
    window.requestAnimationFrame(() => (password || select || submit)?.focus());
  });
})();
