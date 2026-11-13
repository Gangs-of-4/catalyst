/** Numbers the Indian way (12,345), one decimal at most. */
export const fmt = (n: number) =>
  Number.isInteger(n) ? n.toLocaleString("en-IN") : n.toLocaleString("en-IN", { maximumFractionDigits: 1 });

/** Minutes as "2 h 15 min" / "45 min". */
export function minutes(m: number): string {
  const total = Math.round(m);
  if (total < 60) return `${total} min`;
  const h = Math.floor(total / 60);
  const rest = total % 60;
  return rest ? `${h} h ${rest} min` : `${h} h`;
}
