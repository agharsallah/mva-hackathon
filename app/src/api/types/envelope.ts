/** The one response shape every viz-API endpoint uses. */
export interface Envelope<T> {
  data: T;
  cached_at: string | null;
  source: string;
}

export interface Health {
  ok: boolean;
  service: string;
}
