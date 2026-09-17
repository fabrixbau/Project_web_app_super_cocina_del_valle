/* NOTA TEMPORAL PARA APRENDIZAJE:
Este script muestra pierna/muslo únicamente cuando el tercer tiempo seleccionado es pollo.
Django conserva la validación obligatoria para que ocultar campos no reduzca seguridad.
Bajo `data-package-add`, Mesas permite guardar pollo sin pieza como comida pendiente.
Borra esta nota después de comprobar ambos formularios. */

document.querySelectorAll("[data-package-form], [data-internal-package]").forEach((form) => {
  const chickenProduct = form.dataset.chickenProduct;
  const pieceField = form.querySelector("[data-chicken-piece-field], [data-package-chicken-field]");
  const mainInputs = form.querySelectorAll("input[name$='main_course']");
  const pieceInputs = pieceField?.querySelectorAll("input[name$='chicken_piece']") || [];
  const isProgressiveTablePackage = form.hasAttribute("data-package-add");

  if (!chickenProduct || !pieceField || !pieceInputs.length) return;

  const dialog = document.createElement("dialog");
  dialog.className = "chicken-piece-overlay-dialog";
  dialog.innerHTML = `
    <section>
      <header>
        <div><small>GUISADO DE POLLO</small><h2>¿Pierna o muslo?</h2><p>Selecciona la pieza para continuar.</p></div>
        <button type="button" data-chicken-overlay-close aria-label="Cancelar selección">×</button>
      </header>
      <div class="chicken-piece-overlay-actions">
        <button type="button" data-chicken-overlay-piece="leg">Pierna</button>
        <button type="button" data-chicken-overlay-piece="thigh">Muslo</button>
      </div>
    </section>`;
  document.body.append(dialog);

  const selectedMainInput = () => [...mainInputs].find((input) => input.checked);
  const closeWithoutPiece = () => {
    const main = selectedMainInput();
    if (main?.value === chickenProduct && ![...pieceInputs].some((input) => input.checked)) {
      main.checked = false;
    }
    dialog.close();
  };

  dialog.querySelector("[data-chicken-overlay-close]").addEventListener("click", closeWithoutPiece);
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeWithoutPiece();
  });
  dialog.querySelectorAll("[data-chicken-overlay-piece]").forEach((button) => {
    button.addEventListener("click", () => {
      pieceInputs.forEach((input) => {
        input.checked = input.value === button.dataset.chickenOverlayPiece;
      });
      dialog.close();
    });
  });

  function updateChickenPiece(promptForPiece = false) {
    const selectedMain = selectedMainInput()?.value;
    const requiresPiece = selectedMain === chickenProduct;
    pieceField.hidden = true;
    pieceInputs.forEach((input) => {
      input.required = requiresPiece && !isProgressiveTablePackage;
      if (!requiresPiece) input.checked = false;
    });
    if (requiresPiece && promptForPiece && ![...pieceInputs].some((input) => input.checked) && !dialog.open) {
      dialog.showModal();
    }
  }

  mainInputs.forEach((input) => input.addEventListener("change", () => updateChickenPiece(true)));
  form.addEventListener("reset", () => setTimeout(() => updateChickenPiece(false)));
  updateChickenPiece();
});

// Los controles de cada ficha manipulan el radio real del formulario. El grupo sigue
// siendo atómico: sólo se envía cuando los tres tiempos están completos.
document.querySelectorAll("[data-package-choice]").forEach((card) => {
  const input = card.querySelector("input[type='radio']");
  const quantity = card.querySelector("[data-package-choice-quantity]");
  if (!input || !quantity) return;
  const sync = () => {
    quantity.textContent = input.checked ? "1" : "0";
    card.classList.toggle("is-selected", input.checked);
  };
  card.querySelector("[data-package-choice-plus]")?.addEventListener("click", () => {
    input.checked = true;
    input.dispatchEvent(new Event("change", {bubbles: true}));
    card.closest("[data-package-choice-group]")?.querySelectorAll("[data-package-choice]").forEach((candidate) => {
      const candidateInput = candidate.querySelector("input[type='radio']");
      const candidateQuantity = candidate.querySelector("[data-package-choice-quantity]");
      if (candidateQuantity) candidateQuantity.textContent = candidateInput?.checked ? "1" : "0";
      candidate.classList.toggle("is-selected", Boolean(candidateInput?.checked));
    });
  });
  card.querySelector("[data-package-choice-minus]")?.addEventListener("click", () => {
    input.checked = false;
    input.dispatchEvent(new Event("change", {bubbles: true}));
    sync();
  });
  card.querySelector("[data-package-choice-customize]")?.addEventListener("click", () => {
    input.checked = true;
    input.dispatchEvent(new Event("change", {bubbles: true}));
    sync();
    const form = card.closest("form");
    const comment = form?.querySelector("textarea[name$='customization_comment']");
    if (!comment) return;
    if (!comment.value.trim()) comment.value = `${card.dataset.searchName}: `;
    comment.focus({preventScroll: true});
    comment.setSelectionRange(comment.value.length, comment.value.length);
  });
  input.addEventListener("change", sync);
  sync();
});

document.querySelectorAll("[data-package-choice-group]").forEach((group) => {
  group.addEventListener("change", () => {
    group.querySelectorAll("[data-package-choice]").forEach((card) => {
      const selected = Boolean(card.querySelector("input[type='radio']")?.checked);
      card.classList.toggle("is-selected", selected);
      const quantity = card.querySelector("[data-package-choice-quantity]");
      if (quantity) quantity.textContent = selected ? "1" : "0";
    });
  });
});

// Evita el salto del control nativo de checkbox dentro de dialogs móviles. Los botones
// visuales cambian el campo real sin enviar el formulario ni cerrar su capa superior.
document.querySelectorAll(".package-water-toggle label").forEach((control) => {
  const checkbox = control.querySelector("input[type='checkbox']");
  const choices = [...control.querySelectorAll(":scope > span")];
  if (!checkbox || choices.length < 2) return;
  choices.forEach((choice, index) => {
    choice.setAttribute("role", "button");
    choice.tabIndex = 0;
    const choose = () => {
      checkbox.checked = index === 1;
      checkbox.dispatchEvent(new Event("change", {bubbles: true}));
    };
    choice.addEventListener("click", (event) => { event.preventDefault(); event.stopPropagation(); choose(); });
    choice.addEventListener("keydown", (event) => {
      if (!['Enter', ' '].includes(event.key)) return;
      event.preventDefault(); choose();
    });
  });
});

document.querySelectorAll(".table-water-choice").forEach((control) => {
  const checkbox = control.querySelector("input[type='checkbox']");
  if (!checkbox) return;
  control.addEventListener("click", (event) => {
    event.preventDefault();
    checkbox.checked = !checkbox.checked;
    checkbox.dispatchEvent(new Event("change", {bubbles: true}));
  });
});
