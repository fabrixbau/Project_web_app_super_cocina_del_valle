const printTicketButton = document.querySelector("[data-print-ticket]");

printTicketButton?.addEventListener("click", () => window.print());

window.addEventListener("afterprint", () => {
  if (window.frameElement) {
    window.frameElement.remove();
    return;
  }
  if (window.opener) {
    window.close();
    return;
  }

  window.history.back();
}, { once: true });
