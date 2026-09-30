(() => {
  const touchMode = matchMedia("(pointer: coarse)").matches;
  const normalize = (value) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();

  document.querySelectorAll("[data-reference-list]").forEach((list) => {
    const input = list.querySelector("[data-reference-search]");
    const cards = [...list.querySelectorAll("[data-reference-card]")];
    const empty = list.querySelector("[data-reference-empty]");
    if (!input) return;

    const filter = () => {
      const query = normalize(input.value);
      let visible = 0;
      cards.forEach((card) => {
        const matches = !query || normalize(card.dataset.searchText || "").includes(query);
        card.hidden = !matches;
        if (matches) visible += 1;
      });
      if (empty) empty.hidden = visible > 0 || !query;
    };
    input.addEventListener("input", filter);

    if (touchMode) {
      input.readOnly = true;
      input.dataset.touchArmed = "false";
      input.addEventListener("pointerdown", (event) => {
        if (input.dataset.touchArmed === "false") {
          event.preventDefault();
          input.dataset.touchArmed = "true";
          input.focus({preventScroll: true});
          return;
        }
        input.readOnly = false;
      });
      input.addEventListener("blur", () => {
        input.readOnly = true;
        input.dataset.touchArmed = "false";
      });
    }
  });
})();
