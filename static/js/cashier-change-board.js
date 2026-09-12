/* NOTA TEMPORAL PARA APRENDIZAJE: confirmar una devolución actualiza el mismo pedido
sin recargar. Si estamos viendo sólo Pendientes o Devueltos, la fila sale de la lista
al dejar de pertenecer al filtro. Borra esta nota después de leerla. */
const changeFilters = document.querySelector("[data-change-filters]");
// NOTA TEMPORAL PARA APRENDIZAJE: "Efectivo por devolver" describe exclusivamente
// repartos. Si Caja elige Recoger, pasamos a Todos los medios para que el filtro no
// produzca una combinación imposible. Borra esta nota después de leerla.
const changeOrderType = changeFilters?.querySelector("[name='order_type']");
const changePaymentMethod = changeFilters?.querySelector("[name='payment_method']");
changeOrderType?.addEventListener("change", () => {
  if (changeOrderType.value !== "delivery" && changePaymentMethod.value === "cash_change") changePaymentMethod.value = "all";
});
changePaymentMethod?.addEventListener("change", () => {
  if (changePaymentMethod.value === "cash_change") changeOrderType.value = "delivery";
});
changeFilters?.querySelectorAll("input, select").forEach((field) => field.addEventListener("change", () => changeFilters.requestSubmit()));
const settlementFeedback = document.querySelector("[data-settlement-feedback]");
const moneyValue = (element) => Number((element?.textContent || "0").replace(/[^0-9.-]/g, ""));
const paintMoney = (element, amount) => { if (element) element.textContent = new Intl.NumberFormat("es-MX", {style: "currency", currency: "MXN"}).format(Math.max(0, amount)); };

document.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-settlement-form]"); if (!form) return;
  event.preventDefault(); const row = form.closest("[data-change-row]"); const button = form.querySelector("button"); const errorBox = row.querySelector("[data-settlement-error]");
  const wasSettled = row.classList.contains("is-settled"); const amount = Number(row.dataset.changeAmount || 0); button.disabled = true;
  try {
    const response = await fetch(form.action, {method: "POST", body: new FormData(form), headers: {"X-Requested-With": "XMLHttpRequest", Accept: "application/json"}});
    const data = await response.json(); if (!response.ok || !data.ok) throw new Error(data.error || "No se pudo guardar la devolución.");
    const pending = document.querySelector("[data-pending-total]"); const settled = document.querySelector("[data-settled-total]");
    paintMoney(pending, moneyValue(pending) + (data.cash_settlement_confirmed ? -amount : amount));
    paintMoney(settled, moneyValue(settled) + (data.cash_settlement_confirmed ? amount : -amount));
    const activeFilter = changeFilters.querySelector("[name='settlement']").value;
    if (activeFilter !== "all") row.remove();
    else { row.classList.toggle("is-settled", data.cash_settlement_confirmed); form.querySelector("[name='confirmed']").value = data.cash_settlement_confirmed ? "0" : "1"; button.textContent = data.cash_settlement_confirmed ? "Marcar pendiente" : "Confirmar devolución"; button.disabled = false; }
    settlementFeedback.textContent = data.cash_settlement_confirmed ? `Efectivo devuelto; pedido marcado como ${data.status_label}.` : "El efectivo volvió a quedar pendiente."; settlementFeedback.className = "message success"; settlementFeedback.hidden = false;
  } catch (error) { errorBox.textContent = error.message; errorBox.hidden = false; button.disabled = false; }
});
