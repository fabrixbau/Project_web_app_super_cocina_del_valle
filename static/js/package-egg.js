(() => {
  const source = document.getElementById("egg-product-options");
  if (!source) return;
  const products = JSON.parse(source.textContent || "[]");
  if (!products.length) return;
  const initials = JSON.parse(document.getElementById("egg-product-initials")?.textContent || "{}");

  const makeChoice = (name, initial = "") => {
    const label = document.createElement("label");
    label.className = "package-egg-choice";
    const caption = document.createElement("span");
    caption.className = "package-egg-caption";
    caption.textContent = "Huevo opcional";
    label.append(caption);
    const select = document.createElement("select");
    select.name = name;
    select.append(new Option("Sin huevo", ""));
    products.forEach((product) => select.append(new Option(`${product.name} (+$${product.price})`, product.id)));
    select.value = String(initial || "");
    select.querySelectorAll("option").forEach((option) => { option.defaultSelected = option.value === select.value; });
    label.append(select);
    return label;
  };

  document.querySelectorAll("form[data-internal-package], form[data-package-form]").forEach((form) => {
    const existing = form.querySelector("select[name$='egg_product']");
    if (existing) return;
    const first = form.querySelector("[name$='first_course']");
    if (!first) return;
    const name = first.name.replace(/first_course$/, "egg_product");
    const itemId = form.closest("dialog")?.id.match(/^package-edit-(\d+)$/)?.[1];
    const choice = makeChoice(name, itemId ? initials[itemId] : "");
    // Paquetes de Mesas (corrida y ejecutiva): el huevo ocupa el lugar que dejó "Lleva bolillo".
    const slot = form.querySelector("[data-egg-slot]");
    if (slot) {
      slot.replaceWith(choice);
      return;
    }
    const target = form.querySelector(".package-quick-extras") || form.querySelector(".table-package-visual-extras") || form.querySelector(".package-secondary-fields") || form;
    const tableComment = target.querySelector(":scope > .package-comment-field");
    if (tableComment) target.insertBefore(choice, tableComment);
    else target.append(choice);
  });

  // Pedidos: huevo en las opciones de la comida armada tiempo por tiempo. En Mesas ya no
  // se muestra ahí; el huevo se elige en el diálogo de Comida corrida / ejecutiva.
  document.querySelectorAll("#internal-running [data-auto-package-options], #internal-executive [data-auto-package-options]").forEach((container) => {
    container.append(makeChoice("egg_product"));
  });

  const extrasForm = document.querySelector("[data-package-extras-form]");
  if (extrasForm) extrasForm.querySelector(".package-extras-row")?.append(makeChoice("egg_product"));
})();
