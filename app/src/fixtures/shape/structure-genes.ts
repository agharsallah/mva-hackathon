import { ApiError } from '../../api/client';
import type { StructureGene } from '../../api/types';
import { rows } from '../loader';

/**
 * FIXTURE — `/api/panel/structure-genes`, plus the symbol resolution the two
 * per-gene structure fixtures share.
 *
 * ***REAL REFERENCE DATA, NOT A SHAPE.*** `data/panel-structure-genes.json` is
 * `ressources/reference/structure_genes.tsv` as the server reads it: every `ensembl_id`,
 * `biotype` and `coding` flag came from a live `GET /lookup/symbol/homo_sapiens/<symbol>`
 * reply (`tools/build_gene_set.py`, recorded in `docs/step-0/methodology/060`), and the
 * file is written straight out of `mva.viz.geneset.genes()` by
 * `tools/build_protein_fixture.py` so the offline list cannot drift from the committed TSV.
 *
 * Committable because none of it is patient-derived: a gene symbol, a stable Ensembl id
 * and a biotype are public facts. The one field that touches the proband is `in_panel`,
 * and it is a *boolean about which genes were annotated*, not an allele.
 */
const DATA = 'panel-structure-genes';

/**
 * Alias → current symbol, mirroring `mva.viz.geneset.ALIASES`.
 *
 * Kept in step by hand rather than generated, because it has one entry and a generated
 * map would be a build step for six characters. `CCDC84` is HGNC's *previous* symbol for
 * `CENATAC`; Ensembl's `/lookup/symbol` refuses it outright and only `/xrefs/symbol`
 * resolves it, which is why the server never guesses at aliases either.
 */
const ALIASES: Record<string, string> = { CCDC84: 'CENATAC' };

/** The default gene when a request names none — the case's primary candidate. */
const DEFAULT_GENE = 'BUB1B';

/** The gene set, in display order. */
export async function structureGenesFixture(): Promise<StructureGene[]> {
  return rows<StructureGene[]>(DATA);
}

/**
 * The set's own spelling of `gene`, or a 404 the way the live route answers one.
 *
 * Offline used to hand *any* symbol BUB1B's payload with a new name on it. That is no
 * longer honest now that each gene has its own measured fixture: an unknown symbol has no
 * fold to show, and pretending otherwise would put a fabricated comparison on screen. The
 * live route 404s for a gene in neither the panel BED nor the TSV, so this does too.
 */
export async function resolveSymbol(
  gene: string | undefined,
  path: string,
): Promise<StructureGene> {
  const wanted = (gene ?? DEFAULT_GENE).trim().toUpperCase();
  const symbol = ALIASES[wanted] ?? wanted;
  const found = (await structureGenesFixture()).find(
    (entry) => entry.symbol.toUpperCase() === symbol,
  );
  if (!found) {
    throw new ApiError(
      `no structure gene '${gene}': not in ressources/reference/structure_genes.tsv`,
      404,
      path,
    );
  }
  return found;
}
