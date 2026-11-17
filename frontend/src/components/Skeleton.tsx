/** Platzhalter beim Laden; Form wird per className bestimmt (Größe, Radius). */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={`skeleton rounded-control ${className ?? ""}`} />;
}
