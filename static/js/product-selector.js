/* NOTA TEMPORAL PARA APRENDIZAJE:
El mismo selector intercepta formularios públicos y de Mesas. Todos permiten comentario;
si existen grupos también muestra ingredientes. Las opciones con el mismo par son sustitutos:
su equivalente; después inserta option_ids en el formulario original y continúa el flujo normal.
Contador − # +: "+" guarda la pieza en pantalla y reinicia la plantilla; "−" descarta la
pieza en curso y vuelve a cargar la anterior. Con varias piezas se envía un solo
`customization_batch` (JSON) donde las piezas idénticas viajan juntas con su cantidad; el
servidor las registra una por una y une en una línea las que tienen la misma firma.
`window.ProductSelector.open()` reutiliza la ficha para un tiempo del diálogo de paquete:
sin contador, y en lugar de enviar un formulario entrega la selección a quien la pidió.
Borra esta nota después de probar ambos canales. */

(() => {
  const dialog = document.querySelector("[data-product-selector-dialog]");
  const dataNode = document.querySelector("#product-selector-data");
  if (!dialog || !dataNode) return;
  const products = JSON.parse(dataNode.textContent || "{}");
  const groupsContainer = dialog.querySelector("[data-selector-groups]");
  const errorBox = dialog.querySelector("[data-selector-error]");
  const priceElement = dialog.querySelector("[data-selector-price]");
  const confirmLabel = dialog.querySelector("[data-selector-confirm] > span");
  const modifiedBadge = dialog.querySelector("[data-selector-modified]");
  const commentInput = dialog.querySelector("[data-selector-comment]");
  const countElement = dialog.querySelector("[data-selector-count]");
  const decreaseButton = dialog.querySelector("[data-selector-decrease]");
  const increaseButton = dialog.querySelector("[data-selector-increase]");
  const currency = new Intl.NumberFormat("es-MX", {style: "currency", currency: "MXN"});
  const MAX_PIECES = 99;
  let activeForm = null;
  let activeProduct = null;
  let savedPieces = [];
  let externalConfirm = null;

  function selectedIds() {
    return [...dialog.querySelectorAll("[data-option-id]:checked")].map((input) => Number(input.value));
  }

  function currentPiece() {
    return {optionIds: selectedIds(), comment: commentInput.value.trim()};
  }

  // Sin pieza se restablece la plantilla: opciones estándar y comentario vacío.
  function applyPiece(piece) {
    const chosen = piece ? new Set(piece.optionIds) : null;
    dialog.querySelectorAll("[data-option-id]").forEach((input) => {
      input.checked = chosen ? chosen.has(Number(input.value)) : input.dataset.default === "true";
    });
    commentInput.value = piece?.comment || "";
    errorBox.hidden = true;
    groupsContainer.scrollTop = 0;
  }

  function piecePrice(optionIds) {
    const selected = new Set(optionIds);
    let price = Number(activeProduct.base_price);
    activeProduct.groups.forEach((group) => group.options.forEach((option) => {
      if (selected.has(option.id)) price += Number(option.price_adjustment);
    }));
    return price;
  }

  function refreshSummary() {
    if (!activeProduct) return;
    const current = currentPiece();
    const selected = new Set(current.optionIds);
    const defaults = new Set();
    activeProduct.groups.forEach((group) => group.options.forEach((option) => {
      if (option.is_default) defaults.add(option.id);
    }));
    const total = savedPieces.reduce((sum, piece) => sum + piecePrice(piece.optionIds), piecePrice(current.optionIds));
    const count = savedPieces.length + 1;
    priceElement.textContent = currency.format(total);
    if (externalConfirm) confirmLabel.textContent = "Aplicar";
    else confirmLabel.textContent = count > 1 ? `Agregar ${count} productos` : "Agregar producto";
    countElement.textContent = String(count);
    decreaseButton.disabled = savedPieces.length === 0;
    increaseButton.disabled = count >= MAX_PIECES;
    const standardOptions = selected.size === defaults.size && [...selected].every((id) => defaults.has(id));
    modifiedBadge.hidden = standardOptions && !current.comment;
  }

  function missingRequiredGroup() {
    const missing = [...dialog.querySelectorAll(".selector-group[data-required='true']")].find(
      (group) => !group.querySelector("[data-option-id]:checked"),
    );
    if (!missing) return false;
    errorBox.textContent = `Elige una opción en ${missing.querySelector("legend").textContent}.`;
    errorBox.hidden = false;
    return true;
  }

  // Une las piezas idénticas (mismas opciones y mismo comentario, igual que la firma
  // del servidor) para enviarlas como una sola entrada con su cantidad.
  function groupedPieces(pieces) {
    const groups = new Map();
    pieces.forEach((piece) => {
      const optionIds = [...piece.optionIds].sort((a, b) => a - b);
      const comment = piece.comment.split(/\s+/).filter(Boolean).join(" ");
      const key = `${optionIds.join(",")}|${comment.toLocaleLowerCase("es-MX")}`;
      const group = groups.get(key);
      if (group) group.quantity += 1;
      else groups.set(key, {option_ids: optionIds, comment, quantity: 1});
    });
    return [...groups.values()];
  }

  function appendHidden(form, name, value) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    input.dataset.generatedOption = "";
    form.append(input);
  }

  function openSelector(form, product, external = null) {
    activeForm = form;
    activeProduct = product;
    savedPieces = [];
    externalConfirm = external?.onConfirm || null;
    dialog.classList.toggle("is-external", Boolean(externalConfirm));
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
      const options = document.createElement("div");
      options.className = "selector-options";
      section.append(legend, help, options);
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
        input.dataset.default = option.is_default ? "true" : "false";
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
        options.append(label);
      });
      groupsContainer.append(section);
    });
    if (external?.selection) applyPiece(external.selection);
    refreshSummary();
    dialog.showModal();
  }

  // Ficha para un tiempo del paquete: entrega {optionIds, comment, customized}.
  window.ProductSelector = {
    open(productId, {selection = null, onConfirm} = {}) {
      const product = products[String(productId)];
      if (!product || !onConfirm) return false;
      openSelector(null, product, {selection, onConfirm});
      return true;
    },
  };

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
    savedPieces = [];
    externalConfirm = null;
    dialog.close();
  });
  commentInput.addEventListener("input", refreshSummary);

  increaseButton.addEventListener("click", () => {
    if (!activeProduct || savedPieces.length + 1 >= MAX_PIECES || missingRequiredGroup()) return;
    savedPieces.push(currentPiece());
    applyPiece(null);
    refreshSummary();
  });
  decreaseButton.addEventListener("click", () => {
    if (!savedPieces.length) return;
    applyPiece(savedPieces.pop());
    refreshSummary();
  });

  dialog.querySelector("[data-selector-confirm]").addEventListener("click", () => {
    if (missingRequiredGroup()) return;
    if (externalConfirm) {
      const piece = currentPiece();
      const done = externalConfirm;
      externalConfirm = null;
      dialog.close();
      done({...piece, customized: !modifiedBadge.hidden});
      return;
    }
    const pieces = [...savedPieces, currentPiece()];
    activeForm.querySelectorAll("input[data-generated-option]").forEach((input) => input.remove());
    appendHidden(activeForm, "customization_selected", "1");
    if (pieces.length === 1) {
      pieces[0].optionIds.forEach((optionId) => appendHidden(activeForm, "option_ids", optionId));
      appendHidden(activeForm, "customization_comment", pieces[0].comment);
    } else {
      appendHidden(activeForm, "customization_batch", JSON.stringify(groupedPieces(pieces)));
    }
    activeForm.dataset.selectionReady = "true";
    const form = activeForm;
    activeForm = null;
    savedPieces = [];
    dialog.close();
    form.requestSubmit();
  });
})();
