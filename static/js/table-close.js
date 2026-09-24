/* NOTA TEMPORAL PARA APRENDIZAJE:
Este archivo ordena el cobro: un billete selecciona Efectivo, valida que alcance y calcula
el cambio. Los botones de propina rellenan el monto, pero permiten editarlo manualmente.
Django valida nuevamente al enviar. El cobro se procesa directamente, sin confirmación
adicional del navegador. Borra esta nota al terminar. */

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
  const exactInput = form.querySelector('[name="pays_exact"]');
  const cashInput = form.querySelector('[name="cash_tendered"]');
  const exactField = form.querySelector('[data-payment-field="pays_exact"]');
  const cashField = form.querySelector('[data-payment-field="cash_tendered"]');
  const cashSection = form.querySelector("[data-cash-section]");
  const cashQuickFields = form.querySelector("[data-cash-fields]");
  const cashError = form.querySelector("[data-cash-error]");
  const tipHeading = form.querySelector(".tip-selection-section > strong");
  const totalOutput = form.querySelector("[data-payment-total]");
  const changeRow = form.querySelector("[data-payment-change]");
  const changeOutput = changeRow.querySelector("span");

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

  const exactButton = document.createElement("button");
  exactButton.type = "button";
  exactButton.className = "exact-payment-button";
  exactButton.setAttribute("aria-pressed", "false");
  exactButton.addEventListener("click", () => {
    exactInput.checked = !exactInput.checked;
    exactInput.dispatchEvent(new Event("change", {bubbles: true}));
  });
  exactField.classList.add("exact-payment-field");
  exactField.append(exactButton);

  const selectedMethod = () => methodInputs.find((input) => input.checked)?.value;
  const calculate = () => {
    const subtotal = Number.parseFloat(form.dataset.accountSubtotal.replace(",", "."));
    const tip = Number.parseFloat(tipInput.value.replace(",", ".")) || 0;
    const total = subtotal + tip;
    totalOutput.textContent = `$${total.toFixed(2)}`;
    const received = Number.parseFloat(cashInput.value.replace(",", "."));
    const insufficientCash = selectedMethod() === "cash" && !exactInput.checked && Number.isFinite(received) && received < total;
    const showChange = selectedMethod() === "cash" && !exactInput.checked && Number.isFinite(received) && !insufficientCash;
    changeRow.hidden = !showChange;
    changeOutput.textContent = Math.max(0, received - total).toFixed(2);
    cashError.hidden = !insufficientCash;
    cashInput.setCustomValidity(insufficientCash ? "El efectivo recibido es menor al total a pagar." : "");
  };
  const updatePaymentFields = () => {
    const method = selectedMethod();
    form.dataset.selectedPaymentMethod = method || "";
    const isCash = method === "cash";
    if (tipHeading) tipHeading.textContent = `${isCash ? "3" : "2"}. Propina para el mesero`;
    cashSection.hidden = !isCash;
    exactField.hidden = !isCash;
    cashField.hidden = !isCash || exactInput.checked;
    cashQuickFields.hidden = !isCash;
    exactInput.disabled = !isCash;
    cashInput.disabled = !isCash || exactInput.checked;
    if (!isCash) {
      exactInput.checked = false;
      cashInput.value = "";
      form.querySelectorAll("[data-cash-amount]").forEach((button) => button.classList.remove("is-selected"));
    } else if (exactInput.checked) {
      form.querySelectorAll("[data-cash-amount]").forEach((button) => button.classList.remove("is-selected"));
    }
    exactButton.classList.toggle("is-selected", exactInput.checked);
    exactButton.setAttribute("aria-pressed", String(exactInput.checked));
    exactButton.textContent = exactInput.checked ? "✓ Pago exacto" : "Pago exacto";
    calculate();
  };

  openButton.addEventListener("click", () => { calculate(); dialog.showModal(); });
  dismissButton.addEventListener("click", () => dialog.close());
  methodInputs.forEach((input) => input.addEventListener("change", updatePaymentFields));
  exactInput.addEventListener("change", updatePaymentFields);
  tipInput.addEventListener("input", calculate);
  // NOTA TEMPORAL PARA APRENDIZAJE: al enfocar un campo de propina que sigue en "0", se
  // borra ese 0 para que se pueda escribir directo sin tener que borrarlo a mano primero;
  // si lo dejan vacío al salir, vuelve a poner "0". Borra esta nota después de leerla.
  tipInput.addEventListener("focus", () => { if (tipInput.value === "0") tipInput.value = ""; });
  tipInput.addEventListener("blur", () => { if (tipInput.value === "") tipInput.value = "0"; });
  cashInput.addEventListener("input", () => {
    form.querySelectorAll("[data-cash-amount]").forEach((button) => button.classList.remove("is-selected"));
    calculate();
  });
  form.querySelectorAll("[data-cash-amount]").forEach((button) => {
    button.addEventListener("click", () => {
      const cashMethod = methodInputs.find((input) => input.value === "cash");
      cashMethod.checked = true;
      exactInput.checked = false;
      cashInput.disabled = false;
      cashInput.value = button.dataset.cashAmount;
      form.querySelectorAll("[data-cash-amount]").forEach((candidate) => candidate.classList.toggle("is-selected", candidate === button));
      updatePaymentFields();
    });
  });
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
