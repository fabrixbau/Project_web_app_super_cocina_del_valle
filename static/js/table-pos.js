/* NOTA TEMPORAL PARA APRENDIZAJE:
Los botones −, + y × ya no dependen de formularios pequeños: envían directamente su URL
y acción a Django mediante AJAX. La respuesta vuelve a dibujar cantidades y total sin
recargar la página. En desayuno, una categoría configurada puede revelar los paquetes.
El pollo pausa solamente ese clic para preguntar Pierna o Muslo y después continúa por AJAX.
El ticket recibido puede incluir `is_customized`; entonces dibuja la etiqueta Modificado y
las diferencias ya calculadas por Django. Borra esta nota después de comprobarlo.
Borra esta nota después de comprobar el comportamiento. */

const pos = document.querySelector("[data-table-pos]");
const categoryButtons = document.querySelectorAll("[data-category-target]");
const categorySections = document.querySelectorAll(".table-category");
const ticketPanel = document.querySelector("[data-ticket-panel]");
const ticketItems = document.querySelector("[data-ticket-items]");
const ticketCount = document.querySelector("[data-ticket-count]");
const ticketTotal = document.querySelector("[data-ticket-total]");
const csrfToken = document.querySelector("input[name='csrfmiddlewaretoken']")?.value;
const packageLauncher = document.querySelector("[data-package-launcher]");
const chickenChoiceDialog = document.querySelector("[data-chicken-choice-dialog]");
const standardQuantitiesNode = document.querySelector("#table-standard-quantities");
const candidateQuantitiesNode = document.querySelector("#table-candidate-quantities");
// NOTA TEMPORAL PARA APRENDIZAJE: Dividir cuenta (table-split.js) necesita la lista de
// artículos del ticket tal cual está AHORA, no la que se dibujó cuando cargó la página —
// aquí se agregan/quitan productos por AJAX sin recargar. Se expone en window para que
// ese otro archivo, cargado aparte, siempre pueda leer el estado más reciente. Se
// inicializa con lo que ya trae la página y se actualiza cada vez que renderTicket
// vuelve a dibujar el ticket. Borra esta nota después de leerla.
const ticketItemsDataNode = document.querySelector("#table-ticket-items-data");
window.__tableTicketItems = ticketItemsDataNode ? JSON.parse(ticketItemsDataNode.textContent) : [];
const catalogSearch = document.querySelector("[data-catalog-search]");
const catalogSearchResults = document.querySelector("[data-catalog-search-results]");
const catalogSearchEmpty = document.querySelector("[data-catalog-search-empty]");
const breakfastNavigation = document.querySelector(".table-breakfast-command");
const customerAutosaveForm = document.querySelector("[data-table-customer-autosave]");
const categoryCarousel = document.querySelector("[data-category-carousel]");

catalogSearch?.addEventListener("focus", () => breakfastNavigation?.classList.add("search-focused"));
catalogSearch?.addEventListener("blur", () => {
  if (!catalogSearch.value.trim()) breakfastNavigation?.classList.remove("search-focused");
});
let pendingChickenForm = null;
const currency = new Intl.NumberFormat("es-MX", {
  style: "currency", currency: "MXN", currencyDisplay: "narrowSymbol",
});

