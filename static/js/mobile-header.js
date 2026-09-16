(() => {
  const toggle = document.querySelector("[data-mobile-menu-toggle]");
  const panel = document.querySelector("#mobile-account-panel");
  const backdrop = document.querySelector("[data-mobile-menu-backdrop]");
  if (!toggle || !panel || !backdrop) return;

  const closeMenu = () => {
    document.body.classList.remove("mobile-menu-open");
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "Abrir menú de cuenta");
    backdrop.hidden = true;
  };

  const openMenu = () => {
    document.body.classList.add("mobile-menu-open");
    toggle.setAttribute("aria-expanded", "true");
    toggle.setAttribute("aria-label", "Cerrar menú de cuenta");
    backdrop.hidden = false;
  };

  toggle.addEventListener("click", () => {
    if (document.body.classList.contains("mobile-menu-open")) closeMenu();
    else openMenu();
  });
  backdrop.addEventListener("click", closeMenu);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeMenu();
  });
  window.matchMedia("(min-width: 901px)").addEventListener?.("change", (event) => {
    if (event.matches) closeMenu();
  });
})();
