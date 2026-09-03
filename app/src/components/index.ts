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
export { CommandPalette } from './CommandPalette';
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
export { JourneyMap, JourneyProvider } from './journey';
export { type JourneyGroup, type JourneyPage, useJourney } from './journeyContext';
export { JumpToSection, OnThisPage } from './OnThisPage';
export { JourneyFooter, PageHeader } from './PageHeader';

// Small marks
export { Badge, type BadgeProps, Flag } from './Badge';
export { ThemeToggle } from './ThemeToggle';

// Async / query state
export { classifyError, type Failure, type FailureKind } from './failure';
export { ErrorCard, Loaded, Skeleton, type SkeletonVariant } from './QueryState';

// Export tooling
export { AiExport } from './AiExport';
