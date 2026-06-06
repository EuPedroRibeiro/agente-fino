const arcadeSample = document.querySelector(".mario-sample-theme");
const arcadePreviewToggle = document.querySelector("#arcadePreviewToggle");
const arcadePreviewStatus = document.querySelector("#arcadePreviewStatus");

function setArcadePreview(active) {
  if (!arcadeSample || !arcadePreviewToggle || !arcadePreviewStatus) return;
  arcadeSample.classList.toggle("is-previewing", active);
  arcadeSample.dataset.previewState = active ? "active" : "idle";
  arcadePreviewToggle.setAttribute("aria-pressed", String(active));
  arcadePreviewToggle.textContent = active ? "Encerrar preview" : "Aplicar preview";
  arcadePreviewStatus.textContent = active
    ? "Preview ativo somente nesta amostra."
    : "A animacao fica pausada ate voce ativar.";
}

arcadePreviewToggle?.addEventListener("click", () => {
  setArcadePreview(!arcadeSample?.classList.contains("is-previewing"));
});
