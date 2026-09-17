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
    const target = form.querySelector(".package-quick-extras") || form.querySelector(".table-package-visual-extras") || form.querySelector(".package-secondary-fields") || form;
    const tableComment = target.querySelector(":scope > .package-comment-field");
    if (tableComment) target.insertBefore(choice, tableComment);
    else target.append(choice);
  });

  document.querySelectorAll("[data-auto-package-options], #auto-running-meal, #auto-executive-meal").forEach((container) => {
    if (container.matches("[data-auto-package-options]") && container.closest("#internal-running, #internal-executive")) {
      container.append(makeChoice("egg_product"));
    } else if (container.matches("#auto-running-meal, #auto-executive-meal")) {
      container.prepend(makeChoice("egg_product"));
    }
  });

  const extrasForm = document.querySelector("[data-package-extras-form]");
  if (extrasForm) extrasForm.querySelector(".package-extras-row")?.append(makeChoice("egg_product"));
})();
