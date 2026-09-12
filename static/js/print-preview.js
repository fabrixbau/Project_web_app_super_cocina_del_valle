const printTicketButton = document.querySelector("[data-print-ticket]");

printTicketButton?.addEventListener("click", () => window.print());

window.addEventListener("afterprint", () => {
  if (window.opener) {
    window.close();
    return;
  }

  window.history.back();
}, { once: true });
