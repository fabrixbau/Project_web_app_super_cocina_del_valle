/* NOTA TEMPORAL PARA APRENDIZAJE: La barra superior modifica los campos reales del formulario. Los paneles se ocultan para ahorrar espacio, pero Django recibe y valida los mismos datos al guardar. Borra esta nota. */
(() => {
  const form = document.querySelector("[data-internal-order-form]");
  if (!form) return;
  const paymentChoices = document.querySelectorAll("[data-payment-choice]");
  const orderTypeChoices = document.querySelectorAll("[data-order-type-choice]");
  const delivery = form.querySelector("[data-delivery-fields]");
  const cash = document.querySelector("[data-cash-fields]");
  const customerPanel = form.querySelector("[data-customer-panel]");
  const customerSummary = form.querySelector("[data-customer-summary]");
  const customerState = form.querySelector("[data-customer-state]");
  const autosaveState = form.querySelector("[data-autosave-state]");
  const ticketPayment = document.querySelector("[data-ticket-payment]");
  const ticketChangeRow = document.querySelector("[data-ticket-change-row]");
  const ticketChange = document.querySelector("[data-ticket-change]");
  const ticketCashSource = document.querySelector("[data-ticket-cash-source]");
  const ticketCashAmount = document.querySelector("[data-ticket-cash-amount]");
  const tipSection = document.querySelector("[data-internal-tip-section]");
  const tipForm = document.querySelector("[data-internal-tip-form]");
  const deliveryCashHint = cash?.querySelector("[data-delivery-cash-hint]");
  const agendaSearch = form.querySelector("input[name='customer_name']");
  const agendaResults = form.querySelector("[data-customer-agenda-results]");
  const agendaHelp = form.querySelector("[data-customer-agenda-help]");
  const duplicatePhoneWarning = form.querySelector("[data-duplicate-phone-warning]");
  const customerDebtWarning = form.querySelector("[data-customer-debt-warning]");
  const paymentControl = document.querySelector(".ticket-payment-control");
  const paymentDetails = document.createElement("div");
  paymentDetails.className = "ticket-payment-details";
  paymentDetails.dataset.ticketPaymentDetails = "";
  paymentControl?.after(paymentDetails);
  if (paymentControl && cash) {
    cash.querySelectorAll("input, select, textarea").forEach((control) => control.setAttribute("form", form.id));
    paymentDetails.append(cash);
  }
  if (paymentControl && tipSection) paymentDetails.append(tipSection);
  const captureHeading = document.querySelector(".internal-capture-heading");
  const commandBar = form.querySelector(".internal-command-bar");
  const modalityCommand = commandBar?.querySelector(":scope > .command-group:first-child");
  const customerCommand = commandBar?.querySelector(":scope > .customer-command");
  const headingActions = captureHeading?.querySelector(".capture-heading-actions");
  if (captureHeading && headingActions && modalityCommand && customerCommand) {
    headingActions.before(modalityCommand, customerCommand);
    commandBar.hidden = true;
  }
  const formField = (name) => form.elements.namedItem(name);
  const paymentLabels = {cash: "Efectivo", card: "Terminal", transfer: "Transferencia"};
  const refresh = () => {
    const orderType = form.querySelector("input[name='order_type']:checked")?.value || "pickup";
    const paymentMethod = form.querySelector("input[name='payment_method']:checked")?.value || "";
    delivery.hidden = orderType !== "delivery";
    cash.hidden = paymentMethod !== "cash";
    if (deliveryCashHint) deliveryCashHint.hidden = orderType !== "delivery";
    // NOTA TEMPORAL PARA APRENDIZAJE: Telefonista aún puede registrar una propina
    // confirmada por transferencia, pero Terminal se captura después por Caja o por
    // el repartidor cuando realmente se conoce. Borra esta nota después de leerla.
    if (tipSection) tipSection.hidden = !(orderType === "delivery" && paymentMethod === "transfer");
    orderTypeChoices.forEach((button) => button.classList.toggle("is-selected", button.dataset.orderTypeChoice === orderType));
    paymentChoices.forEach((button) => button.classList.toggle("is-selected", button.dataset.paymentChoice === paymentMethod));
    if (ticketPayment) ticketPayment.textContent = paymentLabels[paymentMethod] || "Sin definir";
    const bill = Number(formField("cash_bill")?.value || 0);
    const customCash = Number(formField("cash_custom_amount")?.value || 0);
    const total = Number(form.dataset.orderTotal || 0);
    const tendered = bill || customCash;
    const showChange = paymentMethod === "cash" && tendered >= total && tendered > 0 && !formField("pays_exact")?.checked;
    if (ticketCashSource) ticketCashSource.hidden = paymentMethod !== "cash" || tendered <= 0;
    if (ticketCashAmount) ticketCashAmount.textContent = new Intl.NumberFormat("es-MX", {style: "currency", currency: "MXN"}).format(tendered);
    if (ticketChangeRow) ticketChangeRow.hidden = !showChange;
    if (ticketChange) ticketChange.textContent = new Intl.NumberFormat("es-MX", {style: "currency", currency: "MXN"}).format(Math.max(tendered - total, 0));
    const customerName = form.querySelector("input[name='customer_name']")?.value.trim();
    if (customerSummary) customerSummary.textContent = customerName || "Datos del cliente";
    if (customerState) customerState.textContent = customerName ? (orderType === "delivery" ? "Revisar entrega" : "Editar datos") : "Agregar datos";
    if (agendaHelp) agendaHelp.textContent = orderType === "delivery"
      ? "Si coincide con la agenda, selecciona el cliente o uno de sus domicilios."
      : "Si coincide con la agenda, selecciónalo para completar nombre y teléfono.";
  };
  form.addEventListener("change", refresh);
  form.addEventListener("input", refresh);
  orderTypeChoices.forEach((button) => button.addEventListener("click", () => {
    const field = form.querySelector(`input[name='order_type'][value='${button.dataset.orderTypeChoice}']`);
    if (field) field.checked = true;
    const customerNameField = form.querySelector("input[name='customer_name']");
    if (button.dataset.orderTypeChoice === "pickup" && customerNameField && !customerNameField.value.trim()) {
      customerNameField.value = "Mostrador";
    }
    if (button.dataset.orderTypeChoice === "delivery") {
      const neighborhood = form.querySelector("input[name='neighborhood']");
      if (neighborhood && !neighborhood.value.trim()) neighborhood.value = "del valle centro";
    }
    refresh();
    scheduleAutosave();
  }));
  paymentChoices.forEach((button) => button.addEventListener("click", async () => {
    const field = form.querySelector(`input[name='payment_method'][value='${button.dataset.paymentChoice}']`);
    if (field) field.checked = true;
    // NOTA TEMPORAL PARA APRENDIZAJE: al pasar al pago cerramos Cliente para que
    // ambos paneles no compitan por espacio. Efectivo muestra sus billetes mediante
    // refresh() en la siguiente línea. Borra esta nota después de leerla.
    customerPanel.hidden = true;
    refresh();
    window.clearTimeout(autosaveTimer);
    await autosaveCustomer();
  }));
  document.querySelectorAll("[data-customer-panel-toggle]").forEach((button) => button.addEventListener("click", () => {
    customerPanel.hidden = !customerPanel.hidden;
  }));
  form.querySelectorAll("[data-customer-panel-close]").forEach((button) => button.addEventListener("click", () => { customerPanel.hidden = true; }));

  const compactCustomerView = window.matchMedia("(max-width: 900px)");
  const customerFieldBackdrop = document.createElement("button");
  customerFieldBackdrop.type = "button";
  customerFieldBackdrop.className = "customer-field-backdrop";
  customerFieldBackdrop.setAttribute("aria-label", "Cerrar campo del cliente");
  customerFieldBackdrop.hidden = true;
  document.body.append(customerFieldBackdrop);
  let focusedCustomerLabel = null;
  const closeCustomerField = () => {
    focusedCustomerLabel?.classList.remove("is-customer-field-focused");
    focusedCustomerLabel = null;
    customerFieldBackdrop.hidden = true;
    document.body.classList.remove("customer-field-focus-open");
    document.activeElement?.blur?.();
  };
  customerPanel.querySelectorAll(".internal-form-grid label, .customer-notes-field").forEach((label) => {
    label.addEventListener("focusin", () => {
      if (!compactCustomerView.matches) return;
      focusedCustomerLabel?.classList.remove("is-customer-field-focused");
      focusedCustomerLabel = label;
      label.classList.add("is-customer-field-focused");
      customerFieldBackdrop.hidden = false;
      document.body.classList.add("customer-field-focus-open");
    });
  });
  customerFieldBackdrop.addEventListener("click", closeCustomerField);
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeCustomerField(); });
  compactCustomerView.addEventListener?.("change", (event) => { if (!event.matches) closeCustomerField(); });

  // NOTA TEMPORAL PARA APRENDIZAJE: `select()` mantiene Mostrador como valor útil,
  // pero permite que el primer carácter escrito lo reemplace completo. Borra esta nota.
  const customerNameField = form.querySelector("input[name='customer_name']");
  customerNameField?.addEventListener("focus", () => {
    if (customerNameField.value.trim().toLocaleLowerCase("es-MX") === "mostrador") {
      window.requestAnimationFrame(() => customerNameField.select());
    }
  });

  let autosaveTimer = null;
  async function autosaveCustomer() {
    if (!form.dataset.autosaveUrl) return;
    if (autosaveState) autosaveState.textContent = "Guardando…";
    try {
      const response = await fetch(form.dataset.autosaveUrl, {
        method: "POST", body: new FormData(form),
        headers: {"X-CSRFToken": form.querySelector("input[name='csrfmiddlewaretoken']").value, "X-Requested-With": "XMLHttpRequest"},
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error("No se pudieron guardar los datos.");
      const tipInput = tipForm?.querySelector("input[name='tip_amount']");
      if (tipInput && data.delivery_tip_amount !== undefined) tipInput.value = data.delivery_tip_amount;
      if (data.agenda_customer_id) form.querySelector("input[name='agenda_customer_id']").value = data.agenda_customer_id;
      if (data.agenda_address_id) form.querySelector("input[name='agenda_address_id']").value = data.agenda_address_id;
      if (data.duplicate_customer) showDuplicateCustomer(data.duplicate_customer);
      if (autosaveState) autosaveState.textContent = "Datos guardados automáticamente";
    } catch (error) {
      if (autosaveState) autosaveState.textContent = "No se pudo guardar; revisa los campos";
    }
  }
  function scheduleAutosave() {
    window.clearTimeout(autosaveTimer);
    if (autosaveState) autosaveState.textContent = "Cambios pendientes…";
    autosaveTimer = window.setTimeout(autosaveCustomer, 650);
  }

  // NOTA TEMPORAL PARA APRENDIZAJE: la búsqueda sólo trae fichas internas. Al
  // elegir un domicilio copiamos sus valores a los campos reales y usamos el mismo
  // autoguardado existente. Borra esta nota después de leerla.
  let agendaTimer = null;
  let agendaRequestVersion = 0;
  const setFieldValue = (name, value) => {
    const field = form.querySelector(`[name='${name}']`);
    if (field) field.value = value || "";
  };
  function showCustomerDebt(customer) {
    if (!customerDebtWarning) return;
    const balance = Number(customer?.outstanding_balance || 0);
    customerDebtWarning.replaceChildren();
    if (!balance) { customerDebtWarning.hidden = true; return; }
    const message = document.createElement("strong");
    message.textContent = `Este cliente tiene $${balance.toFixed(2)} pendientes en ${customer.open_debt_count} pedido(s). `;
    const link = document.createElement("a");
    link.href = customer.debt_url;
    link.textContent = "Revisar adeudo";
    customerDebtWarning.append(message, link);
    customerDebtWarning.hidden = false;
  }
  function selectAgendaAddress(customer, address) {
    // NOTA TEMPORAL PARA APRENDIZAJE: invalidamos cualquier consulta anterior para
    // que una respuesta lenta no vuelva a abrir el menú después de seleccionar.
    // Borra esta nota después de leerla.
    agendaRequestVersion += 1;
    window.clearTimeout(agendaTimer);
    setFieldValue("agenda_customer_id", customer.id);
    setFieldValue("customer_name", customer.name);
    setFieldValue("phone", customer.phone);
    const orderType = form.querySelector("input[name='order_type']:checked")?.value || "pickup";
    setFieldValue("agenda_address_id", orderType === "delivery" ? (address?.id || "") : "");
    // NOTA TEMPORAL PARA APRENDIZAJE: Recoger reutiliza la identidad del contacto,
    // pero no su domicilio. Entrega conserva el comportamiento completo existente.
    // Borra esta nota después de leerla.
    if (orderType === "delivery" && address) {
      setFieldValue("street", address.street);
      setFieldValue("exterior_number", address.exterior_number);
      setFieldValue("interior_number", address.interior_number);
      setFieldValue("neighborhood", address.neighborhood);
      setFieldValue("references", address.references);
    }
    agendaResults.hidden = true;
    customerPanel.hidden = true;
    closeCustomerField();
    if (duplicatePhoneWarning) duplicatePhoneWarning.hidden = true;
    showCustomerDebt(customer);
    refresh();
    window.clearTimeout(autosaveTimer);
    autosaveCustomer();
  }
  function renderAgendaResults(customers) {
    agendaResults.replaceChildren();
    if (!customers.length) {
      const empty = document.createElement("p");
      empty.textContent = "No encontramos clientes.";
      agendaResults.append(empty);
    }
    customers.forEach((customer) => {
      const orderType = form.querySelector("input[name='order_type']:checked")?.value || "pickup";
      const card = document.createElement("article");
      const heading = document.createElement("button");
      heading.type = "button";
      heading.className = "customer-agenda-name";
      heading.textContent = `${customer.name}${customer.phone ? ` · ${customer.phone}` : ""}`;
      heading.addEventListener("click", () => selectAgendaAddress(customer, customer.addresses[0] || null));
      card.append(heading);
      if (orderType === "delivery") (customer.addresses.length ? customer.addresses : [null]).forEach((address) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = address ? `${address.street} ${address.exterior_number}${address.neighborhood ? ` · ${address.neighborhood}` : ""}` : "Usar datos del cliente";
        button.addEventListener("click", () => selectAgendaAddress(customer, address));
        card.append(button);
      });
      agendaResults.append(card);
    });
    agendaResults.hidden = false;
  }
  agendaSearch?.addEventListener("input", () => {
    window.clearTimeout(agendaTimer);
    agendaRequestVersion += 1;
    const requestVersion = agendaRequestVersion;
    const query = agendaSearch.value.trim();
    if (query.length < 2) {
      agendaResults.hidden = true;
      return;
    }
    agendaTimer = window.setTimeout(async () => {
      try {
        const response = await fetch(`${form.dataset.customerLookupUrl}?q=${encodeURIComponent(query)}`, {headers: {"Accept": "application/json"}});
        const data = await response.json();
        if (!response.ok) throw new Error();
        if (requestVersion !== agendaRequestVersion || agendaSearch.value.trim() !== query) return;
        renderAgendaResults(data.customers || []);
      } catch (error) {
        if (requestVersion !== agendaRequestVersion) return;
        agendaResults.replaceChildren();
        const message = document.createElement("p");
        message.textContent = "No se pudo consultar la agenda.";
        agendaResults.append(message);
        agendaResults.hidden = false;
      }
    }, 300);
  });
  agendaSearch?.addEventListener("blur", () => {
    window.setTimeout(() => {
      if (!agendaResults.contains(document.activeElement)) agendaResults.hidden = true;
    }, 160);
  });

  let phoneLookupTimer = null;
  const normalizePhone = (value) => {
    const digits = Array.from(value).filter((character) => /[0-9]/.test(character)).join("");
    return digits.length === 12 && digits.startsWith("52") ? digits.slice(2) : digits;
  };
  function showDuplicateCustomer(duplicate) {
    duplicatePhoneWarning.replaceChildren();
    duplicatePhoneWarning.append(document.createTextNode(`Este teléfono ya pertenece a ${duplicate.name}. `));
    const review = document.createElement("a");
    review.href = duplicate.edit_url;
    review.textContent = "Revisar contacto";
    review.target = "_blank";
    duplicatePhoneWarning.append(review, document.createTextNode(" · "));
    const use = document.createElement("button");
    use.type = "button";
    use.textContent = "Usar este cliente";
    use.addEventListener("click", () => selectAgendaAddress(duplicate, duplicate.addresses[0] || null));
    duplicatePhoneWarning.append(use);
    duplicatePhoneWarning.hidden = false;
  }
  form.querySelector("input[name='phone']")?.addEventListener("input", (event) => {
    window.clearTimeout(phoneLookupTimer);
    const phone = normalizePhone(event.target.value);
    if (phone.length < 5) {
      duplicatePhoneWarning.hidden = true;
      return;
    }
    phoneLookupTimer = window.setTimeout(async () => {
      try {
        const response = await fetch(`${form.dataset.customerLookupUrl}?q=${encodeURIComponent(phone)}`, {headers: {"Accept": "application/json"}});
        const data = await response.json();
        const duplicate = (data.customers || []).find((customer) => normalizePhone(customer.phone) === phone);
        duplicatePhoneWarning.replaceChildren();
        if (!duplicate) {
          duplicatePhoneWarning.hidden = true;
          return;
        }
        duplicatePhoneWarning.append(document.createTextNode(`Este teléfono ya pertenece a ${duplicate.name}. `));
        const review = document.createElement("a");
        review.href = duplicate.edit_url;
        review.textContent = "Revisar contacto";
        review.target = "_blank";
        duplicatePhoneWarning.append(review, document.createTextNode(" · "));
        const use = document.createElement("button");
        use.type = "button";
        use.textContent = "Usar este cliente";
        use.addEventListener("click", () => selectAgendaAddress(duplicate, duplicate.addresses[0] || null));
        duplicatePhoneWarning.append(use);
        duplicatePhoneWarning.hidden = false;
      } catch (error) {
        duplicatePhoneWarning.hidden = true;
      }
    }, 350);
  });
  if (form.querySelector("input[name='phone']")?.value.trim()) {
    form.querySelector("input[name='phone']").dispatchEvent(new Event("input"));
  }

  let tipTimer = null;
  async function saveInternalTip() {
    if (!tipForm) return;
    const state = tipForm.querySelector("[data-internal-tip-state]");
    if (state) state.textContent = "Guardando propina…";
    try {
      const response = await fetch(tipForm.getAttribute("action"), {
        method: "POST", body: new FormData(tipForm),
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": tipForm.querySelector("input[name='csrfmiddlewaretoken']").value,
          "Accept": "application/json",
        },
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || "No se pudo guardar la propina.");
      if (state) state.textContent = `Propina guardada: $${data.tip_amount} · Para: ${data.recipient}`;
    } catch (error) {
      if (state) state.textContent = error.message;
    }
  }
  tipForm?.querySelectorAll("[data-internal-tip-value]").forEach((button) => button.addEventListener("click", () => {
    tipForm.querySelector("input[name='tip_amount']").value = button.dataset.internalTipValue;
    window.clearTimeout(tipTimer);
    saveInternalTip();
  }));
  tipForm?.querySelector("input[name='tip_amount']")?.addEventListener("input", () => {
    window.clearTimeout(tipTimer);
    tipTimer = window.setTimeout(saveInternalTip, 600);
  });
  customerPanel.querySelectorAll("input, textarea, select").forEach((field) => {
    field.addEventListener(field.matches("select, input[type='date'], input[type='time']") ? "change" : "input", scheduleAutosave);
  });
  form.querySelectorAll("[data-customer-panel-close]").forEach((button) => button.addEventListener("click", () => {
    window.clearTimeout(autosaveTimer); autosaveCustomer();
  }));
  const errorSummary = form.querySelector("[data-capture-error-summary]");
  if (errorSummary) {
    customerPanel.hidden = false;
    window.requestAnimationFrame(() => {
      const targetSelector = errorSummary.querySelector("a[href^='#']")?.getAttribute("href");
      let target = form.querySelector(targetSelector || "[name='customer_name']");
      if (target?.name === "payment_method") target = document.querySelector("[data-payment-choice]");
      if (target?.name === "cash_bill") target = document.querySelector("[data-cash-value]");
      // NOTA TEMPORAL PARA APRENDIZAJE: primero mostramos el resumen y después dejamos
      // visible y enfocado el campo que realmente debe corregirse. Borra esta nota.
      errorSummary.scrollIntoView({behavior: "smooth", block: "center"});
      window.setTimeout(() => {
        target?.scrollIntoView({behavior: "smooth", block: "center"});
        target?.focus({preventScroll: true});
      }, 350);
    });
  }
  document.querySelectorAll("[data-cash-value]").forEach((button) => button.addEventListener("click", () => {
    const cashMethod = form.querySelector("input[name='payment_method'][value='cash']");
    const bill = formField("cash_bill");
    if (cashMethod) cashMethod.checked = true;
    if (bill) bill.value = button.dataset.cashValue;
    const custom = formField("cash_custom_amount");
    const exact = formField("pays_exact");
    if (custom) custom.value = "";
    if (exact) exact.checked = false;
    refresh();
  }));
  const exact = formField("pays_exact");
  exact?.addEventListener("change", () => {
    if (!exact.checked) return;
    const cashMethod = form.querySelector("input[name='payment_method'][value='cash']");
    const bill = formField("cash_bill");
    const custom = formField("cash_custom_amount");
    if (cashMethod) cashMethod.checked = true;
    if (bill) bill.value = "";
    if (custom) custom.value = "";
    refresh();
  });
  const customCash = formField("cash_custom_amount");
  customCash?.addEventListener("input", () => {
    if (!customCash.value) return;
    const cashMethod = form.querySelector("input[name='payment_method'][value='cash']");
    const bill = formField("cash_bill");
    if (cashMethod) cashMethod.checked = true;
    if (bill) bill.value = "";
    if (exact) exact.checked = false;
    refresh();
  });
  refresh();

  const capture = document.querySelector("[data-internal-capture]");
  if (!capture) return;
  const csrf = document.querySelector("input[name='csrfmiddlewaretoken']")?.value;
  const ticketItems = capture.querySelector("[data-internal-ticket-items]");
  const ticketTotal = capture.querySelector("[data-internal-total]");
  const ticketCount = capture.querySelector("[data-internal-count]");
  const quantitiesNode = document.querySelector("#internal-standard-quantities");
  const candidateQuantitiesNode = document.querySelector("#internal-candidate-quantities");
  const currency = new Intl.NumberFormat("es-MX", {style: "currency", currency: "MXN"});
  const search = capture.querySelector("[data-internal-search]");
  const searchSection = capture.querySelector("[data-internal-search-results]");
  const searchGrid = capture.querySelector("[data-internal-search-grid]");
  const searchEmpty = capture.querySelector("[data-internal-search-empty]");
  const sourceCards = [...capture.querySelectorAll(".internal-category [data-product-name]")];
  const ticketDataNode = document.querySelector("#internal-ticket-data");
  const noteConfig = document.querySelector("[data-order-note-config]");
  const noteDialog = document.querySelector("[data-ticket-note-dialog]");
  const noteForm = noteDialog?.querySelector("[data-ticket-note-form]");
  const ticketBox = capture.querySelector(".internal-live-ticket");
  const printUrls = capture.querySelector("[data-internal-print-urls]");
  let printActions = ticketBox?.querySelector(".ticket-print-actions");
  if (ticketBox && printUrls) {
    if (!printActions) {
      printActions = document.createElement("div");
      printActions.className = "ticket-print-actions";
      [
        [printUrls.dataset.kitchenUrl, "Imprimir cocina", ""],
        [printUrls.dataset.paymentUrl, "Imprimir cobro", ""],
        [printUrls.dataset.customUrl, "Imprimir cocina modificado", "ticket-print-custom"],
      ].forEach(([url, label, className]) => {
        const link = document.createElement("a");
        link.href = url;
        link.textContent = label;
        if (className) link.className = className;
        printActions.append(link);
      });
    }
    ticketBox.querySelector(".current-ticket-heading")?.after(printActions);
  }
  const generalNoteButton = document.createElement("button");
  const generalNoteText = document.createElement("p");
  if (ticketBox && noteConfig) {
    generalNoteButton.type = "button";
    generalNoteButton.className = "ticket-general-note-button";
    generalNoteButton.textContent = "Agregar nota general";
    generalNoteButton.dataset.orderNoteOpen = "";
    generalNoteButton.dataset.url = noteConfig.dataset.url;
    generalNoteButton.dataset.note = noteConfig.dataset.note || "";
    generalNoteText.className = "ticket-general-note";
    generalNoteText.dataset.ticketGeneralNote = "";
    generalNoteText.textContent = noteConfig.dataset.note || "";
    generalNoteText.hidden = !generalNoteText.textContent;
    ticketBox.querySelector(".current-ticket-heading")?.after(generalNoteButton, generalNoteText);
  }

  function normalize(value) {
    return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("es-MX").trim();
  }

  function refreshSearch() {
    const query = normalize(search?.value || "");
    if (!searchSection) return;
    if (!query) {
      searchSection.hidden = true;
      capture.querySelector("[data-internal-category-target].is-selected")?.click();
      return;
    }
    capture.querySelectorAll(".internal-category").forEach((section) => { section.hidden = true; });
    searchSection.hidden = false;
    const matches = sourceCards.filter((card) => normalize(card.dataset.productName).includes(query)).sort((left, right) => {
      const a = normalize(left.dataset.productName); const b = normalize(right.dataset.productName);
      return Number(!a.startsWith(query)) - Number(!b.startsWith(query)) || a.localeCompare(b, "es-MX");
    });
    searchGrid.replaceChildren(...matches.map((card) => card.cloneNode(true)));
    searchEmpty.hidden = matches.length > 0;
    renderQuantities(JSON.parse(quantitiesNode?.textContent || "{}"));
  }

  function renderQuantities(quantities) {
    capture.querySelectorAll("[data-internal-product]").forEach((card) => {
      const quantity = quantities[String(card.dataset.internalProduct)] || 0;
      card.querySelector("[data-internal-quantity]").textContent = quantity;
      card.querySelector("[data-internal-decrease]").disabled = quantity === 0;
    });
  }

  function renderCandidateQuantities(quantities) {
    capture.querySelectorAll("[data-internal-auto-product]").forEach((card) => {
      const quantity = quantities[String(card.dataset.internalAutoProduct)] || 0;
      card.querySelector("[data-internal-auto-quantity]").textContent = quantity;
      card.querySelector("[data-internal-auto-decrease]").disabled = quantity === 0;
    });
  }

  function renderTicket(ticket) {
    ticketItems.replaceChildren();
    ticket.items.forEach((item) => {
      const article = document.createElement("article");
      article.className = "table-ticket-item internal-ticket-item";
      const description = document.createElement("span");
      const name = document.createElement("strong");
      name.textContent = `${item.quantity} × ${item.name}`;
      description.append(name);
      if (item.is_customized) {
        const badge = document.createElement("small");
        badge.textContent = "Modificado";
        description.append(badge);
      }
      if (item.is_package_candidate) {
        const pending = document.createElement("small");
        pending.textContent = "Pendiente de completar paquete";
        description.append(pending);
      }
      if (item.description) {
        const details = document.createElement("small");
        details.textContent = item.description;
        description.append(details);
      }
      const subtotal = document.createElement("strong");
      subtotal.textContent = currency.format(Number(item.subtotal));
      const controls = document.createElement("div");
      controls.className = "quantity-buttons";
      [["decrease", "−", ""], ["increase", "+", ""], ["remove", "×", "danger"]].forEach(([action, text, className]) => {
        const button = document.createElement("button");
        button.type = "button"; button.textContent = text; button.dataset.internalItemAction = action; button.dataset.url = item.change_url;
        if (className) button.className = className;
      controls.append(button);
      });
      if (item.is_package) {
        const editExtras = document.createElement("button");
        editExtras.type = "button";
        editExtras.className = "ticket-edit-extras";
        editExtras.textContent = "Editar extras";
        editExtras.dataset.packageExtrasOpen = "";
        editExtras.dataset.url = item.edit_extras_url;
        editExtras.dataset.water = String(Boolean(item.with_water));
        editExtras.dataset.tortillas = String(Boolean(item.tortillas));
        editExtras.dataset.bread = String(Boolean(item.bread));
        editExtras.dataset.eggProductId = String(item.egg_product_id || "");
        editExtras.dataset.beans = String(Boolean(item.beans));
        editExtras.dataset.comment = item.comment || "";
        controls.append(editExtras);
      }
      const editNote = document.createElement("button");
      editNote.type = "button";
      editNote.className = "ticket-item-note-button";
      editNote.textContent = "Nota";
      editNote.dataset.itemNoteOpen = "";
      editNote.dataset.url = item.edit_note_url;
      editNote.dataset.note = item.comment || "";
      controls.append(editNote);
      article.append(description, subtotal, controls);
      ticketItems.append(article);
    });
    if (!ticket.items.length) {
      const empty = document.createElement("p"); empty.textContent = "Agrega el primer producto."; ticketItems.append(empty);
    }
    ticketTotal.textContent = currency.format(Number(ticket.total));
    ticketCount.textContent = ticket.count;
    const hasItems = ticket.items.length > 0;
    if (ticketBox) ticketBox.hidden = !hasItems;
    capture.classList.toggle("is-ticket-empty", !hasItems);
    if (printActions) {
      printActions.classList.toggle("is-disabled", !ticket.items.length);
      printActions.inert = !ticket.items.length;
      printActions.querySelectorAll("a").forEach((link) => link.setAttribute("aria-disabled", String(!ticket.items.length)));
    }
    generalNoteButton.dataset.note = ticket.note || "";
    generalNoteButton.textContent = ticket.note ? "Editar nota general" : "Agregar nota general";
    generalNoteText.textContent = ticket.note || "";
    generalNoteText.hidden = !ticket.note;
    const orderNotesField = form.querySelector("textarea[name='notes']");
    if (orderNotesField) orderNotesField.value = ticket.note || "";
    form.dataset.orderTotal = ticket.total;
    refresh();
    renderQuantities(ticket.quantities || {});
    renderCandidateQuantities(ticket.candidate_quantities || {});
  }

  async function send(url, body) {
    const response = await fetch(url, {method: "POST", body, headers: {"X-CSRFToken": csrf, "X-Requested-With": "XMLHttpRequest"}});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "No fue posible actualizar el pedido.");
    renderTicket(data.ticket);
  }

  // NOTA TEMPORAL PARA APRENDIZAJE: reutilizamos un solo diálogo para la nota
  // general y las notas de partidas. La URL del botón decide qué registro cambia.
  // Borra esta nota después de leerla.
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-order-note-open], [data-item-note-open]");
    if (!button || !noteForm) return;
    noteForm.action = button.dataset.url;
    noteForm.elements.note.value = button.dataset.note || "";
    noteForm.elements.note.maxLength = button.hasAttribute("data-item-note-open") ? 150 : 1000;
    noteForm.querySelector("[data-ticket-note-title]").textContent = button.hasAttribute("data-item-note-open") ? "Nota del producto" : "Nota general del ticket";
    noteForm.querySelector("[data-ticket-note-error]").hidden = true;
    noteDialog.showModal();
    noteForm.elements.note.focus();
  });
  document.querySelectorAll("[data-ticket-note-close]").forEach((button) => {
    button.addEventListener("click", () => noteDialog.close());
  });
  noteForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const errorBox = noteForm.querySelector("[data-ticket-note-error]");
    try {
      await send(noteForm.action, new FormData(noteForm));
      noteDialog.close();
    } catch (error) {
      errorBox.textContent = error.message;
      errorBox.hidden = false;
    }
  });

  if (ticketDataNode) renderTicket(JSON.parse(ticketDataNode.textContent));

  capture.querySelectorAll("[data-internal-category-target]").forEach((button) => button.addEventListener("click", () => {
    capture.querySelectorAll("[data-internal-category-target]").forEach((candidate) => candidate.classList.remove("is-selected"));
    capture.querySelectorAll(".internal-category").forEach((section) => { section.hidden = true; });
    button.classList.add("is-selected");
    document.querySelector(`#${button.dataset.internalCategoryTarget}`).hidden = false;
  }));
  const initialCategory = capture.querySelector("[data-internal-category-target].is-selected");
  if (initialCategory) document.querySelector(`#${initialCategory.dataset.internalCategoryTarget}`).hidden = false;
  search?.addEventListener("input", refreshSearch);
  search?.addEventListener("focus", () => search.closest(".internal-menu-workspace")?.classList.add("search-focused"));
  search?.addEventListener("blur", () => {
    if (!search.value.trim()) search.closest(".internal-menu-workspace")?.classList.remove("search-focused");
  });

  const categoryCarousel = capture.querySelector("[data-internal-category-carousel]");
  if (categoryCarousel) {
    const viewport = categoryCarousel.querySelector("[data-carousel-viewport]");
    const track = categoryCarousel.querySelector(".category-buttons");
    const previous = categoryCarousel.querySelector("[data-carousel-prev]");
    const next = categoryCarousel.querySelector("[data-carousel-next]");
    const dots = categoryCarousel.querySelector("[data-carousel-dots]");
    let offsets = [0];
    let page = 0;
    let pointerDown = false;
    let dragged = false;
    let startX = 0;
    let startScroll = 0;

    const render = () => {
      page = Math.max(0, Math.min(page, offsets.length - 1));
      dots.replaceChildren(...offsets.map((offset, index) => {
        const dot = document.createElement("button");
        dot.type = "button";
        dot.classList.toggle("is-current", index === page);
        dot.setAttribute("aria-label", `Ir a la página ${index + 1} de categorías`);
        dot.addEventListener("click", () => go(index));
        return dot;
      }));
      previous.disabled = page === 0;
      next.disabled = page === offsets.length - 1;
      categoryCarousel.classList.toggle("has-multiple-pages", offsets.length > 1);
    };
    const go = (target, behavior = "smooth") => {
      page = Math.max(0, Math.min(target, offsets.length - 1));
      viewport.scrollTo({left: offsets[page], behavior});
      render();
    };
    const measure = () => {
      const buttons = [...track.querySelectorAll("[data-internal-category-target]")];
      offsets = [0];
      let pageStart = buttons[0]?.offsetLeft || 0;
      buttons.forEach((button) => {
        if (button.offsetLeft > pageStart && button.offsetLeft + button.offsetWidth - pageStart > viewport.clientWidth) {
          offsets.push(button.offsetLeft);
          pageStart = button.offsetLeft;
        }
      });
      go(Math.min(page, offsets.length - 1), "auto");
    };
    const finish = (event) => {
      if (!pointerDown) return;
      pointerDown = false;
      categoryCarousel.classList.remove("is-dragging");
      if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
      if (!dragged) return;
      page = offsets.reduce((best, offset, index) => Math.abs(offset - viewport.scrollLeft) < Math.abs(offsets[best] - viewport.scrollLeft) ? index : best, 0);
      go(page);
      window.setTimeout(() => { dragged = false; }, 0);
    };
    previous.addEventListener("click", () => go(page - 1));
    next.addEventListener("click", () => go(page + 1));
    viewport.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      pointerDown = true;
      dragged = false;
      startX = event.clientX;
      startScroll = viewport.scrollLeft;
    });
    viewport.addEventListener("pointermove", (event) => {
      if (!pointerDown) return;
      const distance = event.clientX - startX;
      if (Math.abs(distance) > 6 && !dragged) {
        dragged = true;
        categoryCarousel.classList.add("is-dragging");
        viewport.setPointerCapture(event.pointerId);
      }
      if (dragged) viewport.scrollLeft = startScroll - distance;
    });
    viewport.addEventListener("pointerup", finish);
    viewport.addEventListener("pointercancel", finish);
    categoryCarousel.addEventListener("click", (event) => {
      if (!dragged) return;
      event.preventDefault();
      event.stopPropagation();
      dragged = false;
    }, true);
    new ResizeObserver(measure).observe(viewport);
    window.requestAnimationFrame(measure);
  }

  document.querySelectorAll("[data-auto-package-options]").forEach((options) => {
    options.querySelectorAll("[data-auto-toggle]").forEach((button) => button.addEventListener("click", () => {
      const field = options.querySelector(`[data-auto-option='${button.dataset.autoToggle}']`);
      field.checked = !field.checked;
      button.classList.toggle("is-selected", field.checked);
      button.textContent = field.checked
        ? (button.dataset.autoToggle === "with_water" ? "Con agua" : "Con frijoles")
        : (button.dataset.autoToggle === "with_water" ? "Sin agua" : "Sin frijoles");
    }));
    options.querySelectorAll("[data-auto-accompaniment]").forEach((button) => button.addEventListener("click", () => {
      const choice = button.dataset.autoAccompaniment;
      options.querySelector("[data-auto-option='tortillas']").checked = choice === "tortillas";
      options.querySelector("[data-auto-option='bread']").checked = choice === "bread";
      options.querySelectorAll("[data-auto-accompaniment]").forEach((candidate) => candidate.classList.toggle("is-selected", candidate === button));
    }));
    const commentButton = options.querySelector("[data-auto-comment-toggle]");
    const commentInput = options.querySelector("[data-auto-package-comment]");
    commentButton?.remove();
    if (commentInput) {
      commentInput.hidden = false;
      commentInput.placeholder = "Ej. Empacar por separado, sin cebolla o servir primero la sopa";
    }
  });

  document.querySelectorAll("[data-internal-package-open]").forEach((button) => button.addEventListener("click", () => {
    const dialog = document.querySelector(`#${button.dataset.internalPackageOpen}`);
    if (!dialog) return;
    const form = dialog.querySelector("form");
    if (form) form.scrollTop = 0;
    dialog.scrollTop = 0;
    dialog.showModal();
    requestAnimationFrame(() => {
      if (form) form.scrollTop = 0;
      dialog.scrollTop = 0;
    });
  }));
  document.querySelectorAll("[data-package-close]").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));

  document.querySelectorAll("form[data-internal-package]").forEach((packageForm) => {
    const heading = packageForm.querySelector(":scope > .dialog-heading");
    const closeButton = heading?.querySelector("[data-package-close]");
    let search = packageForm.querySelector("[data-package-product-search]")?.closest("label");
    if (!search) {
      search = document.createElement("label");
      search.className = "package-modal-search";
      const caption = document.createElement("span");
      const input = document.createElement("input");
      caption.textContent = "Buscar producto del paquete";
      input.type = "search";
      input.autocomplete = "off";
      input.placeholder = "Escribe el nombre del producto";
      input.dataset.packageProductSearch = "";
      search.append(caption, input);
      heading.insertAdjacentElement("afterend", search);
    }
    const input = search.querySelector("[data-package-product-search]");
    const launcher = document.createElement("button");
    launcher.type = "button";
    launcher.className = "package-modal-search-launcher";
    launcher.setAttribute("aria-label", "Buscar producto válido para el paquete");
    launcher.textContent = "⌕";
    heading.insertBefore(launcher, closeButton);

    const closeSearch = () => {
      packageForm.classList.remove("is-package-search-open");
      input.blur();
    };
    launcher.addEventListener("click", () => {
      packageForm.classList.add("is-package-search-open");
      input.focus({ preventScroll: true });
      input.select();
    });
    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      closeSearch();
    });
    packageForm.addEventListener("pointerdown", (event) => {
      if (!packageForm.classList.contains("is-package-search-open") || search.contains(event.target) || event.target === launcher) return;
      event.preventDefault();
      closeSearch();
    });
  });

  // NOTA TEMPORAL PARA APRENDIZAJE: el buscador vive sólo en la Ejecutiva y filtra
  // por nombre dentro de los tres tiempos. Normalizar acentos permite que "consome"
  // encuentre "consomé". Borra esta nota después de leerla.
  document.querySelectorAll("[data-package-product-search]").forEach((input) => input.addEventListener("input", () => {
    const normalize = (value) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
    const query = normalize(input.value);
    const form = input.closest("[data-internal-package]");
    form.querySelectorAll("[data-package-choice-group]").forEach((group) => {
      let visible = 0;
      group.querySelectorAll("[data-package-choice]").forEach((card) => {
        const matches = !query || normalize(card.dataset.searchName).includes(query);
        card.hidden = !matches;
        if (matches) visible += 1;
      });
      group.querySelector("[data-package-choice-empty]").hidden = visible > 0;
    });
  }));

  // NOTA TEMPORAL PARA APRENDIZAJE: sólo la Corrida puede contener el guisado de
  // pollo del día. Comparamos el ID seleccionado y mostramos Pierna/Muslo únicamente
  // en ese caso; al elegir otro guisado limpiamos la pieza anterior. Borra esta nota.
  document.querySelectorAll("form[data-internal-package]").forEach((form) => {
    const chickenField = form.querySelector("[data-package-chicken-field]");
    if (!chickenField) return;
    const refreshChickenField = () => {
      const selectedMain = form.querySelector("input[name$='main_course']:checked")?.value || "";
      const show = selectedMain === form.dataset.chickenProduct;
      chickenField.hidden = true;
      if (!show) chickenField.querySelectorAll("input[type='radio']").forEach((input) => { input.checked = false; });
    };
    form.querySelectorAll("input[name$='main_course']").forEach((input) => input.addEventListener("change", refreshChickenField));
    refreshChickenField();
  });

  // Presenta tortillas y bolillo como una sola eleccion, conservando los campos
  // que el servidor utiliza para guardar cada extra.
  document.querySelectorAll("form[data-internal-package]").forEach((form) => {
    const extraGroups = form.querySelectorAll(".package-quick-extras .package-toggle-field");
    const accompaniment = extraGroups[1];
    const beans = extraGroups[2];
    const tortillaYes = accompaniment?.querySelector("input[value='yes']");
    const tortillaNo = accompaniment?.querySelector("input[value='no']");
    const choices = accompaniment?.querySelector(".package-yes-no");
    if (choices && tortillaYes && tortillaNo) {
      accompaniment.querySelector("strong").textContent = "Acompañamiento";
      tortillaYes.closest("label").querySelector("span").textContent = "Tortillas";
      tortillaNo.closest("label").querySelector("span").textContent = "Ninguno";
      choices.prepend(tortillaNo.closest("label"));
      const breadLabel = document.createElement("label");
      const breadInput = document.createElement("input");
      breadInput.type = "checkbox";
      breadInput.name = tortillaYes.name.replace(/tortillas$/, "bread");
      breadLabel.append(breadInput, Object.assign(document.createElement("span"), {textContent: "Bolillo"}));
      choices.append(breadLabel);
      choices.classList.add("package-accompaniment-options");
      tortillaNo.checked = true;
      breadInput.addEventListener("change", () => {
        if (breadInput.checked) tortillaNo.checked = true;
      });
      [tortillaYes, tortillaNo].forEach((input) => input.addEventListener("change", () => { breadInput.checked = false; }));
      form.addEventListener("reset", () => window.setTimeout(() => { tortillaNo.checked = true; breadInput.checked = false; }, 0));
    }
    if (beans) {
      beans.querySelector("strong").textContent = "Frijoles";
      const yes = beans.querySelector("input[value='yes']");
      const no = beans.querySelector("input[value='no']");
      if (yes && no) {
        yes.closest("label").querySelector("span").textContent = "Con frijoles";
        no.closest("label").querySelector("span").textContent = "Sin frijoles";
        beans.querySelector(".package-yes-no").prepend(no.closest("label"));
        const beansNo = beans.querySelector("input[value='no']");
        beansNo.checked = true;
        form.addEventListener("reset", () => window.setTimeout(() => { beansNo.checked = true; }, 0));
      }
    }
  });

  const extrasDialog = document.querySelector("[data-package-extras-dialog]");
  const extrasForm = extrasDialog?.querySelector("[data-package-extras-form]");
  document.querySelector("[data-package-extras-close]")?.addEventListener("click", () => extrasDialog.close());
  extrasForm?.elements.tortillas?.addEventListener("change", () => {
    if (extrasForm.elements.tortillas.checked) extrasForm.elements.bread.checked = false;
  });
  extrasForm?.elements.bread?.addEventListener("change", () => {
    if (extrasForm.elements.bread.checked) extrasForm.elements.tortillas.checked = false;
  });
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-package-extras-open]");
    if (!button || !extrasForm) return;
    extrasForm.action = button.dataset.url;
    extrasForm.elements.with_water.checked = button.dataset.water === "true";
    extrasForm.elements.tortillas.checked = button.dataset.tortillas === "true";
    extrasForm.elements.bread.checked = button.dataset.bread === "true";
    extrasForm.elements.beans.checked = button.dataset.beans === "true";
    extrasForm.elements.egg_product.value = button.dataset.eggProductId || "";
    extrasForm.elements.customization_comment.value = button.dataset.comment || "";
    extrasForm.querySelector("[data-package-extras-error]").hidden = true;
    extrasDialog.showModal();
  });
  extrasForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const errorBox = extrasForm.querySelector("[data-package-extras-error]");
    try {
      await send(extrasForm.action, new FormData(extrasForm));
      extrasDialog.close();
    } catch (error) {
      errorBox.textContent = error.message; errorBox.hidden = false;
    }
  });

  let pendingChickenForm = null;
  const chickenDialog = document.querySelector("[data-internal-chicken-dialog]");

  document.addEventListener("submit", async (event) => {
    const addForm = event.target.closest("form[data-internal-add]");
    if (!addForm) return;
    // NOTA TEMPORAL PARA APRENDIZAJE: Comida por orden reutiliza esta misma tarjeta
    // genérica; si el producto es el guisado de pollo del día, la tarjeta trae el
    // atributo data-internal-chicken-choice y un input chicken_piece vacío. Sin
    // pierna/muslo, el backend no encuentra existencia por pieza y rechaza el
    // producto. Borra esta nota después de leerla.
    const chickenField = addForm.querySelector("input[name='chicken_piece']");
    if (addForm.hasAttribute("data-internal-chicken-choice") && chickenField && !chickenField.value) {
      event.preventDefault();
      pendingChickenForm = addForm;
      chickenDialog.showModal();
      return;
    }
    event.preventDefault();
    try { await send(addForm.action, new FormData(addForm)); }
    catch (error) { window.alert(error.message); }
    finally {
      addForm.querySelectorAll("input[data-generated-option]").forEach((input) => input.remove());
      delete addForm.dataset.selectionReady;
      if (chickenField) chickenField.value = "";
    }
  });
  document.querySelector("[data-internal-chicken-close]")?.addEventListener("click", () => {
    pendingChickenForm = null; chickenDialog.close();
  });
  document.querySelectorAll("[data-internal-chicken-piece]").forEach((button) => button.addEventListener("click", () => {
    if (!pendingChickenForm) return;
    pendingChickenForm.querySelector("input[name='chicken_piece']").value = button.dataset.internalChickenPiece;
    const target = pendingChickenForm;
    pendingChickenForm = null;
    chickenDialog.close();
    target.requestSubmit();
  }));

  document.addEventListener("submit", async (event) => {
    const autoForm = event.target.closest("form[data-internal-auto-add]");
    if (!autoForm) return;
    event.preventDefault();
    const chickenField = autoForm.querySelector("input[name='chicken_piece']");
    if (autoForm.hasAttribute("data-internal-chicken-choice") && !chickenField.value) {
      pendingChickenForm = autoForm;
      chickenDialog.showModal();
      return;
    }
    const body = new FormData(autoForm);
    const options = autoForm.closest(".internal-category")?.querySelector("[data-auto-package-options]");
    options?.querySelectorAll("[data-auto-option]").forEach((field) => body.set(field.dataset.autoOption, field.checked ? "1" : "0"));
    body.set("package_comment", options?.querySelector("[data-auto-package-comment]")?.value || "");
    body.set("egg_product", options?.querySelector("select[name='egg_product']")?.value || "");
    try {
      const response = await fetch(autoForm.action, {method: "POST", body, headers: {"X-CSRFToken": csrf, "X-Requested-With": "XMLHttpRequest"}});
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || "No fue posible armar la comida.");
      renderTicket(data.ticket);
      if (data.auto_package_created && options) {
        const eggChoice = options.querySelector("select[name='egg_product']");
        if (eggChoice) eggChoice.value = "";
        options.querySelectorAll("[data-auto-option]").forEach((field) => { field.checked = false; });
        options.querySelectorAll("[data-auto-toggle]").forEach((button) => {
          button.classList.remove("is-selected");
          button.textContent = button.dataset.autoToggle === "with_water" ? "Sin agua" : "Sin frijoles";
        });
        options.querySelectorAll("[data-auto-accompaniment]").forEach((button) => button.classList.toggle("is-selected", button.dataset.autoAccompaniment === "none"));
        const comment = options.querySelector("[data-auto-package-comment]");
        if (comment) comment.value = "";
      }
    } catch (error) { window.alert(error.message); }
    finally {
      if (chickenField) chickenField.value = "";
      autoForm.querySelectorAll("input[data-generated-option]").forEach((input) => input.remove());
      delete autoForm.dataset.selectionReady;
    }
  });

  document.addEventListener("submit", async (event) => {
    const packageForm = event.target.closest("form[data-internal-package]");
    if (!packageForm) return;
    event.preventDefault();
    const errorBox = packageForm.querySelector("[data-package-error]");
    try {
      await send(packageForm.action, new FormData(packageForm));
      packageForm.closest("dialog").close();
      packageForm.reset();
      const resetChickenField = packageForm.querySelector("[data-package-chicken-field]");
      if (resetChickenField) resetChickenField.hidden = true;
      const packageSearch = packageForm.querySelector("[data-package-product-search]");
      if (packageSearch) { packageSearch.value = ""; packageSearch.dispatchEvent(new Event("input")); }
      if (errorBox) errorBox.hidden = true;
    } catch (error) {
      if (errorBox) { errorBox.textContent = error.message; errorBox.hidden = false; }
    }
  });

  capture.addEventListener("click", async (event) => {
    const productImage = event.target.closest(".catalog-product-visual");
    if (productImage) {
      const card = productImage.closest(".catalog-product-card");
      const addForm = card?.querySelector("form[data-internal-auto-add]:not([data-customizable-product]), form[data-internal-add]:not([data-customizable-product])");
      if (addForm) {
        event.preventDefault();
        addForm.requestSubmit();
        return;
      }
    }
    const decrease = event.target.closest("[data-internal-decrease], [data-internal-auto-decrease]");
    const action = event.target.closest("[data-internal-item-action]");
    if (!decrease && !action) return;
    event.preventDefault();
    const button = decrease || action;
    button.disabled = true;
    try { await send(button.dataset.url, action ? new URLSearchParams({action: action.dataset.internalItemAction}) : new URLSearchParams()); }
    catch (error) { window.alert(error.message); }
    finally { if (button.isConnected) button.disabled = false; }
  });

  renderQuantities(JSON.parse(quantitiesNode?.textContent || "{}"));
  renderCandidateQuantities(JSON.parse(candidateQuantitiesNode?.textContent || "{}"));
})();
