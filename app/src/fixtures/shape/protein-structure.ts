import { ApiError } from '../../api/client';
import type { ProteinStructure } from '../../api/types';
import { rows } from '../loader';
import { resolveSymbol } from './structure-genes';

const PATH = '/api/panel/protein-structure';

/**
 * FIXTURE — `/api/panel/protein-structure`. Default gene when none is given: BUB1B.
 *
 * ***THIS ONE IS REAL DATA, NOT A SHAPE.*** `data/protein/<SYMBOL>.json` is that gene's
 * actual AlphaFold model: every `residues[].ca` coordinate, every `plddt`, every
 * `secondary` segment and the `model_url` / `version` / `uniprot` / `protein` fields were
 * produced by running the live endpoint's own parser (`src/mva/viz/proteinstructure.py`)
 * against the model file AlphaFold DB named — see `tools/build_protein_fixture.py` and
 * `docs/step-0/methodology/060`. The offline exhibit draws the **true fold**, per gene.
 *
 * - **Safe to commit** because an AlphaFold prediction is public reference data, identical
 *   for every human. Nothing patient-derived can ride on it: the axis is an amino-acid
 *   index, never a genomic coordinate.
 * - **Nothing is rewritten any more.** The previous version patched `gene` and `protein`
 *   on the way out, because there was one committed model — BUB1B's — and every other gene
 *   got that backbone with its own name on it. Two genes on screen at once turned that
 *   compromise into a visible falsehood ("these proteins are the same shape"), so each gene
 *   now carries its own model and its own real `ENSP`. That real `ENSP` is also what the
 *   matching `gene-structure/<SYMBOL>.json` reports, which is what keeps the client's
 *   `ProteinStructure.protein === GeneStructure.protein` assertion true offline.
 * - **Coordinates are rounded harder than the live route's**, to 0.1 Å with whole-number
 *   pLDDT, on any file that would otherwise exceed ~60 kB. Both are far below the
 *   prediction's own uncertainty; the live route keeps two decimals because there the file
 *   is cached, not committed.
 * - **A non-coding gene answers 422, not a fold.** A lncRNA has no translation, so there
 *   is nothing to fold and never will be — the same status and the same sentence the live
 *   route uses, so the offline app exercises the real error path instead of a fake fold.
 */
export async function proteinStructureFixture(gene?: string): Promise<ProteinStructure> {
  const entry = await resolveSymbol(gene, PATH);
  if (!entry.coding) {
    throw new ApiError(`${entry.symbol} has no protein-coding canonical transcript`, 422, PATH);
  }
  return rows<ProteinStructure>(`protein/${entry.symbol}`);
}
