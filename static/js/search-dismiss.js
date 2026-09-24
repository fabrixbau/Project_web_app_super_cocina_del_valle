(() => {
  const searchInputSelector = [
    "input[type='search']",
    "input[name='q']",
    "input[data-catalog-search]",
    "input[data-internal-search]",
    "input[data-package-product-search]",
    "input[data-menu-search-input]",
    "input[data-delivery-search-input]",
    "input[role='searchbox']",
    "input[enterkeyhint='search']",
    "input[name='search']",
    "input[name='query']",
    ".app-select-search",
  ].join(",");

  const searchBackdropSelector = [
    ".compact-search-backdrop:not([hidden])",
    ".menu-search-backdrop:not([hidden])",
    ".delivery-search-backdrop:not([hidden])",
    ".customer-field-backdrop:not([hidden])",
  ].join(",");

  const isSearchInput = (element) => element instanceof HTMLInputElement && element.matches(searchInputSelector);
  let pointerSearchInput = null;
  let productSearchWasOpenAtPointerDown = false;

  const closeSearchFocus = (input = document.activeElement) => {
    if (input instanceof HTMLElement) input.blur();

    // Cada fondo ya conoce la rutina de cierre de su pantalla. Activarlo conserva
    // esa lógica y evita dejar clases de bloqueo o desenfoque en el documento.
    document.querySelectorAll(searchBackdropSelector).forEach((backdrop) => backdrop.click());

    // Respaldo para focalizadores creados dinámicamente o cerrados durante el mismo evento.
    document.querySelectorAll(".is-compact-field-open").forEach((element) => element.classList.remove("is-compact-field-open"));
    document.querySelectorAll(".menu-catalog-search.is-searching, .delivery-search-filter.is-searching")
      .forEach((element) => element.classList.remove("is-searching"));
    document.body.classList.remove("compact-field-open", "delivery-search-is-open");
    document.querySelectorAll(".compact-search-backdrop, .menu-search-backdrop, .delivery-search-backdrop, .customer-field-backdrop")
      .forEach((backdrop) => { backdrop.hidden = true; });
    document.body.classList.remove("customer-field-focus-open");
    document.querySelectorAll(".is-customer-field-focused").forEach((element) => element.classList.remove("is-customer-field-focused"));
  };

  const finishAfterCurrentSearch = (input) => {
    // Dejamos que el listener de input/submit pinte primero las coincidencias.
    window.requestAnimationFrame(() => closeSearchFocus(input));
  };

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.isComposing || !isSearchInput(event.target)) return;
    finishAfterCurrentSearch(event.target);
  }, true);

  // Los teclados móviles pueden emitir `search` en lugar de keydown al tocar lupa/OK.
  document.addEventListener("search", (event) => {
    if (isSearchInput(event.target)) finishAfterCurrentSearch(event.target);
  }, true);

  document.addEventListener("submit", (event) => {
    const input = event.target.querySelector?.(searchInputSelector);
    if (input) closeSearchFocus(input);
  }, true);

  document.addEventListener("pointerdown", (event) => {
    const pointerButton = event.target.closest("button, input[type='submit']");
    if (!pointerButton) return;
    pointerSearchInput = isSearchInput(document.activeElement) ? document.activeElement : null;
    productSearchWasOpenAtPointerDown = (
      pointerButton.matches(".compact-field-launcher.is-product-search")
      && document.body.classList.contains("compact-field-open")
    );
  }, true);

  document.addEventListener("click", (event) => {
    const button = event.target.closest("button, input[type='submit']");
    if (!button) return;

    const activeInput = (isSearchInput(document.activeElement) ? document.activeElement : null) || pointerSearchInput;
    pointerSearchInput = null;
    const productLauncherWasAlreadyOpen = productSearchWasOpenAtPointerDown;
    productSearchWasOpenAtPointerDown = false;
    const form = button.form || button.closest("form");
    const formSearch = form?.querySelector(searchInputSelector);
    const focusedLauncher = button.matches("[data-menu-search-open], [data-delivery-search-open], .compact-field-launcher.is-product-search");
    const openSearch = button.closest(".is-searching") || (
      button.matches(".compact-field-launcher.is-product-search")
      && productLauncherWasAlreadyOpen
    );

    if (focusedLauncher && openSearch) {
      event.preventDefault();
      event.stopImmediatePropagation();
      const input = openSearch instanceof Element ? openSearch.querySelector(searchInputSelector) || activeInput : activeInput;
      closeSearchFocus(input);
      if (form && typeof form.requestSubmit === "function") form.requestSubmit();
      return;
    }

    // El clic que ABRE la búsqueda también cae dentro de este listener (el botón
    // vive en el mismo <form> que su input). Sin este corte, el código de abajo lo
    // trata como "click fuera de una búsqueda abierta" y dispara un cierre que
    // cancela la apertura antes de que el enfoque llegue a mostrarse.
    if (focusedLauncher) return;

    if (formSearch || activeInput) finishAfterCurrentSearch(formSearch || activeInput);
  }, true);
})();
