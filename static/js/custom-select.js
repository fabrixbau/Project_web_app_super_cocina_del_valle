(() => {
  const enhanced = new WeakSet();

  const closeAll = (except = null) => {
    document.querySelectorAll(".app-select.is-open").forEach((wrapper) => {
      if (wrapper === except) return;
      wrapper.classList.remove("is-open");
      wrapper.querySelector(".app-select-trigger")?.setAttribute("aria-expanded", "false");
    });
  };

  const enhance = (select) => {
    if (
      enhanced.has(select)
      || select.multiple
      || Number(select.size || 0) > 1
      || select.dataset.nativeSelect !== undefined
    ) return;

    enhanced.add(select);
    const wrapper = document.createElement("div");
    wrapper.className = "app-select";
    // Every simple select is a searchable combobox by default. Screens that truly need
    // the browser control can opt out with data-native-select; multiple selects remain native.
    const searchable = true;
    const trigger = document.createElement(searchable ? "input" : "button");
    trigger.type = searchable ? "text" : "button";
    trigger.className = "app-select-trigger";
    if (searchable) {
      trigger.classList.add("app-select-search");
      trigger.setAttribute("role", "combobox");
      trigger.setAttribute("autocomplete", "off");
      trigger.setAttribute("aria-autocomplete", "list");
    }
    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-expanded", "false");
    const value = document.createElement("span");
    value.className = "app-select-value";
    const chevron = document.createElement("span");
    chevron.className = "app-select-chevron";
    chevron.setAttribute("aria-hidden", "true");
    if (!searchable) trigger.append(value, chevron);

    const menu = document.createElement("div");
    menu.className = "app-select-menu";
    menu.setAttribute("role", "listbox");
    wrapper.append(trigger, menu);
    select.parentNode.insertBefore(wrapper, select);
    wrapper.append(select);
    select.classList.add("app-select-native");

    const rebuild = () => {
      menu.replaceChildren();
      [...select.options].forEach((option) => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "app-select-option";
        item.textContent = option.textContent;
        item.dataset.value = option.value;
        item.disabled = option.disabled;
        item.setAttribute("role", "option");
        item.setAttribute("aria-selected", String(option.selected));
        if (option.selected) item.classList.add("is-selected");
        item.addEventListener("click", () => {
          if (option.disabled) return;
          select.value = option.value;
          select.dispatchEvent(new Event("change", { bubbles: true }));
          trigger.focus();
          closeAll();
          filter();
        });
        menu.append(item);
      });
    };

    const filter = (query = "") => {
      const normalized = query.trim().toLocaleLowerCase("es-MX");
      let visible = 0;
      menu.querySelectorAll(".app-select-option").forEach((item) => {
        const matches = !normalized || item.textContent.toLocaleLowerCase("es-MX").includes(normalized);
        item.hidden = !matches;
        if (matches && !item.disabled) visible += 1;
      });
      wrapper.classList.toggle("has-no-results", visible === 0);
    };

    const sync = () => {
      const selected = select.selectedOptions[0] || select.options[0];
      if (searchable) {
        trigger.value = selected?.textContent || "";
        trigger.placeholder = "Escribe para buscar";
      } else {
        value.textContent = selected?.textContent || "Seleccionar";
      }
      trigger.disabled = select.disabled;
      wrapper.classList.toggle("is-disabled", select.disabled);
      menu.querySelectorAll(".app-select-option").forEach((item) => {
        const active = item.dataset.value === select.value;
        item.classList.toggle("is-selected", active);
        item.setAttribute("aria-selected", String(active));
      });
    };

    rebuild();
    sync();
    const toggleMenu = () => {
      const opening = !wrapper.classList.contains("is-open");
      closeAll(wrapper);
      wrapper.classList.toggle("is-open", opening);
      trigger.setAttribute("aria-expanded", String(opening));
      if (opening) menu.querySelector(".is-selected")?.scrollIntoView({ block: "nearest" });
    };
    trigger.addEventListener("click", () => {
      if (searchable && wrapper.classList.contains("is-open")) return;
      toggleMenu();
      if (searchable) trigger.select();
    });
    if (searchable) {
      trigger.addEventListener("focus", () => {
        if (!wrapper.classList.contains("is-open")) toggleMenu();
        trigger.select();
      });
      trigger.addEventListener("input", () => {
        if (!wrapper.classList.contains("is-open")) toggleMenu();
        filter(trigger.value);
      });
      trigger.addEventListener("blur", () => {
        window.setTimeout(() => {
          if (!wrapper.contains(document.activeElement)) { filter(); sync(); }
        }, 0);
      });
    }
    trigger.addEventListener("keydown", (event) => {
      if (!["ArrowDown", "ArrowUp", "Escape"].includes(event.key)) return;
      event.preventDefault();
      if (event.key === "Escape") {
        closeAll();
        return;
      }
      if (!wrapper.classList.contains("is-open")) toggleMenu();
      const items = [...menu.querySelectorAll(".app-select-option:not(:disabled):not([hidden])")];
      const current = items.indexOf(document.activeElement);
      const next = event.key === "ArrowDown"
        ? items[Math.min(current + 1, items.length - 1)]
        : items[Math.max(current - 1, 0)];
      next?.focus();
    });
    menu.addEventListener("keydown", (event) => {
      const items = [...menu.querySelectorAll(".app-select-option:not(:disabled):not([hidden])")];
      const current = items.indexOf(document.activeElement);
      if (event.key === "Escape") {
        event.preventDefault(); closeAll(); trigger.focus();
      } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const offset = event.key === "ArrowDown" ? 1 : -1;
        items[(current + offset + items.length) % items.length]?.focus();
      }
    });
    select.addEventListener("change", sync);
    new MutationObserver(() => { rebuild(); sync(); }).observe(select, {
      childList: true, subtree: true, attributes: true, attributeFilter: ["disabled", "selected"],
    });
  };

  const scan = (root = document) => {
    if (root.matches?.("select")) enhance(root);
    root.querySelectorAll?.("select").forEach(enhance);
  };
  scan();
  new MutationObserver((mutations) => mutations.forEach(({ addedNodes }) => {
    addedNodes.forEach((node) => { if (node.nodeType === Node.ELEMENT_NODE) scan(node); });
  })).observe(document.body, { childList: true, subtree: true });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".app-select")) closeAll();
  });
})();
