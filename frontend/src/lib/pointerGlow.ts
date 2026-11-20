// Cursor-nahes Aufleuchten: setzt --mx/--my (px relativ zum Element) auf dem Element mit `.zap` unter
// dem Zeiger. Ein einziger, per rAF gedrosselter Listener für die ganze App; nur bei Maus/Stift.
// Außerdem ein leerer touchstart-Listener: erst damit löst iOS Safari :active (Tap-Feedback) aus.
export function initPointerGlow(): void {
  let frame = 0;
  let event: PointerEvent | null = null;
  const apply = () => {
    frame = 0;
    const target = (event?.target as Element | null)?.closest<HTMLElement>(".zap");
    if (!event || !target) return;
    const box = target.getBoundingClientRect();
    target.style.setProperty("--mx", `${event.clientX - box.left}px`);
    target.style.setProperty("--my", `${event.clientY - box.top}px`);
  };
  document.addEventListener(
    "pointermove",
    (e) => {
      if (e.pointerType === "touch") return;
      event = e;
      if (!frame) frame = requestAnimationFrame(apply);
    },
    { passive: true },
  );
  document.addEventListener("touchstart", () => {}, { passive: true });
}
