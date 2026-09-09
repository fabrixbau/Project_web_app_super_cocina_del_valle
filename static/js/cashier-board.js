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
  const change = panel.querySelector("[data-change-label]");
  change.textContent = data.payment_method === "cash" ? (data.cash_tendered === "" ? "Monto por definir" : (data.needs_change ? `Cambio $${data.change_required}` : "Sin cambio")) : "";
  const tipPanel = panel.querySelector("[data-cashier-tip]");
  if (tipPanel) {
    tipPanel.hidden = !["card", "transfer"].includes(data.payment_method);
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
    const method = paymentButton.dataset.paymentMethod || "cash";
    const cashAmount = paymentButton.dataset.cashAmount || "";
    if (method === "cash" && !cashAmount) { panel.querySelector("[data-cash-options]").hidden = false; return; }
    try { repaintPayment(panel, await postCashier(panel.dataset.paymentUrl, {payment_method: method, cash_amount: cashAmount})); }
    catch (error) { showError(panel, error); }
    return;
  }
  const release = event.target.closest("[data-cashier-release]");
  if (release) {
    const panel = release.closest("[data-cashier-payment]"); const row = panel.closest("[data-cashier-order]");
    try {
      await postCashier(panel.dataset.releaseUrl, {released: "1"});
      window.clearTimeout(releaseUndoTimer); recentlyReleasedRow = row; recentlyReleasedUrl = panel.dataset.releaseUrl;
      // NOTA TEMPORAL PARA APRENDIZAJE: retiramos físicamente la fila del documento.
      // Guardamos su posición sólo durante tres segundos para poder reinsertarla si el
      // operador pulsa Seguir orden. Borra esta nota después de leerla.
      recentlyReleasedParent = row.parentNode; recentlyReleasedNextSibling = row.nextSibling;
      row.remove(); undoRelease.hidden = false;
      releaseUndoTimer = window.setTimeout(() => { recentlyReleasedRow = null; recentlyReleasedUrl = ""; recentlyReleasedParent = null; recentlyReleasedNextSibling = null; undoRelease.hidden = true; }, 3000);
    } catch (error) { showError(panel, error); }
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
if (filters) { let timer; filters.querySelectorAll("select").forEach((field) => field.addEventListener("change", () => filters.requestSubmit())); filters.querySelector("input").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => filters.requestSubmit(), 450); }); }

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
    if (!nextRegion || nextRegion.innerHTML === region.innerHTML) return;
    region.innerHTML = nextRegion.innerHTML;
    feedback.textContent = "Caja se actualizó con los movimientos más recientes.";
    feedback.className = "message success";
    feedback.hidden = false;
  } catch (_) {
    // Una pérdida temporal de red no bloquea Caja; el siguiente ciclo reintentará.
  }
};
window.setInterval(refreshCashierOrders, 7000);
