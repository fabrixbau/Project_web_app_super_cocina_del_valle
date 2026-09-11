/* NOTA TEMPORAL PARA APRENDIZAJE: Los filtros se envían solos y la asignación usa
fetch para conservar scroll y contexto. La clase is-selected muestra quién quedó
asignado después de cada respuesta del servidor. Borra esta nota. */
const deliveryFilters = document.querySelector("[data-delivery-filters]");
if (deliveryFilters) {
  const scrollStorageKey = "delivery-board-filter-scroll";
  const savedScroll = window.sessionStorage.getItem(scrollStorageKey);
  if (savedScroll !== null) {
    window.sessionStorage.removeItem(scrollStorageKey);
    window.requestAnimationFrame(() => window.scrollTo({ top: Number(savedScroll), behavior: "auto" }));
  }
  deliveryFilters.addEventListener("submit", () => {
    window.sessionStorage.setItem(scrollStorageKey, String(window.scrollY));
  });
  let timer = null;
  deliveryFilters.querySelectorAll("select").forEach((field) => field.addEventListener("change", () => deliveryFilters.requestSubmit()));
  deliveryFilters.querySelectorAll("input[name='delivery_person']").forEach((field) => field.addEventListener("change", () => deliveryFilters.requestSubmit()));
  deliveryFilters.querySelectorAll("input[name='status']").forEach((field) => field.addEventListener("change", () => deliveryFilters.requestSubmit()));
  deliveryFilters.querySelector("input[name='q']")?.addEventListener("input", () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => deliveryFilters.requestSubmit(), 500);
  });
  deliveryFilters.querySelector("[data-clear-delivery-status]")?.addEventListener("click", () => {
    deliveryFilters.querySelectorAll("input[name='status']").forEach((field) => { field.checked = false; });
    deliveryFilters.requestSubmit();
  });
}

const deliveryFeedback = document.querySelector("[data-delivery-feedback]");
document.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-delivery-assign]");
  if (!form) return;
  event.preventDefault();
  const card = form.closest("[data-delivery-card]");
  const errorBox = card.querySelector("[data-delivery-error]");
  const buttons = card.querySelectorAll("[data-person-id]");
  buttons.forEach((button) => { button.disabled = true; });
  try {
    const response = await fetch(form.getAttribute("action"), {
      method: "POST", body: new FormData(form),
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": form.querySelector("input[name='csrfmiddlewaretoken']").value,
        "Accept": "application/json",
      },
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "No se pudo asignar el repartidor.");
    card.querySelector("[data-current-assignee]").textContent = data.delivery_person_name;
    const tipRecipient = card.querySelector("[data-tip-recipient]");
    const tipAmount = Number(card.querySelector("[data-tip-amount]")?.textContent || 0);
    if (tipRecipient && tipAmount > 0) tipRecipient.textContent = data.delivery_person_name;
    buttons.forEach((button) => button.classList.toggle("is-selected", button.dataset.personId === String(data.delivery_person_id)));
    errorBox.hidden = true;
    deliveryFeedback.className = "message success";
    deliveryFeedback.textContent = data.message;
    deliveryFeedback.hidden = false;
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  } finally {
    buttons.forEach((button) => { button.disabled = false; });
  }
});

document.addEventListener("click", (event) => {
  const quickTip = event.target.closest("[data-tip-value]");
  if (!quickTip) return;
  const form = quickTip.closest("[data-delivery-tip]");
  form.querySelector("input[name='tip_amount']").value = quickTip.dataset.tipValue;
  form.requestSubmit();
});

let deliveryTipTimer = null;
document.addEventListener("input", (event) => {
  const input = event.target.closest("[data-delivery-tip] input[name='tip_amount']");
  if (!input) return;
  window.clearTimeout(deliveryTipTimer);
  deliveryTipTimer = window.setTimeout(() => input.form.requestSubmit(), 600);
});

document.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-delivery-tip]");
  if (!form) return;
  event.preventDefault();
  const card = form.closest("[data-delivery-card]");
  const submitButton = form.querySelector("button[type='submit']");
  const errorBox = form.querySelector("[data-tip-error]");
  submitButton.disabled = true;
  try {
    const response = await fetch(form.getAttribute("action"), {
      method: "POST", body: new FormData(form),
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": form.querySelector("input[name='csrfmiddlewaretoken']").value,
        "Accept": "application/json",
      },
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "No se pudo guardar la propina.");
    card.querySelector("[data-tip-amount]").textContent = data.tip_amount;
    card.querySelector("[data-total-with-tip]").textContent = data.total_with_tip;
    card.querySelector("[data-tip-recipient]").textContent = data.recipient;
    errorBox.hidden = true;
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  } finally {
    submitButton.disabled = false;
  }
});

document.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-delivery-status-form]");
  if (!form) return;
  event.preventDefault();
  const card = form.closest("[data-delivery-card]");
  const button = form.querySelector("button[type='submit']");
  const errorBox = card.querySelector("[data-delivery-error]");
  const originalLabel = button.textContent;
  button.disabled = true;
  button.textContent = "Actualizando…";
  try {
    const response = await fetch(form.getAttribute("action"), {
      method: "POST", body: new FormData(form),
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": form.querySelector("input[name='csrfmiddlewaretoken']").value,
        "Accept": "application/json",
      },
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "No se pudo cambiar el estado.");
    card.classList.remove(`status-${card.dataset.deliveryStatus}`);
    card.classList.add(`status-${data.status}`);
    card.dataset.deliveryStatus = data.status;
    card.querySelector("[data-delivery-status-label]").textContent = data.status_label;
    errorBox.hidden = true;
    if (data.next_label) {
      button.textContent = data.next_label;
      button.disabled = false;
    } else {
      form.remove();
    }
  } catch (error) {
    button.disabled = false;
    button.textContent = originalLabel;
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  }
});
