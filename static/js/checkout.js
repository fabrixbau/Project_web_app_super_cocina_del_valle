/* NOTA TEMPORAL PARA APRENDIZAJE:
Este script solo controla visibilidad: muestra las opciones de cambio cuando el método es
efectivo. La seguridad no depende de JavaScript porque Django repite las validaciones.
Borra esta nota después de leerla. */

const paymentMethod = document.querySelector("#id_payment_method");
const cashOptions = document.querySelector("#cash-options");
const cashBill = document.querySelector("#id_cash_bill");
const customAmount = document.querySelector("#id_cash_custom_amount");
const paysExact = document.querySelector("#id_pays_exact");

function updatePaymentFields() {
  const isCash = paymentMethod && paymentMethod.value === "cash";
  cashOptions.hidden = !isCash;
  cashOptions.querySelectorAll("input, select").forEach((field) => {
    field.disabled = !isCash;
  });
}

if (paymentMethod && cashOptions) {
  paymentMethod.addEventListener("change", updatePaymentFields);
  updatePaymentFields();
}

if (cashBill && customAmount && paysExact) {
  cashBill.addEventListener("change", () => {
    if (cashBill.value) { customAmount.value = ""; paysExact.checked = false; }
  });
  customAmount.addEventListener("input", () => {
    if (customAmount.value) { cashBill.value = ""; paysExact.checked = false; }
  });
  paysExact.addEventListener("change", () => {
    if (paysExact.checked) { cashBill.value = ""; customAmount.value = ""; }
  });
}
