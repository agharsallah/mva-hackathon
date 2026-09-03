import type { GeneStructure } from '../../api/types';
import { rows } from '../loader';
import { resolveSymbol } from './structure-genes';

const PATH = '/api/panel/gene-structure';

/**
 * FIXTURE — `/api/panel/gene-structure`. Default gene when none is given: BUB1B.
 *
 * ***MOSTLY REAL DATA NOW.*** This module used to synthesise everything: 23 exons on an
 * arithmetic ladder, BUB1B's domain *names* at invented offsets, and one placeholder
 * `ENSP00000000000` for every gene. That was defensible while one gene was on screen. It
 * stopped being defensible the moment the explorer could put two genes side by side — a
 * generated exon pattern makes every gene look like the same gene, which is a claim, and
 * a false one.
 *
 * So `data/gene-structure/<SYMBOL>.json` is one file per gene, and in each file:
 *
 * - **`exons` are Ensembl's real exon boundaries** on the real canonical transcript, in
 *   transcript order (exon 1 is the *rightmost* box on a minus-strand gene). Real GRCh38
 *   coordinates — public reference data, and the same numbers the live route returns.
 * - **`domains` are the real Pfam / SMART / PROSITE / Gene3D / SUPERFAMILY / CDD calls**
 *   at their real amino-acid offsets, filtered exactly as the server filters them.
 * - **`ensembl_id`, `transcript`, `protein`, `protein_length`, `biotype`, `chrom`,
 *   `start`, `end`, `strand` are all measured**, from a live `/lookup/id?expand=1` reply.
 * - **`candidates` are the one synthetic part, and only for the eight panel genes.**
 *   Three invented alleles per gene — one truncating, one missense, one splice-region with
 *   no amino-acid position — scaled to that protein's length so the lollipop is readable
 *   at 393 residues and at 2,537. Every `rsid` is `rs00000000n`, which is not a real dbSNP
 *   accession. The proband's alleles are never committed, and that is why these exist.
 * - **An off-panel gene has `candidates: []` and `in_panel: false`**, matching the live
 *   route: no annotation was ever run there, so there is nothing to show rather than
 *   nothing to find.
 * - **A non-coding gene has `protein: null` and `domains: []`** with its real exon track
 *   intact — the whole exhibit for a gene that makes no protein.
 *
 * Built by `tools/build_protein_fixture.py`; the run is recorded in
 * `docs/step-0/methodology/060`. The app still badges every payload `fixture:`, because
 * the *candidate* half is not a measurement even though the anatomy is.
 */
export async function geneStructureFixture(gene?: string): Promise<GeneStructure> {
  const entry = await resolveSymbol(gene, PATH);
  return rows<GeneStructure>(`gene-structure/${entry.symbol}`);
}
