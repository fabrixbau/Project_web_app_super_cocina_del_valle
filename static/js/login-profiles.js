(() => {
  const select = document.querySelector("#id_user");
  const panel = document.querySelector("[data-login-access]");
  const password = document.querySelector("#id_password");
  const selectedName = document.querySelector("[data-selected-profile]");
  const cards = [...document.querySelectorAll("[data-login-profile]")];
  if (!select || !panel || !cards.length) return;

  function choose(card, focusPassword = true) {
    select.value = card.dataset.loginProfile;
    cards.forEach(item => {
      const active = item === card;
      item.classList.toggle("is-selected", active);
      item.setAttribute("aria-selected", String(active));
    });
    const name = card.querySelector("strong");
    if (selectedName && name) selectedName.textContent = name.textContent.trim();
    panel.hidden = false;
    panel.classList.add("is-visible");
    if (focusPassword) password?.focus();
  }

  cards.forEach(card => card.addEventListener("click", () => choose(card)));
  const current = cards.find(card => card.dataset.loginProfile === select.value);
  if (current) choose(current, false);
})();
