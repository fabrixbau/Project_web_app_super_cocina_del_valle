(() => {
  const panel = document.querySelector(".sales-report-filters");
  const toggle = panel?.querySelector("[data-sales-filter-toggle]");
  toggle?.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!expanded));
    panel.classList.toggle("is-mobile-expanded", !expanded);
  });
})();
