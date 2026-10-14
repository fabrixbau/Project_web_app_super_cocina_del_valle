/* Ticket de Mesas y Pedidos (ambos usan `.table-ticket`): el botón de flechas del
encabezado lo abre como panel a pantalla completa (letra más grande, un producto por
renglón y el total siempre visible); el mismo botón con las flechas hacia adentro, el
fondo oscuro o Esc lo regresan. Sólo se alterna una clase: no se mueven ni copian
partidas, así sus botones siguen funcionando. El botón sólo aparece cuando el ticket va a
la derecha del catálogo; si va debajo (celular, Mesas en 853×405) ya usa todo el ancho.
El aviso "ticket-expand-change" deja que el límite de renglones de abajo se recalcule. */
const TICKET_EXPAND_ICONS = {
  expand: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 4h6v6M20 4l-7 7M10 20H4v-6M4 20l7-7"/></svg>',
  collapse: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 4l-6 6M14 4v6h6M4 20l6-6M10 20v-6H4"/></svg>',
};
document.querySelectorAll(".table-ticket").forEach((ticket) => {
  const workspace = ticket.closest("[data-table-pos], [data-internal-capture]");
  if (!workspace) return;
  const heading = ticket.querySelector(".current-ticket-heading");
  if (!heading) return;
  ticket.classList.add("ticket-expandable");
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "ticket-expand-toggle";
  const backdrop = document.createElement("div");
  backdrop.className = "ticket-focus-backdrop";
  backdrop.hidden = true;
  document.body.append(backdrop);

  const render = (expanded) => {
    toggle.innerHTML = expanded ? TICKET_EXPAND_ICONS.collapse : TICKET_EXPAND_ICONS.expand;
    toggle.setAttribute("aria-expanded", String(expanded));
    toggle.title = expanded ? "Regresar el ticket a su tamaño normal" : "Ampliar ticket";
    toggle.setAttribute("aria-label", toggle.title);
  };
  const setExpanded = (expanded) => {
    ticket.classList.toggle("is-expanded", expanded);
    document.body.classList.toggle("ticket-focus-active", expanded);
    backdrop.hidden = !expanded;
    render(expanded);
    document.dispatchEvent(new CustomEvent("ticket-expand-change"));
  };
  const collapse = () => setExpanded(false);

  toggle.addEventListener("click", () => setExpanded(!ticket.classList.contains("is-expanded")));
  // El fondo está sobre el resto de la aplicación: este clic sólo cierra el panel y
  // nunca alcanza al producto, categoría o botón que quedó debajo.
  backdrop.addEventListener("click", collapse);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && ticket.classList.contains("is-expanded")) collapse();
  });
  // ¿El ticket va a la derecha del catálogo? Se mide con el panel cerrado y visible.
  const updateAvailability = () => {
    if (ticket.hidden || ticket.classList.contains("is-expanded")) return;
    const box = ticket.getBoundingClientRect();
    const area = workspace.getBoundingClientRect();
    if (!box.width) return;
    toggle.hidden = box.left < area.left + area.width * 0.3;
  };
  // Al cambiar el ancho (girar la tableta) se cierra el panel y se vuelve a medir; los
  // cambios sólo de alto (teclado en pantalla) no lo cierran.
  let lastWidth = window.innerWidth;
  window.addEventListener("resize", () => {
    if (window.innerWidth === lastWidth) return;
    lastWidth = window.innerWidth;
    if (ticket.classList.contains("is-expanded")) collapse();
    updateAvailability();
  });
  window.addEventListener("load", updateAvailability);
  new MutationObserver(updateAvailability).observe(ticket, {attributes: true, attributeFilter: ["hidden"]});
  render(false);
  heading.append(toggle);
  updateAvailability();
});

// Ticket normal en ordenador y TABA+9 (más de 900 px de ancho): el panel va fijo a la
// derecha y su lista se desplaza por dentro. Su alto se ajusta a lo que queda visible
// desde donde empieza, para que el total nunca quede debajo del borde de la pantalla.
(() => {
  const wide = window.matchMedia("(min-width: 901px)");
  const tickets = [...document.querySelectorAll(".table-ticket.ticket-expandable")];
  if (!tickets.length) return;
  const MARGIN = 8;
  const fit = (ticket) => {
    if (!wide.matches || ticket.hidden || ticket.classList.contains("is-expanded")
      || getComputedStyle(ticket).position !== "sticky") {
      ticket.style.removeProperty("max-height");
      return;
    }
    const stickyTop = parseFloat(getComputedStyle(ticket).top) || 0;
    const top = Math.max(ticket.getBoundingClientRect().top, stickyTop);
    // `important`: las reglas del ticket fijan max-height con !important.
    ticket.style.setProperty("max-height", `${Math.floor(window.innerHeight - top - MARGIN)}px`, "important");
  };
  let frame = 0;
  const refresh = () => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => tickets.forEach(fit));
  };
  window.addEventListener("scroll", refresh, {passive: true});
  window.addEventListener("resize", refresh);
  window.addEventListener("load", refresh);
  document.addEventListener("ticket-expand-change", refresh);
  wide.addEventListener?.("change", refresh);
  // El ticket aparece (deja de estar oculto) al agregar el primer producto.
  tickets.forEach((ticket) => new MutationObserver(refresh).observe(ticket, {attributes: true, attributeFilter: ["hidden"]}));
  refresh();
})();

// Tableta horizontal 853×405 (Mesas, donde el ticket va debajo del catálogo): la lista
// del ticket crece conforme se agregan productos hasta mostrar 6 renglones; desde el 7.º
// se desplaza por dentro. En Pedidos el ticket va a la derecha con su propio scroll.
// La altura se mide sobre el 6.º renglón real porque cada partida puede ocupar más
// de una línea (descripción, modificaciones).
(() => {
  const VISIBLE_ROWS = 6;
  const compactTablet = window.matchMedia(
    "(min-width: 780px) and (max-width: 900px) and (max-height: 500px) and (orientation: landscape)",
  );
  const lists = [...document.querySelectorAll("[data-table-pos] .table-ticket-items")];
  if (!lists.length) return;

  const limitRows = (list) => {
    const rows = list.querySelectorAll(":scope > article");
    if (!compactTablet.matches || rows.length <= VISIBLE_ROWS || list.closest(".is-expanded")) {
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
  document.addEventListener("ticket-expand-change", refresh);
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
  const expandToggle = heading.querySelector(".ticket-expand-toggle");
  if (expandToggle) expandToggle.before(total); else heading.append(total);
  const sync = () => { total.textContent = source.textContent.trim(); };
  new MutationObserver(sync).observe(source, {childList: true, characterData: true, subtree: true});
  sync();
});

