/* NOTA TEMPORAL PARA APRENDIZAJE: los filtros se envían al cambiar para mantener el
reporte rápido. El cálculo permanece en Django y no depende del navegador.
Borra esta nota después de leerla. */
const tipReportFilters = document.querySelector("[data-tip-report-filters]");
tipReportFilters?.querySelectorAll("input, select").forEach((field) => field.addEventListener("change", () => tipReportFilters.requestSubmit()));

const detailDialog = document.querySelector("[data-tip-detail-dialog]");
const closeDetail = () => detailDialog?.close();
const addDetailText = (parent, label, value) => {
  const paragraph = document.createElement("p");
  const strong = document.createElement("strong"); strong.textContent = `${label}: `;
  paragraph.append(strong, document.createTextNode(value || "—")); parent.append(paragraph);
};
const renderTipDetail = (detail) => {
  detailDialog.querySelector("[data-detail-kind]").textContent = detail.kind;
  detailDialog.querySelector("[data-detail-reference]").textContent = detail.reference;
  const body = detailDialog.querySelector("[data-tip-detail-body]"); body.replaceChildren();
  const summary = document.createElement("section"); summary.className = "tip-detail-summary";
  addDetailText(summary, "Cliente", detail.customer); addDetailText(summary, detail.responsible_label, detail.responsible);
  addDetailText(summary, "Fecha", detail.date); addDetailText(summary, "Domicilio", detail.address);
  addDetailText(summary, "Pago", detail.payment); addDetailText(summary, "Consumo", `$${detail.consumption}`);
  addDetailText(summary, "Propina", `$${detail.tip}`); addDetailText(summary, "Total", `$${detail.total}`);
  body.append(summary);
  if (detail.notes) { const note = document.createElement("div"); note.className = "tip-detail-note"; addDetailText(note, "Nota general", detail.notes); body.append(note); }
  const title = document.createElement("h3"); title.textContent = "Productos"; body.append(title);
  const items = document.createElement("div"); items.className = "tip-detail-items";
  detail.items.forEach((item) => {
    const row = document.createElement("article");
    const name = document.createElement("strong"); name.textContent = `${item.quantity} × ${item.name}`;
    const price = document.createElement("span"); price.textContent = `$${item.subtotal}`; row.append(name, price);
    if (item.description) { const description = document.createElement("small"); description.textContent = item.description; row.append(description); }
    if (item.comment) { const comment = document.createElement("small"); comment.className = "modified"; comment.textContent = `Nota: ${item.comment}`; row.append(comment); }
    items.append(row);
  });
  if (!detail.items.length) items.textContent = "Este ticket no tiene productos.";
  body.append(items);
};
const openTipDetail = async (row) => {
  detailDialog.querySelector("[data-tip-detail-body]").innerHTML = "<p>Consultando ticket…</p>";
  detailDialog.showModal();
  try {
    const response = await fetch(row.dataset.tipDetailUrl, {headers: {Accept: "application/json"}});
    const data = await response.json(); if (!response.ok || !data.ok) throw new Error(data.error || "No se pudo abrir el ticket.");
    renderTipDetail(data.detail);
  } catch (error) { detailDialog.querySelector("[data-tip-detail-body]").textContent = error.message; }
};
document.addEventListener("click", (event) => { const row = event.target.closest("[data-tip-detail-url]"); if (row) openTipDetail(row); });
document.addEventListener("keydown", (event) => { const row = event.target.closest?.("[data-tip-detail-url]"); if (row && ["Enter", " "].includes(event.key)) { event.preventDefault(); openTipDetail(row); } });
detailDialog?.querySelector("[data-tip-detail-close]")?.addEventListener("click", closeDetail);
detailDialog?.addEventListener("click", (event) => { if (event.target === detailDialog) closeDetail(); });
