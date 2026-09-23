import { Link } from 'react-router-dom';

/** Where the whole zoo is drawn. A step body shows its own slice and points at the rest. */
export const ZOO_PATH = '/track1/iteration4/zoo';

/**
 * The hand-off line under a step body: this step's exhibits are the zoo's own components,
 * served from the same `/api/zoo/*` payloads, so the full dashboard is one click away.
 */
export function ZooLink({ what }: { what: string }) {
  return (
    <p className="text-xs text-chrome-400">
      {what} The whole roster, every lane&rsquo;s report and the any-gene view are on{' '}
      <Link to={ZOO_PATH} className="text-machinery-300 underline underline-offset-2">
        the model zoo
      </Link>
      .
    </p>
  );
}
