/* Añade el flujo de adeudo sin convertir toda la ficha de mesa en formulario. */
const unpaidDialog = document.querySelector("[data-table-unpaid-dialog]");
const unpaidForm = unpaidDialog?.querySelector("[data-table-unpaid-form]");

document.querySelectorAll(".table-tile-more-actions-menu").forEach((menu) => {
  const transferForm = menu.querySelector("form[action*='pasar-a-pedido']");
  if (!transferForm || !unpaidDialog) return;
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "Registrar mesa como no pagada";
  button.dataset.tableUnpaidOpen = "";
  button.dataset.action = transferForm.action.replace("pasar-a-pedido/", "registrar-no-pagada/");
  menu.append(button);
});

document.addEventListener("click", (event) => {
  const opener = event.target.closest("[data-table-unpaid-open]");
  if (opener && unpaidForm) {
    unpaidForm.action = opener.dataset.action;
    unpaidForm.reset();
    unpaidForm.querySelector("[data-customer-picker-id]").value = "";
    unpaidForm.querySelector("[data-customer-picker-results]").hidden = true;
    opener.closest("details")?.removeAttribute("open");
    unpaidDialog.showModal();
    unpaidForm.querySelector("[data-customer-picker-input]").focus();
  }
  if (event.target.closest("[data-table-unpaid-close]")) unpaidDialog?.close();
});
