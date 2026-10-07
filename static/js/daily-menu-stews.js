/* Menú diario · tercer tiempo con hasta 12 guisados.
   - "+ Agregar guisado" muestra el siguiente renglón; "×" lo vacía y lo oculta.
   - Raciones: cada guisado elegido muestra su fila (o pierna y muslo si es de pollo);
     la etiqueta de la fila lleva el nombre del guisado. Las de renglones vacíos se ocultan. */
(() => {
  const list = document.querySelector("[data-stew-list]");
  if (!list) return;
  const chickenIds = new Set(JSON.parse(document.getElementById("daily-chicken-stew-ids")?.textContent || "[]").map(String));
  const rows = [...list.querySelectorAll("[data-stew-row]")];
  const addButton = list.querySelector("[data-stew-add]");

  const selectOf = (row) => row.querySelector("select[data-stew-select]");
  const refreshStock = () => {
    rows.forEach((row) => {
      const slot = row.dataset.stewRow;
      const select = selectOf(row);
      const value = select?.value || "";
      const isChicken = chickenIds.has(value);
      // La opción dice "Categoría · Nombre": en las raciones basta el nombre del guisado.
      const optionText = value ? select.options[select.selectedIndex]?.textContent.trim() || "" : "";
      const name = optionText.includes(" · ") ? optionText.split(" · ").slice(1).join(" · ") : optionText;
      document.querySelectorAll(`[data-stew-stock="${slot}"]`).forEach((stockRow) => {
        const piece = stockRow.dataset.stewPiece;
        stockRow.hidden = !value || row.hidden || (isChicken ? !piece : Boolean(piece));
        const label = stockRow.querySelector(":scope > strong");
        if (label && name) {
          const pieceLabel = piece === "leg" ? " · Pierna" : piece === "thigh" ? " · Muslo" : "";
          label.textContent = `${name}${pieceLabel}`;
        }
      });
    });
    const hiddenRows = rows.filter((row) => row.hidden);
    addButton.hidden = hiddenRows.length === 0;
  };

  addButton.addEventListener("click", () => {
    const next = rows.find((row) => row.hidden);
    if (!next) return;
    next.hidden = false;
    refreshStock();
    selectOf(next)?.focus();
  });
  list.addEventListener("click", (event) => {
    const remove = event.target.closest("[data-stew-remove]");
    if (!remove) return;
    const row = remove.closest("[data-stew-row]");
    const select = selectOf(row);
    if (select) {
      select.value = "";
      select.dispatchEvent(new Event("change", {bubbles: true}));
    }
    // Siempre queda al menos un renglón visible.
    if (rows.filter((candidate) => !candidate.hidden).length > 1) row.hidden = true;
    refreshStock();
  });
  list.addEventListener("change", refreshStock);
  // El borrador del navegador puede llenar renglones ocultos: se muestran si tienen valor.
  rows.forEach((row) => { if (selectOf(row)?.value) row.hidden = false; });
  refreshStock();
  window.setTimeout(() => { rows.forEach((row) => { if (selectOf(row)?.value) row.hidden = false; }); refreshStock(); }, 0);
})();
