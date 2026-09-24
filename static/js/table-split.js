/* NOTA TEMPORAL PARA APRENDIZAJE: este panel vive en su propio <dialog>, separado del
diálogo normal de cobro, a propósito — así su CSS no pelea con el layout ya delicado del
otro. "Regresar" siempre reinicia todo el estado de la división; volver a abrir "Dividir
cuenta" empieza de cero cada vez (así se confirmó con el desarrollador). El responsable
de la mesa es uno solo para todas las cuentas divididas; sólo el método de pago, la
propina y el efectivo cambian por cuenta. Borra esta nota después de leerla. */
(() => {
  const splitDialog = document.querySelector("[data-split-dialog]");
  const splitLauncher = document.querySelector("[data-split-account-open]");
  if (!splitDialog || !splitLauncher) return;

  const MIN_SPLITS = 2;
  const MAX_SPLITS = 6;
  let splitCount = 2;

  const money = (value) => `$${Number(value || 0).toFixed(2)}`;
  const csrfToken = () => document.querySelector("[data-print-csrf] input[name='csrfmiddlewaretoken']")?.value || "";
  const closeAccountDialog = document.querySelector("[data-close-account-dialog]");
  const countValue = splitDialog.querySelector("[data-split-count-value]");
  const itemsList = splitDialog.querySelector("[data-split-items-list]");
  const itemsError = splitDialog.querySelector("[data-split-items-error]");
  const accountsContainer = splitDialog.querySelector("[data-split-accounts]");
  const responsibleButtons = [...splitDialog.querySelectorAll("[data-split-responsible]")];
  const responsibleError = splitDialog.querySelector("[data-split-responsible-error]");
  const splitError = splitDialog.querySelector("[data-split-error]");
  const submitButton = splitDialog.querySelector("[data-split-submit]");
  let responsibleWaiterId = "";

  function splitSubtotalFor(index) {
    let subtotal = 0;
    itemsList.querySelectorAll("[data-split-item]").forEach((item) => {
      if (Number(item.dataset.assignedSplit) === index) subtotal += Number(item.dataset.itemSubtotal);
    });
    return subtotal;
  }

  function recalcSplitCard(card) {
    const index = Number(card.dataset.splitAccount);
    const subtotal = splitSubtotalFor(index);
    const tip = Number(card.querySelector("[data-split-tip]").value || 0);
    card.querySelector("[data-split-subtotal]").textContent = money(subtotal);
    card.querySelector("[data-split-total]").textContent = money(subtotal + tip);
  }

  function recalcAllSplitCards() {
    accountsContainer.querySelectorAll("[data-split-account]").forEach(recalcSplitCard);
  }

  function renderItemButtons() {
    itemsList.querySelectorAll("[data-split-item]").forEach((item) => {
      const assigned = Number(item.dataset.assignedSplit || 0);
      if (assigned > splitCount) item.dataset.assignedSplit = "";
      const container = item.querySelector("[data-split-item-buttons]");
      container.innerHTML = "";
      for (let i = 1; i <= splitCount; i += 1) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = String(i);
        button.dataset.splitItemAssign = String(i);
        button.classList.toggle("is-selected", Number(item.dataset.assignedSplit) === i);
        container.append(button);
      }
    });
  }

  function buildSplitAccountCard(index) {
    const card = document.createElement("article");
    card.className = "table-split-account-card";
    card.dataset.splitAccount = String(index);
    card.innerHTML = `
      <h3>Cuenta ${index}</h3>
      <p>Subtotal: <strong data-split-subtotal>$0.00</strong></p>
      <div class="cashier-payment-buttons" data-split-payment-buttons>
        <button type="button" data-split-payment-method="cash">Efectivo</button>
        <button type="button" data-split-payment-method="card">Terminal</button>
        <button type="button" data-split-payment-method="transfer">Transferencia</button>
      </div>
      <div class="table-split-cash-fields" data-split-cash-fields hidden>
        <div class="cash-quick-buttons">
          <button type="button" data-split-cash-amount="20">$20</button>
          <button type="button" data-split-cash-amount="50">$50</button>
          <button type="button" data-split-cash-amount="100">$100</button>
          <button type="button" data-split-cash-amount="200">$200</button>
          <button type="button" data-split-cash-amount="500">$500</button>
          <button type="button" data-split-cash-amount="exact">Exacto</button>
        </div>
        <label>Otro $<input type="number" min="0" step="0.01" data-split-custom-cash></label>
      </div>
      <label class="table-split-tip-field">Propina $<input type="number" min="0" step="0.01" value="0" data-split-tip></label>
      <p>Total con propina: <strong data-split-total>$0.00</strong></p>
    `;
    return card;
  }

  function ensureSplitAccountCards() {
    accountsContainer.querySelectorAll("[data-split-account]").forEach((card) => {
      if (Number(card.dataset.splitAccount) > splitCount) card.remove();
    });
    for (let i = 1; i <= splitCount; i += 1) {
      if (!accountsContainer.querySelector(`[data-split-account="${i}"]`)) {
        accountsContainer.append(buildSplitAccountCard(i));
      }
    }
  }

  function setSplitCount(next) {
    splitCount = Math.max(MIN_SPLITS, Math.min(MAX_SPLITS, next));
    countValue.textContent = String(splitCount);
    ensureSplitAccountCards();
    renderItemButtons();
    recalcAllSplitCards();
  }

  function resetSplitState() {
    itemsList.querySelectorAll("[data-split-item]").forEach((item) => { item.dataset.assignedSplit = ""; });
    accountsContainer.innerHTML = "";
    responsibleWaiterId = "";
    responsibleButtons.forEach((button) => button.classList.remove("is-selected"));
    itemsError.hidden = true;
    responsibleError.hidden = true;
    splitError.hidden = true;
    setSplitCount(2);
  }

  splitDialog.querySelector("[data-split-count-decrease]").addEventListener("click", () => setSplitCount(splitCount - 1));
  splitDialog.querySelector("[data-split-count-increase]").addEventListener("click", () => setSplitCount(splitCount + 1));

  itemsList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-split-item-assign]");
    if (!button) return;
    const item = button.closest("[data-split-item]");
    item.dataset.assignedSplit = button.dataset.splitItemAssign;
    item.querySelectorAll("[data-split-item-assign]").forEach((candidate) => candidate.classList.toggle("is-selected", candidate === button));
    itemsError.hidden = true;
    recalcAllSplitCards();
  });

  accountsContainer.addEventListener("click", (event) => {
    const methodButton = event.target.closest("[data-split-payment-method]");
    if (methodButton) {
      const card = methodButton.closest("[data-split-account]");
      card.dataset.paymentMethod = methodButton.dataset.splitPaymentMethod;
      card.querySelectorAll("[data-split-payment-method]").forEach((candidate) => candidate.classList.toggle("is-selected", candidate === methodButton));
      card.querySelector("[data-split-cash-fields]").hidden = card.dataset.paymentMethod !== "cash";
      recalcSplitCard(card);
      return;
    }
    const cashButton = event.target.closest("[data-split-cash-amount]");
    if (cashButton) {
      const card = cashButton.closest("[data-split-account]");
      const customCash = card.querySelector("[data-split-custom-cash]");
      if (cashButton.dataset.splitCashAmount === "exact") {
        card.dataset.paysExact = "1";
        customCash.value = "";
        customCash.disabled = true;
      } else {
        card.dataset.paysExact = "";
        customCash.disabled = false;
        customCash.value = cashButton.dataset.splitCashAmount;
      }
      card.querySelectorAll("[data-split-cash-amount]").forEach((candidate) => candidate.classList.toggle("is-selected", candidate === cashButton));
      recalcSplitCard(card);
    }
  });

  accountsContainer.addEventListener("input", (event) => {
    const card = event.target.closest("[data-split-account]");
    if (!card) return;
    if (event.target.matches("[data-split-custom-cash]")) {
      card.dataset.paysExact = "";
      card.querySelectorAll("[data-split-cash-amount]").forEach((candidate) => candidate.classList.remove("is-selected"));
    }
    recalcSplitCard(card);
  });

  responsibleButtons.forEach((button) => {
    button.addEventListener("click", () => {
      responsibleWaiterId = button.dataset.splitResponsible;
      responsibleError.hidden = true;
      responsibleButtons.forEach((candidate) => candidate.classList.toggle("is-selected", candidate === button));
    });
  });

  splitLauncher.addEventListener("click", () => {
    closeAccountDialog?.close();
    resetSplitState();
    splitDialog.showModal();
  });
  splitDialog.querySelector("[data-split-dialog-close]").addEventListener("click", () => splitDialog.close());
  splitDialog.querySelector("[data-split-back]").addEventListener("click", () => {
    splitDialog.close();
    resetSplitState();
    closeAccountDialog?.showModal();
  });

  submitButton.addEventListener("click", async () => {
    splitError.hidden = true;
    const items = [...itemsList.querySelectorAll("[data-split-item]")];
    const unassigned = items.filter((item) => !item.dataset.assignedSplit);
    itemsError.hidden = unassigned.length === 0;
    if (unassigned.length) return;
    if (!responsibleWaiterId) { responsibleError.hidden = false; return; }
    const splits = [];
    for (let i = 1; i <= splitCount; i += 1) {
      const card = accountsContainer.querySelector(`[data-split-account="${i}"]`);
      const itemIds = items.filter((item) => Number(item.dataset.assignedSplit) === i).map((item) => Number(item.dataset.itemId));
      if (!itemIds.length) { splitError.textContent = `La cuenta ${i} no tiene artículos asignados.`; splitError.hidden = false; return; }
      const method = card.dataset.paymentMethod;
      if (!method) { splitError.textContent = `Selecciona el método de pago de la cuenta ${i}.`; splitError.hidden = false; return; }
      const tip = Number(card.querySelector("[data-split-tip]").value || 0);
      let cashTendered = null;
      if (method === "cash") {
        const total = splitSubtotalFor(i) + tip;
        if (card.dataset.paysExact === "1") {
          cashTendered = total;
        } else {
          const customCash = Number(card.querySelector("[data-split-custom-cash]").value || 0);
          if (!customCash || customCash < total) { splitError.textContent = `El efectivo de la cuenta ${i} no cubre su total.`; splitError.hidden = false; return; }
          cashTendered = customCash;
        }
      }
      splits.push({
        item_ids: itemIds, payment_method: method, tip_amount: String(tip),
        cash_tendered: cashTendered !== null ? String(cashTendered) : null,
      });
    }
    submitButton.disabled = true;
    try {
      const response = await fetch(splitDialog.dataset.splitUrl, {
        method: "POST", credentials: "same-origin",
        headers: {"Content-Type": "application/json", "X-CSRFToken": csrfToken()},
        body: JSON.stringify({responsible_waiter: responsibleWaiterId, splits}),
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || "No se pudo dividir la cuenta.");
      window.location.href = result.redirect_url;
    } catch (error) {
      splitError.textContent = error.message; splitError.hidden = false;
    } finally {
      submitButton.disabled = false;
    }
  });
})();
