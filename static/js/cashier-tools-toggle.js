/* NOTA TEMPORAL PARA APRENDIZAJE: mismo botón "Herramientas" en las 7 páginas de
Caja (antes cada una traía su propia copia de este mismo código). En móvil está
colapsado; este script sólo lo expande/colapsa. Borra esta nota después de leerla. */
document.querySelectorAll("[data-cashier-panel-toggle]").forEach((toggle) => {
  const target = toggle.dataset.cashierPanelToggle === "tools"
    ? toggle.closest(".cashier-tools")
    : toggle.closest(".cashier-filter-card");
  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!expanded));
    target?.classList.toggle("is-mobile-expanded", !expanded);
  });
});
