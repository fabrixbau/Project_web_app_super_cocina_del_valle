/* NOTA TEMPORAL PARA APRENDIZAJE: Al desplegar el cambio de mesero colocamos el foco en el PIN; inputmode numeric solicita el teclado numérico de la tablet. Borra esta nota. */
(() => {
  const dropdown = document.querySelector("[data-quick-switch-dropdown]");
  const pin = dropdown?.querySelector("[data-quick-switch-pin]");
  if (!dropdown || !pin) return;
  dropdown.addEventListener("toggle", () => {
    if (dropdown.open) window.requestAnimationFrame(() => pin.focus());
  });
})();