document.querySelectorAll(".table-visual-package-dialog").forEach((dialog) => {
  const form = dialog.querySelector("[data-package-add]");
  const launcher = dialog.querySelector("[data-package-candidate-search-open]");
  const searchPanel = dialog.querySelector("[data-package-candidate-search]");
  const searchInput = dialog.querySelector("[data-package-candidate-search-input]");
  const results = dialog.querySelector("[data-package-candidate-search-results]");
  const empty = dialog.querySelector("[data-package-candidate-search-empty]");
  const candidates = [...dialog.querySelectorAll("[data-package-choice]")];

  const closeCandidateSearch = () => {
    if (!searchPanel) return;
    searchPanel.hidden = true;
    dialog.classList.remove("is-candidate-search-open");
    searchInput?.blur();
  };

  const renderCandidateSearch = () => {
    if (!results || !searchInput) return;
    const query = searchInput.value.trim().toLocaleLowerCase("es-MX");
    const matches = candidates.filter((card) => !query || card.dataset.searchName.includes(query));
    results.replaceChildren(...matches.map((card) => {
      const input = card.querySelector("input[type='radio']");
      const course = card.closest("[data-package-choice-group]")?.querySelector("h3")?.textContent.trim() || "Producto";
      const button = document.createElement("button");
      button.type = "button";
      const name = document.createElement("strong");
      const detail = document.createElement("small");
      name.textContent = card.querySelector("strong")?.textContent || "Producto";
      detail.textContent = course;
      button.append(name, detail);
      button.addEventListener("click", () => {
        input.checked = true;
        input.dispatchEvent(new Event("change", { bubbles: true }));
        card.scrollIntoView({ behavior: "smooth", block: "center" });
        closeCandidateSearch();
      });
      return button;
    }));
    empty.hidden = matches.length > 0;
  };

  launcher?.addEventListener("click", () => {
    searchPanel.hidden = false;
    dialog.classList.add("is-candidate-search-open");
    searchInput.value = "";
    renderCandidateSearch();
    searchInput.focus({ preventScroll: true });
  });
  searchInput?.addEventListener("input", renderCandidateSearch);
  searchInput?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    results.querySelector("button")?.click();
    if (!results.querySelector("button")) closeCandidateSearch();
  });
  searchPanel?.addEventListener("click", (event) => {
    if (event.target === searchPanel) closeCandidateSearch();
  });

  const comment = form?.querySelector("textarea[name$='customization_comment']");
  if (comment) comment.placeholder = "Escribir nota";
  comment?.addEventListener("focus", () => {
    if (!window.matchMedia("(max-width: 900px)").matches) return;
    form.classList.add("is-package-comment-focused");
    window.requestAnimationFrame(() => comment.scrollIntoView({ block: "center" }));
  });
  comment?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    comment.blur();
  });
  comment?.addEventListener("blur", () => form.classList.remove("is-package-comment-focused"));
  form?.addEventListener("pointerdown", (event) => {
    if (!form.classList.contains("is-package-comment-focused") || event.target === comment) return;
    event.preventDefault();
    comment.blur();
  });
});

