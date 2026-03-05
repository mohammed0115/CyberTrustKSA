(function () {
  // simple demo animation for AI stepper progress
  const stepper = document.querySelector("[data-stepper]");
  if (!stepper) return;

  const steps = Array.from(stepper.querySelectorAll("[data-step]"));
  let idx = steps.findIndex((s) => s.dataset.status === "active");
  if (idx < 0) idx = 0;

  setInterval(() => {
    const current = steps[idx];
    if (!current) return;
    const next = steps[idx + 1];
    if (!next) return;

    current.dataset.status = "completed";
    current.classList.remove("animate-pulse");
    current.querySelector("[data-dot]")?.classList.remove("bg-cyan-400");
    current.querySelector("[data-dot]")?.classList.add("bg-emerald-400");

    next.dataset.status = "active";
    next.classList.add("animate-pulse");
    next.querySelector("[data-dot]")?.classList.add("bg-cyan-400");

    idx += 1;
  }, 2500);
})();
