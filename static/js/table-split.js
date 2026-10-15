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
  const MAX_SPLITS = 10;
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

  function renderItemRows() {
    // NOTA TEMPORAL PARA APRENDIZAJE: antes esta lista se armaba una sola vez en el
    // servidor al cargar la página; si se agregaban o quitaban artículos por AJAX
    // después (sin recargar, que es como funciona el resto de Mesas), el panel de
    // dividir se quedaba con una foto vieja del ticket — hasta vacía si se abrió con la
    // cuenta recién creada. Ahora se reconstruye aquí, cada vez que se abre el panel,
    // leyendo `window.__tableTicketItems` (lo mantiene al día table-pos.js, tanto al
    // cargar la página como después de cada cambio en el ticket). Borra esta nota.
    //
    // NOTA TEMPORAL PARA APRENDIZAJE: cuando dos comidas idénticas quedan agrupadas en
    // una sola partida del ticket (mismo producto/paquete, `quantity` > 1), antes sólo
    // se podía repartir el grupo completo a una sola cuenta dividida. Ahora se dibuja
    // una fila por CADA unidad (misma `item_id`, cantidad de filas = `item.quantity`),
    // para poder asignar cada una a una cuenta distinta; el envío al servidor las vuelve
    // a agrupar por `item_id` contando cuántas unidades le tocaron a cada cuenta. Borra
    // esta nota después de leerla.
    const liveItems = window.__tableTicketItems || [];
    itemsList.innerHTML = "";
    liveItems.forEach((item) => {
      const quantity = Math.max(1, Number(item.quantity) || 1);
      const unitSubtotal = Number(item.subtotal) / quantity;
      for (let unit = 1; unit <= quantity; unit += 1) {
        const row = document.createElement("div");
        row.className = "table-split-item";
        row.dataset.splitItem = "";
        row.dataset.itemId = String(item.item_id);
        row.dataset.itemSubtotal = String(unitSubtotal);
        row.dataset.assignedSplit = "";
        const name = document.createElement("span");
        name.className = "table-split-item-name";
        name.textContent = quantity > 1 ? `${item.name} (${unit}/${quantity})` : item.name;
        const price = document.createElement("span");
        price.className = "table-split-item-price";
        price.textContent = money(unitSubtotal);
        const buttons = document.createElement("div");
        buttons.className = "table-split-item-buttons";
        buttons.dataset.splitItemButtons = "";
        row.append(name, price, buttons);
        itemsList.append(row);
      }
    });
  }

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
    // En efectivo no hay propina (Mesas, 2026-10-15).
    const isCash = card.dataset.paymentMethod === "cash";
    const tip = isCash ? 0 : Number(card.querySelector("[data-split-tip]").value || 0);
    card.querySelector("[data-split-subtotal]").textContent = money(subtotal);
    card.querySelector("[data-split-total]").textContent = money(subtotal + tip);
    card.querySelector("[data-split-total-label]").textContent = isCash ? "Total:" : "Total con propina:";
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
      <label class="table-split-tip-field" data-split-tip-field>Propina $<input type="number" min="0" step="0.01" value="0" data-split-tip></label>
      <p><span data-split-total-label>Total con propina:</span> <strong data-split-total>$0.00</strong></p>
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
    renderItemRows();
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
      const tipField = card.querySelector("[data-split-tip-field]");
      tipField.hidden = card.dataset.paymentMethod === "cash";
      if (tipField.hidden) tipField.querySelector("input").value = "0";
      recalcSplitCard(card);
    }
  });

  accountsContainer.addEventListener("input", (event) => {
    const card = event.target.closest("[data-split-account]");
    if (!card) return;
    recalcSplitCard(card);
  });

  // NOTA TEMPORAL PARA APRENDIZAJE: igual que en el diálogo de cobro normal, al enfocar
  // un campo de propina que sigue en "0" se borra para escribir directo; si lo dejan
  // vacío al salir, vuelve a "0". Se delega en el contenedor porque las tarjetas de
  // cuenta se crean dinámicamente. Borra esta nota después de leerla.
  accountsContainer.addEventListener("focusin", (event) => {
    if (event.target.matches("[data-split-tip]") && event.target.value === "0") event.target.value = "";
  });
  accountsContainer.addEventListener("focusout", (event) => {
    if (event.target.matches("[data-split-tip]") && event.target.value === "") event.target.value = "0";
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
      const assignedRows = items.filter((item) => Number(item.dataset.assignedSplit) === i);
      if (!assignedRows.length) { splitError.textContent = `La cuenta ${i} no tiene artículos asignados.`; splitError.hidden = false; return; }
      const quantitiesByItemId = {};
      assignedRows.forEach((row) => {
        const itemId = Number(row.dataset.itemId);
        quantitiesByItemId[itemId] = (quantitiesByItemId[itemId] || 0) + 1;
      });
      const splitItems = Object.entries(quantitiesByItemId).map(([itemId, quantity]) => ({item_id: Number(itemId), quantity}));
      const method = card.dataset.paymentMethod;
      if (!method) { splitError.textContent = `Selecciona el método de pago de la cuenta ${i}.`; splitError.hidden = false; return; }
      const tip = method === "cash" ? 0 : Number(card.querySelector("[data-split-tip]").value || 0);
      splits.push({items: splitItems, payment_method: method, tip_amount: String(tip)});
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