if (customerAutosaveForm) {
  const input = customerAutosaveForm.querySelector("input[name='customer_name']");
  const state = customerAutosaveForm.querySelector("[data-table-customer-save-state]");
  const heading = document.querySelector("[data-table-customer-heading]");
  let savedValue = input.value.trim();
  let saveTimer = null;
  let statusTimer = null;
  let requestSequence = 0;

  const showSaveState = (message, className, hideAfter = 0) => {
    window.clearTimeout(statusTimer);
    state.hidden = false;
    state.textContent = message;
    state.className = className;
    if (hideAfter) statusTimer = window.setTimeout(() => { state.hidden = true; }, hideAfter);
  };

  const saveCustomerName = async () => {
    const currentValue = input.value.trim();
    if (currentValue === savedValue) return;
    const sequence = ++requestSequence;
    showSaveState("Guardando…", "is-saving");
    try {
      const response = await fetch(customerAutosaveForm.action, {
        method: "POST",
        body: new FormData(customerAutosaveForm),
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || "No se pudo guardar el nombre.");
      if (sequence !== requestSequence) return;
      savedValue = data.customer_name;
      input.value = data.customer_name;
      heading.textContent = data.customer_name ? ` · ${data.customer_name}` : "";
      showSaveState("Guardado", "is-saved", 1200);
    } catch (error) {
      if (sequence !== requestSequence) return;
      showSaveState(error.message, "is-error");
    }
  };

  input.addEventListener("input", () => {
    window.clearTimeout(saveTimer);
    requestSequence += 1;
    showSaveState("Pendiente de guardar", "is-pending");
    saveTimer = window.setTimeout(saveCustomerName, 650);
  });
  input.addEventListener("blur", () => {
    window.clearTimeout(saveTimer);
    saveCustomerName();
  });
  customerAutosaveForm.addEventListener("submit", (event) => {
    event.preventDefault();
    window.clearTimeout(saveTimer);
    saveCustomerName();
  });
}

function selectCategory(button) {
    categoryButtons.forEach((candidate) => candidate.classList.remove("is-selected"));
    categorySections.forEach((section) => { section.hidden = true; });
    button.classList.add("is-selected");
    document.querySelector(`#${button.dataset.categoryTarget}`).hidden = false;
    if (packageLauncher && pos.dataset.captureMode === "breakfast") {
      packageLauncher.hidden = button.dataset.showPackages !== "true";
    }
}

categoryButtons.forEach((button) => {
  button.addEventListener("click", () => {
    if (catalogSearch) catalogSearch.value = "";
    if (catalogSearchResults) catalogSearchResults.hidden = true;
    selectCategory(button);
  });
});
const initiallySelectedCategory = document.querySelector("[data-category-target].is-selected");
if (initiallySelectedCategory) selectCategory(initiallySelectedCategory);

if (categoryCarousel) {
  const viewport = categoryCarousel.querySelector("[data-category-carousel-viewport]");
  const track = categoryCarousel.querySelector(".category-buttons");
  const previous = categoryCarousel.querySelector("[data-category-carousel-prev]");
  const next = categoryCarousel.querySelector("[data-category-carousel-next]");
  const dots = categoryCarousel.querySelector("[data-category-carousel-dots]");
  let pageOffsets = [0];
  let currentPage = 0;
  let dragStartX = 0;
  let dragStartScroll = 0;
  let isDragging = false;
  let didDrag = false;
  let settleTimer = null;

  const revealCarouselItems = () => {
    categoryButtons.forEach((button) => button.classList.remove("is-partial-carousel-item"));
  };

  const hidePartialCarouselItems = () => {
    const viewportBounds = viewport.getBoundingClientRect();
    categoryButtons.forEach((button) => {
      const bounds = button.getBoundingClientRect();
      const intersects = bounds.right > viewportBounds.left && bounds.left < viewportBounds.right;
      const fullyVisible = bounds.left >= viewportBounds.left - 1 && bounds.right <= viewportBounds.right + 1;
      button.classList.toggle("is-partial-carousel-item", intersects && !fullyVisible);
    });
  };

  const renderCarousel = () => {
    currentPage = Math.max(0, Math.min(currentPage, pageOffsets.length - 1));
    dots.replaceChildren(...pageOffsets.map((offset, index) => {
      const dot = document.createElement("button");
      dot.type = "button";
      dot.className = index === currentPage ? "is-current" : "";
      dot.setAttribute("aria-label", `Ir a la página ${index + 1} de categorías`);
      dot.setAttribute("aria-current", index === currentPage ? "true" : "false");
      dot.addEventListener("click", () => goToPage(index));
      return dot;
    }));
    previous.disabled = currentPage === 0;
    next.disabled = currentPage === pageOffsets.length - 1;
    categoryCarousel.classList.toggle("has-multiple-pages", pageOffsets.length > 1);
  };

  const goToPage = (page, behavior = "smooth") => {
    currentPage = Math.max(0, Math.min(page, pageOffsets.length - 1));
    window.clearTimeout(settleTimer);
    revealCarouselItems();
    viewport.scrollTo({ left: pageOffsets[currentPage], behavior });
    renderCarousel();
    settleTimer = window.setTimeout(hidePartialCarouselItems, behavior === "smooth" ? 260 : 0);
  };

  const measureCarousel = () => {
    const buttons = [...track.querySelectorAll("[data-category-target]")];
    buttons.forEach((button) => { button.style.marginRight = ""; });
    pageOffsets = [0];
    if (buttons.length && viewport.clientWidth) {
      let pageStart = buttons[0].offsetLeft;
      buttons.forEach((button) => {
        const buttonEnd = button.offsetLeft + button.offsetWidth;
        if (button.offsetLeft > pageStart && buttonEnd - pageStart > viewport.clientWidth) {
          pageOffsets.push(button.offsetLeft);
          pageStart = button.offsetLeft;
        }
      });
    }
    goToPage(Math.min(currentPage, pageOffsets.length - 1), "auto");
  };

  const finishDrag = (event) => {
    if (!isDragging) return;
    isDragging = false;
    categoryCarousel.classList.remove("is-dragging");
    if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
    if (!didDrag) return;
    const closestPage = pageOffsets.reduce((best, offset, index) => (
      Math.abs(offset - viewport.scrollLeft) < Math.abs(pageOffsets[best] - viewport.scrollLeft) ? index : best
    ), 0);
    goToPage(closestPage);
    window.setTimeout(() => { didDrag = false; }, 0);
  };

  previous.addEventListener("click", () => goToPage(currentPage - 1));
  next.addEventListener("click", () => goToPage(currentPage + 1));
  viewport.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    isDragging = true;
    didDrag = false;
    dragStartX = event.clientX;
    dragStartScroll = viewport.scrollLeft;
    window.clearTimeout(settleTimer);
    revealCarouselItems();
  });
  viewport.addEventListener("pointermove", (event) => {
    if (!isDragging) return;
    const distance = event.clientX - dragStartX;
    if (Math.abs(distance) > 5 && !didDrag) {
      didDrag = true;
      categoryCarousel.classList.add("is-dragging");
      viewport.setPointerCapture(event.pointerId);
    }
    if (!didDrag) return;
    viewport.scrollLeft = dragStartScroll - distance;
  });
  viewport.addEventListener("pointerup", finishDrag);
  viewport.addEventListener("pointercancel", finishDrag);
  viewport.addEventListener("pointerleave", (event) => {
    if (isDragging && !didDrag) finishDrag(event);
  });
  categoryCarousel.addEventListener("click", (event) => {
    if (!didDrag) return;
    event.preventDefault();
    event.stopPropagation();
    didDrag = false;
  }, true);
  new ResizeObserver(measureCarousel).observe(viewport);
  window.addEventListener("load", measureCarousel, { once: true });
  window.requestAnimationFrame(measureCarousel);
}

