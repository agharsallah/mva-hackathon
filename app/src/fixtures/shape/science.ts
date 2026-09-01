import type {
  EvidenceRegister,
  EvidenceRow,
  HypothesisRegister,
  HypothesisRow,
} from '../../api/types';
import { rows } from '../loader';

/**
 * FIXTURE — the research register, in the shape it will have once step 1 starts making
 * claims.
 *
 * NOTHING HERE IS MEASURED. Every statement, verdict and confidence is invented to
 * exercise the layout: two claims with two revisions each (one that firmed up, one that
 * was refuted), four observations covering all three directions, and the nulls the real
 * register carries — an opening revision has no confidence, no reasoning and no path.
 * The row tables live in `data/science-hypotheses.json` and `data/science-evidence.json`
 * — this is the INVENTED research register.
 *
 * The live API today returns `table_exists: false` with no rows, because the register has
 * never been written. That empty state is a designed state in the page, not a fallback:
 * the fixture exists so the *populated* layout can be reviewed before there is anything to
 * put in it.
 *
 * No genomic position appears here, and none ever will — `mva-science check` refuses a
 * coordinate in a statement or a claim, and this fixture holds itself to the same rule.
 */

export async function hypothesisRegisterFixture(): Promise<HypothesisRegister> {
  return { table_exists: true, rows: await rows<HypothesisRow[]>('science-hypotheses') };
}

export async function evidenceRegisterFixture(): Promise<EvidenceRegister> {
  return { table_exists: true, rows: await rows<EvidenceRow[]>('science-evidence') };
}
