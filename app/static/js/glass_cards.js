const MAX_TILT = 5;
const LERP = 0.12;

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function bindCard(card) {
  if (card.dataset.sbGlassBound === "1") return;
  card.dataset.sbGlassBound = "1";

  let raf = 0;
  let targetX = 0;
  let targetY = 0;
  let curX = 0;
  let curY = 0;

  const apply = () => {
    raf = 0;
    curX += (targetX - curX) * LERP;
    curY += (targetY - curY) * LERP;
    card.style.setProperty("--sb-tx", `${curY.toFixed(2)}deg`);
    card.style.setProperty("--sb-ty", `${-curX.toFixed(2)}deg`);
    if (Math.abs(targetX - curX) > 0.02 || Math.abs(targetY - curY) > 0.02) {
      raf = requestAnimationFrame(apply);
    }
  };

  const queue = () => {
    if (raf) return;
    raf = requestAnimationFrame(apply);
  };

  card.addEventListener(
    "pointermove",
    (event) => {
      const rect = card.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const nx = (event.clientX - cx) / Math.max(rect.width / 2, 1);
      const ny = (event.clientY - cy) / Math.max(rect.height / 2, 1);
      targetX = Math.max(-1, Math.min(1, nx)) * MAX_TILT;
      targetY = Math.max(-1, Math.min(1, ny)) * MAX_TILT;
      queue();
    },
    { passive: true }
  );

  card.addEventListener(
    "pointerleave",
    () => {
      targetX = 0;
      targetY = 0;
      queue();
    },
    { passive: true }
  );
}

export function bootGlassCards(root = document) {
  if (prefersReducedMotion()) return;
  root.querySelectorAll(".sb-glass-card").forEach(bindCard);
}
