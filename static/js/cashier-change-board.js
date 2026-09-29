/* NOTA TEMPORAL PARA APRENDIZAJE: confirmar una devolución actualiza el mismo pedido
sin recargar. Si estamos viendo sólo Pendientes o Devueltos, la fila sale de la lista
al dejar de pertenecer al filtro. Borra esta nota después de leerla. */
const changeFilters = document.querySelector("[data-change-filters]");
const installChangeDisclosure = (toggle, panel) => toggle?.addEventListener("click", () => {
  const expanded = toggle.getAttribute("aria-expanded") === "true";
  toggle.setAttribute("aria-expanded", String(!expanded));
  panel?.classList.toggle("is-mobile-expanded", !expanded);
});
const changeFilterPanel = document.querySelector(".change-filters");
installChangeDisclosure(changeFilterPanel?.querySelector("[data-change-filter-toggle]"), changeFilterPanel);
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
changeFilters?.querySelectorAll("select, input[type='date']").forEach((field) => field.addEventListener("change", () => changeFilters.requestSubmit()));
const changeSearchInput = changeFilters?.querySelector("[data-change-order-search-input]");
const changeSearchResults = changeFilters?.querySelector("[data-change-order-search-results]");
const changeSearchOptions = (() => {
  try { return JSON.parse(document.querySelector("#change-order-search-options")?.textContent || "[]"); }
  catch (error) { return []; }
})();
const closeChangeSearch = () => { if (changeSearchResults) changeSearchResults.hidden = true; };
const renderChangeSearch = () => {
  if (!changeSearchInput || !changeSearchResults) return;
  const query = changeSearchInput.value.trim().toLocaleLowerCase("es-MX");
  changeSearchResults.replaceChildren();
  if (query.length < 2) { closeChangeSearch(); return; }
  const matches = changeSearchOptions.filter((order) => (
    order.customer.toLocaleLowerCase("es-MX").includes(query) || order.folio.includes(query.replace(/^#/, ""))
  )).slice(0, 10);
  if (!matches.length) { closeChangeSearch(); return; }
  matches.forEach((order) => {
    const button = document.createElement("button");
    button.type = "button";
    const customer = document.createElement("strong");
    const folio = document.createElement("small");
    customer.textContent = order.customer;
    folio.textContent = `Pedido ${order.folio}`;
    button.append(customer, folio);
    button.addEventListener("click", () => {
      changeSearchInput.value = order.folio;
      closeChangeSearch();
      changeFilters.requestSubmit();
    });
    changeSearchResults.append(button);
  });
  changeSearchResults.hidden = false;
};
changeSearchInput?.addEventListener("input", renderChangeSearch);
changeSearchInput?.addEventListener("keydown", (event) => {
  if (event.key === "Enter") { event.preventDefault(); closeChangeSearch(); changeFilters.requestSubmit(); }
  if (event.key === "Escape") closeChangeSearch();
});
document.addEventListener("click", (event) => {
  if (!event.target.closest("[data-change-order-search]")) closeChangeSearch();
});
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
