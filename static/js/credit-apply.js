/* NOTA TEMPORAL PARA APRENDIZAJE:
Pantalla "Aplicar saldo a favor". Recalcula en vivo cuánto se aplica y cuánto saldo
queda. Al marcar un pedido se propone pagarlo completo hasta donde alcance el saldo;
al desmarcarlo su importe queda en 0. El servidor vuelve a validar todo.
Borra esta nota después de leerla. */
(() => {
  const form = document.querySelector("[data-credit-apply]");
  if (!form) return;
  const credit = Number(form.dataset.credit || 0);
  const rows = [...form.querySelectorAll("[data-credit-apply-row]")];
  const totalOutput = form.querySelector("[data-credit-apply-total]");
  const remainingOutput = form.querySelector("[data-credit-apply-remaining]");
  const error = form.querySelector("[data-credit-apply-error]");
  const submit = form.querySelector("[data-credit-apply-submit]");
  const money = new Intl.NumberFormat("es-MX", {style: "currency", currency: "MXN"});
  const cents = (value) => Math.round(Number(value || 0) * 100) / 100;

  const appliedTotal = (except = null) => rows.reduce((sum, row) => {
    if (row === except || !row.querySelector("[data-credit-apply-check]").checked) return sum;
    return sum + cents(row.querySelector("[data-credit-apply-amount]").value);
  }, 0);

  const refresh = () => {
    let total = 0;
    rows.forEach((row) => {
      const check = row.querySelector("[data-credit-apply-check]");
      const input = row.querySelector("[data-credit-apply-amount]");
      const balance = cents(row.dataset.balance);
      const amount = check.checked ? Math.min(cents(input.value), balance) : 0;
      input.disabled = !check.checked;
      total += amount;
      const result = row.querySelector("[data-credit-apply-result]");
      if (!check.checked || amount <= 0) result.textContent = "Sin cambios";
      else if (amount >= balance) result.textContent = "Queda liquidado";
      else result.textContent = `Queda debiendo ${money.format(balance - amount)}`;
      row.classList.toggle("is-selected", check.checked && amount > 0);
    });
    total = cents(total);
    totalOutput.textContent = money.format(total);
    remainingOutput.textContent = money.format(Math.max(credit - total, 0));
    const overLimit = total > credit + 0.001;
    error.hidden = !overLimit;
    submit.disabled = overLimit || total <= 0;
  };

  rows.forEach((row) => {
    const check = row.querySelector("[data-credit-apply-check]");
    const input = row.querySelector("[data-credit-apply-amount]");
    check.addEventListener("change", () => {
      // Al marcar un pedido se propone cubrirlo con lo que quede de saldo.
      input.value = check.checked
        ? cents(Math.max(Math.min(cents(row.dataset.balance), credit - appliedTotal(row)), 0)).toFixed(2)
        : "0.00";
      refresh();
    });
    input.addEventListener("input", refresh);
  });
  refresh();
})();
