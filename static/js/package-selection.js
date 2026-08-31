/* NOTA TEMPORAL PARA APRENDIZAJE:
Este script muestra pierna/muslo únicamente cuando el tercer tiempo seleccionado es pollo.
Django conserva la validación obligatoria para que ocultar campos no reduzca seguridad.
Bajo `data-package-add`, Mesas permite guardar pollo sin pieza como comida pendiente.
Borra esta nota después de comprobar ambos formularios. */

document.querySelectorAll("[data-package-form]").forEach((form) => {
  const chickenProduct = form.dataset.chickenProduct;
  const pieceField = form.querySelector("[data-chicken-piece-field]");
  const mainInputs = form.querySelectorAll("input[name$='main_course']");
  const pieceInputs = pieceField?.querySelectorAll("input[name$='chicken_piece']") || [];
  const isProgressiveTablePackage = form.hasAttribute("data-package-add");

  function updateChickenPiece() {
    const selectedMain = [...mainInputs].find((input) => input.checked)?.value;
    const requiresPiece = selectedMain === chickenProduct;
    pieceField.hidden = !requiresPiece;
    pieceInputs.forEach((input) => {
      input.required = requiresPiece && !isProgressiveTablePackage;
      if (!requiresPiece) input.checked = false;
    });
  }

  mainInputs.forEach((input) => input.addEventListener("change", updateChickenPiece));
  form.addEventListener("reset", () => setTimeout(updateChickenPiece));
  updateChickenPiece();
});
