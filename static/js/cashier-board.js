/* NOTA TEMPORAL PARA APRENDIZAJE: todas las acciones de Caja usan fetch. Esto evita
recargar y perder la fila que se está atendiendo. El backend sigue validando montos,
roles y repartidores aunque los botones sean rápidos. Borra esta nota al leerla. */
const csrfToken = document.querySelector("[name='csrfmiddlewaretoken']")?.value || "";
const feedback = document.querySelector("[data-cashier-feedback]");

const postCashier = async (url, values) => {
  const body = new FormData();
  Object.entries(values).forEach(([key, value]) => body.append(key, value));
  body.append("csrfmiddlewaretoken", csrfToken);
  const response = await fetch(url, {method: "POST", body, headers: {"X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrfToken, Accept: "application/json"}});
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.error || "No se pudo guardar el movimiento.");
  return data;
};

const showError = (panel, error) => { const box = panel.querySelector("[data-cashier-error]"); box.textContent = error.message; box.hidden = false; };
const repaintPayment = (panel, data) => {
  panel.querySelectorAll("[data-payment-method]").forEach((button) => button.classList.toggle("is-selected", button.dataset.paymentMethod === data.payment_method));
  panel.querySelector("[data-cash-options]").hidden = data.payment_method !== "cash";
  panel.querySelector("[data-payment-label]").textContent = data.payment_label;
  const change = panel.querySelector("[data-change-label]");
  change.textContent = data.payment_method === "cash" ? (data.needs_change ? `Cambio $${data.change_required}` : "Sin cambio") : "";
  const handoff = panel.querySelector("[data-handoff]");
  if (handoff) {
    handoff.hidden = data.payment_method !== "cash";
    handoff.classList.toggle("is-confirmed", data.cash_handoff_confirmed);
    handoff.textContent = data.cash_handoff_confirmed ? "✓ Cambio entregado" : (data.needs_change ? `Confirmar entrega de $${data.change_required}` : "Confirmar sin cambio");
  }
  panel.querySelector("[data-cashier-error]").hidden = true;
};

document.addEventListener("click", async (event) => {
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
  const handoff = event.target.closest("[data-handoff]");
  if (handoff) {
    const panel = handoff.closest("[data-cashier-payment]");
    try { repaintPayment(panel, await postCashier(panel.dataset.handoffUrl, {confirmed: handoff.classList.contains("is-confirmed") ? "0" : "1"})); }
    catch (error) { showError(panel, error); }
  }
});

let cashTimer = null;
document.addEventListener("input", (event) => {
  if (!event.target.matches("[data-custom-cash]")) return;
  window.clearTimeout(cashTimer);
  const input = event.target; const panel = input.closest("[data-cashier-payment]");
  cashTimer = window.setTimeout(async () => {
    try { repaintPayment(panel, await postCashier(panel.dataset.paymentUrl, {payment_method: "cash", cash_amount: input.value})); }
    catch (error) { showError(panel, error); }
  }, 600);
});

document.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-cashier-assign]"); if (!form) return;
  event.preventDefault(); const row = form.closest("[data-cashier-order]"); const panel = row.querySelector("[data-cashier-payment]");
  try {
    const response = await fetch(form.action, {method: "POST", body: new FormData(form), headers: {"X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrfToken, Accept: "application/json"}});
    const data = await response.json(); if (!response.ok || !data.ok) throw new Error(data.error || "No se pudo asignar.");
    row.querySelectorAll("[data-person-id]").forEach((button) => button.classList.toggle("is-selected", button.dataset.personId === String(data.delivery_person_id)));
    feedback.textContent = data.message; feedback.className = "message success"; feedback.hidden = false; panel.querySelector("[data-cashier-error]").hidden = true;
  } catch (error) { showError(panel, error); }
});

const filters = document.querySelector("[data-cashier-filters]");
if (filters) { let timer; filters.querySelector("select").addEventListener("change", () => filters.requestSubmit()); filters.querySelector("input").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => filters.requestSubmit(), 450); }); }
