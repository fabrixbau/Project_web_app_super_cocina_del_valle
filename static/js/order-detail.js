/* NOTA TEMPORAL PARA APRENDIZAJE: las acciones de estado se envían en segundo plano.
La respuesta permite actualizar estado, siguiente botón e historial sin reconstruir la
página ni perder la posición del scroll. Borra esta nota después de leerla. */
const detailFeedback = document.querySelector("[data-order-detail-feedback]");
document.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-order-detail-action]");
  if (!form) return;
  event.preventDefault();
  const button = form.querySelector("button");
  const originalLabel = button.textContent;
  button.disabled = true;
  try {
    const response = await fetch(form.getAttribute("action"), {
      method: "POST", body: new FormData(form),
      headers: {"X-Requested-With": "XMLHttpRequest", Accept: "application/json"},
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "No se pudo cambiar el estado.");
    const badge = document.querySelector("[data-order-detail-status]");
    badge.className = `status-badge status-${data.status}`;
    badge.textContent = data.status_label;
    const history = document.querySelector("[data-order-detail-history]");
    history.querySelector("[data-empty-history]")?.remove();
    const entry = document.createElement("li");
    const state = document.createElement("strong"); state.textContent = data.status_label;
    const metadata = document.createElement("small"); metadata.textContent = `${data.changed_at} · ${data.changed_by}`;
    entry.append(state, metadata); history.append(entry);
    const actions = document.querySelector("[data-order-detail-actions]");
    if (data.next_action) {
      form.querySelector("[name='action']").value = data.next_action;
      button.textContent = data.next_action_label;
      button.classList.remove("danger");
      actions.querySelectorAll("form").forEach((candidate) => { if (candidate !== form) candidate.remove(); });
      button.disabled = false;
    } else actions?.remove();
    detailFeedback.textContent = `El pedido ahora está: ${data.status_label}.`;
    detailFeedback.className = "message success";
    detailFeedback.hidden = false;
  } catch (error) {
    button.textContent = originalLabel; button.disabled = false;
    detailFeedback.textContent = error.message;
    detailFeedback.className = "message error";
    detailFeedback.hidden = false;
  }
});
