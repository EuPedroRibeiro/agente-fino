const loginForm = document.querySelector("#loginForm");
const enterButton = document.querySelector("#enterAgenteFinoBtn");
const passwordInput = document.querySelector("#passwordInput");
const loginError = document.querySelector("#loginError");

function showLoginError(message) {
  if (loginError) loginError.textContent = message;
}

loginForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const password = passwordInput?.value || "";
  showLoginError("");

  if (!password) {
    showLoginError("Digite sua senha de acesso.");
    passwordInput?.focus();
    return;
  }

  loginForm.setAttribute("aria-busy", "true");
  enterButton?.setAttribute("aria-busy", "true");
  if (enterButton) enterButton.disabled = true;

  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });

    if (!response.ok) {
      showLoginError(response.status === 401 ? "Senha inválida." : "Não foi possível entrar agora.");
      return;
    }

    localStorage.setItem("agente_fino_authenticated", "true");
    localStorage.setItem("nexus_authenticated", "true");
    window.location.replace(loginForm.dataset.href || "/agent");
  } catch {
    showLoginError("Não foi possível entrar agora.");
  } finally {
    loginForm.removeAttribute("aria-busy");
    enterButton?.removeAttribute("aria-busy");
    if (enterButton) enterButton.disabled = false;
  }
});
