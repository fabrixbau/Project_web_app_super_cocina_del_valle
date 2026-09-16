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
  backdrop.addEventListener("click", closeSearch);
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeSearch(); });
})();
