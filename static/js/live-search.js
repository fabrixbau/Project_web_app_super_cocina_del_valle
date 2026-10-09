/* NOTA TEMPORAL PARA APRENDIZAJE: lupa con sugerencias, la misma en Mesas, Pedidos,
Menú, Repartos, Adeudos y Clientes (celular, tableta y ordenador).
- Desde 1 letra muestra hasta 10 coincidencias parciales (sin acentos ni mayúsculas) y,
  si hay más, "Enter para ver los N resultados".
- Enter sin sugerencia resaltada: la pantalla hace lo de siempre (filtra o busca todo).
- Elegir una sugerencia (toque, clic o Enter con flechas): abre su `url` o, si no tiene,
  deja el texto exacto en la lupa y avisa con el evento `live-search:select` para que la
  pantalla muestre sólo ese elemento.
Fuentes (atributos del input):
  data-live-search-source="#id"   JSON en la página: [{label, detail, url, search}]
  data-live-search-cards="selector"  nombres de tarjetas ya dibujadas (Mesas/Pedidos)
  data-live-search-url="/ruta/"   consulta al servidor (?q=) que responde {results: [...]}
  data-live-search-side="(media query)"  mientras coincida, la lista va en la mitad derecha
                                  de la pantalla (lupa de Mesas/Pedidos en tableta horizontal)
  data-live-search-controls       (con data-live-search-cards) cada sugerencia trae − # + y
                                  Personalizar; presionan los botones reales de la tarjeta, así
                                  que agregan al ticket exactamente igual que el catálogo.
La altura disponible se mide con visualViewport: es el área que no tapa el teclado.
Borra esta nota después de leerla. */
(() => {
  const MAX_SUGGESTIONS = 10;
  const normalize = (value) => String(value || "")
    .normalize("NFD").replace(/[̀-ͯ]/g, "").toLocaleLowerCase("es-MX").trim();

  const rank = (text, query) => {
    if (text.startsWith(query)) return 0;
    if (text.split(/\s+/).some((word) => word.startsWith(query))) return 1;
    return text.includes(query) ? 2 : 99;
  };

  // Tarjetas que arman paquetes (Comida mexicana/ejecutiva): sólo se usan si el producto no
  // tiene otra tarjeta, para que + agregue el producto suelto como en Comida por orden/categoría.
  const AUTO_MEAL_CARD = "[data-auto-meal-card], [data-internal-auto-product]";

  const cardItems = (selector) => {
    const seen = new Map();
    document.querySelectorAll(selector).forEach((card) => {
      const label = (card.querySelector(".catalog-product-information > strong, strong")?.textContent
        || card.dataset.productName || "").trim();
      const key = normalize(label);
      if (!key) return;
      const known = seen.get(key);
      if (!known) seen.set(key, {label, search: key, card});
      else if (known.card.matches(AUTO_MEAL_CARD) && !card.matches(AUTO_MEAL_CARD)) known.card = card;
    });
    return [...seen.values()];
  };

  // Botones reales de la tarjeta: − (restar), contador, + (agregar) y Personalizar (opcional).
  const cardControls = (card) => {
    const quick = card?.querySelector(".catalog-quick-controls");
    const decrease = quick?.querySelector(":scope > button");
    const count = quick?.querySelector(":scope > strong");
    const add = quick?.querySelector("form [type=submit]");
    if (!decrease || !count || !add) return null;
    const customize = card.querySelector(".catalog-customize-form [type=submit], form[data-customizable-product] [type=submit]");
    return {quick, decrease, count, add, customize};
  };

  const setup = (input) => {
    if (input.dataset.liveSearchReady) return;
    input.dataset.liveSearchReady = "1";
    input.setAttribute("autocomplete", "off");
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-expanded", "false");

    const list = document.createElement("div");
    list.className = "live-search-list";
    list.setAttribute("role", "listbox");
    list.hidden = true;
    document.body.append(list);

    let localItems = null;
    let current = [];
    let active = -1;
    let requestId = 0;
    let ignoreNextInput = false;
    let observers = [];
    const withControls = input.hasAttribute("data-live-search-controls");
    const stopObserving = () => {
      observers.forEach((observer) => observer.disconnect());
      observers = [];
    };

    const loadLocal = () => {
      if (localItems) return localItems;
      if (input.dataset.liveSearchCards) return cardItems(input.dataset.liveSearchCards);
      try {
        const raw = JSON.parse(document.querySelector(input.dataset.liveSearchSource)?.textContent || "[]");
        localItems = raw.map((item) => ({...item, search: normalize(item.search || `${item.label} ${item.detail || ""}`)}));
      } catch (_) {
        localItems = [];
      }
      return localItems;
    };

    const sideLayout = input.dataset.liveSearchSide ? window.matchMedia(input.dataset.liveSearchSide) : null;

    const place = () => {
      if (list.hidden) return;
      const viewport = window.visualViewport;
      const visibleTop = viewport ? viewport.offsetTop : 0;
      const visibleLeft = viewport ? viewport.offsetLeft : 0;
      const visibleWidth = viewport ? viewport.width : window.innerWidth;
      const visibleBottom = visibleTop + (viewport ? viewport.height : window.innerHeight);
      if (sideLayout?.matches) {
        // Tableta horizontal: campo a la izquierda, sugerencias en la mitad derecha.
        const half = visibleWidth / 2;
        list.style.left = `${visibleLeft + half + 4}px`;
        list.style.width = `${half - 12}px`;
        list.style.top = `${visibleTop + 8}px`;
        list.style.bottom = "auto";
        list.style.maxHeight = `${Math.max(visibleBottom - visibleTop - 16, 120)}px`;
        return;
      }
      const box = input.getBoundingClientRect();
      const width = Math.max(box.width, Math.min(withControls ? 460 : 320, visibleWidth - 16));
      const left = Math.min(Math.max(visibleLeft + 8, box.left), visibleLeft + visibleWidth - width - 8);
      list.style.left = `${left}px`;
      list.style.width = `${width}px`;
      const below = visibleBottom - box.bottom - 12;
      const above = box.top - visibleTop - 12;
      if (below < 180 && above > below) {
        list.style.top = "auto";
        list.style.bottom = `${window.innerHeight - box.top + 4}px`;
        list.style.maxHeight = `${Math.min(420, above)}px`;
      } else {
        list.style.bottom = "auto";
        list.style.top = `${box.bottom + 4}px`;
        list.style.maxHeight = `${Math.min(420, Math.max(below, 140))}px`;
      }
    };

    const close = () => {
      stopObserving();
      list.hidden = true;
      active = -1;
      input.setAttribute("aria-expanded", "false");
    };

    const highlight = (index) => {
      active = index;
      [...list.querySelectorAll(".live-search-option")].forEach((option, position) => {
        option.classList.toggle("is-active", position === index);
        if (position === index) option.scrollIntoView({block: "nearest"});
      });
    };

    const choose = (item) => {
      close();
      if (item.url) {
        window.location.assign(item.url);
        return;
      }
      input.value = item.label;
      ignoreNextInput = true; // el filtro de la pantalla corre, la lista no se reabre.
      input.dispatchEvent(new Event("input", {bubbles: true}));
      input.dispatchEvent(new CustomEvent("live-search:select", {bubbles: true, detail: {item}}));
      input.blur();
    };

    // Fila con − # + Personalizar que presiona los botones de la tarjeta del producto.
    const controlsFor = (item) => {
      const real = withControls ? cardControls(item.card) : null;
      if (!real) return null;
      const box = document.createElement("div");
      box.className = "live-search-controls";
      const button = (text, label, target, keepOpen = true) => {
        const control = document.createElement("button");
        control.type = "button";
        control.className = "live-search-control";
        control.textContent = text;
        control.setAttribute("aria-label", label + " " + item.label);
        control.addEventListener("pointerdown", (event) => event.preventDefault());
        control.addEventListener("click", (event) => {
          event.stopPropagation();
          if (!keepOpen) {
            close();
            input.blur();
          }
          target.click();
        });
        return control;
      };
      const minus = button("−", "Restar", real.decrease);
      const count = document.createElement("strong");
      count.className = "live-search-count";
      const sync = () => {
        count.textContent = real.count.textContent.trim() || "0";
        minus.disabled = real.decrease.disabled;
        minus.title = real.decrease.title || "";
      };
      sync();
      const observer = new MutationObserver(sync);
      observer.observe(real.quick, {subtree: true, childList: true, characterData: true, attributes: true});
      observers.push(observer);
      box.append(minus, count, button("+", "Agregar", real.add));
      if (real.customize) {
        const customize = button("Personalizar", "Personalizar", real.customize, false);
        customize.classList.add("is-customize");
        box.append(customize);
      }
      return box;
    };

    const render = (items, total, query) => {
      current = items;
      stopObserving();
      list.replaceChildren();
      if (!items.length) {
        const empty = document.createElement("p");
        empty.className = "live-search-empty";
        empty.textContent = "Sin coincidencias";
        list.append(empty);
      }
      items.forEach((item, index) => {
        const option = document.createElement("button");
        option.type = "button";
        option.className = "live-search-option";
        option.setAttribute("role", "option");
        const label = document.createElement("strong");
        label.textContent = item.label;
        option.append(label);
        if (item.detail) {
          const detail = document.createElement("small");
          detail.textContent = item.detail;
          option.append(detail);
        }
        // pointerdown evita que el input pierda el foco antes de elegir.
        option.addEventListener("pointerdown", (event) => event.preventDefault());
        option.addEventListener("click", () => choose(item));
        option.addEventListener("mouseenter", () => highlight(index));
        const controls = controlsFor(item);
        if (controls) {
          const row = document.createElement("div");
          row.className = "live-search-row";
          row.append(option, controls);
          list.append(row);
        } else {
          list.append(option);
        }
      });
      if (items.length && total > items.length) {
        const more = document.createElement("p");
        more.className = "live-search-more";
        more.textContent = `Enter para ver los ${total} resultados`;
        list.append(more);
      }
      active = -1;
      list.hidden = !query;
      input.setAttribute("aria-expanded", String(!list.hidden));
      place();
    };

    const refresh = () => {
      const query = normalize(input.value);
      if (!query) {
        close();
        return;
      }
      if (input.dataset.liveSearchUrl) {
        const id = ++requestId;
        const url = new URL(input.dataset.liveSearchUrl, window.location.origin);
        url.searchParams.set("q", input.value.trim());
        fetch(url, {headers: {"X-Requested-With": "XMLHttpRequest"}})
          .then((response) => (response.ok ? response.json() : {results: []}))
          .then((data) => {
            if (id !== requestId || normalize(input.value) !== query) return;
            const results = data.results || [];
            render(results.slice(0, MAX_SUGGESTIONS), data.total ?? results.length, query);
          })
          .catch(() => {});
        return;
      }
      const matches = loadLocal()
        .map((item) => ({item, score: rank(item.search, query)}))
        .filter(({score}) => score < 99)
        .sort((a, b) => a.score - b.score || a.item.label.localeCompare(b.item.label, "es-MX"))
        .map(({item}) => item);
      render(matches.slice(0, MAX_SUGGESTIONS), matches.length, query);
    };

    let timer = 0;
    input.addEventListener("input", (event) => {
      if (ignoreNextInput) {
        ignoreNextInput = false;
        return;
      }
      window.clearTimeout(timer);
      timer = window.setTimeout(refresh, input.dataset.liveSearchUrl ? 160 : 0);
    });
    input.addEventListener("focus", () => { if (normalize(input.value)) refresh(); });
    // Captura: la sugerencia resaltada gana sobre el Enter propio de cada pantalla.
    input.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        if (list.hidden || !current.length) return;
        event.preventDefault();
        const step = event.key === "ArrowDown" ? 1 : -1;
        highlight((active + step + current.length) % current.length);
      } else if (event.key === "Enter") {
        if (!list.hidden && active >= 0 && current[active]) {
          event.preventDefault();
          event.stopImmediatePropagation();
          choose(current[active]);
        } else {
          close();
        }
      } else if (event.key === "Escape") {
        close();
      }
    }, true);
    input.addEventListener("blur", () => window.setTimeout(close, 120));
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    // El teclado en pantalla cambia el área visible sin cambiar el tamaño de la ventana.
    window.visualViewport?.addEventListener("resize", place);
    window.visualViewport?.addEventListener("scroll", place);
  };

  const scan = () => document.querySelectorAll("input[data-live-search-source], input[data-live-search-cards], input[data-live-search-url]").forEach(setup);
  scan();
  window.LiveSearch = {scan};
})();
