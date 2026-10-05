/**
 * Pure lookups over the manifest — the one place "which group is this page in, what
 * comes next" is answered. Header, PageFrame and the Overview map all call these
 * instead of scanning `modules` themselves.
 */

import { modules } from './index';
import { type FeatureModule, NAV_GROUPS, type NavGroup, type NavGroupId } from './types';

/** The module whose path is exactly `pathname`, or undefined for an unknown route. */
export function moduleAt(pathname: string): FeatureModule | undefined {
  return modules.find((m) => m.path === pathname);
}

export function groupOf(m: FeatureModule | undefined): NavGroup | undefined {
  return m?.group ? NAV_GROUPS.find((g) => g.id === m.group) : undefined;
}

/** Pages in one group, in journey order — detail pages included. */
export function pagesIn(group: NavGroupId): FeatureModule[] {
  return modules.filter((m) => m.group === group);
}

/**
 * Pages in one group that are not a detail of another page — what the section row lists.
 *
 * The reading order (`journey`, `neighbours`) still walks every page: a detail page is part
 * of the journey, it is just not a peer of its parent in the tab row.
 */
export function topLevelIn(group: NavGroupId): FeatureModule[] {
  return pagesIn(group).filter((m) => !m.parent);
}

/** The detail pages of one page, in journey order. Empty for a page that has none. */
export function childrenOf(id: string): FeatureModule[] {
  return modules.filter((m) => m.parent === id);
}

/** The page a group tab lands on: its first page. Every group has at least one. */
export function groupEntry(group: NavGroupId): FeatureModule {
  const first = topLevelIn(group)[0];
  if (!first) throw new Error(`nav group "${group}" has no pages`);
  return first;
}

/** Every grouped page in journey order — the whole reading path, first page to last. */
export function journey(): FeatureModule[] {
  return modules.filter((m) => m.group !== undefined);
}

/**
 * The page before and after `m` on the journey. The overview has no previous page and its
 * next page is the start of the journey; the last page has no next.
 */
export function neighbours(m: FeatureModule): {
  prev: FeatureModule | undefined;
  next: FeatureModule | undefined;
} {
  const path = journey();
  if (m.group === undefined) return { prev: undefined, next: path[0] };
  const i = path.findIndex((x) => x.id === m.id);
  return { prev: i > 0 ? path[i - 1] : modules[0], next: path[i + 1] };
}

/** 1-based position of `m` inside its group, and the group size — for "2 of 3". */
export function positionInGroup(m: FeatureModule): { index: number; total: number } | undefined {
  if (!m.group) return undefined;
  const siblings = pagesIn(m.group);
  return { index: siblings.findIndex((x) => x.id === m.id) + 1, total: siblings.length };
}
