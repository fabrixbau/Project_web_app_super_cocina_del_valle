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
  clone.querySelectorAll(".app-select").forEach((wrapper) => {
    const select = wrapper.querySelector(":scope > select");
    if (!select) return;
    select.classList.remove("app-select-native");
    wrapper.replaceWith(select);
  });
  clone.querySelector("[name='total_amount']").value = ""; clone.querySelector("[name='tip_amount']").value = "0";
  clone.querySelector("[name='terminal_name_reference']").value = ""; clone.querySelector("[name='linked_record']").value = ""; clone.querySelector("[name='tip_recipient']").value = "";
  clone.querySelectorAll("[data-recipient-id]").forEach((button) => button.classList.remove("is-selected")); clone.querySelector("[data-consumption]").textContent = "$0.00";
  clone.querySelector("[data-delete-movement]").hidden = true; clone.querySelector("[data-row-save-state]").textContent = "Escribe el total para crear el movimiento."; board.append(clone);
  refreshLinkedOptions();
}

function refreshLinkedOptions() {
  const selected = new Map();
  board?.querySelectorAll("[data-movement-id]").forEach((row) => { const value = row.querySelector("[name='linked_record']")?.value; if (value) selected.set(value, row); });
  board?.querySelectorAll("[data-movement-id]").forEach((row) => row.querySelectorAll("[name='linked_record'] option[value]").forEach((option) => {
    if (!option.value) return; const owner = selected.get(option.value); if (owner && owner !== row) option.remove();
  }));
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
        const select = row.querySelector("[name='linked_record']");
        select?.selectedOptions[0]?.remove();
        if (select) select.value = "";
      }
      throw new Error(result.error || "No se pudo guardar el movimiento.");
    } if (versions.get(row) !== version) return;
    const wasNew = !row.dataset.movementId; const previousTotal = Number(row.dataset.savedTotal || 0); const previousTip = Number(row.dataset.savedTip || 0);
    row.dataset.movementId = result.movement.id; row.dataset.savedTotal = result.movement.total; row.dataset.savedTip = result.movement.tip; row.classList.remove("is-new"); row.querySelector("[data-delete-movement]").hidden = false; state.textContent = "Guardado";
    setNumber("[data-selected-total]", numberFrom("[data-selected-total]") - previousTotal + Number(result.movement.total)); setNumber("[data-selected-tip]", numberFrom("[data-selected-tip]") - previousTip + Number(result.movement.tip));
    if (wasNew) appendBlankFrom(row);
    refreshLinkedOptions();
    state.classList.remove("text-danger");
  } catch (error) { state.textContent = error.message; state.classList.add("text-danger"); }
  finally { row.dataset.saving = "0"; if (row.dataset.pendingSave === "1") { row.dataset.pendingSave = "0"; saveRow(row); } }
}

function scheduleSave(row, immediate = false) { window.clearTimeout(timers.get(row)); updateConsumption(row); const state = row.querySelector("[data-row-save-state]"); state.textContent = "Pendiente de guardar…"; state.classList.remove("text-danger"); timers.set(row, window.setTimeout(() => saveRow(row), immediate ? 0 : 450)); }

board?.addEventListener("input", (event) => { const row = event.target.closest("[data-movement-id]"); if (row) scheduleSave(row); });
board?.addEventListener("change", (event) => { const row = event.target.closest("[data-movement-id]"); if (!row) return; if (event.target.matches("[name='linked_record']")) { if (event.target.value) { const option = event.target.selectedOptions[0]; row.querySelector("[name='total_amount']").value = option.dataset.linkTotal || ""; row.querySelector("[name='tip_amount']").value = option.dataset.linkTip || "0"; const recipient = option.dataset.linkRecipient || ""; row.querySelector("[name='tip_recipient']").value = recipient; row.querySelectorAll("[data-recipient-id]").forEach((button) => button.classList.toggle("is-selected", button.dataset.recipientId === recipient)); } } scheduleSave(row, true); });
board?.addEventListener("click", async (event) => {
  const recipientButton = event.target.closest("[data-recipient-id]");
  if (recipientButton) { const row = recipientButton.closest("[data-movement-id]"); const hidden = row.querySelector("[name='tip_recipient']"); const deselect = hidden.value === recipientButton.dataset.recipientId; hidden.value = deselect ? "" : recipientButton.dataset.recipientId; row.querySelectorAll("[data-recipient-id]").forEach((button) => button.classList.toggle("is-selected", !deselect && button === recipientButton)); scheduleSave(row, true); return; }
  const deleteButton = event.target.closest("[data-delete-movement]"); if (!deleteButton || deleteButton.hidden) return;
  const row = deleteButton.closest("[data-movement-id]"); deleteButton.disabled = true;
  try { const body = new FormData(); body.append("csrfmiddlewaretoken", document.querySelector("input[name='csrfmiddlewaretoken']").value); const url = board.dataset.deleteTemplate.replace("/0/", `/${row.dataset.movementId}/`); const response = await fetch(url, {method: "POST", body, headers: {"X-Requested-With": "XMLHttpRequest", Accept: "application/json"}}); const result = await response.json(); if (!response.ok || !result.ok) throw new Error(result.error || "No se pudo eliminar."); setNumber("[data-selected-total]", numberFrom("[data-selected-total]") - Number(row.dataset.savedTotal || 0)); setNumber("[data-selected-tip]", numberFrom("[data-selected-tip]") - Number(row.dataset.savedTip || 0)); row.remove(); refreshLinkedOptions(); } catch (error) { row.querySelector("[data-row-save-state]").textContent = error.message; deleteButton.disabled = false; }
});

document.querySelector("[data-cut-status-form]")?.addEventListener("submit", async (event) => { event.preventDefault(); const form = event.currentTarget; const button = form.querySelector("button"); button.disabled = true; try { const response = await fetch(form.action, {method: "POST", body: new FormData(form), headers: {"X-Requested-With": "XMLHttpRequest", Accept: "application/json"}}); const result = await response.json(); if (!response.ok || !result.ok) throw new Error(result.error || "No se pudo cambiar el corte."); window.location.reload(); } catch (error) { feedback.textContent = error.message; feedback.className = "message error"; feedback.hidden = false; button.disabled = false; } });
refreshLinkedOptions();
})();
