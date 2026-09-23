import { useNavigate } from 'react-router-dom';

import { AgreementMatrix } from '../AgreementMatrix';
import { ConfirmedRankBars } from '../ConfirmedRankBars';
import { Disagreements } from '../Disagreements';
import { ZOO_PATH, ZooLink } from './ZooLink';

/** Iteration 4, step 6 — the merge: where the lanes agree, and where the fusion puts the pair. */
export default function MergedBody() {
  const navigate = useNavigate();
  // A disputed gene opens in the zoo's any-gene view, which this step page does not carry.
  const onGene = (symbol: string) => navigate(`${ZOO_PATH}?gene=${encodeURIComponent(symbol)}`);
  return (
    <div className="space-y-4">
      <AgreementMatrix />
      <ConfirmedRankBars />
      <Disagreements onGene={onGene} />
      <ZooLink what="The agreement matrix, the fused ranks and the disputes are the merge's own tables." />
    </div>
  );
}
