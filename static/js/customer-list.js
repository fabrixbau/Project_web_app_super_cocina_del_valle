// NOTA TEMPORAL PARA APRENDIZAJE: eliminar una ficha también elimina sus domicilios,
// por eso pedimos una confirmación explícita. El servidor vuelve a validar permisos y
// adeudos aunque se omita este JavaScript. Borra esta nota después de leerla.
document.addEventListener("submit", (event) => {
  const form = event.target.closest("[data-customer-delete]");
  if (!form) return;
  if (form.hasAttribute("data-has-debts")) {
    event.preventDefault();
    const message = form.querySelector(".customer-delete-message");
    if (message) {
      message.hidden = false;
      window.clearTimeout(Number(message.dataset.hideTimer || 0));
      message.dataset.hideTimer = String(window.setTimeout(() => {
        message.hidden = true;
      }, 3500));
    }
    return;
  }
  const customerName = form.dataset.customerName || "este cliente";
  if (!window.confirm(`¿Eliminar a ${customerName} y sus domicilios de la agenda? Esta acción no se puede deshacer.`)) {
    event.preventDefault();
  }
});
