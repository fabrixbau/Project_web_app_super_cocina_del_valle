/* Menú diario: borrador en el navegador.
   Lo capturado (tiempos, agua, raciones y avisos) se guarda en localStorage mientras se escribe;
   al recargar o volver a la página se recupera con el aviso "Recuperamos lo que llevabas…".
   "Nuevo" y cada menú en edición tienen su propio borrador (clave = ruta de la página).
   Al pulsar "Guardar menú" o "Descartar borrador" se borra. Sólo existe en este navegador. */
(() => {
  const form = document.querySelector("[data-daily-menu-draft]");
  if (!form) return;
  const key = `sc-daily-menu-draft:${form.dataset.dailyMenuDraft}`;
  const note = document.querySelector("[data-daily-draft-note]");
  const fields = () => [...form.elements].filter((field) => field.name && field.name !== "csrfmiddlewaretoken" && field.type !== "submit" && field.type !== "button");
  const read = () => { try { return JSON.parse(localStorage.getItem(key) || "null"); } catch (_) { return null; } };
  const write = (data) => { try { localStorage.setItem(key, JSON.stringify(data)); } catch (_) { /* sin almacenamiento */ } };
  const forget = () => { try { localStorage.removeItem(key); } catch (_) { /* sin almacenamiento */ } };
  const valueOf = (field) => (field.type === "checkbox" || field.type === "radio") ? field.checked : field.value;
  const snapshot = () => Object.fromEntries(fields().map((field) => [`${field.name}|${field.type === "radio" ? field.value : ""}`, valueOf(field)]));

  // Si el servidor regresó errores (POST rechazado) se respeta lo que trae la página.
  const serverRejected = Boolean(form.querySelector(".errorlist"));
  const original = snapshot();
  const draft = serverRejected ? null : read();
  if (draft) {
    let changed = false;
    fields().forEach((field) => {
      const id = `${field.name}|${field.type === "radio" ? field.value : ""}`;
      if (!(id in draft) || draft[id] === valueOf(field)) return;
      if (field.type === "checkbox" || field.type === "radio") field.checked = draft[id];
      else field.value = draft[id];
      field.dispatchEvent(new Event("change", {bubbles: true}));  // custom-select se sincroniza
      changed = true;
    });
    if (changed && note) note.hidden = false;
    else forget();
  }

  let timer = null;
  const save = () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => {
      const current = snapshot();
      const differs = Object.keys(current).some((id) => current[id] !== original[id]);
      if (differs) write(current); else forget();
    }, 250);
  };
  form.addEventListener("input", save);
  form.addEventListener("change", save);
  form.addEventListener("submit", forget);
  note?.querySelector("[data-daily-draft-discard]")?.addEventListener("click", () => {
    forget();
    window.location.reload();
  });
})();
