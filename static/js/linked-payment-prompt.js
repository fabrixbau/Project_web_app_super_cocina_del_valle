/* Ventana "¿liquidar también el otro?" entre Transferencias y Cuentas por cobrar.
   Un <form data-linked-prompt> se detiene al enviarse y pregunta:
     - Sí  → pone "1" en el campo oculto data-linked-field y envía.
     - No  → pone "0" y envía.
     - Cancelar → no envía nada.
   Con data-linked-min-amount, sólo pregunta si el input name="amount" cubre ese monto
   (un abono parcial no liquida el adeudo, así que no hay nada que preguntar). */
(() => {
  const dialog = document.createElement("dialog");
  dialog.className = "linked-payment-dialog";
  dialog.innerHTML = `
    <div class="linked-payment-body">
      <h2 data-linked-dialog-title></h2>
      <p data-linked-dialog-message></p>
      <div class="linked-payment-actions">
        <button type="button" data-linked-choice="yes"></button>
        <button type="button" class="secondary-action" data-linked-choice="no"></button>
        <button type="button" class="linked-payment-cancel" data-linked-choice="cancel">Cancelar</button>
      </div>
    </div>`;
  document.body.append(dialog);
  const title = dialog.querySelector("[data-linked-dialog-title]");
  const message = dialog.querySelector("[data-linked-dialog-message]");
  const yesButton = dialog.querySelector('[data-linked-choice="yes"]');
  const noButton = dialog.querySelector('[data-linked-choice="no"]');
  let targetForm = null;

  const send = (value) => {
    const form = targetForm;
    dialog.close();
    if (!form) return;
    const field = form.querySelector(`input[name="${form.dataset.linkedField}"]`);
    if (field) field.value = value;
    form.dataset.linkedReady = "1";
    form.requestSubmit();
  };

  document.addEventListener("submit", (event) => {
    const form = event.target.closest("form[data-linked-prompt]");
    if (!form) return;
    if (form.dataset.linkedReady === "1") { delete form.dataset.linkedReady; return; }
    const minAmount = Number(form.dataset.linkedMinAmount || 0);
    if (minAmount > 0) {
      const amount = Number(form.querySelector('input[name="amount"]')?.value || 0);
      if (amount < minAmount) return; // abono parcial: se envía sin preguntar
    }
    event.preventDefault();
    targetForm = form;
    title.textContent = form.dataset.linkedTitle || "";
    message.textContent = form.dataset.linkedMessage || "";
    yesButton.textContent = form.dataset.linkedYes || "Sí";
    noButton.textContent = form.dataset.linkedNo || "No";
    dialog.showModal();
  });

  dialog.addEventListener("click", (event) => {
    const choice = event.target.closest("[data-linked-choice]")?.dataset.linkedChoice;
    if (choice === "yes") send("1");
    else if (choice === "no") send("0");
    else if (choice === "cancel" || event.target === dialog) { targetForm = null; dialog.close(); }
  });
})();