function normalizedSearchText(value) {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("es-MX").trim();
}

catalogSearch?.addEventListener("input", () => {
  const query = normalizedSearchText(catalogSearch.value);
  if (!query) {
    catalogSearchResults.hidden = true;
    catalogSearchResults.querySelectorAll("[data-catalog-product]").forEach((card) => { card.hidden = false; });
    const selectedCategory = document.querySelector("[data-category-target].is-selected") || initiallySelectedCategory;
    if (selectedCategory) selectCategory(selectedCategory);
    return;
  }
  categorySections.forEach((section) => { section.hidden = true; });
  if (packageLauncher) packageLauncher.hidden = true;
  catalogSearchResults.hidden = false;
  const resultGrid = catalogSearchResults.querySelector(".table-product-grid");
  const rankedCards = [...catalogSearchResults.querySelectorAll("[data-catalog-product]")].map((card) => {
    const productName = normalizedSearchText(card.dataset.productName || "");
    let relevance = 99;
    if (productName.startsWith(query)) relevance = 0;
    else if (productName.split(/\s+/).some((word) => word.startsWith(query))) relevance = 1;
    else if (productName.includes(query)) relevance = 2;
    return {card, productName, relevance};
  }).sort((first, second) => first.relevance - second.relevance || first.productName.localeCompare(second.productName, "es-MX"));
  let matches = 0;
  rankedCards.forEach(({card, relevance}) => {
    card.hidden = relevance === 99;
    if (relevance !== 99) matches += 1;
    resultGrid.append(card);
  });
  catalogSearchEmpty.hidden = matches > 0;
});

// Lupa con sugerencias (live-search.js): al elegir un producto sólo queda su tarjeta.
document.addEventListener("live-search:select", (event) => {
  if (!event.target.matches?.("[data-catalog-search]") || !catalogSearchResults) return;
  const chosen = normalizedSearchText(event.detail.item.label);
  catalogSearchResults.querySelectorAll("[data-catalog-product]").forEach((card) => {
    card.hidden = normalizedSearchText(card.dataset.productName || "") !== chosen;
  });
  catalogSearchEmpty.hidden = true;
});

function ticketButton(item, action, label, className = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.className = className;
  button.dataset.ticketAction = action;
  button.dataset.ticketUrl = item.change_url;
  button.setAttribute("aria-label", action === "increase" ? "Sumar uno" : action === "decrease" ? "Restar uno" : "Eliminar producto");
  return button;
}

function packageEditButton(item) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "ticket-package-edit";
  button.dataset.packageEditOpen = "";
  button.dataset.packageId = item.package_id;
  button.dataset.editUrl = item.edit_url;
  button.dataset.firstCourse = item.first_course_id || "";
  button.dataset.secondCourse = item.second_course_id || "";
  button.dataset.mainCourse = item.main_course_id || "";
  button.dataset.chickenPiece = item.chicken_piece || "";
  button.dataset.withWater = item.with_water ? "true" : "false";
  button.dataset.bread = item.bread ? "true" : "false";
  button.dataset.refillExtra = item.refill_extra ? "true" : "false";
  const name = document.createElement("strong");
  name.textContent = item.name;
  button.append(name);
  if (!item.is_complete) {
    const badge = document.createElement("span");
    badge.className = "incomplete-badge";
    badge.textContent = "Pendiente";
    button.append(badge);
  }
  return button;
}

function renderTicket(ticket) {
  renderStockWarnings(ticket.stock_warnings || []);
  window.__tableTicketItems = ticket.items;
  ticketItems.replaceChildren();
  const split = ticket.split || {enabled: false, slots: [], paid: []};
  if (split.enabled) renderSplitSections(ticket.items, split);
  else ticket.items.forEach((item) => ticketItems.append(buildTicketRow(item, null)));
  renderSplitControls(split);
  ticketCount.textContent = ticket.count;
  ticketTotal.textContent = currency.format(Number(ticket.total_display));
  const closeForm = document.querySelector("[data-close-account-form]");
  if (closeForm) { closeForm.dataset.accountSubtotal = ticket.total_display; closeForm.dataset.ticketTotal = ticket.total_display; }
  const hasItems = ticket.items.length > 0;
  ticketPanel.hidden = !hasItems;
  pos.classList.toggle("has-ticket", hasItems);
  renderStandardQuantities(ticket.standard_quantities || {});
  renderCandidateQuantities(ticket.candidate_quantities || {}, ticket.meal_quantities || {});
}

