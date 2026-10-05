/**
 * Export for AI analysis: what one exhibit looks like once it is off the screen.
 *
 * The narrative fields are the flattened text of the props the exhibit already renders, so
 * the exported document says what a figure means before it shows the numbers behind it.
 */

export interface ExhibitRecord {
  /** Route pathname the exhibit was mounted on — the export's page scope. */
  page: string;
  title: string;
  legend: string;
  reading?: string;
  source?: string;
  cachedAt?: string | null;
  /** The endpoint payload behind the exhibit, or undefined when none was wired. */
  data?: unknown;
}

/** One endpoint of a multi-endpoint bundle, fetched or failed. */
export interface EndpointRecord {
  path: string;
  source?: string;
  cachedAt?: string | null;
  data?: unknown;
  error?: string;
}
