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

// Tableta horizontal 853×405 (Mesas y Pedidos): la lista del ticket crece conforme se
// agregan productos hasta mostrar 6 renglones; desde el 7.º se desplaza por dentro.
// La altura se mide sobre el 6.º renglón real porque cada partida puede ocupar más
// de una línea (descripción, modificaciones).
(() => {
  const VISIBLE_ROWS = 6;
  const compactTablet = window.matchMedia(
    "(min-width: 780px) and (max-width: 900px) and (max-height: 500px) and (orientation: landscape)",
  );
  const lists = [...document.querySelectorAll(
    "[data-table-pos] .table-ticket-items, [data-internal-capture] .table-ticket-items",
  )];
  if (!lists.length) return;

  const limitRows = (list) => {
    const rows = list.querySelectorAll(":scope > article");
    if (!compactTablet.matches || rows.length <= VISIBLE_ROWS) {
      list.classList.remove("is-row-limited");
      list.style.removeProperty("max-height");
      return;
    }
    const sixth = rows[VISIBLE_ROWS - 1].getBoundingClientRect();
    if (!sixth.height) return; // Ticket oculto: se mide cuando vuelva a mostrarse.
    const top = list.getBoundingClientRect().top;
    const paddingBottom = parseFloat(getComputedStyle(list).paddingBottom) || 0;
    // `important`: otras reglas del ticket fijan max-height con !important.
    list.style.setProperty("max-height", `${Math.ceil(sixth.bottom - top + list.scrollTop + paddingBottom)}px`, "important");
    list.classList.add("is-row-limited");
  };
  const refresh = () => lists.forEach(limitRows);

  lists.forEach((list) => {
    new MutationObserver(() => limitRows(list)).observe(list, {childList: true, subtree: true});
  });
  compactTablet.addEventListener?.("change", refresh);
  window.addEventListener("resize", refresh);
  // Al abrir la página los renglones aún cambian de alto (fuentes, botones de impresión);
  // se vuelve a medir cuando termina de cargar y cada vez que el ticket cambia de tamaño.
  window.addEventListener("load", refresh);
  document.fonts?.ready.then(refresh);
  if (window.ResizeObserver) {
    const observer = new ResizeObserver(() => refresh());
    lists.forEach((list) => observer.observe(list.closest(".table-ticket") || list));
  }
  refresh();
})();

// Todos los tickets (Mesas, Pedidos y menú público) repiten el total en su encabezado,
// junto a "N artículos". Es un reflejo del total de abajo: cada pantalla sigue
// actualizando sólo ese total y aquí se copia su texto en cuanto cambia.
document.querySelectorAll(".table-ticket").forEach((ticket) => {
  const heading = ticket.querySelector(".current-ticket-heading");
  const source = ticket.querySelector(".table-ticket-total strong");
  if (!heading || !source || heading.querySelector(".ticket-heading-total")) return;
  const total = document.createElement("strong");
  total.className = "ticket-heading-total";
  total.title = "Total del ticket";
  heading.append(total);
  const sync = () => { total.textContent = source.textContent.trim(); };
  new MutationObserver(sync).observe(source, {childList: true, characterData: true, subtree: true});
  sync();
});

