/* NOTA TEMPORAL PARA APRENDIZAJE: widget genérico para elegir un cliente de la
agenda escribiendo su nombre o teléfono, reutilizando el mismo endpoint de
búsqueda que ya usa la captura de Pedidos (customer_lookup). A diferencia de ese
buscador, este no conoce domicilios ni modalidad — sólo entrega el id del
cliente elegido en un input oculto, para formularios simples como el depósito
de saldo a favor en Caja. Borra esta nota después de leerla. */
document.querySelectorAll("[data-customer-picker]").forEach((picker) => {
  const input = picker.querySelector("[data-customer-picker-input]");
  const idField = picker.querySelector("[data-customer-picker-id]");
  const results = picker.querySelector("[data-customer-picker-results]");
  const lookupUrl = picker.dataset.customerLookupUrl;
  if (!input || !idField || !results || !lookupUrl) return;

  let timer = null;
  let requestVersion = 0;

  const renderResults = (customers) => {
    results.replaceChildren();
    if (!customers.length) {
      const empty = document.createElement("p");
      empty.textContent = "No encontramos clientes.";
      results.append(empty);
      results.hidden = false;
      return;
    }
    customers.forEach((customer) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = `${customer.name}${customer.phone ? ` · ${customer.phone}` : ""}`;
      button.addEventListener("click", () => {
        input.value = customer.name;
        idField.value = customer.id;
        results.hidden = true;
      });
      results.append(button);
    });
    results.hidden = false;
  };

  input.addEventListener("input", () => {
    idField.value = "";
    window.clearTimeout(timer);
    requestVersion += 1;
    const currentVersion = requestVersion;
    const query = input.value.trim();
    if (query.length < 2) {
      results.hidden = true;
      return;
    }
    timer = window.setTimeout(async () => {
      try {
        const response = await fetch(`${lookupUrl}?q=${encodeURIComponent(query)}`, {headers: {"Accept": "application/json"}});
        const data = await response.json();
        if (!response.ok || currentVersion !== requestVersion) return;
        renderResults(data.customers || []);
      } catch (error) {
        if (currentVersion !== requestVersion) return;
        results.replaceChildren();
        const message = document.createElement("p");
        message.textContent = "No se pudo consultar la agenda.";
        results.append(message);
        results.hidden = false;
      }
    }, 300);
  });

  input.addEventListener("blur", () => {
    window.setTimeout(() => {
      if (!results.contains(document.activeElement)) results.hidden = true;
    }, 160);
  });
});
