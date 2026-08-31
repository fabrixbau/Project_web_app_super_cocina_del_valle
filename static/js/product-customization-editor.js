/* NOTA TEMPORAL PARA APRENDIZAJE:
Este editor mantiene grupos e ingredientes en memoria y sincroniza un JSON oculto antes de
guardar. "Par de sustitución" conecta equivalentes: crema y mayonesa pueden compartir Aderezo.
Django vuelve a validar todo el contenido en el servidor. Borra esta nota cuando comprendas el flujo. */

(() => {
  const editor = document.querySelector("[data-customization-editor]");
  if (!editor) return;

  const form = editor.closest("form");
  const list = editor.querySelector("[data-group-list]");
  const payloadInput = editor.querySelector("[data-customization-payload]");
  const emptyMessage = editor.querySelector("[data-empty-groups]");
  const errorBox = editor.querySelector("[data-customization-errors]");
  const librarySelect = editor.querySelector("[data-group-library]");
  const parseScript = (id) => JSON.parse(document.querySelector(id)?.textContent || "[]");
  let groups = parseScript("#product-customization-data");
  const library = parseScript("#product-customization-library");

  const normalizeGroup = (group = {}) => ({
    id: group.id || null,
    shared_key: group.shared_key || null,
    name: group.name || "",
    selection_type: group.selection_type === "single" ? "single" : "multiple",
    is_required: group.is_required === true,
    options: (group.options || []).map(normalizeOption),
  });

  function normalizeOption(option = {}) {
    return {
      id: option.id || null,
      name: option.name || "",
      price_adjustment: String(option.price_adjustment ?? "0.00"),
      replacement_pair: option.replacement_pair || "",
      is_default: option.is_default === true,
      is_available: option.is_available !== false,
    };
  }

  groups = groups.map(normalizeGroup);

  function element(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function field(labelText, input) {
    const label = element("label", "integrated-field");
    label.append(element("strong", "", labelText), input);
    return label;
  }

  function textInput(value, onInput, attributes = {}) {
    const input = document.createElement("input");
    input.type = attributes.type || "text";
    input.value = value;
    Object.entries(attributes).forEach(([key, attributeValue]) => {
      if (key !== "type") input.setAttribute(key, attributeValue);
    });
    input.addEventListener("input", () => { onInput(input.value); sync(); });
    return input;
  }

  function checkbox(labelText, checked, onChange, className = "") {
    const label = element("label", `integrated-check ${className}`.trim());
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = checked;
    input.addEventListener("change", () => { onChange(input.checked); render(); });
    label.append(input, element("span", "", labelText));
    return label;
  }

  function actionButton(label, action, className = "") {
    const button = element("button", className, label);
    button.type = "button";
    button.addEventListener("click", action);
    return button;
  }

  function renderOption(group, groupIndex, option, optionIndex) {
    const row = element("article", "integrated-option-row");
    const name = textInput(option.name, (value) => { option.name = value; }, {placeholder: "Ej. Jitomate"});
    const charge = textInput(option.price_adjustment, (value) => { option.price_adjustment = value; }, {type: "number", min: "0", step: "0.50"});
    const replacementPair = textInput(option.replacement_pair, (value) => { option.replacement_pair = value; }, {placeholder: "Ej. Aderezo"});
    const standard = checkbox("Estándar", option.is_default, (checked) => {
      if (checked && group.selection_type === "single") {
        group.options.forEach((candidate) => { candidate.is_default = false; });
      }
      if (checked && option.replacement_pair.trim()) {
        group.options.forEach((candidate) => {
          if (candidate !== option && candidate.replacement_pair.trim().toLocaleLowerCase("es-MX") === option.replacement_pair.trim().toLocaleLowerCase("es-MX")) {
            candidate.is_default = false;
          }
        });
      }
      option.is_default = checked;
      if (checked) option.is_available = true;
    }, "standard-option");
    const available = checkbox("Disponible", option.is_available, (checked) => {
      option.is_available = checked;
      if (!checked) option.is_default = false;
    });
    const actions = element("div", "integrated-row-actions");
    actions.append(
      actionButton("↑", () => moveItem(group.options, optionIndex, -1), "compact-button"),
      actionButton("↓", () => moveItem(group.options, optionIndex, 1), "compact-button"),
      actionButton("×", () => { group.options.splice(optionIndex, 1); render(); }, "danger compact-button"),
    );
    row.append(
      field("Ingrediente u opción", name),
      field("Cargo adicional", charge),
      field("Par de sustitución", replacementPair),
      standard,
      available,
      actions,
    );
    return row;
  }

  function renderGroup(group, groupIndex) {
    const card = element("section", "integrated-group-card");
    const heading = element("header");
    heading.append(element("strong", "", `Grupo ${groupIndex + 1}`));
    const groupActions = element("div", "integrated-row-actions");
    groupActions.append(
      actionButton("↑", () => moveItem(groups, groupIndex, -1), "compact-button"),
      actionButton("↓", () => moveItem(groups, groupIndex, 1), "compact-button"),
      actionButton("Eliminar grupo", () => { groups.splice(groupIndex, 1); render(); }, "danger compact-button"),
    );
    heading.append(groupActions);

    const settings = element("div", "integrated-group-settings");
    const name = textInput(group.name, (value) => { group.name = value; }, {placeholder: "Ej. Ingredientes del sándwich"});
    const selection = document.createElement("select");
    [["multiple", "Elegir varias opciones"], ["single", "Elegir una opción"]].forEach(([value, label]) => {
      const option = element("option", "", label);
      option.value = value;
      option.selected = group.selection_type === value;
      selection.append(option);
    });
    selection.addEventListener("change", () => {
      group.selection_type = selection.value;
      if (selection.value === "single") {
        let foundDefault = false;
        group.options.forEach((option) => {
          if (option.is_default && !foundDefault) foundDefault = true;
          else if (option.is_default) option.is_default = false;
        });
      }
      render();
    });
    settings.append(field("Nombre del grupo", name), field("Forma de elegir", selection));
    settings.append(checkbox("Debe conservar al menos una opción", group.is_required, (checked) => { group.is_required = checked; }));

    const options = element("div", "integrated-option-list");
    group.options.forEach((option, optionIndex) => options.append(renderOption(group, groupIndex, option, optionIndex)));
    if (!group.options.length) options.append(element("p", "empty-customization-message", "Agrega por lo menos un ingrediente."));
    const addOption = actionButton("Agregar ingrediente", () => {
      group.options.push(normalizeOption());
      render();
    }, "secondary-action");
    card.append(heading, settings, options, addOption);
    return card;
  }

  function moveItem(collection, index, direction) {
    const target = index + direction;
    if (target < 0 || target >= collection.length) return;
    [collection[index], collection[target]] = [collection[target], collection[index]];
    render();
  }

  function sync() {
    payloadInput.value = JSON.stringify(groups.map((group, groupIndex) => ({
      ...group,
      sort_order: (groupIndex + 1) * 10,
      options: group.options.map((option, optionIndex) => ({
        ...option, sort_order: (optionIndex + 1) * 10,
      })),
    })));
  }

  function render() {
    list.innerHTML = "";
    groups.forEach((group, index) => list.append(renderGroup(group, index)));
    emptyMessage.hidden = groups.length > 0;
    sync();
  }

  library.forEach((group, index) => {
    const option = element("option", "", group.source_label);
    option.value = String(index);
    librarySelect.append(option);
  });

  editor.querySelector("[data-add-group]").addEventListener("click", () => {
    groups.push(normalizeGroup({options: [normalizeOption()]}));
    render();
  });
  editor.querySelector("[data-copy-group]").addEventListener("click", () => {
    const index = Number.parseInt(librarySelect.value, 10);
    if (!Number.isInteger(index) || !library[index]) return;
    const copy = normalizeGroup(structuredClone(library[index]));
    const currentNames = new Set(groups.map((group) => group.name.toLocaleLowerCase("es-MX")));
    const originalName = copy.name;
    let copyNumber = 1;
    while (currentNames.has(copy.name.toLocaleLowerCase("es-MX"))) {
      copy.name = `${originalName} (copia${copyNumber > 1 ? ` ${copyNumber}` : ""})`;
      copyNumber += 1;
    }
    groups.push(copy);
    librarySelect.value = "";
    render();
  });

  form.addEventListener("submit", (event) => {
    sync();
    errorBox.hidden = true;
    const invalidGroup = groups.find((group) => !group.name.trim() || !group.options.length || group.options.some((option) => !option.name.trim()));
    if (invalidGroup) {
      event.preventDefault();
      errorBox.textContent = "Completa el nombre de cada grupo e ingrediente antes de guardar.";
      errorBox.hidden = false;
      editor.scrollIntoView({behavior: "smooth", block: "start"});
    }
  });

  render();
})();
