// =========================
// Bootstrap toast auto-init
// =========================
document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("toast-container");
  if (container) {
    const toasts = container.querySelectorAll(".toast");
    toasts.forEach((el) => {
      const t = new bootstrap.Toast(el, { delay: 3000, autohide: true });
      t.show();
    });
  }
});