// ---------------------------------------------------------------- cuentas separadas
// Con "Separar cuentas" el ticket se agrupa en Cuenta 1, 2… (y "Sin asignar"). Tocar la
// cabecera de una cuenta la vuelve activa: lo que se agregue cae ahí. "⇄" mueve una pieza
// a otra cuenta; "Pre-cuenta" imprime sólo esa cuenta y "Cobrar" la cobra por separado.
const splitBar = document.querySelector("[data-split-bar]");

function splitButton(label, data, className = "") {
  const button = document.createElement("button");
  button.type = "button";
  if (className) button.className = className;
  button.textContent = label;
  Object.entries(data).forEach(([key, value]) => { button.dataset[key] = value; });
  return button;
}

function renderSplitSections(items, split) {
  const bySlot = new Map();
  items.forEach((item) => {
    const slot = item.split_slot || 0;
    if (!bySlot.has(slot)) bySlot.set(slot, []);
    bySlot.get(slot).push(item);
  });
  split.slots.forEach((slot) => {
    const section = document.createElement("section");
    section.className = `ticket-split-section${split.active === slot.number ? " is-active" : ""}`;
    const header = document.createElement("header");
    const select = splitButton("", {splitAction: "select", slot: slot.number}, "ticket-split-select");
    const title = document.createElement("strong");
    title.textContent = slot.label;
    const total = document.createElement("span");
    total.textContent = currency.format(Number(slot.total_display));
    select.append(title, total);
    if (split.active === slot.number) {
      const badge = document.createElement("small");
      badge.textContent = "Agregando aquí";
      select.append(badge);
    }
    const actions = document.createElement("div");
    actions.className = "ticket-split-actions";
    const print = document.createElement("a");
    print.href = splitBar.dataset.paymentPrintUrl + `?cuenta=${slot.number}`;
    print.dataset.directPrint = "";
    print.dataset.splitSlot = slot.number;
    print.textContent = "Pre-cuenta";
    if (!slot.count) print.setAttribute("aria-disabled", "true");
    const pay = splitButton("Cobrar", {splitPay: slot.number, payUrl: slot.pay_url, payTotal: slot.total_display}, "ticket-split-pay");
    pay.disabled = !slot.count;
    actions.append(print, pay);
    if (slot.removable) actions.append(splitButton("×", {splitAction: "remove", slot: slot.number}, "danger ticket-split-remove"));
    header.append(select, actions);
    section.append(header);
    const rows = bySlot.get(slot.number) || [];
    if (rows.length) rows.forEach((item) => section.append(buildTicketRow(item, split)));
    else {
      const empty = document.createElement("p");
      empty.className = "ticket-split-empty";
      empty.textContent = "Sin productos. Toca la cuenta y agrega desde el menú, o usa ⇄ en otra cuenta.";
      section.append(empty);
    }
    ticketItems.append(section);
  });
  const unassigned = bySlot.get(0) || [];
  if (unassigned.length) {
    const section = document.createElement("section");
    section.className = "ticket-split-section is-unassigned";
    const header = document.createElement("header");
    const title = document.createElement("strong");
    title.textContent = `Sin asignar · ${currency.format(Number(split.unassigned_total_display))}`;
    header.append(title);
    section.append(header);
    unassigned.forEach((item) => section.append(buildTicketRow(item, split)));
    ticketItems.append(section);
  }
  ticketItems.append(splitButton("+ Agregar cuenta", {splitAction: "add"}, "ticket-split-add"));
}

function renderSplitControls(split) {
  if (!splitBar) return;
  splitBar.querySelectorAll("[data-split-action^='mode_']").forEach((button) => {
    button.setAttribute("aria-pressed", String((button.dataset.splitAction === "mode_on") === Boolean(split.enabled)));
  });
  ticketPanel.classList.toggle("is-split", Boolean(split.enabled));
  const closeLauncher = document.querySelector("[data-close-account-open]");
  if (closeLauncher) closeLauncher.hidden = Boolean(split.enabled);
  const paid = document.querySelector("[data-split-paid]");
  if (paid) {
    paid.replaceChildren();
    (split.paid || []).forEach((entry) => {
      const link = document.createElement("a");
      link.href = entry.url;
      link.textContent = `✓ ${entry.label} cobrada · ${currency.format(Number(entry.total_display))} · ${entry.method}`;
      paid.append(link);
    });
    paid.hidden = !(split.paid || []).length;
  }
}

