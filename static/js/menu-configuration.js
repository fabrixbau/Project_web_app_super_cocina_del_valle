(() => {
  const compactView = window.matchMedia("(max-width: 900px)");

  const actions = document.querySelector(".menu-admin-actions");
  const actionsToggle = actions?.querySelector("[data-menu-actions-toggle]");
  actionsToggle?.addEventListener("click", () => {
    const expanded = actionsToggle.getAttribute("aria-expanded") === "true";
    actionsToggle.setAttribute("aria-expanded", String(!expanded));
    actions.classList.toggle("is-mobile-expanded", !expanded);
  });

  const categoryPanel = document.querySelector(".menu-category-panel");
  const categoryToggle = categoryPanel?.querySelector("[data-menu-category-toggle]");
  const categoryButton = categoryToggle?.querySelector("button");
  const toggleCategories = () => {
    if (!compactView.matches) return;
    const expanded = categoryButton.getAttribute("aria-expanded") === "true";
    categoryButton.setAttribute("aria-expanded", String(!expanded));
    categoryPanel.classList.toggle("is-mobile-expanded", !expanded);
  };
  categoryToggle?.addEventListener("click", (event) => {
    if (event.target.closest("a")) return;
    toggleCategories();
  });

  // Tablet horizontal y computadora: el botón "Categorías (N)" de la fila de filtros muestra u
  // oculta el panel y se recuerda la última elección en este navegador.
  const desktopToggle = document.querySelector("[data-menu-categories-desktop]");
  const CATEGORIES_KEY = "sc-menu-categories-open";
  // Tablet horizontal (≤900px): el panel usa el modo compacto; abrirlo muestra su contenido.
  const landscapeTablet = window.matchMedia("(min-width: 700px) and (max-width: 900px) and (orientation: landscape)");
  const setDesktopCategories = (open, remember) => {
    categoryPanel?.classList.toggle("is-desktop-collapsed", !open);
    if (landscapeTablet.matches) {
      categoryPanel?.classList.toggle("is-mobile-expanded", open);
      categoryButton?.setAttribute("aria-expanded", String(open));
    }
    desktopToggle?.setAttribute("aria-expanded", String(open));
    if (remember) { try { localStorage.setItem(CATEGORIES_KEY, open ? "1" : "0"); } catch (_) { /* sin almacenamiento */ } }
  };
  let rememberedOpen = false;
  try { rememberedOpen = localStorage.getItem(CATEGORIES_KEY) === "1"; } catch (_) { /* sin almacenamiento */ }
  setDesktopCategories(rememberedOpen, false);
  desktopToggle?.addEventListener("click", () => {
    setDesktopCategories(desktopToggle.getAttribute("aria-expanded") !== "true", true);
  });

  // Buscar / filtrar recarga la página: se conserva la posición del scroll.
  const SCROLL_KEY = "sc-menu-filter-scroll";
  document.querySelector("[data-menu-filters]")?.addEventListener("submit", () => {
    try { sessionStorage.setItem(SCROLL_KEY, String(window.scrollY)); } catch (_) { /* sin almacenamiento */ }
  });
  let savedScroll = null;
  try { savedScroll = sessionStorage.getItem(SCROLL_KEY); sessionStorage.removeItem(SCROLL_KEY); } catch (_) { /* sin almacenamiento */ }
  if (savedScroll !== null) {
    const restore = () => window.scrollTo({top: Math.min(Number(savedScroll) || 0, document.documentElement.scrollHeight), behavior: "instant"});
    restore();
    window.addEventListener("load", restore, {once: true});
  }

  const search = document.querySelector("[data-menu-search]");
  const searchOpen = search?.querySelector("[data-menu-search-open]");
  const searchInput = search?.querySelector("[data-menu-search-input]");
  const backdrop = document.createElement("button");
  backdrop.type = "button";
  backdrop.className = "menu-search-backdrop";
  backdrop.setAttribute("aria-label", "Cerrar búsqueda");
  backdrop.hidden = true;
  document.body.append(backdrop);
  const closeSearch = () => {
    search?.classList.remove("is-searching");
    backdrop.hidden = true;
  };
  searchOpen?.addEventListener("click", () => {
    search?.classList.add("is-searching");
    backdrop.hidden = false;
    window.requestAnimationFrame(() => searchInput?.focus());
  });
  const submitSearch = (event) => {
    if (event.type === "keydown" && (event.key !== "Enter" || event.isComposing)) return;
    event.preventDefault();
    const form = searchInput?.form;
    if (!form) return;
    closeSearch();
    searchInput.blur();
    form.requestSubmit();
  };
  searchInput?.addEventListener("keydown", submitSearch);
  // Algunos teclados virtuales emiten `search` en vez de un keydown al pulsar
  // Buscar/Ir. Ambos caminos aplican los mismos filtros del formulario.
  searchInput?.addEventListener("search", submitSearch);
  backdrop.addEventListener("click", closeSearch);
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeSearch(); });
})();
