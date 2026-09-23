import { CoverageTable } from '../CoverageTable';
import { ModelCards } from '../ModelCards';
import { ZooLink } from './ZooLink';

/** Iteration 4, step 2 — the registry: which lanes exist, and what each can see. */
export default function RegistryBody() {
  return (
    <div className="space-y-4">
      <ModelCards />
      <CoverageTable />
      <ZooLink what="These are the registry's cards and coverage, live from the warehouse." />
    </div>
  );
}
