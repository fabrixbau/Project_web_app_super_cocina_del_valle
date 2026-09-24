/* NOTA TEMPORAL PARA APRENDIZAJE: cada fila se autoguarda con debounce. La primera
fila se convierte en movimiento persistente y deja inmediatamente otra vacía debajo;
así Caja captura consecutivamente sin botones Guardar. Borra esta nota al leerla. */
(() => {
const terminalFilters = document.querySelector("[data-terminal-filters]");
const terminalTools = document.querySelector(".terminal-mobile-tools");
const terminalToolsToggle = terminalTools?.querySelector("[data-terminal-tools-toggle]");
terminalToolsToggle?.addEventListener("click", () => {
  const expanded = terminalToolsToggle.getAttribute("aria-expanded") === "true";
  terminalToolsToggle.setAttribute("aria-expanded", String(!expanded));
  terminalTools.classList.toggle("is-mobile-expanded", !expanded);
});
terminalFilters?.querySelectorAll("input, select").forEach((field) => field.addEventListener("change", () => terminalFilters.requestSubmit()));

const board = document.querySelector("[data-terminal-board]");
const feedback = document.querySelector("[data-terminal-feedback]");
const timers = new WeakMap();
const versions = new WeakMap();
const money = (value) => Number(value || 0).toFixed(2);
const numberFrom = (selector) => Number((document.querySelector(selector)?.textContent || "0").replace(/[^0-9.-]/g, ""));
const setNumber = (selector, value) => { const node = document.querySelector(selector); if (node) node.textContent = money(value); };

function rowData(row) {
  return {
    cut_id: board.dataset.cutId,
    movement_id: row.dataset.movementId || "",
    total_amount: row.querySelector("[name='total_amount']").value,
    tip_amount: row.querySelector("[name='tip_amount']").value || "0",
    tip_recipient: row.querySelector("[name='tip_recipient']").value,
    terminal_name_reference: row.querySelector("[name='terminal_name_reference']").value,
    linked_record: row.querySelector("[name='linked_record']").value,
  };
}

function updateConsumption(row) {
  const data = rowData(row); const total = Number(data.total_amount || 0); const tip = Number(data.tip_amount || 0);
  row.querySelector("[data-consumption]").textContent = `$${money(total - tip)}`;
}

function appendBlankFrom(row) {
  if (board.querySelector(".terminal-movement-row.is-new[data-movement-id='']")) return;
  const clone = row.cloneNode(true); clone.dataset.movementId = ""; clone.dataset.savedTotal = "0"; clone.dataset.savedTip = "0"; clone.classList.add("is-new");
  // NOTA TEMPORAL PARA APRENDIZAJE: cloneNode copia data-saving/data-pending-save tal
  // cual estén en la fila original en ese instante. Como este clonado ocurre dentro
  // del try de saveRow, la fila original todavía tiene data-saving="1"; sin este
  // reinicio, la tarjeta nueva nace "atorada" y su primer guardado nunca se ejecuta.
  // Borra esta nota después de leerla.
  delete clone.dataset.saving; delete clone.dataset.pendingSave;
  clone.querySelector("[name='total_amount']").value = ""; clone.querySelector("[name='tip_amount']").value = "0";
  clone.querySelector("[name='terminal_name_reference']").value = ""; clone.querySelector("[name='linked_record']").value = ""; clone.querySelector("[name='tip_recipient']").value = "";
  clone.querySelector("[data-link-trigger]").textContent = "Vincular";
  clone.querySelectorAll("[data-recipient-id]").forEach((button) => button.classList.remove("is-selected")); clone.querySelector("[data-consumption]").textContent = "$0.00";
  clone.querySelector("[data-delete-movement]").hidden = true; clone.querySelector("[data-row-save-state]").textContent = "Escribe el total para crear el movimiento."; board.append(clone);
}

async function saveRow(row) {
  const data = rowData(row); const total = Number(data.total_amount || 0); if (!total || total <= 0) return;
  if (row.dataset.saving === "1") { row.dataset.pendingSave = "1"; return; }
  row.dataset.saving = "1";
  const state = row.querySelector("[data-row-save-state]"); const version = (versions.get(row) || 0) + 1; versions.set(row, version); state.textContent = "Guardando…";
  const body = new FormData(); Object.entries(data).forEach(([key, value]) => body.append(key, value));
  body.append("csrfmiddlewaretoken", document.querySelector("input[name='csrfmiddlewaretoken']").value);
  try {
    const response = await fetch(board.dataset.saveUrl, {method: "POST", body, headers: {"X-Requested-With": "XMLHttpRequest", Accept: "application/json"}}); const result = await response.json();
    if (!response.ok || !result.ok) {
      if (result.code === "link_already_used") {
        row.querySelector("[name='linked_record']").value = "";
        row.querySelector("[data-link-trigger]").textContent = row.dataset.revertLinkLabel || "Vincular";
        if (row.dataset.revertTotal !== undefined) row.querySelector("[name='total_amount']").value = row.dataset.revertTotal;
        if (row.dataset.revertTip !== undefined) row.querySelector("[name='tip_amount']").value = row.dataset.revertTip;
        if (row.dataset.revertRecipient !== undefined) {
          const recipient = row.dataset.revertRecipient;
          row.querySelector("[name='tip_recipient']").value = recipient;
          row.querySelectorAll("[data-recipient-id]").forEach((button) => button.classList.toggle("is-selected", button.dataset.recipientId === recipient));
        }
        updateConsumption(row);
      }
      throw new Error(result.error || "No se pudo guardar el movimiento.");
    } if (versions.get(row) !== version) return;
    const wasNew = !row.dataset.movementId; const previousTotal = Number(row.dataset.savedTotal || 0); const previousTip = Number(row.dataset.savedTip || 0);
    row.dataset.movementId = result.movement.id; row.dataset.savedTotal = result.movement.total; row.dataset.savedTip = result.movement.tip; row.classList.remove("is-new"); row.querySelector("[data-delete-movement]").hidden = false; state.textContent = "Guardado";
    setNumber("[data-selected-total]", numberFrom("[data-selected-total]") - previousTotal + Number(result.movement.total)); setNumber("[data-selected-tip]", numberFrom("[data-selected-tip]") - previousTip + Number(result.movement.tip));
    if (wasNew) appendBlankFrom(row);
    scheduleSummaryRefresh();
    state.classList.remove("text-danger");
  } catch (error) { state.textContent = error.message; state.classList.add("text-danger"); }
  finally { row.dataset.saving = "0"; if (row.dataset.pendingSave === "1") { row.dataset.pendingSave = "0"; saveRow(row); } }
}

function scheduleSave(row, immediate = false) { window.clearTimeout(timers.get(row)); updateConsumption(row); const state = row.querySelector("[data-row-save-state]"); state.textContent = "Pendiente de guardar…"; state.classList.remove("text-danger"); timers.set(row, window.setTimeout(() => saveRow(row), immediate ? 0 : 450)); }

let summaryRefreshTimer = null;
// NOTA TEMPORAL PARA APRENDIZAJE: "Conciliación de propinas por persona" (y las
// tarjetas de Aplicación/Diferencia arriba) se calculan en el servidor a partir de
// TODOS los movimientos del corte, no sólo el que acaba de guardarse — reconstruir esa
// cuenta en JS duplicaría la lógica de negocio. En vez de eso, tras cada guardado o
// borrado exitoso se vuelve a pedir la misma página (con los mismos filtros activos) y
// se reemplaza esa sección con la versión fresca. El debounce evita pedir la página una
// vez por cada guardado si varias filas se guardan casi al mismo tiempo. Borra esta
// nota después de leerla.
async function refreshPersonSummary() {
  try {
    const response = await fetch(window.location.href, {credentials: "same-origin", headers: {"X-Requested-With": "XMLHttpRequest"}, cache: "no-store"});
    if (!response.ok) return;
    const doc = new DOMParser().parseFromString(await response.text(), "text/html");
    const freshSummary = doc.querySelector(".terminal-person-summary");
    const currentSummary = document.querySelector(".terminal-person-summary");
    if (freshSummary && currentSummary) currentSummary.replaceWith(freshSummary);
    const freshGrid = doc.querySelector(".terminal-reconciliation-grid");
    const currentGrid = document.querySelector(".terminal-reconciliation-grid");
    if (freshGrid && currentGrid) currentGrid.replaceWith(freshGrid);
  } catch (_) { /* deja la sección como estaba si falla la actualización en segundo plano */ }
}
function scheduleSummaryRefresh() { window.clearTimeout(summaryRefreshTimer); summaryRefreshTimer = window.setTimeout(refreshPersonSummary, 400); }

board?.addEventListener("input", (event) => { const row = event.target.closest("[data-movement-id]"); if (row) scheduleSave(row); });
board?.addEventListener("click", async (event) => {
  const recipientButton = event.target.closest("[data-recipient-id]");
  if (recipientButton) { const row = recipientButton.closest("[data-movement-id]"); const hidden = row.querySelector("[name='tip_recipient']"); const deselect = hidden.value === recipientButton.dataset.recipientId; hidden.value = deselect ? "" : recipientButton.dataset.recipientId; row.querySelectorAll("[data-recipient-id]").forEach((button) => button.classList.toggle("is-selected", !deselect && button === recipientButton)); scheduleSave(row, true); return; }
  const linkTrigger = event.target.closest("[data-link-trigger]");
  if (linkTrigger) { openLinkDialog(linkTrigger.closest("[data-movement-id]")); return; }
  const deleteButton = event.target.closest("[data-delete-movement]"); if (!deleteButton || deleteButton.hidden) return;
  const row = deleteButton.closest("[data-movement-id]"); deleteButton.disabled = true;
  try { const body = new FormData(); body.append("csrfmiddlewaretoken", document.querySelector("input[name='csrfmiddlewaretoken']").value); const url = board.dataset.deleteTemplate.replace("/0/", `/${row.dataset.movementId}/`); const response = await fetch(url, {method: "POST", body, headers: {"X-Requested-With": "XMLHttpRequest", Accept: "application/json"}}); const result = await response.json(); if (!response.ok || !result.ok) throw new Error(result.error || "No se pudo eliminar."); setNumber("[data-selected-total]", numberFrom("[data-selected-total]") - Number(row.dataset.savedTotal || 0)); setNumber("[data-selected-tip]", numberFrom("[data-selected-tip]") - Number(row.dataset.savedTip || 0)); row.remove(); scheduleSummaryRefresh(); } catch (error) { row.querySelector("[data-row-save-state]").textContent = error.message; deleteButton.disabled = false; }
});

document.querySelector("[data-cut-status-form]")?.addEventListener("submit", async (event) => { event.preventDefault(); const form = event.currentTarget; const button = form.querySelector("button"); button.disabled = true; try { const response = await fetch(form.action, {method: "POST", body: new FormData(form), headers: {"X-Requested-With": "XMLHttpRequest", Accept: "application/json"}}); const result = await response.json(); if (!response.ok || !result.ok) throw new Error(result.error || "No se pudo cambiar el corte."); window.location.reload(); } catch (error) { feedback.textContent = error.message; feedback.className = "message error"; feedback.hidden = false; button.disabled = false; } });

/* NOTA TEMPORAL PARA APRENDIZAJE: el diálogo de Vincular es uno solo, compartido por
todas las filas; se llena de nuevo cada vez que se abre leyendo en ese instante el
vínculo actual de las demás filas (para no ofrecer un pedido/mesa ya tomado) y
comparando Total/Propina/Propina-para de la fila contra los del candidato. Si la fila
está vacía o todo coincide, se vincula de una vez; si algo no coincide, se detiene y
pide Sobrescribir/Guardar como nuevo/Cancelar. Borra esta nota después de leerla. */
const linkDialog = document.querySelector("[data-link-dialog]");
const linkDialogList = linkDialog?.querySelector("[data-link-dialog-list]");
const linkDialogConflict = linkDialog?.querySelector("[data-link-dialog-conflict]");
const linkDialogDiff = linkDialog?.querySelector("[data-link-dialog-diff]");
const linkCandidatesData = JSON.parse(document.getElementById("terminal-link-candidates")?.textContent || "[]");
const tableGroupLabel = board?.dataset.tableGroupLabel || "Mesas";
let activeLinkRow = null;
let pendingCandidate = null;

function recipientLabel(id) {
  if (!id) return "Sin asignar";
  const button = board.querySelector(`[data-recipient-id="${CSS.escape(String(id))}"]`);
  return button ? button.textContent : "Sin asignar";
}

function rowHasTypedData(row) {
  const total = Number(row.querySelector("[name='total_amount']").value || 0);
  const tip = Number(row.querySelector("[name='tip_amount']").value || 0);
  const recipient = row.querySelector("[name='tip_recipient']").value || "";
  return total > 0 || tip > 0 || Boolean(recipient);
}

function fieldsMatch(row, candidate) {
  const total = Number(row.querySelector("[name='total_amount']").value || 0);
  const tip = Number(row.querySelector("[name='tip_amount']").value || 0);
  const recipient = row.querySelector("[name='tip_recipient']").value || "";
  return {
    total: total.toFixed(2) === Number(candidate.total).toFixed(2),
    tip: tip.toFixed(2) === Number(candidate.tip).toFixed(2),
    recipient: recipient === String(candidate.recipient_id || ""),
  };
}

function applyCandidateToRow(row, candidate) {
  // NOTA TEMPORAL PARA APRENDIZAJE: se guarda una foto de lo que había antes de aplicar
  // el candidato, para poder restaurar la fila completa (no sólo el vínculo) si el
  // guardado falla porque alguien más ya tomó ese pedido/mesa (link_already_used) —
  // antes sólo se limpiaba el vínculo y la fila quedaba "atorada" con el total/propina/
  // responsable del candidato fallido todavía puestos. Borra esta nota después de leerla.
  row.dataset.revertTotal = row.querySelector("[name='total_amount']").value;
  row.dataset.revertTip = row.querySelector("[name='tip_amount']").value;
  row.dataset.revertRecipient = row.querySelector("[name='tip_recipient']").value;
  row.dataset.revertLinkLabel = row.querySelector("[data-link-trigger]").textContent;
  row.querySelector("[name='linked_record']").value = candidate ? candidate.value : "";
  if (candidate) {
    row.querySelector("[name='total_amount']").value = Number(candidate.total).toFixed(2);
    row.querySelector("[name='tip_amount']").value = Number(candidate.tip).toFixed(2);
    const recipient = candidate.recipient_id ? String(candidate.recipient_id) : "";
    row.querySelector("[name='tip_recipient']").value = recipient;
    row.querySelectorAll("[data-recipient-id]").forEach((button) => button.classList.toggle("is-selected", button.dataset.recipientId === recipient));
    row.querySelector("[data-link-trigger]").textContent = candidate.label;
  } else {
    row.querySelector("[data-link-trigger]").textContent = "Vincular";
  }
  scheduleSave(row, true);
}

function renderCandidateList(row) {
  // NOTA TEMPORAL PARA APRENDIZAJE: un candidato puede estar tomado de dos formas
  // distintas. (1) `candidate.movement_id` viene del servidor y cubre cualquier
  // movimiento YA GUARDADO, sin importar si es de este mismo corte/proveedor o de
  // otro (p. ej. un pedido vinculado en Mercado Pago antes de cambiarle el método de
  // pago a Transferencia); antes esto se ignoraba por completo y sólo se miraban las
  // filas visibles EN ESTA MISMA pestaña, así que un vínculo de otra pestaña nunca se
  // detectaba aquí y el guardado fallaba una y otra vez con "ya se usó". (2)
  // `takenElsewhere` cubre el caso más reciente: otra fila de esta misma página que
  // acaba de aplicar un candidato de forma optimista pero cuyo guardado todavía no se
  // confirma, así que el `movement_id` embebido en la página (tomado en la carga) aún
  // no lo refleja. Se necesitan los dos. Borra esta nota después de leerla.
  const currentMovementId = row.dataset.movementId ? Number(row.dataset.movementId) : null;
  const takenElsewhere = new Set();
  board.querySelectorAll("[data-movement-id]").forEach((otherRow) => {
    if (otherRow === row) return;
    const value = otherRow.querySelector("[name='linked_record']").value;
    if (value) takenElsewhere.add(value);
  });
  const available = linkCandidatesData.filter((candidate) => {
    if (candidate.movement_id && candidate.movement_id !== currentMovementId) return false;
    return !takenElsewhere.has(candidate.value);
  });
  linkDialogList.innerHTML = "";
  const unlinkButton = document.createElement("button");
  unlinkButton.type = "button"; unlinkButton.className = "terminal-link-candidate"; unlinkButton.textContent = "Sin vincular";
  unlinkButton.addEventListener("click", () => { applyCandidateToRow(row, null); closeLinkDialog(); });
  linkDialogList.append(unlinkButton);
  const groups = [["order", "Entregas a domicilio"], ["table", tableGroupLabel]];
  let anyCandidate = false;
  groups.forEach(([kind, label]) => {
    const items = available.filter((candidate) => candidate.kind === kind);
    if (!items.length) return;
    anyCandidate = true;
    const heading = document.createElement("p");
    heading.className = "terminal-link-candidate-group"; heading.textContent = label;
    linkDialogList.append(heading);
    items.forEach((candidate) => {
      const match = fieldsMatch(row, candidate);
      const isMatch = match.total && match.tip && match.recipient;
      const button = document.createElement("button");
      button.type = "button";
      button.className = `terminal-link-candidate ${isMatch ? "is-match" : "is-mismatch"}`;
      button.innerHTML = `<strong>${candidate.label}</strong><small>${isMatch ? "✓ Coincide" : "⚠ No coincide"} · $${Number(candidate.total).toFixed(2)} · propina $${Number(candidate.tip).toFixed(2)} · ${recipientLabel(candidate.recipient_id)}</small>`;
      button.addEventListener("click", () => handleCandidateClick(row, candidate));
      linkDialogList.append(button);
    });
  });
  if (!anyCandidate) {
    const empty = document.createElement("p");
    empty.className = "terminal-link-candidate-empty"; empty.textContent = "No hay pedidos ni mesas disponibles para vincular.";
    linkDialogList.append(empty);
  }
}

function handleCandidateClick(row, candidate) {
  if (!rowHasTypedData(row)) { applyCandidateToRow(row, candidate); closeLinkDialog(); return; }
  const match = fieldsMatch(row, candidate);
  if (match.total && match.tip && match.recipient) { applyCandidateToRow(row, candidate); closeLinkDialog(); return; }
  showConflict(row, candidate, match);
}

function showConflict(row, candidate, match) {
  pendingCandidate = candidate;
  linkDialogList.hidden = true;
  linkDialogConflict.hidden = false;
  const rows = [];
  if (!match.total) rows.push(["Total cobrado", `$${Number(row.querySelector("[name='total_amount']").value || 0).toFixed(2)}`, `$${Number(candidate.total).toFixed(2)}`]);
  if (!match.tip) rows.push(["Propina", `$${Number(row.querySelector("[name='tip_amount']").value || 0).toFixed(2)}`, `$${Number(candidate.tip).toFixed(2)}`]);
  if (!match.recipient) rows.push(["Propina para", recipientLabel(row.querySelector("[name='tip_recipient']").value), recipientLabel(candidate.recipient_id)]);
  linkDialogDiff.innerHTML = "<tr><th>Campo</th><th>Ya escrito</th><th>Del pedido/mesa</th></tr>"
    + rows.map(([field, before, after]) => `<tr><td>${field}</td><td>${before}</td><td>${after}</td></tr>`).join("");
}

function openLinkDialog(row) {
  if (!linkDialog || row.querySelector("[data-link-trigger]").disabled) return;
  activeLinkRow = row; pendingCandidate = null;
  linkDialogList.hidden = false; linkDialogConflict.hidden = true;
  renderCandidateList(row);
  linkDialog.showModal();
}

function closeLinkDialog() { linkDialog?.close(); activeLinkRow = null; pendingCandidate = null; }

linkDialog?.querySelector("[data-link-dialog-close]")?.addEventListener("click", closeLinkDialog);
linkDialog?.querySelector("[data-link-conflict-cancel]")?.addEventListener("click", closeLinkDialog);
linkDialog?.querySelector("[data-link-conflict-overwrite]")?.addEventListener("click", () => {
  if (activeLinkRow && pendingCandidate) applyCandidateToRow(activeLinkRow, pendingCandidate);
  closeLinkDialog();
});
linkDialog?.querySelector("[data-link-conflict-new]")?.addEventListener("click", () => {
  const blankRow = board.querySelector(".terminal-movement-row.is-new[data-movement-id='']");
  if (blankRow && pendingCandidate) applyCandidateToRow(blankRow, pendingCandidate);
  closeLinkDialog();
});
})();
