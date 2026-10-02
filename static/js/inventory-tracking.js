(() => {
  const touchMode = matchMedia("(pointer: coarse)").matches;
  const normalize = (value) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();

  document.querySelectorAll("[data-reference-list]").forEach((list) => {
    const input = list.querySelector("[data-reference-search]");
    const cards = [...list.querySelectorAll("[data-reference-card]")];
    const empty = list.querySelector("[data-reference-empty]");
    const channelButtons = [...list.querySelectorAll("[data-reference-channel]")];
    let channel = "";
    if (!input) return;

    // Búsqueda por texto y filtro por canal (Todos / Mesas / Pedidos) se combinan.
    const filter = () => {
      const query = normalize(input.value);
      let visible = 0;
      cards.forEach((card) => {
        const matches = (!query || normalize(card.dataset.searchText || "").includes(query))
          && (!channel || card.dataset.channel === channel);
        card.hidden = !matches;
        if (matches) visible += 1;
      });
      if (empty) empty.hidden = visible > 0 || (!query && !channel);
    };
    input.addEventListener("input", filter);
    channelButtons.forEach((button) => button.addEventListener("click", () => {
      channel = button.dataset.referenceChannel;
      channelButtons.forEach((candidate) => candidate.classList.toggle("is-active", candidate === button));
      filter();
    }));

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
