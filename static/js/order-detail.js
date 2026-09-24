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

(() => {
  const responsiveView = window.matchMedia("(max-width: 900px)");
  const main = document.querySelector("main.internal-panel");
  const heading = document.querySelector(".page-heading");
  const grid = document.querySelector(".order-detail-grid");
  const history = document.querySelector(".status-history")?.closest("section.card");
  if (!heading || !grid || !history) return;

  heading.classList.add("order-detail-heading");
  const backLink = [...document.querySelectorAll("main.internal-panel > p > a")]
    .find((link) => link.getAttribute("href")?.includes("/pedidos/"));
  const backRow = backLink?.parentElement;
  if (backLink) {
    backLink.classList.add("order-detail-back");
    backLink.setAttribute("aria-label", "Volver a pedidos");
    heading.prepend(backLink);
    if (backRow && !backRow.textContent.trim()) backRow.remove();
  }

  heading.querySelectorAll(".action-group a").forEach((link) => {
    const label = link.textContent.trim().toLowerCase();
    if (label.includes("editar")) link.classList.add("is-edit-action");
    if (label.includes("imprimir")) {
      link.classList.add("is-print-action");
      if (label.includes("cobro")) link.classList.add("is-payment-print-action");
      else if (label.includes("modificado")) link.classList.add("is-custom-print-action");
      else link.classList.add("is-kitchen-print-action");
    }
  });

  const originalParent = history.parentNode;
  const originalNext = history.nextSibling;
  const actionCard = document.querySelector("[data-order-detail-actions]");
  const summaryCards = main
    ? [...main.querySelectorAll(":scope > section.card.spaced-card")]
      .filter((card) => card !== actionCard && card !== history)
    : [];
  const summaryAnchor = summaryCards[0] ? document.createComment("order-summary-start") : null;
  const summaryActionGrid = document.createElement("div");
  summaryActionGrid.className = "order-summary-action-grid";
  if (summaryAnchor) originalParent.insertBefore(summaryAnchor, summaryCards[0]);
  history.classList.add("order-detail-history-card");
  const arrange = () => {
    if (responsiveView.matches) {
      summaryCards.forEach((card) => summaryActionGrid.append(card));
      if (actionCard) summaryActionGrid.append(actionCard);
      if (summaryCards.length || actionCard) originalParent.insertBefore(summaryActionGrid, history);
      grid.append(history);
    } else {
      if (summaryActionGrid.isConnected) {
        summaryCards.forEach((card) => grid.append(card));
        if (actionCard) originalParent.insertBefore(actionCard, summaryActionGrid);
        summaryActionGrid.remove();
      }
      summaryCards.forEach((card) => grid.append(card));
      grid.append(history);
    }
  };
  responsiveView.addEventListener?.("change", arrange);
  arrange();
})();

(() => {
  const printStatus = document.querySelector("[data-print-job-status]");
  if (!printStatus) return;
  const jobId = printStatus.dataset.jobId;
  (async () => {
    for (let attempt = 0; attempt < 15; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      try {
        const response = await fetch(`/app/impresion/estado/${jobId}/`, { credentials: "same-origin", cache: "no-store" });
        if (!response.ok) return;
        const job = await response.json();
        if (job.status === "printed") { printStatus.textContent = "Comanda enviada a la impresora de la Dell."; printStatus.classList.add("text-success"); return; }
        if (job.status === "failed") { printStatus.textContent = "La comanda no se pudo imprimir. Avisa al administrador antes de reintentar."; printStatus.classList.add("text-danger"); return; }
        if (job.status === "expired") { printStatus.textContent = "La impresora se desconectó antes de imprimir la comanda. Usa “Imprimir cocina modificado” para reintentar."; printStatus.classList.add("text-danger"); return; }
      } catch (_) { return; }
    }
  })();
})();
