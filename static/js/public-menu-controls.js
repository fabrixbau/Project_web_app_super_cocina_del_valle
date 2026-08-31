/* NOTA TEMPORAL PARA APRENDIZAJE:
Este archivo actualiza el carrito sin abandonar el menú. El contador de la tarjeta representa
solo la receta estándar; el selector sigue enviando las personalizaciones como partidas distintas.
Borra esta nota cuando termines de revisar el flujo. */

(() => {
  const stateNode = document.querySelector("#public-cart-controls");
  if (!stateNode) return;
  const csrfToken = document.querySelector("input[name='csrfmiddlewaretoken']")?.value;
  const cartLinkCount = document.querySelector("[data-public-cart-count]");
  let queue = Promise.resolve();

  function render(cart) {
    document.querySelectorAll("[data-public-product]").forEach((card) => {
      const quantity = cart.standard_quantities[String(card.dataset.publicProduct)] || 0;
      card.querySelector("[data-standard-quantity]").textContent = quantity;
      card.querySelector("[data-public-decrease]").disabled = quantity === 0;
    });
    if (cartLinkCount) cartLinkCount.textContent = cart.count;
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
