(() => {
  const input = document.querySelector("[data-board-order-search-input]");
  const results = document.querySelector("[data-board-order-search-results]");
  const container = document.querySelector("[data-board-order-search]");
  if (!input || !results || !container) return;

  let options = [];
  try {
    options = JSON.parse(document.querySelector("#board-order-search-options")?.textContent || "[]");
  } catch (_) {
    options = [];
  }

  const close = () => { results.hidden = true; };
  const normalize = (value) => String(value || "").toLocaleLowerCase("es-MX");
  const openExactOrder = (folio) => {
    const params = new URLSearchParams();
    params.set("q", folio);
    window.location.assign(`${window.location.pathname}?${params.toString()}`);
  };
  const render = () => {
    const query = normalize(input.value.trim());
    results.replaceChildren();
    if (query.length < 2) { close(); return; }
    const folioQuery = query.replace(/^#/, "");
    const matches = options.filter((order) => (
      normalize(order.customer).includes(query) || String(order.folio).includes(folioQuery)
    )).slice(0, 10);
    if (!matches.length) { close(); return; }
    matches.forEach((order) => {
      const button = document.createElement("button");
      button.type = "button";
      const customer = document.createElement("strong");
      const folio = document.createElement("small");
      customer.textContent = order.customer;
      folio.textContent = `Pedido ${order.folio}`;
      button.append(customer, folio);
      button.addEventListener("click", () => openExactOrder(order.folio));
      results.append(button);
    });
    results.hidden = false;
  };

  input.addEventListener("input", render);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") close();
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest("[data-board-order-search]")) close();
  });
})();
