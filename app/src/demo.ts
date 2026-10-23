/**
 * The shareable demo build (`pnpm build:demo`): no API call, no address, and only the
 * SYNTHETIC rows in `fixtures/demo/` (written by `tools/build_demo_fixtures.py`).
 * A build-time constant, so every branch it turns off is dropped from the bundle.
 */
export const DEMO: boolean = import.meta.env.VITE_DEMO === 'true';

/** The sample the header and exports name: public GIAB HG002 in the demo. */
export const SAMPLE_ID: string = DEMO ? 'HG002 (demo)' : 'PROBAND01';
