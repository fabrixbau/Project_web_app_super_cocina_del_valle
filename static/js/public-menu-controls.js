/* NOTA TEMPORAL PARA APRENDIZAJE:
Este archivo actualiza el carrito sin abandonar el menú. El contador de la tarjeta representa
solo la receta estándar; el selector sigue enviando las personalizaciones como partidas distintas.
Borra esta nota cuando termines de revisar el flujo. */

(() => {
  const stateNode = document.querySelector("#public-cart-controls");
  if (!stateNode) return;
  const csrfToken = document.querySelector("input[name='csrfmiddlewaretoken']")?.value;
  const cartLinkCount = document.querySelector("[data-public-cart-count]");
  const ticket = document.querySelector("[data-public-ticket]");
  const ticketItems = document.querySelector("[data-public-ticket-items]");
  const ticketCount = document.querySelector("[data-public-ticket-count]");
  const ticketTotal = document.querySelector("[data-public-ticket-total]");
  const ticketNote = document.querySelector("[data-public-ticket-note]");
  let queue = Promise.resolve();

  function render(cart) {
    if (ticket) ticket.hidden = cart.count === 0;
    document.querySelectorAll("[data-public-product]").forEach((card) => {
      const quantity = cart.standard_quantities[String(card.dataset.publicProduct)] || 0;
      card.querySelector("[data-standard-quantity]").textContent = quantity;
      card.querySelector("[data-public-decrease]").disabled = quantity === 0;
    });
    if (cartLinkCount) cartLinkCount.textContent = cart.count;
    if (ticketCount) ticketCount.textContent = cart.count;
    if (ticketTotal) ticketTotal.textContent = `$${cart.total_display}`;
    if (ticketNote) {
      ticketNote.textContent = cart.note || "";
      ticketNote.hidden = !cart.note;
    }
    if (ticketItems) {
      ticketItems.replaceChildren();
      if (!cart.items.length) {
        const empty = document.createElement("p");
        empty.textContent = "Agrega el primer producto.";
        ticketItems.append(empty);
      }
      cart.items.forEach((item) => {
        const row = document.createElement("article");
        row.className = "table-ticket-item public-ticket-item";
        const copy = document.createElement("span");
        const name = document.createElement("strong");
        name.textContent = `${item.quantity} × ${item.name}`;
        copy.append(name);
        if (item.detail) { const detail = document.createElement("small"); detail.textContent = item.detail; copy.append(detail); }
        const price = document.createElement("strong"); price.textContent = `$${item.subtotal}`;
        const controls = document.createElement("div"); controls.className = "quantity-buttons";
        [["−", "decrease"], ["+", "increase"], ["×", "remove"]].forEach(([label, action]) => {
          const button = document.createElement("button"); button.type = "button"; button.textContent = label;
          button.dataset.publicTicketAction = action; button.dataset.updateUrl = item.update_url;
          button.dataset.removeUrl = item.remove_url; button.dataset.quantity = item.quantity;
          if (action === "remove") button.className = "danger";
          controls.append(button);
        });
        if (item.customizable) {
          const editForm = document.createElement("form");
          editForm.method = "post"; editForm.action = item.customize_url;
          editForm.dataset.publicCustomAdd = ""; editForm.dataset.customizableProduct = item.product_id;
          const editButton = document.createElement("button"); editButton.type = "submit";
          editButton.className = "ticket-edit-extras"; editButton.textContent = "Editar complementos";
          editForm.append(editButton); controls.append(editForm);
        }
        const noteButton = document.createElement("button"); noteButton.type = "button";
        noteButton.className = "ticket-item-note"; noteButton.textContent = "Nota";
        noteButton.dataset.publicItemNote = ""; noteButton.dataset.noteUrl = item.note_url;
        controls.append(noteButton);
        row.append(copy, price, controls); ticketItems.append(row);
      });
    }
  }

  function showError(message) {
    document.querySelector("[data-public-menu-error]")?.remove();
    const error = document.createElement("p");
    error.className = "message error";
    error.dataset.publicMenuError = "";
    error.textContent = message;
    document.querySelector("main").prepend(error);
  }

  function send(url, body, source) {
    queue = queue.then(async () => {
      source.disabled = true;
      try {
        const response = await fetch(url, {
          method: "POST", body,
          headers: {"X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrfToken},
        });
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || "No fue posible actualizar el carrito.");
        render(data.cart);
      } catch (error) {
        showError(error.message);
      } finally {
        if (source.isConnected) source.disabled = false;
      }
    });
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-public-decrease]");
    if (!button) return;
    event.preventDefault();
    send(button.dataset.url, new URLSearchParams(), button);
  });

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-public-item-note]");
    if (!button) return;
    const note = window.prompt("Nota para este producto (déjalo vacío para quitarla):", "");
    if (note === null) return;
    send(button.dataset.noteUrl, new URLSearchParams({note}), button);
  });

  document.addEventListener("click", (event) => {
    const image = event.target.closest("[data-public-image-add]");
    if (!image) return;
    image.closest("[data-public-product]")?.querySelector("form[data-public-standard-add] button")?.click();
  });

  document.addEventListener("keydown", (event) => {
    if ((event.key === "Enter" || event.key === " ") && event.target.matches("[data-public-image-add]")) {
      event.preventDefault(); event.target.click();
    }
  });

  document.addEventListener("click", (event) => {
    const tab = event.target.closest("[data-public-category]");
    if (!tab) return;
    const nav = tab.closest("[data-public-tabs]");
    nav.querySelectorAll("[data-public-category]").forEach((button) => button.classList.toggle("is-selected", button === tab));
    const area = nav.closest(".public-category-area");
    area.querySelectorAll("[data-public-panel]").forEach((panel) => { panel.hidden = panel.dataset.publicPanel !== tab.dataset.publicCategory; });
  });

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-public-ticket-action]");
    if (!button) return;
    const action = button.dataset.publicTicketAction;
    const quantity = Number(button.dataset.quantity);
    if (action === "remove" || (action === "decrease" && quantity === 1)) send(button.dataset.removeUrl, new URLSearchParams(), button);
    else send(button.dataset.updateUrl, new URLSearchParams({quantity: String(quantity + (action === "increase" ? 1 : -1))}), button);
  });

  const noteDialog = document.querySelector("[data-public-note-dialog]");
  document.querySelector("[data-public-note-open]")?.addEventListener("click", () => {
    noteDialog.querySelector("textarea").value = ticketNote?.textContent || ""; noteDialog.showModal();
  });
  document.querySelector("[data-public-note-close]")?.addEventListener("click", () => noteDialog.close());
  document.querySelector("[data-public-note-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const response = await fetch(event.currentTarget.action, {method: "POST", body: new FormData(event.currentTarget), headers: {"X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrfToken}});
    const data = await response.json(); if (response.ok && data.ok) { render(data.cart); noteDialog.close(); } else showError(data.error || "No fue posible guardar la nota.");
  });

  document.addEventListener("submit", (event) => {
    const form = event.target.closest("form[data-public-standard-add], form[data-public-custom-add]");
    if (!form) return;
    event.preventDefault();
    const button = form.querySelector("button[type='submit']");
    send(form.action, new FormData(form), button);
    form.querySelectorAll("input[data-generated-option]").forEach((input) => input.remove());
    delete form.dataset.selectionReady;
  });

  render(JSON.parse(stateNode.textContent || "{}"));
})();
