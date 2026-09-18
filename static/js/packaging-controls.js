/* NOTA TEMPORAL PARA APRENDIZAJE:
Los botones escriben en inputs reales. El servidor vuelve a validar estas cantidades;
el número dibujado no es la fuente autoritativa. Borra esta nota después de leerla. */
document.addEventListener("click", (event) => {
  const card = event.target.closest("[data-package-packaging] article");
  const button = event.target.closest("[data-packaging-change]")
    || card?.querySelector('[data-packaging-change="1"]');
  if (!button) return;
  const counter = button.closest(".package-packaging-counter")
    || button.closest("article")?.querySelector(".package-packaging-counter");
  const input = counter?.querySelector("input[type='hidden']");
  const output = counter?.querySelector("output");
  if (!input || !output) return;
  const next = Math.max(0, Math.min(
    99,
    Number(input.value || 0) + Number(button.dataset.packagingChange),
  ));
  input.value = String(next);
  output.value = String(next);
  output.textContent = String(next);
});

document.addEventListener("reset", (event) => {
  if (!event.target.matches("[data-package-form], [data-internal-package]")) return;
  window.setTimeout(() => event.target.querySelectorAll(".package-packaging-counter").forEach((counter) => {
    const input = counter.querySelector("input[type='hidden']");
    const output = counter.querySelector("output");
    if (input && output) output.textContent = input.value || "0";
  }));
});
