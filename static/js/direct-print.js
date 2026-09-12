(() => {
  let printing = false;

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[href]");
    if (!link || !/^\/(?:app\/)?(?:pedidos\/\d+|mesas\/cuentas\/\d+)\/imprimir\/(?:cocina|cobro)\/$/.test(new URL(link.href).pathname)) return;
    event.preventDefault();
    if (printing) return;
    printing = true;

    const frame = document.createElement("iframe");
    frame.title = "Impresión del ticket";
    frame.style.cssText = "position:fixed;left:-10000px;top:0;width:80mm;height:100mm;border:0;";
    frame.addEventListener("load", async () => {
      const page = frame.contentDocument;
      if (!page?.querySelector(".thermal-ticket")) {
        frame.remove();
        printing = false;
        window.location.assign(link.href);
        return;
      }
      try {
        await page.fonts.ready;
        frame.contentWindow.addEventListener("afterprint", () => {
          printing = false;
          frame.remove();
        }, { once: true });
        frame.contentWindow.focus();
        frame.contentWindow.print();
      } catch (_) {
        frame.remove();
        printing = false;
        window.location.assign(link.href);
      }
    }, { once: true });
    frame.src = link.href;
    document.body.append(frame);
  });
})();
