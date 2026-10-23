import type { Entry } from '../loader';
import { regionEnvelope, searchEnvelope } from '../shape/search';

/** The demo's only platform routes: search and region lookup, without catalog or provenance. */
export const demoEntries: Record<string, Entry> = {
  '/api/search': { envelope: async (p) => searchEnvelope(p) },
  '/api/callset/region': { envelope: async (p) => regionEnvelope(p) },
};
