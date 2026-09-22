/* NOTA TEMPORAL PARA APRENDIZAJE: todas las acciones de Caja usan fetch. Esto evita
recargar y perder la fila que se está atendiendo. El backend sigue validando montos,
roles y repartidores aunque los botones sean rápidos. Borra esta nota al leerla. */
const csrfToken = document.querySelector("[name='csrfmiddlewaretoken']")?.value || "";
const feedback = document.querySelector("[data-cashier-feedback]");
const undoRelease = document.querySelector("[data-cashier-undo]");
let cashierRequestsInProgress = 0;
let releaseUndoTimer = null;
let recentlyReleasedRow = null;
let recentlyReleasedUrl = "";
let recentlyReleasedParent = null;
let recentlyReleasedNextSibling = null;
// iPad Air en horizontal supera 900px, pero sigue siendo una superficie táctil.
// Conservamos el tablero de escritorio en monitores y activamos las fichas plegables
// hasta 1200px únicamente cuando el dispositivo tiene puntero táctil.
const compactCashierView = window.matchMedia("(max-width: 900px), (max-width: 1200px) and (pointer: coarse)");

const enhanceCashierCards = (scope = document) => {
  scope.querySelectorAll("[data-cashier-order]").forEach((card) => {
    const totalLabel = card.querySelector(".cashier-order-priority > div:last-child > small");
    if (totalLabel) totalLabel.textContent = "Total";
    if (card.querySelector("[data-cashier-card-toggle]")) return;
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "cashier-card-toggle";
    toggle.dataset.cashierCardToggle = "";
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "Mostrar detalles del pedido");
    toggle.innerHTML = '<svg aria-hidden="true" viewBox="0 0 20 20"><path d="m4 7 6 6 6-6"/></svg>';
    card.prepend(toggle);

    if (compactCashierView.matches && !card.querySelector(".cashier-compact-summary")) {
      const priority = card.querySelector(".cashier-order-priority");
      const customer = priority?.firstElementChild;
      const total = priority?.lastElementChild;
      const assignment = card.matches(".type-delivery") ? card.querySelector(".cashier-assignment") : null;
      const compactSummary = document.createElement("div");
      compactSummary.className = "cashier-compact-summary";
      if (customer) compactSummary.append(customer);
      if (assignment) compactSummary.append(assignment);
      if (total && total !== customer) compactSummary.append(total);
      card.insertBefore(compactSummary, toggle.nextSibling);
    }
  });
};

enhanceCashierCards();

const revealFocusedCashierOrder = () => {
  const orderId = new URLSearchParams(window.location.search).get("focus_order");
  if (!orderId) return;
  const card = document.querySelector(`[data-cashier-order-id="${CSS.escape(orderId)}"]`);
  if (!card) return;
  card.classList.add("is-detail-expanded", "is-cashier-target");
  const toggle = card.querySelector("[data-cashier-card-toggle]");
  toggle?.setAttribute("aria-expanded", "true");
  window.requestAnimationFrame(() => card.scrollIntoView({behavior: "smooth", block: "center"}));
  window.setTimeout(() => card.classList.remove("is-cashier-target"), 3000);
};

revealFocusedCashierOrder();

