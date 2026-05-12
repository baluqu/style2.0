const MAX_TILT = 5;
const LERP = 0.12;
const boundCards = new Set();
let laneListenerBound = false;

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function currentMotionLane() {
  const lane = window.__sbMotion?.lane || document.documentElement?.dataset?.sbMotionLane || "idle";
  return String(lane || "idle").trim().toLowerCase();
}

function tertiaryGainForLane() {
  const lane = currentMotionLane();
  if (lane === "primary") return 0.08;
  if (lane === "secondary") return 0.36;
  return 1;
}

function bindLaneListener() {
  if (laneListenerBound) return;
  laneListenerBound = true;
  window.addEventListener("sb:motion-lane-change", () => {
    boundCards.forEach((card) => {
      if (!card?.isConnected) {
        boundCards.delete(card);
        return;
      }
      card.dispatchEvent(new CustomEvent("sb:lane-refresh"));
    });
  });
}

function bindCard(card) {
  if (card.dataset.sbGlassBound === "1") return;
  card.dataset.sbGlassBound = "1";
  boundCards.add(card);

  let raf = 0;
  let targetX = 0;
  let targetY = 0;
  let curX = 0;
  let curY = 0;

  const apply = () => {
    raf = 0;
    const laneGain = tertiaryGainForLane();
    const effectiveTargetX = targetX * laneGain;
    const effectiveTargetY = targetY * laneGain;
    curX += (effectiveTargetX - curX) * LERP;
    curY += (effectiveTargetY - curY) * LERP;
    card.style.setProperty("--sb-tx", `${curY.toFixed(2)}deg`);
    card.style.setProperty("--sb-ty", `${-curX.toFixed(2)}deg`);
    if (Math.abs(effectiveTargetX - curX) > 0.02 || Math.abs(effectiveTargetY - curY) > 0.02) {
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
      const laneGain = tertiaryGainForLane();
      if (laneGain < 0.12) {
        targetX = 0;
        targetY = 0;
        queue();
        return;
      }
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

  card.addEventListener("sb:lane-refresh", queue, { passive: true });
}

export function bootGlassCards(root = document) {
  if (prefersReducedMotion()) return;
  bindLaneListener();
  root.querySelectorAll(".sb-glass-card").forEach(bindCard);
}
