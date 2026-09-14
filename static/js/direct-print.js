(() => {
  let sending = false;

  function notice(message, error = false) {
    let element = document.getElementById("print-station-notice");
    if (!element) {
      element = document.createElement("div");
      element.id = "print-station-notice";
      element.setAttribute("role", "status");
      element.style.cssText = "position:fixed;right:1rem;bottom:1rem;z-index:9999;max-width:24rem;padding:.8rem 1rem;border-radius:.7rem;color:#fff;box-shadow:0 6px 22px #0005;font:600 1rem/1.4 Arial,sans-serif";
      document.body.append(element);
    }
    element.style.background = error ? "#a52b27" : "#20533f";
    element.textContent = message;
    clearTimeout(element.dismissTimer);
    element.dismissTimer = setTimeout(() => element.remove(), 6500);
  }

  async function watchJob(jobId, label) {
    for (let attempt = 0; attempt < 15; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      try {
        const response = await fetch(`/app/impresion/estado/${jobId}/`, { credentials: "same-origin", cache: "no-store" });
        if (!response.ok) return;
        const job = await response.json();
        if (job.status === "printed") {
          notice(`${label}: enviado a la impresora de la Dell.`);
          return;
        }
        if (job.status === "failed") {
          notice(`${label}: la Dell reportó un error. Avisa al administrador antes de reintentar.`, true);
          return;
        }
      } catch (_) {
        return;
      }
    }
  }

  document.addEventListener("click", async (event) => {
    const link = event.target.closest("a[href]");
    if (!link) return;
    const match = new URL(link.href).pathname.match(/^\/app\/(pedidos\/(\d+)|mesas\/cuentas\/(\d+))\/imprimir\/(cocina|cobro)\/$/);
    if (!match) return;
    event.preventDefault();
    if (link.getAttribute("aria-disabled") === "true") return;
    if (sending) return;
    sending = true;
    try {
      const captureForm = document.querySelector("[data-internal-order-form]");
      if (captureForm) {
        const data = new FormData(captureForm);
        if (match[4] === "cobro") data.set("for_print", "1");
        const saved = await fetch(captureForm.dataset.autosaveUrl, {
          method: "POST", credentials: "same-origin", body: data,
          headers: { "X-CSRFToken": data.get("csrfmiddlewaretoken"), "X-Requested-With": "XMLHttpRequest" },
        });
        const savedResult = await saved.json();
        if (!saved.ok || !savedResult.ok) throw new Error("Revisa los datos de cobro antes de imprimir; no se guardaron.");
      }
      const response = await fetch("/app/impresion/solicitar/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": document.querySelector("[data-print-csrf] input[name=csrfmiddlewaretoken]")?.value || "",
        },
        body: JSON.stringify({
          source_type: match[2] ? "order" : "table",
          source_id: Number(match[2] || match[3]),
          ticket_type: match[4] === "cocina" ? "kitchen" : "payment",
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "No se pudo enviar el ticket.");
      notice(`${result.label}: enviado a la Dell (trabajo #${result.job_id}).`);
      watchJob(result.job_id, result.label);
    } catch (error) {
      notice(error.message || "Error al enviar el ticket.", true);
    } finally {
      sending = false;
    }
  });
})();
