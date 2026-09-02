/* NOTA TEMPORAL PARA APRENDIZAJE: esta advertencia consulta la agenda mientras se
escribe, pero CustomerForm repite la validación en servidor. Así la integridad no
depende de JavaScript. Borra esta nota después de leerla. */
document.querySelectorAll("[data-customer-agenda-form]").forEach((form) => {
  const phoneField = form.querySelector("input[name='phone']");
  const warning = form.querySelector("[data-agenda-phone-warning]");
  if (!phoneField || !warning) return;
  const normalizePhone = (value) => Array.from(value).filter((character) => /[0-9]/.test(character)).join("");
  let timer = null;
  phoneField.addEventListener("input", () => {
    window.clearTimeout(timer);
    const phone = normalizePhone(phoneField.value);
    if (phone.length < 5) {
      warning.hidden = true;
      return;
    }
    timer = window.setTimeout(async () => {
      try {
        const response = await fetch(`${form.dataset.customerLookupUrl}?q=${encodeURIComponent(phone)}`, {headers: {"Accept": "application/json"}});
        const data = await response.json();
        const currentId = Number(form.dataset.customerId || 0);
        const duplicate = (data.customers || []).find((customer) => customer.id !== currentId && normalizePhone(customer.phone) === phone);
        warning.replaceChildren();
        if (!duplicate) {
          warning.hidden = true;
          return;
        }
        warning.append(document.createTextNode(`Este teléfono ya pertenece a ${duplicate.name}. `));
        const link = document.createElement("a");
        link.href = duplicate.edit_url;
        link.textContent = "Revisar contacto registrado";
        warning.append(link);
        warning.hidden = false;
      } catch (error) {
        warning.hidden = true;
      }
    }, 350);
  });
  if (phoneField.value.trim()) phoneField.dispatchEvent(new Event("input"));
});
