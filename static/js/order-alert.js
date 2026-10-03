/* Alerta de pedidos web (Administrador y Telefonista).
   - Cada 15 s pregunta cuántos pedidos web siguen sin atender (notificación sin abrir).
   - Mientras haya alguno, el marco de toda la pantalla parpadea en amarillo (body.has-order-alert),
     el título de la pestaña dice "🔔 (N) Nuevo pedido" y el contador se actualiza sin recargar.
   - Suena un "ding" corto sólo cuando llega una notificación nueva (no en cada página). El
     navegador sólo permite el sonido después de que el usuario tocó la página una vez.
   - Deja de parpadear cuando abren cada aviso con "Atender y abrir" en Notificaciones. */
(() => {
  const script = document.currentScript;
  const url = script?.dataset.orderAlertUrl;
  if (!url) return;
  const POLL_MS = 15000;
  const STORAGE_KEY = "sc-last-order-notification";
  const baseTitle = document.title;
  const badge = document.querySelector("[data-notification-count]");
  const dot = document.querySelector("[data-notification-dot]");
  const status = document.querySelector("[data-order-alert-status]");
  let audio = null;

  const readLast = () => { try { return Number(localStorage.getItem(STORAGE_KEY)) || 0; } catch (_) { return 0; } };
  const writeLast = (value) => { try { localStorage.setItem(STORAGE_KEY, String(value)); } catch (_) { /* sin almacenamiento */ } };

  // El audio se habilita con el primer toque (regla de los navegadores).
  const unlock = () => {
    if (audio) return;
    const Context = window.AudioContext || window.webkitAudioContext;
    if (Context) audio = new Context();
  };
  ["pointerdown", "keydown"].forEach((type) => document.addEventListener(type, unlock, {once: true, capture: true}));

  const ding = () => {
    if (!audio) return;
    if (audio.state === "suspended") audio.resume();
    const now = audio.currentTime;
    [[880, 0], [1320, 0.16]].forEach(([frequency, delay]) => {
      const tone = audio.createOscillator();
      const volume = audio.createGain();
      tone.type = "sine";
      tone.frequency.value = frequency;
      volume.gain.setValueAtTime(0.0001, now + delay);
      volume.gain.exponentialRampToValueAtTime(0.35, now + delay + 0.02);
      volume.gain.exponentialRampToValueAtTime(0.0001, now + delay + 0.35);
      tone.connect(volume).connect(audio.destination);
      tone.start(now + delay);
      tone.stop(now + delay + 0.4);
    });
  };

  const render = (pending, total) => {
    document.body.classList.toggle("has-order-alert", pending > 0);
    document.title = pending > 0 ? `🔔 (${pending}) Nuevo pedido · ${baseTitle}` : baseTitle;
    if (badge) { badge.textContent = String(total); badge.hidden = total <= 0; }
    if (dot) dot.hidden = total <= 0;
    if (status) status.textContent = pending > 0 ? `${pending} pedido${pending === 1 ? "" : "s"} sin atender` : "";
  };

  const check = async () => {
    try {
      const response = await fetch(url, {headers: {Accept: "application/json"}, cache: "no-store", credentials: "same-origin"});
      if (!response.ok) return;
      const data = await response.json();
      const last = readLast();
      if (data.latest > last) {
        // La primera vez en este navegador sólo se guarda (no suena por avisos viejos).
        if (last && data.pending > 0) ding();
        writeLast(data.latest);
      }
      render(data.pending, data.total);
    } catch (_) { /* sin conexión: se reintenta en la siguiente vuelta */ }
  };

  render(Number(script.dataset.orderAlertPending) || 0, Number(badge?.textContent) || 0);
  check();
  window.setInterval(check, POLL_MS);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) check(); });
})();
