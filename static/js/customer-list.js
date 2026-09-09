// NOTA TEMPORAL PARA APRENDIZAJE: eliminar una ficha también elimina sus domicilios,
// por eso pedimos una confirmación explícita. El servidor vuelve a validar permisos y
// adeudos aunque se omita este JavaScript. Borra esta nota después de leerla.
document.addEventListener("submit", (event) => {
  const form = event.target.closest("[data-customer-delete]");
  if (!form) return;
  const customerName = form.dataset.customerName || "este cliente";
  if (!window.confirm(`¿Eliminar a ${customerName} y sus domicilios de la agenda? Esta acción no se puede deshacer.`)) {
    event.preventDefault();
  }
});
