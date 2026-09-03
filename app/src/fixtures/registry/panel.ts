/**
 * Fixture registry fragment: the MVA candidate panel exhibits.
 *
 * `/api/panel/background` is transcribed measurement with no synthesis, so it loads
 * straight off `data/panel-background.json`. Every other path is param-driven and its
 * synthesis lives in `../shape/*`; see those modules for what is measured, placeholder,
 * or synthetic in each.
 *
 * The three structure paths carry **real** upstream data committed into the repository,
 * so their `source` strings name the manifest that says which upstream, at which release,
 * with which digest — `_provenance.json` beside the per-gene files, and
 * `structure_genes.provenance.json` beside the gene-set TSV. Those manifests are written
 * by `tools/build_protein_fixture.py` and `tools/build_gene_set.py` on every run and are
 * listed, normalised, by `/api/provenance/reference`.
 */
import type { PanelBackgroundRow } from '../../api/types';
import type { Entry } from '../loader';
import { rows } from '../loader';
import { clinvarPresenceFixture } from '../shape/clinvar-presence';
import { geneStructureFixture } from '../shape/gene-structure';
import { panelAnnotationsFixture } from '../shape/panel-annotations';
import { panelConstraintFixture } from '../shape/panel-constraint';
import { panelGenesFixture } from '../shape/panel-genes';
import { panelHetPairsFixture } from '../shape/panel-het-pairs';
import { locusFixture } from '../shape/panel-locus';
import { panelSuppressedFixture } from '../shape/panel-suppressed';
import { proteinStructureFixture } from '../shape/protein-structure';
import { structureGenesFixture } from '../shape/structure-genes';

export const panelEntries: Record<string, Entry> = {
  '/api/panel/genes': {
    source: 'results.panel_gene_density + panel BED',
    load: () => panelGenesFixture(),
  },
  '/api/panel/constraint': {
    source: 'PLACEHOLDER gnomAD constraint + ClinVar counts',
    load: () => panelConstraintFixture(),
  },
  // Transcribed from the executed derivation, so the offline exhibit shows the real
  // result rather than a plausible-looking one. Still marked `fixture:` in the UI.
  '/api/panel/background': {
    source: 'transcribed results.panel_gene_background',
    load: () => rows<PanelBackgroundRow[]>('panel-background'),
  },
  // `gene` is optional here, unlike /api/panel/locus: omitted means the whole panel.
  '/api/panel/annotations': {
    source: 'SYNTHETIC positions — never real',
    load: (p) => panelAnnotationsFixture(p?.gene as string | undefined),
  },
  '/api/panel/locus': {
    source: 'SYNTHETIC positions — never real',
    load: (p) => locusFixture((p?.gene as string | undefined) ?? 'BUB1B'),
  },
  '/api/panel/het-pairs': {
    source: 'SYNTHETIC positions — never real',
    load: (p) => panelHetPairsFixture((p?.gene as string | undefined) ?? 'BUB1B'),
  },
  // The per-gene ClinVar P/LP counts are MEASURED off the committed extract; every
  // callset-side hit and every position is shaped so the exhibit has one of each state.
  '/api/panel/clinvar-presence': {
    source: 'measured ClinVar P/LP counts, SHAPED hits, SYNTHETIC positions',
    load: (p) => clinvarPresenceFixture(p?.gene as string | undefined),
  },
  // The per-gene, per-FILTER census is MEASURED; the record positions are synthetic.
  '/api/panel/suppressed': {
    source: 'measured per-gene FILTER census, SYNTHETIC record positions',
    load: (p) => panelSuppressedFixture(p?.gene as string | undefined),
  },
  // The curated gene set the structure explorer is addressed by. REAL: written straight
  // out of the committed TSV, whose every id and biotype came from a live Ensembl reply.
  '/api/panel/structure-genes': {
    source:
      'ressources/reference/structure_genes.tsv + panel BED — provenance: ressources/reference/structure_genes.provenance.json',
    load: () => structureGenesFixture(),
  },
  // REAL Ensembl exons and domains, one measured file per gene. The only synthesised part
  // is `candidates`, and only for the eight annotated panel genes — the proband's alleles
  // are never committed. See `../shape/gene-structure.ts` for the field-by-field split.
  '/api/panel/gene-structure': {
    source:
      'REAL Ensembl exons + domains; SYNTHETIC candidates, panel genes only — per-gene provenance: app/src/fixtures/data/gene-structure/_provenance.json',
    load: (p) => geneStructureFixture(p?.gene as string | undefined),
  },
  // Wholly REAL data: each coding gene's own AlphaFold alpha-carbon trace, public
  // reference data identical for every human. A non-coding gene answers 422, as live does.
  '/api/panel/protein-structure': {
    source:
      'REAL per-gene AlphaFold models — public reference data; per-gene model url, version and digest: app/src/fixtures/data/protein/_provenance.json',
    load: (p) => proteinStructureFixture(p?.gene as string | undefined),
  },
};
