/* Finalizar pedido (/pedir/finalizar/) por pasos.
   - Pasos: un panel a la vez con transición; "Continuar" valida el paso (sección en rojo con
     "qué hacer" y "qué pasó", sacudida suave) y "← Atrás" regresa. La barra de progreso marca
     los pasos hechos. Si el servidor regresó errores, abre el primer paso con error.
   - Campos: etiqueta flotante (CSS), palomita verde al quedar bien, celular con formato
     "55 1234 5678" y sugerencias de calles de reparto (la lista se abre hacia donde haya más
     espacio visible, para no quedar debajo del teclado).
   - Reloj propio: horas de hoy cada 15 minutos (las que manda el servidor). Elegir una hora
     significa "quiero un horario"; "Mejor lo antes posible" regresa al modo inmediato.
   - Efectivo: billete, otra cantidad o pago exacto (sólo una opción).
   - Al enviar: "Enviando…" con animación. Django vuelve a validar todo. */
(() => {
  const form = document.querySelector("[data-pp-checkout]");
  if (!form) return;
  const readJSON = (id) => { try { return JSON.parse(document.getElementById(id)?.textContent || "null"); } catch (_) { return null; } };
  const slots = readJSON("pp-schedule-slots") || [];
  const help = readJSON("pp-field-help") || {};
  const streets = readJSON("pp-delivery-streets") || [];
  const total = Number.parseFloat(form.dataset.total) || 0;
  const isDelivery = form.dataset.orderType === "delivery";
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const label12 = (value) => {
    const [hour, minute] = value.split(":").map(Number);
    return `${hour % 12 || 12}:${String(minute).padStart(2, "0")} ${hour < 12 ? "a. m." : "p. m."}`;
  };
  const normalize = (value) => String(value || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/[^a-z0-9 ]/g, " ").replace(/\b(av|avenida|calle)\b/g, " ").replace(/\bcerrada\b/g, "cda").replace(/\s+/g, " ").trim();
  const digits = (value) => {
    let only = String(value || "").replace(/\D/g, "");
    if (only.length === 12 && only.startsWith("52")) only = only.slice(2);
    return only;
  };
  const value = (name) => (form.querySelector(`[name='${name}']`)?.value || "").trim();

  // ---------------------------------------------------------------- errores (compartido)
  const summary = form.querySelector("[data-pp-error-summary]");
  const summaryList = form.querySelector("[data-pp-error-list]");
  const fieldBox = (name) => form.querySelector(`[data-pp-field='${name}']`);
  const sectionOf = (name) => (fieldBox(name) || form.querySelector(`[name='${name}']`))?.closest("[data-pp-section]");

  function refreshSection(section) {
    if (!section) return;
    section.classList.toggle("has-error", Boolean(section.querySelector("[data-pp-section-errors] .pp-error-item")));
  }
  function clearField(name) {
    fieldBox(name)?.classList.remove("is-invalid");
    const section = sectionOf(name);
    section?.querySelectorAll(`[data-pp-section-errors] .pp-error-item[data-field='${name}']`).forEach((item) => item.remove());
    refreshSection(section);
    summaryList?.querySelectorAll(`li[data-field='${name}']`).forEach((item) => item.remove());
    if (summary && summaryList && !summaryList.children.length) summary.hidden = true;
  }

  // ---------------------------------------------------------------- reloj
  const schedule = form.querySelector("[data-pp-schedule]");
  if (schedule) {
    const mode = schedule.querySelector("[data-pp-schedule-mode]");
    const timeInput = schedule.querySelector("[data-pp-schedule-time]");
    const asapButton = schedule.querySelector("[data-pp-schedule-asap]");
    const clockButton = schedule.querySelector("[data-pp-schedule-open]");
    const clockLabel = schedule.querySelector("[data-pp-schedule-label]");
    const panel = schedule.querySelector("[data-pp-clock-panel]");
    const hoursBox = schedule.querySelector("[data-pp-clock-hours]");
    const minutesBox = schedule.querySelector("[data-pp-clock-minutes]");
    const prefix = schedule.dataset.pickup === "true" ? "Recoger hoy a las" : "Entregar hoy a las";
    const hours = [...new Set(slots.map((slot) => slot.slice(0, 2)))];
    let hour = null;

    const choose = (choice) => {
      if (!choice) return;
      timeInput.value = choice;
      mode.value = "later";
      hour = choice.slice(0, 2);
      clearField("requested_time");
      render();
    };
    const render = () => {
      const later = mode.value === "later" && timeInput.value;
      asapButton.setAttribute("aria-pressed", String(!later));
      if (clockButton) {
        clockButton.setAttribute("aria-pressed", String(Boolean(later)));
        clockLabel.textContent = later ? `${prefix} ${label12(timeInput.value)}` : "Elegir hora";
      }
      if (!hoursBox) return;
      hoursBox.replaceChildren(...hours.map((option) => {
        const button = document.createElement("button");
        button.type = "button";
        const number = Number(option);
        button.innerHTML = `${number % 12 || 12}<small>${number < 12 ? "a. m." : "p. m."}</small>`;
        button.classList.toggle("is-active", option === hour);
        button.addEventListener("click", () => {
          // Mover la hora ya cuenta como elegir horario: se conserva el minuto si existe.
          const keep = timeInput.value.slice(3);
          choose(slots.find((slot) => slot === `${option}:${keep}`) || slots.find((slot) => slot.startsWith(`${option}:`)));
        });
        return button;
      }));
      minutesBox.replaceChildren(...["00", "15", "30", "45"].map((minute) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = `:${minute}`;
        const candidate = `${hour}:${minute}`;
        button.disabled = !hour || !slots.includes(candidate);
        button.classList.toggle("is-active", Boolean(later) && timeInput.value === candidate);
        button.addEventListener("click", () => choose(candidate));
        return button;
      }));
    };
    const resetToAsap = () => {
      mode.value = "asap";
      timeInput.value = "";
      hour = null;
      if (panel) panel.hidden = true;
      clockButton?.setAttribute("aria-expanded", "false");
      clearField("requested_time");
      render();
    };
    asapButton.addEventListener("click", resetToAsap);
    schedule.querySelector("[data-pp-schedule-reset]")?.addEventListener("click", resetToAsap);
    clockButton?.addEventListener("click", () => {
      panel.hidden = !panel.hidden;
      clockButton.setAttribute("aria-expanded", String(!panel.hidden));
      if (!panel.hidden && !hour) hour = timeInput.value ? timeInput.value.slice(0, 2) : hours[0];
      render();
    });
    schedule.querySelector("[data-pp-clock-done]")?.addEventListener("click", () => {
      panel.hidden = true;
      clockButton.setAttribute("aria-expanded", "false");
    });
    if (timeInput.value) hour = timeInput.value.slice(0, 2);
    render();
  }

  // ---------------------------------------------------------------- efectivo
  const cash = form.querySelector("[data-pp-cash]");
  const methodInputs = [...form.querySelectorAll("input[name='payment_method']")];
  const billInputs = [...form.querySelectorAll("input[name='cash_bill']")];
  const customAmount = form.querySelector("input[name='cash_custom_amount']");
  const paysExact = form.querySelector("input[name='pays_exact']");
  const method = () => methodInputs.find((input) => input.checked)?.value || "";
  const refreshCash = () => {
    if (!cash) return;
    const isCash = method() === "cash";
    cash.hidden = !isCash;
    cash.querySelectorAll("input").forEach((input) => { input.disabled = !isCash; });
  };
  methodInputs.forEach((input) => input.addEventListener("change", () => { refreshCash(); clearField("payment_method"); }));
  billInputs.forEach((input) => input.addEventListener("change", () => {
    if (customAmount) customAmount.value = "";
    if (paysExact) paysExact.checked = false;
    clearField("cash_bill"); clearField("cash_custom_amount");
  }));
  customAmount?.addEventListener("input", () => {
    if (customAmount.value) { billInputs.forEach((input) => { input.checked = false; }); if (paysExact) paysExact.checked = false; }
    clearField("cash_bill"); clearField("cash_custom_amount");
  });
  paysExact?.addEventListener("change", () => {
    if (paysExact.checked) { billInputs.forEach((input) => { input.checked = false; }); if (customAmount) customAmount.value = ""; }
    clearField("cash_bill"); clearField("cash_custom_amount");
  });
  refreshCash();

  // ---------------------------------------------------------------- celular y palomitas
  const phoneInput = form.querySelector("[data-pp-phone]");
  const formatPhone = (raw) => {
    const only = digits(raw).slice(0, 10);
    return [only.slice(0, 2), only.slice(2, 6), only.slice(6, 10)].filter(Boolean).join(" ");
  };
  phoneInput?.addEventListener("input", () => {
    const atEnd = phoneInput.selectionStart === phoneInput.value.length;
    if (!/^\+?52/.test(phoneInput.value.replace(/\s/g, "")) || digits(phoneInput.value).length <= 10) {
      phoneInput.value = formatPhone(phoneInput.value);
      if (atEnd) phoneInput.setSelectionRange(phoneInput.value.length, phoneInput.value.length);
    }
  });
  if (phoneInput?.value) phoneInput.value = formatPhone(phoneInput.value);
  const fieldIsGood = (name) => {
    if (name === "phone") return digits(value("phone")).length === 10;
    if (["customer_first_name", "customer_last_name", "street", "exterior_number"].includes(name)) return Boolean(value(name));
    return false;
  };
  form.addEventListener("focusout", (event) => {
    const name = event.target.name;
    if (name) fieldBox(name)?.classList.toggle("is-valid", fieldIsGood(name));
  });
  form.addEventListener("input", (event) => {
    if (!event.target.name) return;
    clearField(event.target.name);
    if (!fieldIsGood(event.target.name)) fieldBox(event.target.name)?.classList.remove("is-valid");
  });

  // ---------------------------------------------------------------- sugerencias de calle
  const streetInput = form.querySelector("[data-pp-street]");
  const streetList = document.querySelector("[data-pp-street-list]");
  if (streetInput && streetList && streets.length) {
    let active = -1;
    const close = () => { streetList.hidden = true; active = -1; };
    const place = () => {
      const viewport = window.visualViewport;
      const top = viewport ? viewport.offsetTop : 0;
      const bottom = top + (viewport ? viewport.height : window.innerHeight);
      const box = streetInput.getBoundingClientRect();
      const below = bottom - box.bottom - 10;
      const above = box.top - top - 10;
      streetList.style.left = `${box.left}px`;
      streetList.style.width = `${box.width}px`;
      if (below < 160 && above > below) {
        streetList.style.top = "auto";
        streetList.style.bottom = `${window.innerHeight - box.top + 4}px`;
        streetList.style.maxHeight = `${Math.min(260, above)}px`;
      } else {
        streetList.style.bottom = "auto";
        streetList.style.top = `${box.bottom + 4}px`;
        streetList.style.maxHeight = `${Math.min(260, Math.max(below, 120))}px`;
      }
    };
    const pick = (name) => {
      streetInput.value = name;
      clearField("street");
      fieldBox("street")?.classList.add("is-valid");
      close();
      form.querySelector("[name='exterior_number']")?.focus();
    };
    const refresh = () => {
      const query = normalize(streetInput.value);
      if (!query) { close(); return; }
      const matches = streets.filter((name) => normalize(name).includes(query)).slice(0, 8);
      if (!matches.length) { close(); return; }
      streetList.replaceChildren(...matches.map((name) => {
        const option = document.createElement("button");
        option.type = "button";
        option.setAttribute("role", "option");
        option.textContent = name;
        option.addEventListener("pointerdown", (event) => event.preventDefault());
        option.addEventListener("click", () => pick(name));
        return option;
      }));
      streetList.hidden = false;
      active = -1;
      place();
    };
    streetInput.addEventListener("input", refresh);
    streetInput.addEventListener("focus", refresh);
    streetInput.addEventListener("blur", () => window.setTimeout(close, 120));
    streetInput.addEventListener("keydown", (event) => {
      const options = [...streetList.querySelectorAll("button")];
      if (streetList.hidden || !options.length) return;
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        active = (active + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
        options.forEach((option, index) => option.classList.toggle("is-active", index === active));
      } else if (event.key === "Enter" && active >= 0) {
        event.preventDefault();
        pick(options[active].textContent);
      } else if (event.key === "Escape") {
        close();
      }
    });
    window.visualViewport?.addEventListener("resize", () => { if (!streetList.hidden) place(); });
    window.addEventListener("scroll", () => { if (!streetList.hidden) place(); }, true);
  }

  // ---------------------------------------------------------------- validación por paso
  const STEP_FIELDS = {
    datos: ["customer_first_name", "phone"],
    domicilio: ["street", "exterior_number"],
    horario: [],
    pago: ["payment_method", "cash_bill", "cash_custom_amount"],
  };
  function collectErrors(stepName) {
    const errors = [];
    const add = (name, label, what) => errors.push({name, label, what, help: help[name] || ""});
    const wants = (name) => !stepName || STEP_FIELDS[stepName]?.includes(name);
    if (wants("phone")) {
      const phone = digits(value("phone"));
      if (!phone) add("phone", "Número celular", "Este dato está vacío.");
      else if (phone.length !== 10) add("phone", "Número celular", `El número que escribiste tiene ${phone.length} dígito${phone.length === 1 ? "" : "s"}.`);
    }
    if (wants("customer_first_name") && !value("customer_first_name")) add("customer_first_name", "Nombre", "Este dato está vacío.");
    if (isDelivery && wants("street")) {
      // Calle y número vacíos los decide el servidor (cliente registrado con su celular).
      if (value("street") && !value("exterior_number")) add("exterior_number", "Número exterior", "Este dato está vacío.");
      if (!value("street") && value("exterior_number")) add("street", "Calle", "Este dato está vacío.");
    }
    if (isDelivery && wants("payment_method")) {
      if (!method()) add("payment_method", "Forma de pago", "Este dato está vacío.");
      else if (method() === "cash") {
        const bill = billInputs.find((input) => input.checked)?.value;
        const custom = Number.parseFloat(customAmount?.value || "");
        const chosen = [bill, customAmount?.value, paysExact?.checked].filter(Boolean).length;
        if (!chosen) add("cash_bill", "Billete", "No elegiste billete, cantidad ni pago exacto.");
        else if (bill && Number(bill) < total) add("cash_bill", "Billete", `$${bill} no alcanza para el total de $${total.toFixed(2)}.`);
        else if (!bill && customAmount?.value && custom < total) add("cash_custom_amount", "Otra cantidad", `$${custom.toFixed(2)} no alcanza para el total de $${total.toFixed(2)}.`);
      }
    }
    return errors;
  }

  function showErrors(errors) {
    form.querySelectorAll("[data-pp-section-errors]").forEach((box) => box.replaceChildren());
    form.querySelectorAll(".is-invalid").forEach((box) => box.classList.remove("is-invalid"));
    form.querySelectorAll("[data-pp-section].has-error").forEach((section) => section.classList.remove("has-error"));
    summaryList.replaceChildren();
    errors.forEach((error) => {
      const section = sectionOf(error.name);
      fieldBox(error.name)?.classList.add("is-invalid");
      if (section) {
        const item = document.createElement("div");
        item.className = "pp-error-item";
        item.dataset.field = error.name;
        const doLine = document.createElement("p");
        doLine.className = "pp-error-do";
        doLine.textContent = error.help;
        const whatLine = document.createElement("p");
        whatLine.className = "pp-error-what";
        whatLine.innerHTML = "<b>Qué pasó:</b> ";
        whatLine.append(error.what);
        item.append(doLine, whatLine);
        section.querySelector("[data-pp-section-errors]")?.append(item);
        section.classList.add("has-error");
      }
      const li = document.createElement("li");
      li.dataset.field = error.name;
      const link = document.createElement("a");
      link.href = `#${section?.id || ""}`;
      link.textContent = `${section?.querySelector("h2")?.textContent.trim() || ""} · ${error.label}`;
      li.append(link);
      summaryList.append(li);
    });
    summary.hidden = false;
    const first = form.querySelector("[data-pp-section].has-error");
    if (first && !reduceMotion) {
      first.classList.remove("is-shaking");
      void first.offsetWidth;
      first.classList.add("is-shaking");
    }
    (first || summary).scrollIntoView({behavior: reduceMotion ? "auto" : "smooth", block: "start"});
    window.setTimeout(() => first?.querySelector(".is-invalid input, .is-invalid textarea")?.focus({preventScroll: true}), 450);
  }

  // ---------------------------------------------------------------- pasos
  const panels = [...form.querySelectorAll("[data-pp-step]")];
  const progress = [...form.querySelectorAll("[data-pp-progress-step]")];
  const back = form.querySelector("[data-pp-step-back]");
  const next = form.querySelector("[data-pp-step-next]");
  const nav = form.querySelector("[data-pp-step-nav]");
  const submitBar = form.querySelector("[data-pp-submit-bar]");
  let current = 0;
  const showStep = (index, direction = 1) => {
    current = Math.max(0, Math.min(index, panels.length - 1));
    panels.forEach((panel, position) => {
      const visible = position === current;
      panel.hidden = !visible;
      panel.classList.remove("is-entering-forward", "is-entering-back");
      if (visible && !reduceMotion) panel.classList.add(direction > 0 ? "is-entering-forward" : "is-entering-back");
    });
    progress.forEach((step, position) => {
      step.classList.toggle("is-done", position < current);
      step.classList.toggle("is-current", position === current);
    });
    const last = current === panels.length - 1;
    back.hidden = current === 0;
    next.hidden = last;
    nav.classList.toggle("is-first", current === 0);
    submitBar.hidden = !last;
    form.scrollIntoView({behavior: reduceMotion ? "auto" : "smooth", block: "start"});
  };
  next.addEventListener("click", () => {
    const errors = collectErrors(panels[current].dataset.ppStep);
    if (errors.length) { showErrors(errors); return; }
    if (summary) summary.hidden = true;
    showStep(current + 1, 1);
  });
  back.addEventListener("click", () => showStep(current - 1, -1));
  progress.forEach((step, position) => step.addEventListener("click", () => {
    if (position < current) showStep(position, -1);
  }));

  // ---------------------------------------------------------------- envío
  const send = form.querySelector("[data-pp-send]");
  form.addEventListener("submit", (event) => {
    const errors = collectErrors(null);
    if (errors.length) {
      event.preventDefault();
      const firstStep = panels.findIndex((panel) => errors.some((error) => sectionOf(error.name) === panel));
      if (firstStep >= 0 && firstStep !== current) showStep(firstStep, -1);
      showErrors(errors);
      return;
    }
    send.disabled = true;
    send.classList.add("is-sending");
    send.querySelector("span").textContent = "Enviando…";
  });

  // Resumen: abierto en pantallas grandes; desplegable en celular.
  const details = document.querySelector("[data-pp-summary-details]");
  if (details && window.matchMedia("(min-width: 900px)").matches) details.open = true;

  // Inicio: si el servidor regresó errores, se abre el primer paso que los tiene.
  const serverErrorStep = panels.findIndex((panel) => panel.classList.contains("has-error"));
  showStep(serverErrorStep >= 0 ? serverErrorStep : 0, 1);
  if (serverErrorStep >= 0 && summary && !summary.hidden) {
    window.setTimeout(() => panels[serverErrorStep].scrollIntoView({behavior: "smooth", block: "start"}), 150);
  }
})();
