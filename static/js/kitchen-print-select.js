(() => {
  const form = document.querySelector("[data-kitchen-print-selection]");
  if (!form) return;
  const rows = [...form.querySelectorAll("[data-print-item]")];
  const setSelection = (checked) => rows.forEach((checkbox) => {
    checkbox.checked = checked;
    const quantity = checkbox.closest(".selection-row")?.querySelector("input[type='number']");
    if (quantity) quantity.disabled = !checked;
  });
  form.querySelector("[data-select-all]")?.addEventListener("click", () => setSelection(true));
  form.querySelector("[data-select-none]")?.addEventListener("click", () => setSelection(false));
  rows.forEach((checkbox) => checkbox.addEventListener("change", () => {
    const quantity = checkbox.closest(".selection-row")?.querySelector("input[type='number']");
    if (quantity) quantity.disabled = !checkbox.checked;
  }));
})();
