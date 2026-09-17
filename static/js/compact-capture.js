(() => {
  const responsiveView = window.matchMedia("(max-width: 900px)");
  const fields = [
    ...document.querySelectorAll("[data-catalog-search], [data-internal-search]"),
    ...document.querySelectorAll(".table-customer-form input[type='text']"),
  ];
  if (!fields.length) return;

  const backdrop = document.createElement("button");
  backdrop.type = "button";
  backdrop.className = "compact-search-backdrop";
  backdrop.setAttribute("aria-label", "Cerrar campo");
  backdrop.hidden = true;
  document.body.append(backdrop);
  let activeLabel = null;

  const closeField = () => {
    activeLabel?.classList.remove("is-compact-field-open");
    activeLabel = null;
    backdrop.hidden = true;
    document.body.classList.remove("compact-field-open");
  };

  fields.forEach((input) => {
    const label = input.closest("label");
    if (!label || label.classList.contains("compact-field-ready")) return;
    const isCustomer = input.closest(".table-customer-form");
    const launcher = document.createElement("button");
    launcher.type = "button";
    launcher.className = `compact-field-launcher ${isCustomer ? "is-customer" : "is-product-search"}`;
    launcher.setAttribute("aria-label", isCustomer ? "Escribir nombre del cliente" : "Buscar producto");
    launcher.innerHTML = isCustomer
      ? '<span aria-hidden="true">✎</span><span>Cliente</span>'
      : '<svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="11" cy="11" r="6"></circle><path d="m16 16 5 5"></path></svg>';
    label.classList.add("compact-field-ready");
    const carousel = isCustomer ? null : input.matches("[data-catalog-search]")
      ? document.querySelector(".table-operation-header .category-carousel, .table-catalog .category-carousel")
      : document.querySelector(".internal-menu-workspace .internal-category-carousel");
    if (carousel) carousel.prepend(launcher);
    else label.before(launcher);
    launcher.addEventListener("click", () => {
      if (isCustomer && !responsiveView.matches) return;
      closeField();
      activeLabel = label;
      label.classList.add("is-compact-field-open");
      backdrop.hidden = false;
      document.body.classList.add("compact-field-open");
      input.focus({ preventScroll: true });
      input.select?.();
    });
  });

  backdrop.addEventListener("click", closeField);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeField();
  });
  responsiveView.addEventListener?.("change", (event) => {
    if (!event.matches) closeField();
  });
})();

(() => {
  const heading = document.querySelector(".internal-capture-heading");
  const title = heading?.querySelector("[data-capture-title-toggle]");
  if (!heading || !title) return;

  const close = () => {
    heading.classList.remove("is-title-expanded");
    title.setAttribute("aria-expanded", "false");
  };
  const toggle = () => {
    const expanded = heading.classList.toggle("is-title-expanded");
    title.setAttribute("aria-expanded", String(expanded));
  };

  title.addEventListener("click", (event) => {
    event.stopPropagation();
    toggle();
  });
  title.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    toggle();
  });
  document.addEventListener("click", (event) => {
    if (!heading.contains(event.target)) close();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") close();
  });
})();
