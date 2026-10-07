/* NOTA TEMPORAL PARA APRENDIZAJE:
Este script muestra pierna/muslo únicamente cuando el tercer tiempo seleccionado es pollo.
Django conserva la validación obligatoria para que ocultar campos no reduzca seguridad.
Bajo `data-package-add`, Mesas permite guardar pollo sin pieza como comida pendiente.
Borra esta nota después de comprobar ambos formularios. */

document.querySelectorAll("[data-package-form], [data-internal-package]").forEach((form) => {
  // Guisados de pollo del día ("12,15"): cualquiera de ellos pide pierna o muslo.
  const chickenProducts = (form.dataset.chickenProduct || "").split(",").filter(Boolean);
  const chickenProduct = chickenProducts.length ? chickenProducts : null;
  const isChicken = (value) => Boolean(value) && chickenProducts.includes(String(value));
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
    if (isChicken(main?.value) && ![...pieceInputs].some((input) => input.checked)) {
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
    const requiresPiece = isChicken(selectedMain);
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

// Los paquetes internos pueden cobrarse con dos tiempos sin cambiar su precio.
// La marca viaja en el formulario para que cocina, edición y transferencias conserven
// cuál de los dos primeros tiempos fue omitido. El portal de clientes ([data-pp-package])
// detecta 2 tiempos solo y tiene su propio contador (public-portal.js).
document.querySelectorAll("[data-package-form]:not([data-pp-package]), [data-internal-package]").forEach((form) => {
  const firstInputs = [...form.querySelectorAll("input[name$='first_course']")];
  const secondInputs = [...form.querySelectorAll("input[name$='second_course']")];
  if (!firstInputs.length || !secondInputs.length) return;

  let toggle = form.querySelector("input[name$='two_course']");
  if (!toggle) {
    toggle = document.createElement("input");
    toggle.type = "checkbox";
    toggle.name = firstInputs[0].name.replace(/first_course$/, "two_course");
  }
  let control = toggle.closest(".package-two-course-toggle");
  if (!control) {
    control = document.createElement("label");
    control.className = "package-two-course-toggle";
    toggle.before(control);
    control.append(toggle);
    const switcher = document.createElement("span");
    switcher.className = "package-two-course-switch";
    switcher.setAttribute("aria-hidden", "true");
    const copy = document.createElement("span");
    copy.innerHTML = "<strong>2 tiempos</strong>";
    control.append(switcher, copy);
  }
  const heading = form.querySelector(":scope > .dialog-heading");
  const searchButton = heading?.querySelector("[data-package-candidate-search-open]");
  const closeButton = heading?.querySelector("[data-package-close]");
  (searchButton || closeButton)?.before(control);

  const groups = [firstInputs, secondInputs];
  const clearGroup = (inputs) => inputs.forEach((input) => {
    input.checked = false;
    input.required = false;
    input.dispatchEvent(new Event("change", {bubbles: true}));
  });
  const refresh = () => {
    const enabled = toggle.checked;
    groups.forEach((inputs) => inputs.forEach((input) => { input.required = !enabled; }));
    form.classList.toggle("is-two-course-package", enabled);
  };
  // Al encender 2 tiempos sólo se quita algo si primer Y segundo tiempo estaban
  // elegidos: se conserva el que se eligió al último. Con uno solo no se borra nada.
  let lastChosenGroup = null;
  const hasChoice = (inputs) => inputs.some((input) => input.checked);
  [...firstInputs, ...secondInputs].forEach((input) => input.addEventListener("change", () => {
    if (!input.checked) return;
    const ownGroup = firstInputs.includes(input) ? firstInputs : secondInputs;
    lastChosenGroup = ownGroup;
    if (!toggle.checked) return;
    clearGroup(ownGroup === firstInputs ? secondInputs : firstInputs);
    refresh();
  }));
  toggle.addEventListener("change", () => {
    if (toggle.checked && hasChoice(firstInputs) && hasChoice(secondInputs)) {
      clearGroup(lastChosenGroup === firstInputs ? secondInputs : firstInputs);
    }
    refresh();
  });
  form.addEventListener("reset", () => setTimeout(refresh));
  refresh();
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
  // Personalizar elige este producto para su tiempo y abre la ficha de ingredientes.
  // Si el producto no tiene ficha disponible, se conserva el respaldo anterior:
  // escribir su nombre en el comentario del paquete y llevar la vista hasta ahí.
  card.querySelector("[data-package-choice-customize]")?.addEventListener("click", () => {
    input.checked = true;
    input.dispatchEvent(new Event("change", {bubbles: true}));
    sync();
    const form = card.closest("form");
    if (form?.packageCustomizations?.open(input)) return;
    const comment = form?.querySelector("textarea[name$='customization_comment']");
    if (!comment) return;
    if (!comment.value.trim()) comment.value = `${card.dataset.searchName}: `;
    comment.scrollIntoView({block: "center"});
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

/* NOTA TEMPORAL PARA APRENDIZAJE: diálogo de paquete con varias comidas.
- Personalizar abre la ficha de ingredientes del producto (window.ProductSelector) y guarda
  lo elegido por tiempo en `component_customizations` (JSON). El servidor sólo toma la
  del producto que quedó elegido en ese tiempo.
- Contador − # + junto a "2 tiempos": "+" guarda el paquete armado (todos los campos del
  formulario) y limpia la plantilla completa, con 2 tiempos apagado; "−" descarta el
  paquete en curso y vuelve a cargar el anterior. Al enviar con paquetes guardados se
  agrega `package_batch` (JSON) y los paquetes idénticos viajan juntos con su cantidad.
Borra esta nota después de probar Mesas y Pedidos. */
document.querySelectorAll("form[data-package-form]:not([data-historical-edit-form]):not([data-pp-package]), form[data-internal-package]").forEach((form) => {
  const COURSE_FIELD = /(first_course|second_course|main_course)$/;
  const SKIPPED_FIELDS = ["csrfmiddlewaretoken", "package_batch"];
  const MAX_PACKAGES = 99;
  const dialog = form.closest("dialog");
  const errorBox = form.querySelector("[data-package-error]");
  let customizations = {};
  let savedPackages = [];
  let restoringTemplate = false;

  const customizationField = document.createElement("input");
  customizationField.type = "hidden";
  customizationField.name = "component_customizations";
  form.append(customizationField);

  // ---- Personalización por tiempo -------------------------------------------------
  const refreshCustomizedCards = () => {
    form.querySelectorAll("[data-package-choice]").forEach((card) => {
      const input = card.querySelector("input[type='radio']");
      const field = input?.name.match(COURSE_FIELD)?.[1];
      const customized = Boolean(
        input?.checked && field && customizations[field]?.product_id === input.value,
      );
      card.classList.toggle("is-customized", customized);
      const button = card.querySelector("[data-package-choice-customize]");
      if (button) button.textContent = customized ? "Personalizado ✓" : "Personalizar";
    });
  };
  const writeCustomizations = () => {
    customizationField.value = Object.keys(customizations).length ? JSON.stringify(customizations) : "";
    refreshCustomizedCards();
  };
  const loadCustomizations = (raw) => {
    try { customizations = raw ? JSON.parse(raw) : {}; } catch { customizations = {}; }
    writeCustomizations();
  };

  form.packageCustomizations = {
    open(input) {
      const field = input.name.match(COURSE_FIELD)?.[1];
      if (!field || !window.ProductSelector) return false;
      const current = customizations[field]?.product_id === input.value ? customizations[field] : null;
      const launch = () => window.ProductSelector.open(input.value, {
        selection: current ? {optionIds: current.option_ids, comment: current.comment} : null,
        onConfirm: ({optionIds, comment, customized}) => {
          if (customized) customizations[field] = {product_id: input.value, option_ids: optionIds, comment};
          else delete customizations[field];
          writeCustomizations();
        },
      });
      // Si el pollo abrió primero su ventanita de pierna o muslo, la ficha espera a que cierre.
      const chickenPrompt = document.querySelector(".chicken-piece-overlay-dialog[open]");
      if (chickenPrompt) {
        chickenPrompt.addEventListener("close", () => { if (input.checked) launch(); }, {once: true});
        return true;
      }
      return launch();
    },
  };
  form.addEventListener("change", refreshCustomizedCards);

  // ---- Contador de paquetes -------------------------------------------------------
  const counter = document.createElement("div");
  counter.className = "product-selector-counter package-dialog-counter";
  counter.setAttribute("role", "group");
  counter.setAttribute("aria-label", "Paquetes por agregar");
  counter.innerHTML = `
    <button type="button" data-package-count-decrease aria-label="Quitar el paquete en curso y editar el anterior">−</button>
    <strong data-package-count aria-live="polite">1</strong>
    <button type="button" data-package-count-increase aria-label="Guardar este paquete y armar otro">+</button>`;
  const heading = form.querySelector(":scope > .dialog-heading");
  const anchor = heading?.querySelector(".package-two-course-toggle, [data-package-candidate-search-open], .package-modal-search-launcher, [data-package-close]");
  if (anchor) anchor.before(counter);
  else heading?.append(counter);
  const countElement = counter.querySelector("[data-package-count]");
  const decreaseButton = counter.querySelector("[data-package-count-decrease]");
  const increaseButton = counter.querySelector("[data-package-count-increase]");
  const submitButton = form.querySelector("[data-package-submit], button[type='submit']");
  const submitText = submitButton?.textContent || "";

  const refreshCounter = () => {
    const count = savedPackages.length + 1;
    countElement.textContent = String(count);
    decreaseButton.disabled = savedPackages.length === 0;
    increaseButton.disabled = count >= MAX_PACKAGES;
    if (submitButton) submitButton.textContent = count > 1 ? `Agregar ${count} paquetes al ticket` : submitText;
  };

  const showError = (message) => {
    if (!errorBox) {
      window.alert(message);
      return;
    }
    errorBox.className = "message error";
    errorBox.textContent = message;
    errorBox.hidden = false;
  };
  const clearError = () => {
    if (!errorBox) return;
    errorBox.replaceChildren();
    errorBox.className = "";
    // Pedidos oculta su caja de error con `hidden`; Mesas la deja vacía.
    errorBox.hidden = form.matches("[data-internal-package]");
  };

  // Todos los campos del paquete en pantalla, sin token ni lote.
  const snapshot = () => [...new FormData(form).entries()]
    .filter(([name, value]) => typeof value === "string" && !SKIPPED_FIELDS.includes(name));

  const syncPackagingOutputs = () => form.querySelectorAll(".package-packaging-counter").forEach((box) => {
    const input = box.querySelector("input[type='hidden']");
    const output = box.querySelector("output");
    if (!input || !output) return;
    output.value = input.value || "0";
    output.textContent = input.value || "0";
  });
  // Las tarjetas, el huevo y la pieza de pollo se redibujan al escuchar `change`.
  const refreshControls = () => {
    form.querySelectorAll("input[type='radio']").forEach((input) => {
      if (COURSE_FIELD.test(input.name)) input.dispatchEvent(new Event("change", {bubbles: true}));
    });
    form.querySelectorAll("select").forEach((select) => select.dispatchEvent(new Event("change", {bubbles: true})));
  };

  // Restablece la plantilla. Algunos scripts reaplican sus valores por omisión en un
  // `setTimeout` tras `reset`; `after` corre después de ellos.
  const resetTemplate = (after) => {
    restoringTemplate = true;
    form.reset();
    // Los envases guardan su cantidad en inputs ocultos, que `reset` no regresa a cero.
    form.querySelectorAll(".package-packaging-counter input[type='hidden']").forEach((input) => { input.value = "0"; });
    customizations = {};
    window.setTimeout(() => {
      const twoCourse = form.querySelector("input[name$='two_course']");
      if (twoCourse?.checked) {
        twoCourse.checked = false;
        twoCourse.dispatchEvent(new Event("change", {bubbles: true}));
      }
      refreshControls();
      writeCustomizations();
      after?.();
      syncPackagingOutputs();
      restoringTemplate = false;
    });
  };

  const applySnapshot = (fields) => {
    const pairs = new Set(fields.map(([name, value]) => `${name}\u0000${value}`));
    const values = new Map();
    fields.forEach(([name, value]) => { if (!values.has(name)) values.set(name, value); });
    // 2 tiempos va primero: al encenderse limpia primer y segundo tiempo.
    const twoCourse = form.querySelector("input[name$='two_course']");
    if (twoCourse) {
      twoCourse.checked = pairs.has(`${twoCourse.name}\u0000${twoCourse.value}`);
      twoCourse.dispatchEvent(new Event("change", {bubbles: true}));
    }
    const assign = () => [...form.elements].forEach((element) => {
      if (!element.name || element === twoCourse || element.type === "file" || SKIPPED_FIELDS.includes(element.name)) return;
      if (element.type === "radio" || element.type === "checkbox") {
        element.checked = pairs.has(`${element.name}\u0000${element.value}`);
      } else if (values.has(element.name)) {
        element.value = values.get(element.name);
      }
    });
    assign();
    refreshControls();
    // Algunos `change` desmarcan extras ligados (p. ej. bolillo); se vuelven a aplicar.
    assign();
    loadCustomizations(values.get("component_customizations") || "");
  };

  const hasAnyCourse = () => [...form.querySelectorAll("input[type='radio']")]
    .some((input) => COURSE_FIELD.test(input.name) && input.checked);

  increaseButton.addEventListener("click", () => {
    if (savedPackages.length + 1 >= MAX_PACKAGES) return;
    if (!hasAnyCourse()) {
      showError("Elige los tiempos de este paquete antes de armar otro.");
      return;
    }
    if (!form.checkValidity()) {
      showError("Completa este paquete antes de armar otro.");
      return;
    }
    clearError();
    savedPackages.push(snapshot());
    resetTemplate();
    refreshCounter();
    form.scrollTop = 0;
    if (dialog) dialog.scrollTop = 0;
  });
  decreaseButton.addEventListener("click", () => {
    if (!savedPackages.length) return;
    const previous = savedPackages.pop();
    clearError();
    resetTemplate(() => applySnapshot(previous));
    refreshCounter();
  });

  // Con paquetes guardados, el envío normal lleva el lote completo. Este listener
  // corre antes que los de Mesas y Pedidos (que escuchan en `document`).
  form.addEventListener("submit", () => {
    form.querySelectorAll("input[name='package_batch']").forEach((input) => input.remove());
    if (!savedPackages.length) return;
    const groups = new Map();
    [...savedPackages, snapshot()].forEach((fields) => {
      const key = JSON.stringify([...fields].sort());
      const group = groups.get(key);
      if (group) group.quantity += 1;
      else groups.set(key, {fields, quantity: 1});
    });
    const batch = document.createElement("input");
    batch.type = "hidden";
    batch.name = "package_batch";
    batch.value = JSON.stringify([...groups.values()]);
    form.append(batch);
  });

  // Tras agregar al ticket, al reabrir o al cerrar el diálogo, el contador vuelve a 1.
  const discardSaved = () => {
    savedPackages = [];
    form.querySelectorAll("input[name='package_batch']").forEach((input) => input.remove());
    refreshCounter();
  };
  form.addEventListener("reset", () => {
    if (restoringTemplate) return;
    customizations = {};
    writeCustomizations();
    discardSaved();
  });
  dialog?.addEventListener("close", discardSaved);
  refreshCounter();
});
