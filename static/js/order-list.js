/* NOTA TEMPORAL PARA APRENDIZAJE: La fila funciona como acceso al detalle, pero los
botones y formularios conservan su propia acción. También aceptamos Enter para que el
tablero pueda usarse con teclado. Borra esta nota después de leerla. */
// NOTA TEMPORAL PARA APRENDIZAJE: usamos delegación para que las filas recibidas
// por la actualización periódica conserven su comportamiento sin volver a registrar
// listeners en cada una. Borra esta nota después de leerla.
document.addEventListener("click", (event) => {
  const row = event.target.closest("[data-order-row-url]");
  if (!row || event.target.closest("a, button, input, select, textarea, form, details, summary, label")) return;
  window.location.href = row.dataset.orderRowUrl;
});
document.addEventListener("keydown", (event) => {
  const row = event.target.closest?.("[data-order-row-url]");
  if (!row || event.key !== "Enter" || event.target !== row) return;
  window.location.href = row.dataset.orderRowUrl;
});

const filterForm = document.querySelector("[data-order-filters]");
const filterToggle = document.querySelector("[data-order-filter-toggle]");
if (filterForm && filterToggle) {
  filterToggle.addEventListener("click", () => {
    const expanded = filterToggle.getAttribute("aria-expanded") === "true";
    filterToggle.setAttribute("aria-expanded", String(!expanded));
    filterForm.classList.toggle("is-mobile-expanded", !expanded);
  });
}
if (filterForm) {
  // NOTA TEMPORAL PARA APRENDIZAJE: el campo de texto ya NO se auto-envía mientras se
  // escribe (antes lo hacía 500ms después de cada tecla, recargando la página entera y
  // quitando el foco — en móvil, la pausa natural entre letras suele ser mayor a esos
  // 500ms, así que sólo dejaba escribir un carácter a la vez). Ahora sólo se busca con
  // Enter (envío nativo del formulario) o cambiando fecha/select. Borra esta nota.
  filterForm.querySelectorAll("select, input[type='date']").forEach((field) => {
    field.addEventListener("change", () => filterForm.requestSubmit());
  });
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-order-payment-method]");
  if (!button) return;
  const panel = button.closest("[data-order-payment]");
  const feedbackNode = panel.querySelector("[data-order-payment-feedback]");
  panel.querySelectorAll("[data-order-payment-method]").forEach((item) => { item.disabled = true; });
  const body = new FormData();
  body.append("payment_method", button.dataset.orderPaymentMethod);
  body.append("cash_amount", "");
  body.append("csrfmiddlewaretoken", panel.querySelector("[name='csrfmiddlewaretoken']").value);
  try {
    const response = await fetch(panel.dataset.paymentUrl, {
      method: "POST", body,
      headers: {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "No se pudo cambiar la forma de pago.");
    panel.querySelectorAll("[data-order-payment-method]").forEach((item) => {
      item.classList.toggle("is-selected", item.dataset.orderPaymentMethod === data.payment_method);
    });
    feedbackNode.textContent = data.payment_label;
    feedbackNode.classList.remove("is-error");
  } catch (error) {
    feedbackNode.textContent = error.message;
    feedbackNode.classList.add("is-error");
  } finally {
    panel.querySelectorAll("[data-order-payment-method]").forEach((item) => { item.disabled = false; });
  }
});

const feedback = document.querySelector("[data-order-board-feedback]");
let orderBoardRequestsInProgress = 0;
document.addEventListener("submit", async (event) => {
  const statusForm = event.target.closest(".order-row-actions form");
  // NOTA TEMPORAL PARA APRENDIZAJE: la columna también contiene la acción contable
  // "No pagó". Esa acción debe conservar su POST normal y no entrar en la máquina
  // AJAX de estados operativos. Borra esta nota después de leerla.
  if (!statusForm || statusForm.matches("[data-debt-create-form]")) return;
  event.preventDefault();
  const row = statusForm.closest("[data-order-status]");
  const button = statusForm.querySelector("button[type='submit']");
  const rowError = statusForm.querySelector("[data-row-status-error]");
  const originalLabel = button.textContent;
  button.disabled = true;
  button.textContent = "Actualizando…";
  orderBoardRequestsInProgress += 1;
  try {
    // NOTA TEMPORAL PARA APRENDIZAJE: el formulario contiene un input llamado
    // `action`; en HTML eso puede ocultar la propiedad JavaScript form.action y
    // devolver el propio input. getAttribute obtiene siempre la URL real. Borra esta nota.
    const response = await fetch(statusForm.getAttribute("action"), {
      method: "POST", body: new FormData(statusForm),
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": statusForm.querySelector("input[name='csrfmiddlewaretoken']").value,
        "Accept": "application/json",
      },
    });
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json() : {};
    if (!response.ok || !data.ok) {
      const requestError = new Error(data.error || "No se pudo cambiar el estado.");
      requestError.recoveryUrl = data.recovery_url;
      requestError.recoveryLabel = data.recovery_label;
      throw requestError;
    }
    row.classList.remove(`status-${row.dataset.orderStatus}`);
    row.classList.add(`status-${data.status}`);
    row.dataset.orderStatus = data.status;
    const label = row.querySelector(".order-status-label");
    Array.from(label.classList).filter((name) => name.startsWith("status-")).forEach((name) => label.classList.remove(name));
    label.classList.add(`status-${data.status}`);
    label.textContent = data.status_label;
    if (data.next_action) {
      statusForm.querySelector("input[name='action']").value = data.next_action;
      button.textContent = data.next_action_label;
      button.disabled = false;
    } else {
      statusForm.closest(".order-row-actions").innerHTML = "<small>Sin acción pendiente</small>";
    }
    if (feedback) feedback.hidden = true;
    if (rowError) rowError.hidden = true;
  } catch (error) {
    button.disabled = false;
    button.textContent = originalLabel;
    if (feedback) {
      feedback.className = "message error";
      feedback.textContent = error.message;
      feedback.hidden = false;
    }
    if (rowError) {
      rowError.textContent = error.recoveryLabel ? `${error.message} · ${error.recoveryLabel}` : error.message;
      rowError.href = error.recoveryUrl || "#";
      rowError.hidden = false;
    }
  } finally { orderBoardRequestsInProgress -= 1; }
});

// NOTA TEMPORAL PARA APRENDIZAJE: cada siete segundos pedimos la misma URL, por lo
// que se respetan Buscar/Mostrar/Estado/Tipo. Reemplazamos sólo la lista y mantenemos
// el scroll. Si alguien está interactuando con una fila, esperamos al siguiente ciclo.
// Borra esta nota después de leerla.
const refreshOrderBoard = async () => {
  const region = document.querySelector("[data-order-live-region]");
  const activeInside = region?.contains(document.activeElement)
    && document.activeElement?.matches("button, a, input, select, textarea");
  if (!region || document.hidden || orderBoardRequestsInProgress > 0 || activeInside) return;
  try {
    const response = await fetch(window.location.href, {
      headers: {"X-Requested-With": "XMLHttpRequest"}, cache: "no-store",
    });
    if (!response.ok) return;
    const nextDocument = new DOMParser().parseFromString(await response.text(), "text/html");
    const nextRegion = nextDocument.querySelector("[data-order-live-region]");
    if (!nextRegion || nextRegion.innerHTML === region.innerHTML) return;
    region.innerHTML = nextRegion.innerHTML;
  } catch (_) {
    // Una interrupción temporal de red no bloquea el tablero; el siguiente ciclo reintenta.
  }
};
window.setInterval(refreshOrderBoard, 7000);
