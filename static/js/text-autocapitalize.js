(() => {
  const textFieldSelector = 'input:not([type]), input[type="text"], textarea';
  const freeEntrySelector = [
    'input[type="password"]',
    'input[name="username"]',
    'input[autocomplete="username"]',
    'input[autocomplete="current-password"]',
    'input[autocomplete="new-password"]',
  ].join(", ");

  const isFreeEntryField = (field) => field.matches?.(freeEntrySelector);

  const capitalizeFirstLetter = (field) => {
    if (!field.matches(textFieldSelector) || isFreeEntryField(field) || field.hasAttribute("data-no-autocapitalize")) return;
    const match = field.value.match(/\p{L}/u);
    if (!match) return;
    const index = match.index;
    const uppercase = match[0].toLocaleUpperCase("es-MX");
    if (uppercase === match[0]) return;
    const selectionStart = field.selectionStart;
    const selectionEnd = field.selectionEnd;
    field.value = `${field.value.slice(0, index)}${uppercase}${field.value.slice(index + match[0].length)}`;
    if (selectionStart !== null && selectionEnd !== null) {
      const difference = uppercase.length - match[0].length;
      field.setSelectionRange(selectionStart + difference, selectionEnd + difference);
    }
  };

  document.querySelectorAll(textFieldSelector).forEach((field) => {
    field.setAttribute("autocapitalize", isFreeEntryField(field) ? "none" : "sentences");
    capitalizeFirstLetter(field);
  });

  document.querySelectorAll(freeEntrySelector).forEach((field) => {
    field.setAttribute("autocapitalize", "none");
    field.setAttribute("spellcheck", "false");
  });

  document.addEventListener("focusin", (event) => {
    if (isFreeEntryField(event.target)) {
      event.target.setAttribute("autocapitalize", "none");
    } else if (event.target.matches?.(textFieldSelector)) {
      event.target.setAttribute("autocapitalize", "sentences");
    }
  });
  document.addEventListener("input", (event) => capitalizeFirstLetter(event.target));
})();
