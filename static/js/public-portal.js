/* Portal de clientes (/pedir/): comportamiento de la interfaz nueva.
   - Menú: barra "Ver pedido" (celular) que abre el ticket como hoja inferior; se actualiza con
     el aviso `public-cart-rendered` que emite public-menu-controls.js.
   - Menú: resalta en la barra de categorías la sección que se está viendo.
   - Paquete: botones − / + de cantidad y total en vivo del botón Agregar. */
(() => {
  const money = (value) => `$${value.toFixed(2)}`;

  // ---------------------------------------------------------------- carrito (menú)
  const ticket = document.querySelector("[data-pp-ticket]");
  const bar = document.querySelector("[data-pp-cart-bar]");
  const backdrop = document.querySelector("[data-pp-sheet-backdrop]");
  const barTotal = document.querySelector("[data-pp-cart-total]");

  const closeSheet = () => {
    if (!ticket) return;
    ticket.classList.remove("is-open");
    if (backdrop) backdrop.hidden = true;
    document.body.classList.remove("pp-sheet-open");
  };
  const openSheet = () => {
    if (!ticket || ticket.hidden) return;
    ticket.classList.add("is-open");
    if (backdrop) backdrop.hidden = false;
    document.body.classList.add("pp-sheet-open");
  };

  bar?.addEventListener("click", openSheet);
  backdrop?.addEventListener("click", closeSheet);
  document.querySelector("[data-pp-ticket-close]")?.addEventListener("click", closeSheet);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && ticket?.classList.contains("is-open")) closeSheet();
  });
  document.addEventListener("public-cart-rendered", (event) => {
    const cart = event.detail || {};
    const count = Number(cart.count) || 0;
    if (bar) bar.hidden = count === 0;
    if (barTotal) barTotal.textContent = `$${cart.total_display || "0.00"}`;
    if (!count) closeSheet();
  });

  // ---------------------------------------------------------------- categorías (menú)
  const nav = document.querySelector("[data-pp-category-nav]");
  if (nav && "IntersectionObserver" in window) {
    const links = [...nav.querySelectorAll("a[href^='#']")];
    const sections = links.map((link) => document.querySelector(link.getAttribute("href"))).filter(Boolean);
    const activate = (id) => links.forEach((link) => {
      const active = link.getAttribute("href") === `#${id}`;
      link.classList.toggle("is-active", active);
      if (active) {
        // Mantiene visible la categoría activa dentro de la barra horizontal.
        const left = link.offsetLeft - (nav.clientWidth - link.offsetWidth) / 2;
        nav.scrollTo({left, behavior: "smooth"});
      }
    });
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (visible) activate(visible.target.id);
    }, {rootMargin: "-130px 0px -55% 0px"});
    sections.forEach((section) => observer.observe(section));
  }

  // ---------------------------------------------------------------- paquete
  const packageForm = document.querySelector("[data-pp-package]");
  if (packageForm) {
    const quantityInput = packageForm.querySelector("[data-pp-quantity]");
    const totalNode = packageForm.querySelector("[data-pp-package-total]");
    const water = packageForm.querySelector("input[name='with_water']");
    const priceWithout = Number.parseFloat(packageForm.dataset.priceWithoutWater) || 0;
    const priceWith = Number.parseFloat(packageForm.dataset.priceWithWater) || 0;
    const quantity = () => Math.min(99, Math.max(1, Number.parseInt(quantityInput.value, 10) || 1));
    const refresh = () => {
      const unit = water?.checked ? priceWith : priceWithout;
      totalNode.textContent = money(unit * quantity());
    };
    packageForm.querySelectorAll("[data-pp-quantity-step]").forEach((button) => button.addEventListener("click", () => {
      quantityInput.value = String(Math.min(99, Math.max(1, quantity() + Number(button.dataset.ppQuantityStep))));
      refresh();
    }));
    quantityInput.addEventListener("input", refresh);
    quantityInput.addEventListener("blur", () => { quantityInput.value = String(quantity()); refresh(); });
    water?.addEventListener("change", refresh);
    refresh();
  }
})();
