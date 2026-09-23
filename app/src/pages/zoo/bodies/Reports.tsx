import { ModelReport } from '../ModelReport';
import { useModelParam } from '../route';
import { ZooLink } from './ZooLink';

/** Iteration 4, step 5 — one report per lane, from the template this step tested. */
export default function ReportsBody() {
  const [modelKey, setModelKey] = useModelParam();
  return (
    <div className="space-y-4">
      <ModelReport modelKey={modelKey} onModelKey={setModelKey} />
      <ZooLink what="Pick a lane above to read its generated report; the written section is marked." />
    </div>
  );
}
