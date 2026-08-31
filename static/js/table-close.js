/* NOTA TEMPORAL PARA APRENDIZAJE:
Este archivo ordena el cobro: un billete selecciona Efectivo, valida que alcance y calcula
el cambio. Los botones de propina rellenan el monto, pero permiten editarlo manualmente.
Django valida nuevamente al enviar. El cobro se procesa directamente, sin confirmación
adicional del navegador. Borra esta nota al terminar. */

(() => {
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
  const totalOutput = form.querySelector("[data-payment-total]");
  const changeRow = form.querySelector("[data-payment-change]");
  const changeOutput = changeRow.querySelector("span");

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
    const isCash = method === "cash";
    cashSection.hidden = Boolean(method) && !isCash;
    exactField.hidden = !isCash;
    cashField.hidden = !isCash || exactInput.checked;
    cashQuickFields.hidden = Boolean(method) && !isCash;
    exactInput.disabled = !isCash;
    cashInput.disabled = !isCash || exactInput.checked;
    if (!isCash) {
      exactInput.checked = false;
      cashInput.value = "";
      form.querySelectorAll("[data-cash-amount]").forEach((button) => button.classList.remove("is-selected"));
    } else if (exactInput.checked) {
      form.querySelectorAll("[data-cash-amount]").forEach((button) => button.classList.remove("is-selected"));
    }
    calculate();
  };

  openButton.addEventListener("click", () => { calculate(); dialog.showModal(); });
  dismissButton.addEventListener("click", () => dialog.close());
  methodInputs.forEach((input) => input.addEventListener("change", updatePaymentFields));
  exactInput.addEventListener("change", updatePaymentFields);
  tipInput.addEventListener("input", calculate);
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
  updatePaymentFields();
})();
