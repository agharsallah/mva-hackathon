/**
 * One horizontal stacked bar: parts of a whole, drawn as flex segments with a 2px surface
 * gap between them (no strokes — the gap separates neighbours). Used for a claims tally and
 * for lineage coverage, the two places this page shows composition.
 *
 * Identity is never colour alone: every segment carries its label and count in `title` and
 * in the bar's accessible name, and each call site prints a legend with the words.
 */

export interface Segment {
  key: string;
  value: number;
  color: string;
  label: string;
}

export function SegmentBar({
  segments,
  /** The value the full track stands for; defaults to the segments' own sum. */
  scale,
  height = 8,
  label,
  onHover,
}: {
  segments: Segment[];
  scale?: number;
  height?: number;
  label: string;
  onHover?: (segment: Segment | null) => void;
}) {
  const shown = segments.filter((s) => s.value > 0);
  const sum = shown.reduce((n, s) => n + s.value, 0);
  const full = Math.max(scale ?? sum, sum, 1);
  const name = `${label}: ${shown.map((s) => `${s.value} ${s.label}`).join(', ') || 'none'}`;

  return (
    <div
      role="img"
      aria-label={name}
      className="flex w-full items-stretch overflow-hidden"
      style={{ height }}
    >
      {shown.length === 0 ? (
        <div className="w-full rounded-sm border border-dashed border-line" />
      ) : (
        <div
          className="flex items-stretch gap-[2px] overflow-hidden rounded-sm"
          style={{ width: `${(100 * sum) / full}%`, minWidth: shown.length * 4 }}
        >
          {shown.map((s) => (
            <div
              key={s.key}
              role="presentation"
              title={`${s.label}: ${s.value}`}
              onMouseEnter={onHover ? () => onHover(s) : undefined}
              onMouseLeave={onHover ? () => onHover(null) : undefined}
              style={{ flexGrow: s.value, flexBasis: 0, background: s.color, minWidth: 3 }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
