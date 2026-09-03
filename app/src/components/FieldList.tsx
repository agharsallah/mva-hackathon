/**
 * FieldList — a key/value list rendered as `<dl>`, the semantic tag for exactly this shape.
 *
 * Three page files (`catalog/DeliveryInventory`, `catalog/ReadStoreCard`,
 * `science/HypothesisBoard`) each hand-roll a `<dl><div className="flex gap-2"><dt/><dd/>
 * </div></dl>` list with slightly different spacing. Two layouts cover both: `columns` is a
 * fixed-width label beside a value (object metadata, facts); `inline` runs the label and value
 * as one sentence (`Prediction — …`, `Refuted by — …`).
 */
import type { ReactNode } from 'react';

export interface Field {
  key: string;
  label: ReactNode;
  value: ReactNode;
  /** Only meaningful for `layout="inline"`; tints the label (e.g. a warning-coloured label). */
  labelClassName?: string;
}

export interface FieldListProps {
  fields: Field[];
  layout?: 'columns' | 'inline';
  /** `columns` layout only — the fixed label column width, in px. */
  labelWidth?: number;
  className?: string;
}

export function FieldList({
  fields,
  layout = 'columns',
  labelWidth = 96,
  className,
}: FieldListProps) {
  if (layout === 'inline') {
    return (
      <dl className={className ?? 'space-y-2 text-xs leading-relaxed'}>
        {fields.map((f) => (
          <div key={f.key}>
            <dt className={f.labelClassName ?? 'inline font-semibold text-chrome-400'}>
              {f.label}
            </dt>
            <dd className="inline text-chrome-400"> — {f.value}</dd>
          </div>
        ))}
      </dl>
    );
  }
  return (
    <dl className={className ?? 'space-y-1 text-micro'}>
      {fields.map((f) => (
        <div key={f.key} className="flex gap-2">
          <dt className="shrink-0 text-chrome-600" style={{ width: labelWidth }}>
            {f.label}
          </dt>
          <dd className="min-w-0 break-words font-mono text-chrome-400">{f.value}</dd>
        </div>
      ))}
    </dl>
  );
}
