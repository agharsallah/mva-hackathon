/**
 * Barrel — the one place page code imports shared components from.
 *
 * `Header` is deliberately excluded: it is mounted once by the app shell, never by a page.
 * Grouped by concern, not alphabetically, so a newcomer can read this file as a map of what
 * exists rather than a sorted list.
 */

// Charts and their scaffolding
export { Chip, Exhibit, type ExhibitProps } from './Exhibit';
export { type Layout, Plot, type PlotProps, type Trace } from './Plot';
export { baseLayout, scene3d } from './plotLayout';

// Data display
export { type Column, DataTable, type SortValue } from './DataTable';
export { type Field, FieldList, type FieldListProps } from './FieldList';
export { NormChip } from './NormChip';
export { pickNorm } from './pickNorm';
export { StatTile, type StatTileProps } from './StatTile';

// Layout and structure
export { Card, type CardProps } from './Card';
export {
  Section,
  Select,
  type SelectGroup,
  type SelectOption,
  TextFilter,
  Toggle,
} from './Controls';
export { EmptyState, type EmptyStateProps } from './EmptyState';
export { Callout, Explainer, type ExplainerProps, type Term } from './Explainer';
export { Footer } from './Footer';

// Small marks
export { Badge, type BadgeProps, Flag } from './Badge';

// Async / query state
export { ErrorCard, Loaded, Skeleton } from './QueryState';

// Export tooling
export { AiExport } from './AiExport';
