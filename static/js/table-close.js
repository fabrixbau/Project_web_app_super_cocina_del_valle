/* Cobro de Mesas. En efectivo sólo se elige el método y el responsable: no se pide propina
ni con cuánto paga (decisión del dueño 2026-10-15). Terminal y Transferencia piden la
propina; sus botones rellenan el monto y se puede editar a mano. Django valida al enviar. */

(() => {
  // NOTA TEMPORAL PARA APRENDIZAJE: esto corre siempre, incluso en la pantalla de resumen
  // ya cerrada donde el diálogo de cobro ni se dibuja, porque ahí es donde vive el aviso
  // del ticket de cobro que se manda a imprimir en automático al cerrar. Borra esta nota.
  const printStatus = document.querySelector("[data-print-job-status]");
  if (printStatus) {
    const jobId = printStatus.dataset.jobId;
    (async () => {
      for (let attempt = 0; attempt < 15; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        try {
          const response = await fetch(`/app/impresion/estado/${jobId}/`, { credentials: "same-origin", cache: "no-store" });
          if (!response.ok) return;
          const job = await response.json();
          if (job.status === "printed") { printStatus.textContent = "Ticket de cobro enviado a la impresora de la Dell."; printStatus.classList.add("text-success"); return; }
          if (job.status === "failed") { printStatus.textContent = "El ticket de cobro no se pudo imprimir. Avisa al administrador antes de reintentar."; printStatus.classList.add("text-danger"); return; }
          if (job.status === "expired") { printStatus.textContent = "La impresora se desconectó antes de imprimir el ticket de cobro. Usa “Imprimir cobro” para reintentar."; printStatus.classList.add("text-danger"); return; }
        } catch (_) { return; }
      }
    })();
  }

  const dialog = document.querySelector("[data-close-account-dialog]");
  const form = document.querySelector("[data-close-account-form]");
  if (!dialog || !form) return;

  const openButton = document.querySelector("[data-close-account-open]");
  const dismissButton = dialog.querySelector("[data-close-account-dismiss]");
  const methodInputs = [...form.querySelectorAll('[name="payment_method"]')];
  const tipInput = form.querySelector('[name="tip_amount"]');
  const tipSection = form.querySelector("[data-tip-section]");
  const responsibleHeading = form.querySelector("[data-responsible-heading]");
  const totalOutput = form.querySelector("[data-payment-total]");
  const totalLabel = form.querySelector("[data-payment-total-label]");

  const paymentIcons = {
    cash: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="6" width="18" height="12" rx="2"></rect><circle cx="12" cy="12" r="2.5"></circle><path d="M7 9.5h.01M17 14.5h.01"></path></svg>',
    card: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="3" width="14" height="18" rx="2"></rect><path d="M8 7h8M8 11h8M9 17h6"></path><path d="M3 9h3M18 9h3"></path></svg>',
    transfer: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8h15"></path><path d="m16 5 3 3-3 3"></path><path d="M20 16H5"></path><path d="m8 13-3 3 3 3"></path></svg>',
  };
  const paymentLabels = {cash: "Efectivo", card: "Terminal", transfer: "Transferencia"};

  methodInputs.forEach((input) => {
    const label = input.closest("label");
    if (!label || !paymentIcons[input.value]) return;
    label.classList.add("payment-method-card");
    label.dataset.method = input.value;
    const icon = document.createElement("span");
    icon.className = "payment-method-icon";
    icon.innerHTML = paymentIcons[input.value];
    const copy = document.createElement("strong");
    copy.textContent = paymentLabels[input.value];
    const check = document.createElement("span");
    check.className = "payment-method-check";
    check.textContent = "✓";
    label.replaceChildren(input, icon, copy, check);
  });


  const selectedMethod = () => methodInputs.find((input) => input.checked)?.value;
  const calculate = () => {
    const subtotal = Number.parseFloat(form.dataset.accountSubtotal.replace(",", "."));
    const tip = selectedMethod() === "cash" ? 0 : Number.parseFloat(tipInput.value.replace(",", ".")) || 0;
    totalOutput.textContent = `$${(subtotal + tip).toFixed(2)}`;
  };
  const updatePaymentFields = () => {
    const method = selectedMethod();
    form.dataset.selectedPaymentMethod = method || "";
    const isCash = method === "cash";
    tipSection.hidden = isCash;
    if (isCash) {
      tipInput.value = "0";
      form.querySelectorAll("[data-tip-amount]").forEach((button) => button.classList.remove("is-selected"));
    }
    // Sin propina (efectivo) el responsable pasa a ser el paso 2; sigue abajo de todo.
    if (responsibleHeading) responsibleHeading.textContent = `${isCash ? "2" : "3"}. ¿A nombre de quién se queda la mesa?`;
    if (totalLabel) totalLabel.textContent = isCash ? "Total:" : "Total con propina:";
    calculate();
  };

  // El mismo diálogo cobra el ticket completo o sólo una cuenta separada (Cuenta N).
  const titleNode = dialog.querySelector(".dialog-heading h2");
  const defaultTitle = titleNode?.textContent || "";
  const defaultAction = form.getAttribute("action");
  const splitLauncher = form.querySelector("[data-split-account-open]");
  openButton.addEventListener("click", () => {
    form.setAttribute("action", defaultAction);
    if (titleNode) titleNode.textContent = defaultTitle;
    if (splitLauncher) splitLauncher.hidden = false;
    if (form.dataset.ticketTotal) form.dataset.accountSubtotal = form.dataset.ticketTotal;
    calculate();
    dialog.showModal();
  });
  window.__openTablePayment = ({action, subtotal, title}) => {
    form.setAttribute("action", action);
    form.dataset.accountSubtotal = subtotal;
    if (titleNode) titleNode.textContent = title;
    if (splitLauncher) splitLauncher.hidden = true;
    calculate();
    dialog.showModal();
  };
  dismissButton.addEventListener("click", () => dialog.close());
  methodInputs.forEach((input) => input.addEventListener("change", updatePaymentFields));
  tipInput.addEventListener("input", calculate);
  // NOTA TEMPORAL PARA APRENDIZAJE: al enfocar un campo de propina que sigue en "0", se
  // borra ese 0 para que se pueda escribir directo sin tener que borrarlo a mano primero;
  // si lo dejan vacío al salir, vuelve a poner "0". Borra esta nota después de leerla.
  tipInput.addEventListener("focus", () => { if (tipInput.value === "0") tipInput.value = ""; });
  tipInput.addEventListener("blur", () => { if (tipInput.value === "") tipInput.value = "0"; });
  form.querySelectorAll("[data-tip-amount]").forEach((button) => {
    button.addEventListener("click", () => {
      tipInput.value = button.dataset.tipAmount;
      form.querySelectorAll("[data-tip-amount]").forEach((candidate) => candidate.classList.toggle("is-selected", candidate === button));
      calculate();
    });
  });
  tipInput.addEventListener("input", () => {
    form.querySelectorAll("[data-tip-amount]").forEach((button) => button.classList.remove("is-selected"));
  });

  const responsibleWaiterSelect = form.querySelector('[name="responsible_waiter"]');
  const responsibleWaiterError = form.querySelector("[data-responsible-waiter-error]");
  form.querySelectorAll("[data-responsible-waiter]").forEach((button) => {
    button.addEventListener("click", () => {
      responsibleWaiterSelect.value = button.dataset.responsibleWaiter;
      responsibleWaiterError.hidden = true;
      form.querySelectorAll("[data-responsible-waiter]").forEach((candidate) => candidate.classList.toggle("is-selected", candidate === button));
    });
  });
  form.addEventListener("submit", (event) => {
    if (!responsibleWaiterSelect || !responsibleWaiterSelect.value) {
      event.preventDefault();
      if (responsibleWaiterError) {
        responsibleWaiterError.hidden = false;
        responsibleWaiterError.scrollIntoView({block: "center"});
      }
    }
  });

  updatePaymentFields();
})();
