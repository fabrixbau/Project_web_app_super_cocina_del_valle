(() => {
  const enhanced = new WeakSet();
  const compactViewport = window.matchMedia("(max-width: 900px)");
  const touchTabletViewport = window.matchMedia("(max-width: 900px), (max-width: 1200px) and (pointer: coarse)");

  const isCompactViewport = () => compactViewport.matches;
  const usesTouchInteraction = (wrapper) => (
    isCompactViewport()
    || (touchTabletViewport.matches && Boolean(wrapper?.querySelector("select[data-click-toggle-select]")))
  );
  const resetCompactTrigger = (wrapper) => {
    const trigger = wrapper.querySelector(".app-select-search");
    if (!trigger || !usesTouchInteraction(wrapper)) return;
    trigger.readOnly = true;
    trigger.inputMode = "none";
    wrapper.classList.remove("is-keyboard-ready");
  };

  // NOTA TEMPORAL PARA APRENDIZAJE: en celular, tableta y ordenador el panel se
  // ancla al campo con position:fixed usando sus coordenadas reales. Así escapa de
  // contenedores con overflow (p. ej. el huevo dentro del formulario del paquete)
  // y puede abrirse hacia arriba o hacia abajo, según dónde quede más espacio
  // visible. visualViewport descuenta el teclado en pantalla. Borra esta nota.
  const MENU_GAP = 6;
  const VIEWPORT_EDGE = 8;
  const MIN_MENU_HEIGHT = 132;
  const restoreSelection = new WeakMap();

  const visibleBounds = () => {
    const viewport = window.visualViewport;
    const top = viewport ? viewport.offsetTop : 0;
    const left = viewport ? viewport.offsetLeft : 0;
    const width = viewport ? viewport.width : window.innerWidth;
    const height = viewport ? viewport.height : window.innerHeight;
    return { top, left, width, height, right: left + width, bottom: top + height };
  };

  // Un campo cuenta como visible si al menos la mitad sigue a la vista, tanto en
  // la pantalla como dentro de los contenedores con scroll que lo recortan.
  const anchorIsVisible = (trigger, bounds) => {
    const rect = trigger.getBoundingClientRect();
    let top = bounds.top;
    let bottom = bounds.bottom;
    for (let node = trigger.parentElement; node && node !== document.body; node = node.parentElement) {
      if (getComputedStyle(node).overflowY === "visible") continue;
      const clip = node.getBoundingClientRect();
      top = Math.max(top, clip.top);
      bottom = Math.min(bottom, clip.bottom);
    }
    return Math.min(rect.bottom, bottom) - Math.max(rect.top, top) >= rect.height / 2;
  };

  // Si un ancestro tiene transform, filter o contain, `position: fixed` se mide
  // desde ese ancestro y no desde la pantalla; se resta su esquina para compensar.
  const fixedOrigin = (wrapper) => {
    for (let node = wrapper.parentElement; node && node !== document.documentElement; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (
        style.transform !== "none"
        || style.perspective !== "none"
        || style.filter !== "none"
        || (style.backdropFilter && style.backdropFilter !== "none")
        || /transform|perspective|filter/.test(style.willChange)
        || /paint|layout|strict|content/.test(style.contain)
      ) {
        const rect = node.getBoundingClientRect();
        return { top: rect.top + node.clientTop, left: rect.left + node.clientLeft };
      }
    }
    return { top: 0, left: 0 };
  };

  const clearMenuPosition = (wrapper) => {
    wrapper.classList.remove("is-anchored", "opens-up");
    ["--menu-top", "--menu-left", "--menu-width", "--menu-max-height"].forEach((name) => {
      wrapper.style.removeProperty(name);
    });
  };

  // Abre hacia abajo si la lista completa cabe; si no, hacia el lado con más
  // espacio. Con `keepDirection` conserva el lado elegido al abrir (scroll, filtro).
  const positionMenu = (wrapper, { keepDirection = false } = {}) => {
    const trigger = wrapper.querySelector(".app-select-trigger");
    const menu = wrapper.querySelector(".app-select-menu");
    const bounds = visibleBounds();
    const rect = trigger.getBoundingClientRect();
    const cap = isCompactViewport() ? Math.min(bounds.height * .52, 384) : 280;
    const needed = Math.min(menu.scrollHeight + (menu.offsetHeight - menu.clientHeight), cap);
    const spaceBelow = bounds.bottom - rect.bottom - MENU_GAP - VIEWPORT_EDGE;
    const spaceAbove = rect.top - bounds.top - MENU_GAP - VIEWPORT_EDGE;
    const openUpward = keepDirection && wrapper.classList.contains("is-anchored")
      ? wrapper.classList.contains("opens-up")
      : spaceBelow < needed && spaceAbove > spaceBelow;
    const space = openUpward ? spaceAbove : spaceBelow;
    const maxHeight = Math.min(cap, Math.max(space, 96));
    const height = Math.min(needed, maxHeight);
    const minWidth = wrapper.closest(".package-egg-choice") ? 220 : 0;
    const width = Math.min(Math.max(rect.width, minWidth), bounds.width - VIEWPORT_EDGE * 2);
    const preferredLeft = width > rect.width ? rect.right - width : rect.left;
    const left = Math.min(
      Math.max(bounds.left + VIEWPORT_EDGE, preferredLeft),
      bounds.right - width - VIEWPORT_EDGE,
    );
    const top = openUpward ? rect.top - MENU_GAP - height : rect.bottom + MENU_GAP;
    const origin = fixedOrigin(wrapper);

    wrapper.classList.add("is-anchored");
    wrapper.classList.toggle("opens-up", openUpward);
    wrapper.style.setProperty("--menu-width", `${width}px`);
    wrapper.style.setProperty("--menu-max-height", `${maxHeight}px`);
    wrapper.style.setProperty("--menu-left", `${left - origin.left}px`);
    wrapper.style.setProperty("--menu-top", `${top - origin.top}px`);
    return {
      fits: space >= Math.min(needed, MIN_MENU_HEIGHT),
      anchorVisible: anchorIsVisible(trigger, bounds),
    };
  };

  const closeMenu = (wrapper) => {
    wrapper.classList.remove("is-open");
    wrapper.querySelector(".app-select-trigger")?.setAttribute("aria-expanded", "false");
    resetCompactTrigger(wrapper);
    clearMenuPosition(wrapper);
    // Descarta lo escrito en el buscador y vuelve a mostrar la opción fijada.
    restoreSelection.get(wrapper)?.();
  };

  const closeAll = (except = null) => {
    document.querySelectorAll(".app-select.is-open").forEach((wrapper) => {
      if (wrapper !== except) closeMenu(wrapper);
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
    // Every simple select is searchable by default. Mesa y Huevo opcional son listas
    // cortas: funcionan como botón desplegable, de modo que tocar otra vez la misma
    // barra cierre las opciones sin convertirla en campo de texto ni abrir teclado.
    const searchable = select.name !== "table_id" && !select.closest(".package-egg-choice");
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
    resetCompactTrigger(wrapper);

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
          if (!isCompactViewport()) trigger.focus();
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
    restoreSelection.set(wrapper, () => { filter(); sync(); });
    const toggleMenu = () => {
      const opening = !wrapper.classList.contains("is-open");
      closeAll(wrapper);
      wrapper.classList.toggle("is-open", opening);
      trigger.setAttribute("aria-expanded", String(opening));
      if (opening) {
        positionMenu(wrapper);
        // `scrollIntoView` también podía desplazar la página en pantallas táctiles;
        // ese movimiento alteraba el mismo toque y hacía parecer que el panel se
        // abría y cerraba. Ajustamos únicamente el scroll interno de la lista.
        const selectedItem = menu.querySelector(".is-selected");
        if (selectedItem) {
          const itemTop = selectedItem.offsetTop;
          const itemBottom = itemTop + selectedItem.offsetHeight;
          if (itemTop < menu.scrollTop) menu.scrollTop = itemTop;
          else if (itemBottom > menu.scrollTop + menu.clientHeight) {
            menu.scrollTop = itemBottom - menu.clientHeight;
          }
        }
      } else {
        clearMenuPosition(wrapper);
      }
    };
    let openedFromPointer = false;
    trigger.addEventListener("pointerdown", (event) => {
      if (!searchable || !usesTouchInteraction(wrapper)) return;
      if (!wrapper.classList.contains("is-open")) {
        // En móviles el foco nativo ocurre antes de `click`; cancelarlo aquí evita
        // que el teclado alcance a aparecer durante el primer toque.
        event.preventDefault();
        openedFromPointer = true;
        toggleMenu();
        resetCompactTrigger(wrapper);
        trigger.blur();
        return;
      }
      if (!trigger.readOnly) return;
      // Segundo toque: ahora sí convertimos la barra en escribible.
      trigger.readOnly = false;
      trigger.inputMode = "search";
      wrapper.classList.add("is-keyboard-ready");
    });
    trigger.addEventListener("click", (event) => {
      if (openedFromPointer) {
        event.preventDefault();
        openedFromPointer = false;
        return;
      }
      if (searchable && usesTouchInteraction(wrapper)) {
        if (!wrapper.classList.contains("is-open")) {
          toggleMenu();
          resetCompactTrigger(wrapper);
          trigger.blur();
          return;
        }
        if (trigger.readOnly) {
          trigger.readOnly = false;
          trigger.inputMode = "search";
          wrapper.classList.add("is-keyboard-ready");
          trigger.focus({ preventScroll: true });
          trigger.select();
        }
        return;
      }
      if (searchable && wrapper.classList.contains("is-open")) return;
      toggleMenu();
      if (searchable) trigger.select();
    });
    if (searchable) {
      trigger.addEventListener("focus", () => {
        if (usesTouchInteraction(wrapper) && trigger.readOnly) return;
        if (!wrapper.classList.contains("is-open")) toggleMenu();
        if (!usesTouchInteraction(wrapper) || !trigger.readOnly) trigger.select();
      });
      trigger.addEventListener("input", () => {
        if (!wrapper.classList.contains("is-open")) toggleMenu();
        filter(trigger.value);
        // La lista cambia de alto al filtrar; se reajusta sin cambiar de lado.
        positionMenu(wrapper, { keepDirection: true });
      });
      trigger.addEventListener("blur", () => {
        window.setTimeout(() => {
          if (wrapper.dataset.preserveMobileFilter === "1") {
            delete wrapper.dataset.preserveMobileFilter;
            resetCompactTrigger(wrapper);
            return;
          }
          if (!wrapper.contains(document.activeElement)) { filter(); sync(); resetCompactTrigger(wrapper); }
        }, 0);
      });
    }
    trigger.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && searchable) {
        event.preventDefault();
        filter(trigger.value);
        trigger.blur();
        resetCompactTrigger(wrapper);
        return;
      }
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

  // Al desplazar la página (o cualquier contenedor), el panel acompaña a su campo.
  // Si el scroll deja la lista sin espacio visible o saca el campo de la vista, se
  // cierra conservando la opción fijada. Mientras se escribe en táctil, el teclado
  // también mueve la página: ahí el panel solo cambia de lado, salvo que el campo
  // desaparezca. El scroll interno de la propia lista se ignora.
  let refreshFrame = 0;
  let closeOnOverflow = false;
  const refreshOpenMenus = (fromScroll) => {
    closeOnOverflow = closeOnOverflow || fromScroll;
    if (refreshFrame) return;
    refreshFrame = window.requestAnimationFrame(() => {
      const shouldClose = closeOnOverflow;
      refreshFrame = 0;
      closeOnOverflow = false;
      document.querySelectorAll(".app-select.is-open").forEach((wrapper) => {
        const typing = wrapper.classList.contains("is-keyboard-ready");
        const { fits, anchorVisible } = positionMenu(wrapper, { keepDirection: !typing });
        if (!shouldClose || (anchorVisible && (fits || typing))) return;
        if (wrapper.contains(document.activeElement)) document.activeElement.blur();
        closeMenu(wrapper);
      });
    });
  };
  document.addEventListener("scroll", (event) => {
    if (event.target instanceof Element && event.target.closest(".app-select-menu")) return;
    refreshOpenMenus(true);
  }, { capture: true, passive: true });
  window.addEventListener("resize", () => refreshOpenMenus(false));
  window.visualViewport?.addEventListener("resize", () => refreshOpenMenus(false));

  const refreshViewportMode = () => {
    document.querySelectorAll(".app-select").forEach((wrapper) => {
      const trigger = wrapper.querySelector(".app-select-search");
      if (!trigger) return;
      if (usesTouchInteraction(wrapper)) resetCompactTrigger(wrapper);
      else {
        trigger.readOnly = false;
        trigger.removeAttribute("inputmode");
        wrapper.classList.remove("is-keyboard-ready");
      }
    });
  };
  compactViewport.addEventListener?.("change", refreshViewportMode);
  touchTabletViewport.addEventListener?.("change", refreshViewportMode);

  const dismissFocusedSearch = () => {
    if (document.activeElement instanceof HTMLInputElement) document.activeElement.blur();
    document.querySelectorAll(
      ".compact-search-backdrop:not([hidden]), .menu-search-backdrop:not([hidden]), .delivery-search-backdrop:not([hidden])"
    ).forEach((backdrop) => backdrop.click());
  };
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || !event.target.matches("input[type='search'], input[data-catalog-search], input[data-menu-search-input]")) return;
    window.setTimeout(dismissFocusedSearch, 0);
  });
  document.addEventListener("search", (event) => {
    if (event.target.matches("input[type='search'], input[data-catalog-search], input[data-menu-search-input]")) dismissFocusedSearch();
  });
  document.addEventListener("pointerdown", (event) => {
    if (!event.target.closest("button[type='submit'], input[type='submit']")) return;
    if (document.activeElement instanceof HTMLInputElement) document.activeElement.blur();
  });
})();
