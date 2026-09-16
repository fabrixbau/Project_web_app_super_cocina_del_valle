(() => {
  const compactView = window.matchMedia("(max-width: 900px)");
  if (!compactView.matches) return;

  const installDisclosure = (section, content, label) => {
    if (!section || !content.length) return;
    section.classList.add("debt-collapsible", "is-collapsed");
    content.forEach((element) => element.classList.add("debt-collapsible-content"));
    const button = document.createElement("button");
    button.type = "button";
    button.className = "debt-disclosure-toggle";
    button.setAttribute("aria-expanded", "false");
    button.setAttribute("aria-label", `Mostrar ${label}`);
    button.innerHTML = '<svg aria-hidden="true" viewBox="0 0 20 20"><path d="m4 7 6 6 6-6"/></svg>';
    section.append(button);
    button.addEventListener("click", () => {
      const collapsed = section.classList.toggle("is-collapsed");
      button.setAttribute("aria-expanded", String(!collapsed));
      button.setAttribute("aria-label", `${collapsed ? "Mostrar" : "Ocultar"} ${label}`);
    });
    section.addEventListener("click", (event) => {
      if (event.target.closest("button, a, input, select, textarea, label, form")) return;
      if (event.target.closest(".debt-collapsible-content")) return;
      button.click();
    });
  };

  const heading = document.querySelector("main.internal-panel > .page-heading");
  installDisclosure(
    heading,
    [heading?.querySelector("p"), heading?.querySelector(".page-heading-actions")].filter(Boolean),
    "opciones de cuentas por cobrar",
  );

  const createCard = document.querySelector(".debt-create-card");
  installDisclosure(
    createCard,
    [createCard?.querySelector("p"), createCard?.querySelector("form")].filter(Boolean),
    "registro de pedido no pagado",
  );
})();
