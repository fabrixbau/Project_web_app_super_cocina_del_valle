(() => {
  const form = document.querySelector("[data-product-editor]");
  if (!form) return;

  const price = form.querySelector("[name='price']");
  const order = form.querySelector("[name='sort_order']");
  price?.setAttribute("inputmode", "decimal");
  order?.setAttribute("inputmode", "numeric");

  if (form.hasAttribute("data-product-create")) {
    const category = form.querySelector("[name='category']");
    const dataNode = document.querySelector("#category-next-product-orders");
    const nextOrders = dataNode ? JSON.parse(dataNode.textContent) : {};
    const applyNextOrder = () => {
      if (category.value && Object.hasOwn(nextOrders, category.value)) {
        order.value = nextOrders[category.value];
      }
    };
    category?.addEventListener("change", applyNextOrder);
    if (category?.value && !form.querySelector(".capture-error-summary")) applyNextOrder();
  }

  const imageControl = form.querySelector("[data-product-image-control]");
  const imageInput = imageControl?.querySelector("input[type='file']");
  const placeholder = imageControl?.querySelector("[data-product-image-placeholder]");
  const framing = imageControl?.querySelector("[data-product-image-framing]");
  const cropWindow = imageControl?.querySelector("[data-product-image-crop-window]");
  const zoomControl = imageControl?.querySelector("[data-product-image-zoom]");
  const resetButton = imageControl?.querySelector("[data-product-image-reset]");
  const positionX = form.querySelector("[name='image_position_x']");
  const positionY = form.querySelector("[name='image_position_y']");
  const zoomValue = form.querySelector("[name='image_zoom']");
  let cropImage;
  let objectUrl;

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const renderFraming = () => {
    if (!cropImage) return;
    const x = Number(positionX?.value || 50);
    const y = Number(positionY?.value || 50);
    const zoom = Number(zoomValue?.value || 1);
    cropImage.style.objectPosition = `${x}% ${y}%`;
    cropImage.style.transformOrigin = `${x}% ${y}%`;
    cropImage.style.transform = `scale(${zoom})`;
    if (zoomControl) zoomControl.value = zoom;
  };
  const openFraming = (src) => {
    if (!framing || !cropWindow || !src) return;
    cropImage = cropWindow.querySelector("img") || document.createElement("img");
    cropImage.src = src;
    cropImage.alt = "Vista previa del encuadre del producto";
    cropImage.draggable = false;
    cropWindow.replaceChildren(cropImage);
    framing.hidden = false;
    renderFraming();
  };

  const currentPreview = imageControl?.querySelector("[data-product-image-preview]");
  if (currentPreview?.src) openFraming(currentPreview.src);
  imageInput?.addEventListener("change", () => {
    const file = imageInput.files?.[0];
    if (!file) return;
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = URL.createObjectURL(file);
    let preview = imageControl.querySelector("[data-product-image-preview]");
    if (!preview) {
      preview = document.createElement("img");
      preview.dataset.productImagePreview = "";
      placeholder?.replaceChildren(preview);
    }
    preview.src = objectUrl;
    preview.alt = "Vista previa de la imagen seleccionada";
    imageControl.classList.add("has-new-image");
    openFraming(objectUrl);
  });

  zoomControl?.addEventListener("input", () => {
    zoomValue.value = zoomControl.value;
    renderFraming();
  });
  resetButton?.addEventListener("click", () => {
    positionX.value = 50;
    positionY.value = 50;
    zoomValue.value = 1;
    renderFraming();
  });

  let dragStart;
  cropWindow?.addEventListener("pointerdown", (event) => {
    if (!cropImage) return;
    dragStart = { pointerX: event.clientX, pointerY: event.clientY, x: Number(positionX.value || 50), y: Number(positionY.value || 50) };
    cropWindow.setPointerCapture(event.pointerId);
    cropWindow.classList.add("is-dragging");
  });
  cropWindow?.addEventListener("pointermove", (event) => {
    if (!dragStart) return;
    const bounds = cropWindow.getBoundingClientRect();
    positionX.value = Math.round(clamp(dragStart.x - ((event.clientX - dragStart.pointerX) / bounds.width) * 100, 0, 100));
    positionY.value = Math.round(clamp(dragStart.y - ((event.clientY - dragStart.pointerY) / bounds.height) * 100, 0, 100));
    renderFraming();
  });
  const finishDrag = () => { dragStart = null; cropWindow?.classList.remove("is-dragging"); };
  cropWindow?.addEventListener("pointerup", finishDrag);
  cropWindow?.addEventListener("pointercancel", finishDrag);
  zoomControl?.addEventListener("input", () => {
    if (zoomValue) zoomValue.value = Number(zoomControl.value).toFixed(2);
    renderFraming();
  });
  resetButton?.addEventListener("click", () => {
    if (positionX) positionX.value = 50;
    if (positionY) positionY.value = 50;
    if (zoomValue) zoomValue.value = "1.00";
    renderFraming();
  });
})();
