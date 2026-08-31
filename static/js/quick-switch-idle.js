/* NOTA TEMPORAL PARA APRENDIZAJE: Reiniciamos un reloj con cada interacción. A los tres minutos enviamos el formulario seguro de bloqueo; no cerramos la sesión para permitir el regreso con PIN. Borra esta nota. */
(() => {
  const form = document.querySelector("[data-quick-lock-form]");
  if (!form) return;
  const idleMilliseconds = 180000;
  let timeoutId;
  const lock = () => form.requestSubmit();
  const reset = () => { window.clearTimeout(timeoutId); timeoutId = window.setTimeout(lock, idleMilliseconds); };
  ["pointerdown", "keydown", "touchstart", "scroll"].forEach((eventName) => document.addEventListener(eventName, reset, { passive: true }));
  document.addEventListener("visibilitychange", () => { if (!document.hidden) reset(); });
  reset();
})();