const postCashier = async (url, values) => {
  cashierRequestsInProgress += 1;
  const body = new FormData();
  Object.entries(values).forEach(([key, value]) => body.append(key, value));
  body.append("csrfmiddlewaretoken", csrfToken);
  try {
    const response = await fetch(url, {method: "POST", body, headers: {"X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrfToken, Accept: "application/json"}});
    const data = await response.json();
    if (!response.ok || !data.ok) {
      const error = new Error(data.error || "No se pudo guardar el movimiento.");
      error.recoveryUrl = data.recovery_url || "";
      error.recoveryLabel = data.recovery_label || "";
      throw error;
    }
    return data;
  } finally { cashierRequestsInProgress -= 1; }
};

const showError = (panel, error) => { const box = panel.querySelector("[data-cashier-error]"); box.textContent = error.message; box.hidden = false; };
const repaintPayment = (panel, data) => {
  const row = panel.closest("[data-cashier-order]");
  panel.querySelectorAll("[data-payment-method]").forEach((button) => button.classList.toggle("is-selected", button.dataset.paymentMethod === data.payment_method));
  panel.querySelector("[data-cash-options]").hidden = data.payment_method !== "cash";
  panel.querySelectorAll("[data-cash-amount]").forEach((button) => {
    const selected = data.payment_method === "cash" && (
      (button.dataset.cashAmount === "exact" && data.cash_tendered !== "" && !data.needs_change)
      || (button.dataset.cashAmount !== "exact" && Number(button.dataset.cashAmount) === Number(data.cash_tendered) && data.needs_change)
    );
    button.classList.toggle("is-selected", selected);
  });
  panel.querySelector("[data-payment-label]").textContent = data.payment_label;
  row?.querySelector("[data-priority-payment]")?.replaceChildren(data.payment_label);
  const priorityCash = row?.querySelector("[data-priority-cash]");
  if (priorityCash) priorityCash.textContent = data.payment_method === "cash" ? (data.needs_change ? `Paga con $${data.cash_tendered}` : "Pago exacto") : "";
  const change = panel.querySelector("[data-change-label]");
  change.textContent = data.payment_method === "cash" ? (data.cash_tendered === "" ? "Monto por definir" : (data.needs_change ? `Cambio $${data.change_required}` : "Sin cambio")) : "";
  panel.querySelector("[data-payment-result]")?.classList.toggle("has-change", data.payment_method === "cash" && data.needs_change);
  const tipPanel = panel.querySelector("[data-cashier-tip]");
  if (tipPanel) {
    const tipAllowed = data.payment_method === "transfer";
    tipPanel.hidden = !tipAllowed;
    tipPanel.inert = !tipAllowed;
    tipPanel.querySelectorAll("button, input").forEach((control) => { control.disabled = !tipAllowed; });
    tipPanel.querySelector("[data-cashier-tip-value]").textContent = data.tip_amount;
    tipPanel.querySelector("[data-cashier-total-tip]").textContent = data.total_with_tip;
    tipPanel.querySelector("[data-cashier-custom-tip]").value = data.tip_amount;
    tipPanel.querySelectorAll("[data-cashier-tip-amount]").forEach((button) => button.classList.toggle("is-selected", Number(button.dataset.cashierTipAmount) === Number(data.tip_amount)));
  }
  panel.querySelector("[data-cashier-error]").hidden = true;
};

const repaintCashierTip = (panel, data) => {
  panel.querySelector("[data-cashier-tip-value]").textContent = data.tip_amount;
  panel.querySelector("[data-cashier-total-tip]").textContent = data.total_with_tip;
  panel.querySelector("[data-cashier-custom-tip]").value = data.tip_amount;
  panel.querySelectorAll("[data-cashier-tip-amount]").forEach((button) => button.classList.toggle("is-selected", Number(button.dataset.cashierTipAmount) === Number(data.tip_amount)));
  panel.querySelector("[data-cashier-tip-error]").hidden = true;
};

document.addEventListener("click", async (event) => {
  const cardToggle = event.target.closest("[data-cashier-card-toggle]");
  if (cardToggle) {
    const card = cardToggle.closest("[data-cashier-order]");
    const expanded = cardToggle.getAttribute("aria-expanded") === "true";
    cardToggle.setAttribute("aria-expanded", String(!expanded));
    cardToggle.setAttribute("aria-label", expanded ? "Mostrar detalles del pedido" : "Ocultar detalles del pedido");
    card.classList.toggle("is-detail-expanded", !expanded);
    return;
  }
  const tipButton = event.target.closest("[data-cashier-tip-amount]");
  if (tipButton) {
    const panel = tipButton.closest("[data-cashier-tip]");
    try { repaintCashierTip(panel, await postCashier(panel.dataset.tipUrl, {tip_amount: tipButton.dataset.cashierTipAmount})); }
    catch (error) { const box = panel.querySelector("[data-cashier-tip-error]"); box.textContent = error.message; box.hidden = false; }
    return;
  }
  const paymentButton = event.target.closest("[data-payment-method], [data-cash-amount]");
  if (paymentButton) {
    const panel = paymentButton.closest("[data-cashier-payment]");
    const isSelectedMethod = paymentButton.matches("[data-payment-method]") && paymentButton.classList.contains("is-selected");
    if (isSelectedMethod) {
      try { repaintPayment(panel, await postCashier(panel.dataset.paymentUrl, {payment_method: "", cash_amount: ""})); }
      catch (error) { showError(panel, error); }
      return;
    }
    const method = paymentButton.dataset.paymentMethod || "cash";
    const cashAmount = paymentButton.dataset.cashAmount || "";
    if (method === "cash" && !cashAmount) {
      try { repaintPayment(panel, await postCashier(panel.dataset.paymentUrl, {payment_method: "cash", cash_amount: ""})); }
      catch (error) { showError(panel, error); }
      return;
    }
    try { repaintPayment(panel, await postCashier(panel.dataset.paymentUrl, {payment_method: method, cash_amount: cashAmount})); }
    catch (error) { showError(panel, error); }
    return;
  }
  const release = event.target.closest("[data-cashier-release]");
  if (release) {
    const panel = release.closest("[data-cashier-payment]"); const row = panel.closest("[data-cashier-order]");
    const parent = row.parentNode;
    const nextSibling = row.nextSibling;
    row.remove();
    try {
      await postCashier(panel.dataset.releaseUrl, {released: "1"});
      window.clearTimeout(releaseUndoTimer); recentlyReleasedRow = row; recentlyReleasedUrl = panel.dataset.releaseUrl;
      // NOTA TEMPORAL PARA APRENDIZAJE: retiramos físicamente la fila del documento.
      // Guardamos su posición sólo durante tres segundos para poder reinsertarla si el
      // operador pulsa Seguir orden. Borra esta nota después de leerla.
      recentlyReleasedParent = parent; recentlyReleasedNextSibling = nextSibling;
      undoRelease.hidden = false;
      releaseUndoTimer = window.setTimeout(() => { recentlyReleasedRow = null; recentlyReleasedUrl = ""; recentlyReleasedParent = null; recentlyReleasedNextSibling = null; undoRelease.hidden = true; }, 3000);
    } catch (error) {
      if (nextSibling?.parentNode === parent) parent.insertBefore(row, nextSibling);
      else parent?.append(row);
      showError(panel, error);
    }
  }
});

// NOTA TEMPORAL PARA APRENDIZAJE: la fila abre el pedido sólo desde su superficie
// libre. Cualquier botón, enlace o campo conserva su acción y no provoca navegación.
// Borra esta nota después de leerla.
const openCashierOrder = (row) => { window.location.href = row.dataset.cashierOrderUrl; };
document.addEventListener("click", (event) => {
  const row = event.target.closest("[data-cashier-order-url]");
  if (!row || event.target.closest("[data-cashier-payment], button, a, input, select, textarea, label, form")) return;
  openCashierOrder(row);
});
document.addEventListener("keydown", (event) => {
  const row = event.target.closest?.("[data-cashier-order-url]");
  if (!row || !["Enter", " "].includes(event.key) || event.target !== row) return;
  event.preventDefault(); openCashierOrder(row);
});

undoRelease?.querySelector("[data-cashier-undo-action]")?.addEventListener("click", async () => {
  if (!recentlyReleasedRow || !recentlyReleasedUrl) return;
  window.clearTimeout(releaseUndoTimer);
  try {
    await postCashier(recentlyReleasedUrl, {released: "0"});
    if (recentlyReleasedNextSibling?.parentNode === recentlyReleasedParent) recentlyReleasedParent.insertBefore(recentlyReleasedRow, recentlyReleasedNextSibling);
    else recentlyReleasedParent?.append(recentlyReleasedRow);
    recentlyReleasedRow.scrollIntoView({behavior: "smooth", block: "center"});
    recentlyReleasedRow = null; recentlyReleasedUrl = ""; recentlyReleasedParent = null; recentlyReleasedNextSibling = null; undoRelease.hidden = true;
  } catch (error) {
    undoRelease.querySelector("span").textContent = error.message;
    releaseUndoTimer = window.setTimeout(() => { undoRelease.hidden = true; }, 3000);
  }
});

let cashTimer = null;
const cashierTipTimers = new WeakMap();
document.addEventListener("input", (event) => {
  if (event.target.matches("[data-cashier-custom-tip]")) {
    const input = event.target; const panel = input.closest("[data-cashier-tip]");
    window.clearTimeout(cashierTipTimers.get(input));
    panel.querySelectorAll("[data-cashier-tip-amount]").forEach((button) => button.classList.remove("is-selected"));
    cashierTipTimers.set(input, window.setTimeout(async () => {
      try { repaintCashierTip(panel, await postCashier(panel.dataset.tipUrl, {tip_amount: input.value})); }
      catch (error) { const box = panel.querySelector("[data-cashier-tip-error]"); box.textContent = error.message; box.hidden = false; }
    }, 400));
    return;
  }
  if (!event.target.matches("[data-custom-cash]")) return;
  window.clearTimeout(cashTimer);
  const input = event.target; const panel = input.closest("[data-cashier-payment]");
  panel.querySelectorAll("[data-cash-amount]").forEach((button) => button.classList.remove("is-selected"));
  panel.querySelector("[data-change-label]").textContent = "Actualizando…";
  cashTimer = window.setTimeout(async () => {
    try { repaintPayment(panel, await postCashier(panel.dataset.paymentUrl, {payment_method: "cash", cash_amount: input.value})); }
    catch (error) { showError(panel, error); }
  }, 250);
});

document.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-cashier-assign]"); if (!form) return;
  event.preventDefault(); const row = form.closest("[data-cashier-order]"); const panel = row.querySelector("[data-cashier-payment]");
  cashierRequestsInProgress += 1;
  try {
    const response = await fetch(form.action, {method: "POST", body: new FormData(form), headers: {"X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrfToken, Accept: "application/json"}});
    const data = await response.json(); if (!response.ok || !data.ok) throw new Error(data.error || "No se pudo asignar.");
    row.querySelectorAll("[data-person-id]").forEach((button) => button.classList.toggle("is-selected", button.dataset.personId === String(data.delivery_person_id)));
    const courier = row.querySelector("[data-priority-courier]");
    if (courier) courier.textContent = data.delivery_person_name || form.querySelector("button").textContent.trim();
    feedback.textContent = data.message; feedback.className = "message success"; feedback.hidden = false; panel.querySelector("[data-cashier-error]").hidden = true;
  } catch (error) { showError(panel, error); }
  finally { cashierRequestsInProgress -= 1; }
});

// NOTA TEMPORAL PARA APRENDIZAJE: el servidor decide cuál transición es válida y
// devuelve el siguiente botón. El navegador únicamente repinta esta parte de la fila,
// por eso la pantalla no salta al inicio. Borra esta nota después de leerla.
document.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-cashier-status-form]");
  if (!form) return;
  event.preventDefault();
  const panel = form.closest("[data-cashier-status]");
  const errorLink = panel.querySelector("[data-cashier-status-error]");
  const button = form.querySelector("button");
  button.disabled = true;
  try {
    // getAttribute evita que el input name="action" sustituya la propiedad form.action.
    const data = await postCashier(form.getAttribute("action"), {action: form.querySelector("[name='action']").value});
    const badge = panel.querySelector("[data-cashier-status-label]");
    badge.className = `status-badge status-${data.status}`;
    badge.textContent = data.status_label;
    errorLink.hidden = true;
    if (data.next_action) {
      form.querySelector("[name='action']").value = data.next_action;
      button.textContent = data.next_action_label;
      button.disabled = false;
    } else {
      form.remove();
      panel.insertAdjacentHTML("beforeend", '<small data-cashier-no-action>Sin acción pendiente</small>');
    }
  } catch (error) {
    errorLink.textContent = error.message;
    if (error.recoveryUrl) {
      errorLink.href = error.recoveryUrl;
      errorLink.textContent = `${error.message} · ${error.recoveryLabel}`;
    } else errorLink.removeAttribute("href");
    errorLink.hidden = false;
    button.disabled = false;
  }
});

