/* Portal de clientes (/pedir/): comportamiento de la interfaz nueva.
   - Menú: barra "Ver pedido" (celular) que abre el ticket como hoja inferior; se actualiza con
     el aviso `public-cart-rendered` que emite public-menu-controls.js.
   - Menú: resalta en la barra de categorías la sección que se está viendo.
   - Paquete: botones − / + de cantidad y total en vivo del botón Agregar. */
(() => {
  const money = (value) => `$${value.toFixed(2)}`;

  // ---------------------------------------------------------------- carrito (menú)
  const ticket = document.querySelector("[data-pp-ticket]");
  const bar = document.querySelector("[data-pp-cart-bar]");
  const backdrop = document.querySelector("[data-pp-sheet-backdrop]");
  const barTotal = document.querySelector("[data-pp-cart-total]");

  const closeSheet = () => {
    if (!ticket) return;
    ticket.classList.remove("is-open");
    if (backdrop) backdrop.hidden = true;
    document.body.classList.remove("pp-sheet-open");
  };
  const openSheet = () => {
    if (!ticket || ticket.hidden) return;
    ticket.classList.add("is-open");
    if (backdrop) backdrop.hidden = false;
    document.body.classList.add("pp-sheet-open");
  };

  bar?.addEventListener("click", openSheet);
  backdrop?.addEventListener("click", closeSheet);
  document.querySelector("[data-pp-ticket-close]")?.addEventListener("click", closeSheet);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && ticket?.classList.contains("is-open")) closeSheet();
  });
  document.addEventListener("public-cart-rendered", (event) => {
    const cart = event.detail || {};
    const count = Number(cart.count) || 0;
    if (bar) bar.hidden = count === 0;
    if (barTotal) barTotal.textContent = `$${cart.total_display || "0.00"}`;
    if (!count) closeSheet();
  });

  // ---------------------------------------------------------------- categorías (menú)
  const nav = document.querySelector("[data-pp-category-nav]");
  if (nav && "IntersectionObserver" in window) {
    const links = [...nav.querySelectorAll("a[href^='#']")];
    const sections = links.map((link) => document.querySelector(link.getAttribute("href"))).filter(Boolean);
    const activate = (id) => links.forEach((link) => {
      const active = link.getAttribute("href") === `#${id}`;
      link.classList.toggle("is-active", active);
      if (active) {
        // Mantiene visible la categoría activa dentro de la barra horizontal.
        const left = link.offsetLeft - (nav.clientWidth - link.offsetWidth) / 2;
        nav.scrollTo({left, behavior: "smooth"});
      }
    });
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (visible) activate(visible.target.id);
    }, {rootMargin: "-130px 0px -55% 0px"});
    sections.forEach((section) => observer.observe(section));
  }

  // ---------------------------------------------------------------- pizarra del menú del día
  // Pestañas Comida corrida | Comida ejecutiva y "+N opciones más" de la plancha.
  // Tocar otra vez la pestaña ya elegida (o doble toque) abre su armador, igual que
  // "Armar mi comida corrida/ejecutiva →".
  document.querySelectorAll("[data-pp-board]").forEach((board) => {
    const tabs = [...board.querySelectorAll("[data-pp-board-select]")];
    tabs.forEach((tab) => tab.addEventListener("click", () => {
      if (tab.getAttribute("aria-selected") === "true") {
        const builder = board.querySelector(`a.pp-today-cta[data-pp-board-for='${tab.dataset.ppBoardSelect}']`);
        if (builder) window.location.href = builder.href;
        return;
      }
      board.dataset.ppBoardTab = tab.dataset.ppBoardSelect;
      tabs.forEach((candidate) => candidate.setAttribute("aria-selected", String(candidate === tab)));
    }));
    const more = board.querySelector("[data-pp-board-more]");
    more?.addEventListener("click", () => {
      const open = more.getAttribute("aria-expanded") !== "true";
      board.querySelectorAll("[data-pp-board-extra]").forEach((item) => { item.hidden = !open; });
      more.setAttribute("aria-expanded", String(open));
      more.textContent = open ? "Ver menos" : more.dataset.moreLabel;
    });
  });

  // ---------------------------------------------------------------- paquete
  // Contador − # + como el del personal: "+" guarda la comida en curso y limpia la plantilla;
  // "−" descarta la que se está armando y regresa a la anterior. Al enviar, todas viajan en
  // `package_batch` (mismo formato que Mesas/Pedidos). Si sólo hay primer o segundo tiempo
  // más el guisado, es una comida de 2 tiempos: se pide confirmación (mismo precio).
  const packageForm = document.querySelector("[data-pp-package]");
  if (packageForm) {
    const priceWithout = Number.parseFloat(packageForm.dataset.priceWithoutWater) || 0;
    const priceWith = Number.parseFloat(packageForm.dataset.priceWithWater) || 0;
    const totalNode = packageForm.querySelector("[data-pp-package-total]");
    const countNode = packageForm.querySelector("[data-pp-meal-count]");
    const decrease = packageForm.querySelector("[data-pp-meal-decrease]");
    const increase = packageForm.querySelector("[data-pp-meal-increase]");
    const submit = packageForm.querySelector("[data-pp-submit]");
    const payButton = packageForm.querySelector("[data-pp-submit-pay]");
    const built = packageForm.querySelector("[data-pp-built]");
    const builtList = packageForm.querySelector("[data-pp-built-list]");
    const dialog = document.querySelector("[data-pp-two-course-dialog]");
    const dialogText = dialog?.querySelector("[data-pp-two-course-text]");
    const SKIPPED = ["csrfmiddlewaretoken", "package_batch"];
    const saved = [];

    const checked = (name) => packageForm.querySelector(`input[name='${name}']:checked`);
    const labelOf = (input) => input?.closest("label")?.querySelector("span")?.textContent.trim() || "";
    const water = () => packageForm.querySelector("input[name='with_water']");
    const hasAnyCourse = () => ["first_course", "second_course", "main_course"].some((name) => checked(name));
    const isTwoCourse = () => Boolean(checked("main_course")) && Boolean(checked("first_course")) !== Boolean(checked("second_course"));
    const currentPrice = () => (water()?.checked ? priceWith : priceWithout);

    // Detalle de cómo quedó armada la comida en curso.
    const describe = () => {
      const piece = labelOf(checked("chicken_piece"));
      const main = labelOf(checked("main_course"));
      return [
        isTwoCourse() ? "2 tiempos" : "",
        labelOf(checked("first_course")), labelOf(checked("second_course")),
        piece ? `${main} (${piece.toLowerCase()})` : main,
        water()?.checked ? "con agua" : "sin agua",
        checked("tortillas")?.value === "yes" ? "con tortillas" : "sin tortillas",
        checked("beans")?.value === "yes" ? "con frijoles" : "sin frijoles",
      ].filter(Boolean).join(" · ");
    };
    const snapshot = () => [...new FormData(packageForm).entries()]
      .filter(([name, value]) => typeof value === "string" && !SKIPPED.includes(name));

    // Guisado, primer o segundo tiempo, Sí/No de tortillas y frijoles, y pieza si es pollo.
    const validateCurrent = () => {
      if (!checked("first_course") && !checked("second_course")) {
        const first = packageForm.querySelector("input[name='first_course']");
        first?.setCustomValidity("Elige el primer o el segundo tiempo.");
        first?.reportValidity();
        first?.setCustomValidity("");
        return false;
      }
      return packageForm.reportValidity();
    };
    const confirmTwoCourse = () => new Promise((resolve) => {
      if (!isTwoCourse() || !dialog) { resolve(true); return; }
      const courses = ["first_course", "second_course", "main_course"].map((name) => labelOf(checked(name))).filter(Boolean);
      dialogText.textContent = `Armaste esta comida con sólo dos tiempos: ${courses.join(" + ")}.`;
      dialog.returnValue = "";
      dialog.addEventListener("close", () => resolve(dialog.returnValue === "ok"), {once: true});
      dialog.showModal();
    });

    const render = () => {
      countNode.textContent = String(saved.length + 1);
      decrease.disabled = saved.length === 0 && !hasAnyCourse();
      built.hidden = saved.length === 0;
      builtList.replaceChildren(...saved.map((meal, index) => {
        const item = document.createElement("li");
        const copy = document.createElement("span");
        const title = document.createElement("strong");
        title.textContent = `Comida ${index + 1} · ${money(meal.price)}`;
        const detail = document.createElement("small");
        detail.textContent = meal.text;
        copy.append(title, detail);
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "pp-built-remove";
        remove.textContent = "×";
        remove.setAttribute("aria-label", `Quitar la comida ${index + 1}`);
        remove.addEventListener("click", () => { saved.splice(index, 1); render(); });
        item.append(copy, remove);
        return item;
      }));
      const current = hasAnyCourse() || !saved.length ? currentPrice() : 0;
      totalNode.textContent = money(saved.reduce((sum, meal) => sum + meal.price, 0) + current);
      const meals = saved.length + (hasAnyCourse() ? 1 : 0);
      submit.textContent = meals > 1 ? `Agregar ${meals} y seguir pidiendo` : "Agregar y seguir pidiendo";
    };

    // `reset` también lo escucha package-selection.js (pieza de pollo); se repinta después.
    const resetTemplate = () => {
      packageForm.reset();
      window.setTimeout(render);
    };
    const loadMeal = (fields) => {
      packageForm.reset();
      window.setTimeout(() => {
        const pairs = new Set(fields.map(([name, value]) => `${name}\u0000${value}`));
        packageForm.querySelectorAll("input[type='radio'], input[type='checkbox']").forEach((input) => {
          input.checked = pairs.has(`${input.name}\u0000${input.value}`);
        });
        render();
      });
    };

    increase.addEventListener("click", async () => {
      if (!validateCurrent() || !(await confirmTwoCourse())) return;
      saved.push({fields: snapshot(), text: describe(), price: currentPrice()});
      resetTemplate();
      packageForm.scrollIntoView({behavior: "smooth", block: "start"});
    });
    decrease.addEventListener("click", () => {
      if (saved.length) loadMeal(saved.pop().fields);
      else resetTemplate();
    });
    // Tocar otra vez un tiempo ya elegido lo desmarca (así se arma una comida de 2 tiempos).
    packageForm.querySelectorAll("[data-pp-course] .pp-choice").forEach((label) => {
      const input = label.querySelector("input[type='radio']");
      label.addEventListener("pointerdown", () => { input.dataset.wasChecked = input.checked ? "true" : ""; });
      input.addEventListener("click", () => {
        if (input.dataset.wasChecked !== "true") return;
        input.dataset.wasChecked = "";
        input.checked = false;
        input.dispatchEvent(new Event("change", {bubbles: true}));
      });
    });
    packageForm.addEventListener("change", render);

    packageForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const meals = saved.map((meal) => meal.fields);
      if (hasAnyCourse() || !meals.length) {
        if (!validateCurrent() || !(await confirmTwoCourse())) return;
        meals.push(snapshot());
      }
      // Las comidas idénticas viajan juntas con su cantidad.
      const groups = new Map();
      meals.forEach((fields) => {
        const key = JSON.stringify([...fields].sort());
        const group = groups.get(key);
        if (group) group.quantity += 1;
        else groups.set(key, {fields, quantity: 1});
      });
      packageForm.querySelectorAll("input[name='package_batch']").forEach((input) => input.remove());
      const batch = document.createElement("input");
      batch.type = "hidden";
      batch.name = "package_batch";
      batch.value = JSON.stringify([...groups.values()]);
      packageForm.append(batch);
      // form.submit() no manda el botón pulsado: el destino (menú o pago) va en un campo oculto.
      packageForm.querySelectorAll("input[name='next']").forEach((input) => input.remove());
      const next = document.createElement("input");
      next.type = "hidden";
      next.name = "next";
      next.value = event.submitter?.value === "checkout" ? "checkout" : "menu";
      packageForm.append(next);
      submit.disabled = true;
      if (payButton) payButton.disabled = true;
      packageForm.submit();
    });
    render();
  }
})();
