/* NOTA TEMPORAL PARA APRENDIZAJE:
Las listas reordenan sus nodos reales; por eso la previsualización y los inputs enviados
siempre coinciden. Mouse usa drag/drop y el asa también acepta Pointer Events para tablet.
Las flechas son una alternativa accesible. Borra esta nota después de probarlo. */

const sortableLists = document.querySelectorAll("[data-sortable-list]");
let draggedItem = null;
let pointerItem = null;

function refreshPositions(list) {
  list.querySelectorAll(".category-order-item").forEach((item, index) => {
    item.querySelector(".order-position").textContent = index + 1;
  });
}

function itemAfterPointer(list, clientY) {
  const items = [...list.querySelectorAll(".category-order-item:not(.is-dragging)")];
  return items.reduce((closest, item) => {
    const box = item.getBoundingClientRect();
    const offset = clientY - box.top - box.height / 2;
    return offset < 0 && offset > closest.offset ? {offset, item} : closest;
  }, {offset: Number.NEGATIVE_INFINITY, item: null}).item;
}

sortableLists.forEach((list) => {
  refreshPositions(list);
  list.addEventListener("dragstart", (event) => {
    const item = event.target.closest(".category-order-item");
    if (!item) return;
    draggedItem = item;
    item.classList.add("is-dragging");
    event.dataTransfer.effectAllowed = "move";
  });
  list.addEventListener("dragover", (event) => {
    if (!draggedItem || draggedItem.parentElement !== list) return;
    event.preventDefault();
    const nextItem = itemAfterPointer(list, event.clientY);
    list.insertBefore(draggedItem, nextItem);
  });
  list.addEventListener("dragend", () => {
    if (!draggedItem) return;
    const parent = draggedItem.parentElement;
    draggedItem.classList.remove("is-dragging");
    draggedItem = null;
    refreshPositions(parent);
  });
  list.addEventListener("click", (event) => {
    const button = event.target.closest("[data-move-up], [data-move-down]");
    if (!button) return;
    const item = button.closest(".category-order-item");
    if (button.hasAttribute("data-move-up") && item.previousElementSibling) {
      list.insertBefore(item, item.previousElementSibling);
    } else if (button.hasAttribute("data-move-down") && item.nextElementSibling) {
      list.insertBefore(item.nextElementSibling, item);
    }
    refreshPositions(list);
  });
});

document.querySelectorAll("[data-drag-handle]").forEach((handle) => {
  handle.addEventListener("pointerdown", (event) => {
    if (event.pointerType === "mouse") return;
    pointerItem = handle.closest(".category-order-item");
    pointerItem.classList.add("is-dragging");
    handle.setPointerCapture(event.pointerId);
    event.preventDefault();
  });
  handle.addEventListener("pointermove", (event) => {
    if (!pointerItem || !handle.hasPointerCapture(event.pointerId)) return;
    const list = pointerItem.parentElement;
    const nextItem = itemAfterPointer(list, event.clientY);
    list.insertBefore(pointerItem, nextItem);
    event.preventDefault();
  });
  const finishPointerSort = (event) => {
    if (!pointerItem) return;
    const list = pointerItem.parentElement;
    pointerItem.classList.remove("is-dragging");
    pointerItem = null;
    if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
    refreshPositions(list);
  };
  handle.addEventListener("pointerup", finishPointerSort);
  handle.addEventListener("pointercancel", finishPointerSort);
});

document.querySelectorAll("[data-visibility-toggle]").forEach((checkbox) => {
  checkbox.addEventListener("change", () => {
    const item = checkbox.closest(".category-order-item");
    item.classList.toggle("is-hidden-category", !checkbox.checked);
    item.querySelector("[data-visibility-status]").textContent = checkbox.checked
      ? "Visible para clientes"
      : "Oculta para clientes";
  });
});