const filters = document.querySelector("[data-cashier-filters]");
if (filters) { let timer; filters.querySelectorAll("select, input[type='date']").forEach((field) => field.addEventListener("change", () => filters.requestSubmit())); filters.querySelector("input[name='q']").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => filters.requestSubmit(), 450); }); }

const cashierTools = document.querySelector(".cashier-tools");
const unpaidQuick = document.querySelector(".cashier-unpaid-quick");
if (cashierTools && unpaidQuick) cashierTools.append(unpaidQuick);

document.querySelectorAll("[data-cashier-panel-toggle]").forEach((toggle) => {
  const target = toggle.dataset.cashierPanelToggle === "tools"
    ? toggle.closest(".cashier-tools")
    : toggle.closest(".cashier-filter-card");
  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!expanded));
    target?.classList.toggle("is-mobile-expanded", !expanded);
  });
});

// La consulta periódica trae la misma vista y extrae sólo la lista. Si Caja está
// escribiendo o guardando, esperamos al siguiente ciclo para no borrar su interacción.
const refreshCashierOrders = async () => {
  const region = document.querySelector("[data-cashier-live-region]");
  const activeField = document.activeElement?.matches("input, textarea, select") && region?.contains(document.activeElement);
  if (!region || cashierRequestsInProgress > 0 || activeField || recentlyReleasedRow) return;
  try {
    const response = await fetch(window.location.href, {headers: {"X-Requested-With": "XMLHttpRequest"}, cache: "no-store"});
    if (!response.ok) return;
    const nextDocument = new DOMParser().parseFromString(await response.text(), "text/html");
    const nextRegion = nextDocument.querySelector("[data-cashier-live-region]");
    if (nextRegion) {
      enhanceCashierCards(nextRegion);
      region.querySelectorAll("[data-cashier-order].is-detail-expanded").forEach((currentCard) => {
        const url = currentCard.dataset.cashierOrderUrl;
        const nextCard = [...nextRegion.querySelectorAll("[data-cashier-order]")]
          .find((card) => card.dataset.cashierOrderUrl === url);
        if (!nextCard) return;
        nextCard.classList.add("is-detail-expanded");
        nextCard.querySelector("[data-cashier-card-toggle]")?.setAttribute("aria-expanded", "true");
      });
    }
    if (!nextRegion || nextRegion.innerHTML === region.innerHTML) return;
    region.innerHTML = nextRegion.innerHTML;
    enhanceCashierCards(region);
  } catch (_) {
    // Una pérdida temporal de red no bloquea Caja; el siguiente ciclo reintentará.
  }
};
window.setInterval(refreshCashierOrders, 7000);
