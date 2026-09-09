/* NOTA TEMPORAL PARA APRENDIZAJE:
El mismo comportamiento sirve para Mesas y Telefonistas porque ambos tickets usan
`.table-ticket`. Sólo alternamos una clase en su cuadrícula; no movemos ni copiamos
partidas, por lo que sus botones siguen funcionando. Borra esta nota después de leerla. */
document.querySelectorAll(".table-ticket").forEach((ticket) => {
  const workspace = ticket.closest("[data-table-pos], [data-internal-capture], [data-public-workspace]");
  if (!workspace) return;
  ticket.classList.add("ticket-expandable");
  ticket.title = "Haz clic en el fondo para ampliar o reducir el ticket";
  const backdrop = document.createElement("div");
  backdrop.className = "ticket-focus-backdrop";
  backdrop.hidden = true;
  document.body.append(backdrop);

  const collapse = () => {
    workspace.classList.remove("ticket-expanded");
    ticket.classList.remove("is-expanded");
    backdrop.hidden = true;
    document.body.classList.remove("ticket-focus-active");
    ticket.title = "Haz clic en el fondo para ampliar el ticket";
  };

  const expand = () => {
    workspace.classList.add("ticket-expanded");
    ticket.classList.add("is-expanded");
    backdrop.hidden = false;
    document.body.classList.add("ticket-focus-active");
    ticket.title = "Haz clic en el fondo para regresar al tamaño normal";
  };

  ticket.addEventListener("click", (event) => {
    if (event.target.closest("button, a, input, textarea, select, label, form, summary, details")) return;
    if (workspace.classList.contains("ticket-expanded")) collapse();
    else expand();
  });

  // El fondo está sobre el resto de la aplicación: este clic sólo cierra el enfoque
  // y nunca alcanza al producto, categoría o botón que quedó debajo.
  backdrop.addEventListener("click", collapse);

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !workspace.classList.contains("ticket-expanded")) return;
    collapse();
  });
});
