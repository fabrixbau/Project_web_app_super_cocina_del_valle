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
const catalogSearch = document.querySelector("[data-catalog-search]");
const catalogSearchResults = document.querySelector("[data-catalog-search-results]");
const catalogSearchEmpty = document.querySelector("[data-catalog-search-empty]");
let pendingChickenForm = null;
const currency = new Intl.NumberFormat("es-MX", {
  style: "currency", currency: "MXN", currencyDisplay: "narrowSymbol",
});

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
  ticketItems.replaceChildren();
  ticket.items.forEach((item) => {
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
    row.append(information, subtotal, controls);
    ticketItems.append(row);
  });
  ticketCount.textContent = ticket.count;
  ticketTotal.textContent = currency.format(Number(ticket.total_display));
  const closeForm = document.querySelector("[data-close-account-form]");
  if (closeForm) closeForm.dataset.accountSubtotal = ticket.total_display;
  const hasItems = ticket.items.length > 0;
  ticketPanel.hidden = !hasItems;
  pos.classList.toggle("has-ticket", hasItems);
  renderStandardQuantities(ticket.standard_quantities || {});
  renderCandidateQuantities(ticket.candidate_quantities || {});
}

function renderStandardQuantities(quantities) {
  document.querySelectorAll("[data-catalog-product]:not([data-auto-meal-card])").forEach((card) => {
    const quantity = quantities[String(card.dataset.catalogProduct)] || 0;
    card.querySelector("[data-standard-quantity]").textContent = quantity;
    card.querySelector("[data-catalog-decrease]").disabled = quantity === 0;
  });
}

function renderCandidateQuantities(quantities) {
  document.querySelectorAll("[data-auto-meal-card]").forEach((card) => {
    const quantity = quantities[String(card.dataset.catalogProduct)] || 0;
    card.querySelector("[data-standard-quantity]").textContent = quantity;
    card.querySelector("[data-catalog-decrease]").disabled = quantity === 0;
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
      onSuccess?.();
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
    form.action = form.dataset.addUrl;
    form.querySelector("[data-package-submit]").textContent = "Agregar al ticket";
    dialog.showModal();
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
    const refillInput = form.querySelector("input[name$='refill_extra']");
    if (waterInput) waterInput.checked = editButton.dataset.withWater === "true";
    if (refillInput) refillInput.checked = editButton.dataset.refillExtra === "true";
    form.querySelector("input[name$='main_course']:checked")?.dispatchEvent(new Event("change", {bubbles: true}));
    form.querySelector("[data-package-submit]").textContent = "Guardar cambios";
    dialog.showModal();
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

if (standardQuantitiesNode) {
  renderStandardQuantities(JSON.parse(standardQuantitiesNode.textContent || "{}"));
}
if (candidateQuantitiesNode) {
  renderCandidateQuantities(JSON.parse(candidateQuantitiesNode.textContent || "{}"));
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
