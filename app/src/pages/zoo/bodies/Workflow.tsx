import { RunManifest } from '../RunManifest';
import { ZooLineage } from '../ZooLineage';
import { ZooLink } from './ZooLink';

/** Iteration 4, step 4 — the DAG: what each run cost, and the lineage every stage wrote. */
export default function WorkflowBody() {
  return (
    <div className="space-y-4">
      <RunManifest />
      <ZooLineage />
      <ZooLink what="Every run manifest the DAG recorded, and every lineage edge its stages appended." />
    </div>
  );
}
