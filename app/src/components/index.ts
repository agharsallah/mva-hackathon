/**
 * Barrel — the one place page code imports shared components from.
 *
 * `Header` is deliberately excluded: it is mounted once by the app shell, never by a page.
 * Grouped by concern, not alphabetically, so a newcomer can read this file as a map of what
 * exists rather than a sorted list.
 */

// Charts and their scaffolding
export { Exhibit, Chip, type ExhibitProps } from './Exhibit';
export { Plot, baseLayout, scene3d, type PlotProps, type Trace, type Layout } from './Plot';

// Data display
export { DataTable, type Column, type SortValue } from './DataTable';
export { StatTile, type StatTileProps } from './StatTile';
export { NormChip, pickNorm } from './NormChip';
export { FieldList, type Field, type FieldListProps } from './FieldList';

// Layout and structure
export { Card, type CardProps } from './Card';
export { Section, Toggle, Select, TextFilter } from './Controls';
export { Explainer, Callout, type Term, type ExplainerProps } from './Explainer';
export { EmptyState, type EmptyStateProps } from './EmptyState';

// Small marks
export { Badge, Flag, type BadgeProps } from './Badge';

// Async / query state
export { Loaded, Skeleton, ErrorCard } from './QueryState';

// Export tooling
export { AiExport } from './AiExport';
