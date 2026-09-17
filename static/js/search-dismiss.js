(() => {
  const searchInputSelector = [
    "input[type='search']",
    "input[name='q']",
    "input[data-catalog-search]",
    "input[data-internal-search]",
    "input[data-package-product-search]",
    "input[data-menu-search-input]",
    "input[data-delivery-search-input]",
    ".app-select-search",
  ].join(",");

  const searchBackdropSelector = [
    ".compact-search-backdrop:not([hidden])",
    ".menu-search-backdrop:not([hidden])",
    ".delivery-search-backdrop:not([hidden])",
  ].join(",");

  const isSearchInput = (element) => element instanceof HTMLInputElement && element.matches(searchInputSelector);
  let pointerSearchInput = null;

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
    document.querySelectorAll(".compact-search-backdrop, .menu-search-backdrop, .delivery-search-backdrop")
      .forEach((backdrop) => { backdrop.hidden = true; });
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
    if (!event.target.closest("button, input[type='submit']")) return;
    pointerSearchInput = isSearchInput(document.activeElement) ? document.activeElement : null;
  }, true);

  document.addEventListener("click", (event) => {
    const button = event.target.closest("button, input[type='submit']");
    if (!button) return;

    const activeInput = (isSearchInput(document.activeElement) ? document.activeElement : null) || pointerSearchInput;
    pointerSearchInput = null;
    const form = button.form || button.closest("form");
    const formSearch = form?.querySelector(searchInputSelector);
    const focusedLauncher = button.matches("[data-menu-search-open], [data-delivery-search-open], .compact-field-launcher.is-product-search");
    const openSearch = button.closest(".is-searching") || (button.matches(".compact-field-launcher.is-product-search") && document.body.classList.contains("compact-field-open"));

    if (focusedLauncher && openSearch) {
      event.preventDefault();
      event.stopImmediatePropagation();
      const input = openSearch instanceof Element ? openSearch.querySelector(searchInputSelector) || activeInput : activeInput;
      closeSearchFocus(input);
      if (form && typeof form.requestSubmit === "function") form.requestSubmit();
      return;
    }

    if (formSearch || activeInput) finishAfterCurrentSearch(formSearch || activeInput);
  }, true);
})();
