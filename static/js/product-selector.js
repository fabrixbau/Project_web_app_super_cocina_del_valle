/* NOTA TEMPORAL PARA APRENDIZAJE:
El mismo selector intercepta formularios públicos y de Mesas. Todos permiten comentario;
si existen grupos también muestra ingredientes. Las opciones con el mismo par son sustitutos:
su equivalente; después inserta option_ids en el formulario original y continúa el flujo normal.
Borra esta nota después de probar ambos canales. */

(() => {
  const dialog = document.querySelector("[data-product-selector-dialog]");
  const dataNode = document.querySelector("#product-selector-data");
  if (!dialog || !dataNode) return;
  const products = JSON.parse(dataNode.textContent || "{}");
  const groupsContainer = dialog.querySelector("[data-selector-groups]");
  const errorBox = dialog.querySelector("[data-selector-error]");
  const priceElement = dialog.querySelector("[data-selector-price]");
  const modifiedBadge = dialog.querySelector("[data-selector-modified]");
  const commentInput = dialog.querySelector("[data-selector-comment]");
  const currency = new Intl.NumberFormat("es-MX", {style: "currency", currency: "MXN"});
  let activeForm = null;
  let activeProduct = null;

  function selectedIds() {
    return [...dialog.querySelectorAll("[data-option-id]:checked")].map((input) => Number(input.value));
  }

  function refreshSummary() {
    if (!activeProduct) return;
    const selected = new Set(selectedIds());
    const defaults = new Set();
    let price = Number(activeProduct.base_price);
    activeProduct.groups.forEach((group) => group.options.forEach((option) => {
      if (option.is_default) defaults.add(option.id);
      if (selected.has(option.id)) price += Number(option.price_adjustment);
    }));
    priceElement.textContent = currency.format(price);
    const standardOptions = selected.size === defaults.size && [...selected].every((id) => defaults.has(id));
    modifiedBadge.hidden = standardOptions && !commentInput.value.trim();
  }

  function openSelector(form, product) {
    activeForm = form;
    activeProduct = product;
    dialog.querySelector("[data-selector-product-name]").textContent = product.name;
    errorBox.hidden = true;
    commentInput.value = "";
    groupsContainer.replaceChildren();
    if (!product.groups.length) {
      const explanation = document.createElement("p");
      explanation.className = "selector-without-ingredients";
      explanation.textContent = "Este producto no tiene ingredientes configurados. Puedes agregar una indicación especial en el comentario.";
      groupsContainer.append(explanation);
    }
    product.groups.forEach((group) => {
      const section = document.createElement("fieldset");
      section.className = "selector-group";
      section.dataset.required = group.is_required ? "true" : "false";
      const legend = document.createElement("legend");
      legend.textContent = group.name;
      const help = document.createElement("small");
      help.textContent = group.selection_type === "single"
        ? (group.is_required ? "Elige una opción" : "Puedes elegir una opción")
        : (group.is_required ? "Conserva al menos una opción" : "Agrega o quita ingredientes");
      section.append(legend, help);
      group.options.forEach((option) => {
        const label = document.createElement("label");
        label.className = "selector-option";
        const input = document.createElement("input");
        input.type = group.selection_type === "single" ? "radio" : "checkbox";
        input.name = `selector-group-${group.id}`;
        input.value = option.id;
        input.dataset.optionId = option.id;
        input.dataset.optionGroup = group.id;
        input.dataset.replacementPair = option.replacement_pair || "";
        input.checked = option.is_default;
        const text = document.createElement("span");
        const name = document.createElement("strong");
        name.textContent = option.name;
        const adjustment = document.createElement("small");
        const amount = Number(option.price_adjustment);
        adjustment.textContent = amount ? `+${currency.format(amount)}` : (option.is_default ? "Incluido" : "Sin cargo");
        text.append(name, adjustment);
        label.append(input, text);
        input.addEventListener("change", () => {
          if (input.checked && input.dataset.replacementPair) {
            dialog.querySelectorAll("[data-option-id]:checked").forEach((candidate) => {
              if (candidate !== input && candidate.dataset.optionGroup === input.dataset.optionGroup && candidate.dataset.replacementPair.toLocaleLowerCase("es-MX") === input.dataset.replacementPair.toLocaleLowerCase("es-MX")) {
                candidate.checked = false;
              }
            });
          }
          refreshSummary();
        });
        section.append(label);
      });
      groupsContainer.append(section);
    });
    refreshSummary();
    dialog.showModal();
  }

  document.addEventListener("submit", (event) => {
    const form = event.target.closest("form[data-customizable-product]");
    if (!form || form.dataset.selectionReady === "true" || form.querySelector("input[data-generated-option]")) {
      if (form) delete form.dataset.selectionReady;
      return;
    }
    const product = products[String(form.dataset.customizableProduct)];
    if (!product) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    openSelector(form, product);
  }, true);

  dialog.querySelector("[data-selector-close]").addEventListener("click", () => {
    activeForm = null;
    dialog.close();
  });
  commentInput.addEventListener("input", refreshSummary);
  dialog.querySelector("[data-selector-confirm]").addEventListener("click", () => {
    const missing = [...dialog.querySelectorAll(".selector-group[data-required='true']")].find(
      (group) => !group.querySelector("[data-option-id]:checked"),
    );
    if (missing) {
      errorBox.textContent = `Elige una opción en ${missing.querySelector("legend").textContent}.`;
      errorBox.hidden = false;
      return;
    }
    activeForm.querySelectorAll("input[data-generated-option]").forEach((input) => input.remove());
    const selectionMarker = document.createElement("input");
    selectionMarker.type = "hidden";
    selectionMarker.name = "customization_selected";
    selectionMarker.value = "1";
    selectionMarker.dataset.generatedOption = "";
    activeForm.append(selectionMarker);
    selectedIds().forEach((optionId) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "option_ids";
      input.value = optionId;
      input.dataset.generatedOption = "";
      activeForm.append(input);
    });
    const comment = document.createElement("input");
    comment.type = "hidden";
    comment.name = "customization_comment";
    comment.value = commentInput.value.trim();
    comment.dataset.generatedOption = "";
    activeForm.append(comment);
    activeForm.dataset.selectionReady = "true";
    const form = activeForm;
    activeForm = null;
    dialog.close();
    form.requestSubmit();
  });
})();
