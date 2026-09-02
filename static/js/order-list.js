/* NOTA TEMPORAL PARA APRENDIZAJE: La fila funciona como acceso al detalle, pero los
botones y formularios conservan su propia acción. También aceptamos Enter para que el
tablero pueda usarse con teclado. Borra esta nota después de leerla. */
document.querySelectorAll("[data-order-row-url]").forEach((row) => {
  const openDetail = () => { window.location.href = row.dataset.orderRowUrl; };
  row.addEventListener("click", (event) => {
    if (event.target.closest("a, button, input, select, textarea, form")) return;
    openDetail();
  });
  row.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.target.closest("button, input, select, textarea")) return;
    openDetail();
  });
});

const filterForm = document.querySelector("[data-order-filters]");
if (filterForm) {
  let searchTimer = null;
  filterForm.querySelectorAll("select").forEach((field) => {
    field.addEventListener("change", () => filterForm.requestSubmit());
  });
  filterForm.querySelector("input[name='q']")?.addEventListener("input", () => {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => filterForm.requestSubmit(), 500);
  });
}

const feedback = document.querySelector("[data-order-board-feedback]");
document.addEventListener("submit", async (event) => {
  const statusForm = event.target.closest(".order-row-actions form");
  if (!statusForm) return;
  event.preventDefault();
  const row = statusForm.closest("[data-order-status]");
  const button = statusForm.querySelector("button[type='submit']");
  const rowError = statusForm.querySelector("[data-row-status-error]");
  const originalLabel = button.textContent;
  button.disabled = true;
  button.textContent = "Actualizando…";
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
  }
});