function buildTicketRow(item, split) {
    const row = document.createElement("article");
    row.className = "table-ticket-item";
    const information = document.createElement("div");
    if (item.is_package) {
      information.append(packageEditButton(item));
    } else {
      const name = document.createElement("strong");
      name.textContent = item.name;
      if (item.is_customized) {
        const badge = document.createElement("span");
        badge.className = "customized-warning";
        badge.textContent = "Modificado";
        name.append(" ", badge);
      }
      information.append(name);
    }
    if (item.description) {
      const description = document.createElement("small");
      description.textContent = item.description;
      information.append(description);
    }
    // Cómo quedó modificado: ingredientes del producto o cada tiempo del paquete.
    (item.modifications || []).forEach((text) => {
      const modification = document.createElement("small");
      modification.className = "ticket-item-modification";
      modification.textContent = text;
      information.append(modification);
    });
    const subtotal = document.createElement("strong");
    subtotal.textContent = currency.format(Number(item.subtotal_display));
    const controls = document.createElement("div");
    controls.className = "quantity-buttons";
    const quantity = document.createElement("span");
    quantity.textContent = item.quantity;
    controls.append(
      ticketButton(item, "decrease", "−"), quantity,
      ticketButton(item, "increase", "+"),
      ticketButton(item, "remove", "×", "danger"),
    );
    let moveMenu = null;
    if (split?.enabled) {
      controls.prepend(splitButton("⇄", {splitMoveOpen: ""}, "ticket-split-move-open"));
      const menu = document.createElement("div");
      menu.className = "ticket-split-move-menu";
      menu.hidden = true;
      split.slots.filter((slot) => slot.number !== item.split_slot).forEach((slot) => {
        menu.append(splitButton(`→ ${slot.label}`, {splitMove: item.item_id, slot: slot.number}));
      });
      if (item.split_slot) menu.append(splitButton("→ Sin asignar", {splitMove: item.item_id, slot: 0}));
      moveMenu = menu;
    }
    row.append(information, subtotal, controls);
    // El menú "mover a…" se abre dentro del renglón (no flota sobre el catálogo).
    if (moveMenu) row.append(moveMenu);
    return row;
}

function renderStockWarnings(warnings) {
  let panel = ticketPanel.querySelector("[data-stock-warnings]");
  if (!panel) {
    panel = document.createElement("aside");
    panel.dataset.stockWarnings = "";
    panel.className = "ticket-stock-warnings";
    ticketItems.before(panel);
  }
  panel.replaceChildren(...warnings.map((warning) => {
    const message = document.createElement("strong");
    message.textContent = `⚠ ${warning.message}`;
    return message;
  }));
  panel.hidden = warnings.length === 0;
}

function renderStandardQuantities(quantities) {
  document.querySelectorAll("[data-catalog-product]:not([data-auto-meal-card])").forEach((card) => {
    const quantity = quantities[String(card.dataset.catalogProduct)] || 0;
    card.querySelector("[data-standard-quantity]").textContent = quantity;
    card.querySelector("[data-catalog-decrease]").disabled = quantity === 0;
  });
}

// El número cuenta todas las piezas del producto (sueltas y ya dentro de un paquete);
// "−" sólo quita piezas sueltas, así que se desactiva cuando todas están en paquete.
function renderCandidateQuantities(quantities, mealQuantities = quantities) {
  document.querySelectorAll("[data-auto-meal-card]").forEach((card) => {
    const productKey = String(card.dataset.catalogProduct);
    const loose = quantities[productKey] || 0;
    const total = mealQuantities[productKey] || 0;
    card.querySelector("[data-standard-quantity]").textContent = total;
    const decrease = card.querySelector("[data-catalog-decrease]");
    decrease.disabled = loose === 0;
    decrease.title = loose === 0 && total > 0 ? "Ya forma parte de un paquete; quítalo desde el ticket" : "";
  });
}

function showError(message) {
  document.querySelector("[data-pos-error]")?.remove();
  const error = document.createElement("p");
  error.className = "message error";
  error.dataset.posError = "";
  error.textContent = message;
  pos.before(error);
}

let requestQueue = Promise.resolve();

