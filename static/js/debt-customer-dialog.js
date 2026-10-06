/* "No pagó" en un pedido sin cliente de la agenda (Pedidos, Caja y Cambios).
   En vez del error "Vincula un cliente…", se abre un panel: buscar al cliente por nombre o
   celular (el mismo buscador de la agenda; el celular del pedido se busca de inmediato) o
   crear uno nuevo. Al confirmar se agregan customer_id o new_customer_name/phone al
   formulario original y se envía. Django vuelve a validar (celular repetido, etc.). */
(() => {
  const dialog = document.querySelector("[data-debt-customer-dialog]");
  if (!dialog) return;
  const search = dialog.querySelector("[data-debt-customer-search]");
  const results = dialog.querySelector("[data-debt-customer-results]");
  const chosenNote = dialog.querySelector("[data-debt-customer-chosen]");
  const newBox = dialog.querySelector("[data-debt-customer-new]");
  const newName = dialog.querySelector("[data-debt-new-name]");
  const newPhone = dialog.querySelector("[data-debt-new-phone]");
  const error = dialog.querySelector("[data-debt-customer-error]");
  const orderLabel = dialog.querySelector("[data-debt-customer-order]");
  let targetForm = null;
  let chosen = null;
  let timer = null;
  let version = 0;

  const showError = (message) => { error.textContent = message; error.hidden = !message; };
  const choose = (customer) => {
    chosen = customer;
    chosenNote.textContent = `Cliente elegido: ${customer.name}${customer.phone ? ` · ${customer.phone}` : ""}`;
    chosenNote.hidden = false;
    results.querySelectorAll("button").forEach((button) => button.classList.toggle("is-selected", Number(button.dataset.customerId) === customer.id));
    newBox.open = false;
    showError("");
  };
  const render = (customers) => {
    results.replaceChildren();
    if (!customers.length) {
      const empty = document.createElement("p");
      empty.textContent = "No encontramos clientes. Puedes crear uno nuevo abajo.";
      results.append(empty);
      return;
    }
    customers.forEach((customer) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.customerId = customer.id;
      button.textContent = `${customer.name}${customer.phone ? ` · ${customer.phone}` : ""}`;
      button.addEventListener("click", () => choose(customer));
      results.append(button);
    });
  };
  const lookup = (query) => {
    window.clearTimeout(timer);
    version += 1;
    const current = version;
    if (query.trim().length < 2) { results.replaceChildren(); return; }
    timer = window.setTimeout(async () => {
      try {
        const response = await fetch(`${dialog.dataset.customerLookupUrl}?q=${encodeURIComponent(query.trim())}`, {headers: {Accept: "application/json"}});
        const data = await response.json();
        if (current === version) render(data.customers || []);
      } catch (_) {
        if (current === version) showError("No se pudo consultar la agenda.");
      }
    }, 250);
  };
  search.addEventListener("input", () => { chosen = null; chosenNote.hidden = true; lookup(search.value); });

  document.addEventListener("submit", (event) => {
    const form = event.target.closest("form[data-needs-customer]");
    if (!form || form.dataset.customerReady === "1") return;
    event.preventDefault();
    form.closest("details")?.removeAttribute("open");
    targetForm = form;
    chosen = null;
    chosenNote.hidden = true;
    showError("");
    newBox.open = false;
    orderLabel.textContent = `Pedido ${form.dataset.orderLabel || ""}`;
    newName.value = form.dataset.orderName || "";
    newPhone.value = form.dataset.orderPhone || "";
    // El celular del pedido se busca de inmediato: si ya existe, aparece como sugerencia.
    search.value = form.dataset.orderPhone || form.dataset.orderName || "";
    results.replaceChildren();
    lookup(search.value);
    dialog.showModal();
  });

  dialog.querySelector("[data-debt-customer-close]").addEventListener("click", () => dialog.close());
  dialog.querySelector("[data-debt-customer-confirm]").addEventListener("click", () => {
    if (!targetForm) return;
    targetForm.querySelectorAll("input[data-debt-extra]").forEach((input) => input.remove());
    const add = (name, value) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = name;
      input.value = value;
      input.dataset.debtExtra = "";
      targetForm.append(input);
    };
    if (newBox.open) {
      if (!newName.value.trim()) { showError("Escribe el nombre del cliente nuevo."); return; }
      add("new_customer_name", newName.value.trim());
      add("new_customer_phone", newPhone.value.trim());
    } else if (chosen) {
      add("customer_id", chosen.id);
    } else {
      showError("Elige un cliente de la lista o abre «Crear cliente nuevo».");
      return;
    }
    targetForm.dataset.customerReady = "1";
    dialog.close();
    targetForm.requestSubmit();
  });
})();