function enqueueRequest({url, body, source, onSuccess}) {
  requestQueue = requestQueue.then(async () => {
    try {
      const response = await fetch(url, {
        method: "POST", body,
        headers: {"X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrfToken},
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || "No fue posible actualizar el ticket.");
      renderTicket(data.ticket);
      onSuccess?.(data);
    } catch (error) {
      if (source?.matches("[data-package-add]")) {
        const container = source.querySelector("[data-package-error]");
        container.className = "message error";
        container.textContent = error.message;
      } else {
        showError(error.message);
      }
    } finally {
      if (source?.matches("[data-ticket-action]") && source.isConnected) source.disabled = false;
      if (source?.matches("[data-catalog-decrease]") && source.isConnected) {
        const displayedQuantity = source.closest("[data-catalog-product]").querySelector("[data-standard-quantity]").textContent;
        source.disabled = Number(displayedQuantity) === 0;
      }
      if (source?.matches("[data-chicken-choice]")) {
        source.querySelector("input[name='chicken_piece']").value = "";
      }
      if (source?.matches("[data-product-add]")) {
        source.querySelectorAll("input[data-generated-option]").forEach((input) => input.remove());
        delete source.dataset.selectionReady;
      }
    }
  });
}

document.querySelector("[data-chicken-choice-close]")?.addEventListener("click", () => {
  pendingChickenForm = null;
  chickenChoiceDialog.close();
});
document.querySelectorAll("[data-chicken-piece]").forEach((button) => {
  button.addEventListener("click", () => {
    if (!pendingChickenForm) return;
    pendingChickenForm.querySelector("input[name='chicken_piece']").value = button.dataset.chickenPiece;
    const form = pendingChickenForm;
    pendingChickenForm = null;
    chickenChoiceDialog.close();
    form.requestSubmit();
  });
});

document.querySelectorAll("[data-package-open]").forEach((button) => {
  button.addEventListener("click", () => {
    const dialog = document.querySelector(`#${button.dataset.packageOpen}`);
    const form = dialog.querySelector("[data-package-add]");
    form.reset();
    // NOTA TEMPORAL PARA APRENDIZAJE: form.reset() sí limpia los radios, pero no
    // dispara "change" — y los contadores (+/-) y el resaltado de cada tarjeta sólo
    // se actualizan escuchando ese evento (package-selection.js). Sin este disparo
    // manual, la comida anterior se queda marcada visualmente aunque el formulario
    // ya esté limpio. Borra esta nota después de leerla.
    form.querySelectorAll("input[type='radio']").forEach((input) => {
      input.dispatchEvent(new Event("change", {bubbles: true}));
    });
    form.action = form.dataset.addUrl;
    form.querySelector("[data-package-submit]").textContent = "Agregar al ticket";
    dialog.showModal();
    window.requestAnimationFrame(() => {
      form.scrollTop = 0;
      dialog.scrollTop = 0;
    });
  });
});
document.querySelectorAll("[data-package-close]").forEach((button) => {
  button.addEventListener("click", () => button.closest("dialog").close());
});

document.addEventListener("click", (event) => {
  const editButton = event.target.closest("[data-package-edit-open]");
  if (editButton) {
    const absoluteEditUrl = new URL(editButton.dataset.editUrl, window.location.href).href;
    const historicalForm = [...document.querySelectorAll("[data-historical-edit-form]")].find(
      (candidate) => candidate.action === absoluteEditUrl,
    );
    const dialog = historicalForm?.closest("dialog") || document.querySelector(`#package-${editButton.dataset.packageId}`);
    if (!dialog) {
      showError("No encontramos el formulario del menú original de esta comida.");
      return;
    }
    const form = historicalForm || dialog.querySelector("[data-package-add]");
    form.reset();
    form.action = editButton.dataset.editUrl;
    const setRadio = (suffix, value) => {
      form.querySelectorAll(`input[name$='${suffix}']`).forEach((input) => {
        input.checked = Boolean(value) && input.value === value;
      });
    };
    setRadio("first_course", editButton.dataset.firstCourse);
    setRadio("second_course", editButton.dataset.secondCourse);
    setRadio("main_course", editButton.dataset.mainCourse);
    setRadio("chicken_piece", editButton.dataset.chickenPiece);
    const waterInput = form.querySelector("input[name$='with_water']");
    const breadInput = form.querySelector("input[name$='bread']");
    const refillInput = form.querySelector("input[name$='refill_extra']");
    const twoCourseInput = form.querySelector("input[name$='two_course']");
    if (waterInput) waterInput.checked = editButton.dataset.withWater === "true";
    if (breadInput) breadInput.checked = editButton.dataset.bread === "true" || (!Object.hasOwn(editButton.dataset, "bread") && breadInput.defaultChecked);
    if (refillInput) refillInput.checked = editButton.dataset.refillExtra === "true";
    if (twoCourseInput && Object.hasOwn(editButton.dataset, "twoCourse")) {
      twoCourseInput.checked = editButton.dataset.twoCourse === "true";
    }
    // NOTA TEMPORAL PARA APRENDIZAJE: setRadio asigna .checked directamente, sin
    // disparar "change" — los contadores (+/-) y el resaltado de cada tarjeta de
    // primer/segundo/tercer tiempo sólo se sincronizan escuchando ese evento
    // (package-selection.js). Se dispara en las tres, no sólo en tercer tiempo.
    // Borra esta nota después de leerla.
    form.querySelectorAll("input[name$='first_course'], input[name$='second_course'], input[name$='main_course']").forEach((input) => {
      input.dispatchEvent(new Event("change", {bubbles: true}));
    });
    form.querySelector("[data-package-submit]").textContent = "Guardar cambios";
    dialog.showModal();
    window.requestAnimationFrame(() => {
      form.scrollTop = 0;
      dialog.scrollTop = 0;
    });
    return;
  }
  // NOTA TEMPORAL PARA APRENDIZAJE: la imagen envía el mismo formulario estándar
  // que el botón +. Así conserva personalización, pollo y armado automático sin
  // duplicar reglas. Borra esta nota después de leerla.
  const productImage = event.target.closest(".catalog-product-visual");
  if (productImage) {
    const standardAddForm = productImage.closest("[data-catalog-product]")?.querySelector(
      "form[data-product-add]:not([data-customizable-product])"
    );
    if (standardAddForm) {
      event.preventDefault();
      standardAddForm.requestSubmit();
      return;
    }
  }
  const catalogDecrease = event.target.closest("[data-catalog-decrease]");
  if (catalogDecrease) {
    event.preventDefault();
    catalogDecrease.disabled = true;
    enqueueRequest({url: catalogDecrease.dataset.url, body: new URLSearchParams(), source: catalogDecrease});
    return;
  }
  const button = event.target.closest("[data-ticket-action]");
  if (!button) return;
  event.preventDefault();
  button.disabled = true;
  const body = new URLSearchParams({action: button.dataset.ticketAction});
  enqueueRequest({url: button.dataset.ticketUrl, body, source: button});
});

document.addEventListener("click", (event) => {
  if (!splitBar) return;
  const action = event.target.closest("[data-split-action]");
  if (action) {
    event.preventDefault();
    const body = new URLSearchParams({action: action.dataset.splitAction});
    if (action.dataset.slot) body.set("slot", action.dataset.slot);
    enqueueRequest({url: splitBar.dataset.splitUrl, body, source: action});
    return;
  }
  const opener = event.target.closest("[data-split-move-open]");
  if (opener) {
    const menu = opener.closest(".table-ticket-item")?.querySelector(".ticket-split-move-menu");
    if (!menu) return;
    document.querySelectorAll(".ticket-split-move-menu").forEach((other) => { if (other !== menu) other.hidden = true; });
    menu.hidden = !menu.hidden;
    return;
  }
  const move = event.target.closest("[data-split-move]");
  if (move) {
    const body = new URLSearchParams({item_id: move.dataset.splitMove, slot: move.dataset.slot});
    enqueueRequest({url: splitBar.dataset.splitMoveUrl, body, source: move});
    return;
  }
  const pay = event.target.closest("[data-split-pay]");
  if (pay) {
    window.__openTablePayment?.({action: pay.dataset.payUrl, subtotal: pay.dataset.payTotal, title: `Cobrar Cuenta ${pay.dataset.splitPay}`});
  }
});

// Al cargar: con cuentas separadas el ticket se dibuja agrupado; si no, sólo se pintan
// los controles (y las cuentas ya cobradas por separado).
const initialTicketNode = document.querySelector("#table-ticket-data");
if (initialTicketNode) {
  const initialTicket = JSON.parse(initialTicketNode.textContent);
  if (initialTicket.split?.enabled) renderTicket(initialTicket);
  else renderSplitControls(initialTicket.split || {enabled: false, paid: []});
}

if (standardQuantitiesNode) {
  renderStandardQuantities(JSON.parse(standardQuantitiesNode.textContent || "{}"));
}
if (candidateQuantitiesNode) {
  renderCandidateQuantities(
    JSON.parse(candidateQuantitiesNode.textContent || "{}"),
    JSON.parse(document.querySelector("#table-meal-quantities")?.textContent || "{}"),
  );
}

document.addEventListener("submit", (event) => {
  const form = event.target.closest("form[data-product-add], form[data-package-add]");
  if (!form) return;
  if (
    form.matches("[data-chicken-choice]")
    && !form.querySelector("input[name='chicken_piece']")?.value
  ) {
    event.preventDefault();
    pendingChickenForm = form;
    chickenChoiceDialog.showModal();
    return;
  }
  event.preventDefault();
  enqueueRequest({
    url: form.action,
    body: new FormData(form),
    source: form,
    onSuccess: form.matches("[data-package-add]") ? () => {
      form.querySelector("[data-package-error]").replaceChildren();
      form.closest("dialog").close();
      form.reset();
      form.action = form.dataset.addUrl;
      form.querySelector("[data-package-submit]").textContent = form.hasAttribute("data-historical-edit-form") ? "Guardar cambios" : "Agregar al ticket";
    } : null,
  });
});
