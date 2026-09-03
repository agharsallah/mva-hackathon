/**
 * GET /api/panel/protein-structure?gene=… — the folded protein of one panel gene, as a
 * per-residue alpha-carbon trace, from the AlphaFold Protein Structure Database (or an
 * experimental PDB entry when one is preferred).
 *
 * Why a trace and not the coordinate file: the browser draws a backbone tube through the
 * alpha carbons (the one atom every residue has, the spine of the chain) and paints each
 * residue; it never needs the ~8,000 side-chain atoms, and parsing mmCIF client-side
 * would mean shipping a second structure library next to three.js. The server parses
 * once and caches, like `/api/panel/gene-structure`.
 *
 * Everything here is **public reference data**: the model is the same for every human.
 * Nothing patient-derived rides on it — candidate alleles are painted client-side from
 * `GeneStructure.candidates[].protein_pos`, which is an amino-acid index, not a genomic
 * coordinate. This payload is publishable as-is.
 *
 * A 502 means AlphaFold DB / Ensembl / RCSB was unreachable — never a fixture-shaped
 * stand-in from the live server.
 */
export interface ProteinStructure {
  gene: string;
  /**
   * Ensembl translation id (ENSP…). MUST equal `GeneStructure.protein`, or every painted
   * residue lands on a different sequence. The client asserts this before painting.
   */
  protein: string;
  /** UniProt accession the model was fetched by (e.g. BUB1B → `O60566`). */
  uniprot: string | null;
  /** `alphafold` = a *prediction*; `pdb` = an experimental structure. Never silently mixed. */
  provenance: 'alphafold' | 'pdb';
  /** The coordinate file that was parsed, verbatim, for the exhibit's provenance line. */
  model_url: string;
  /** Model version as the source API reported it (AlphaFold `latestVersion`); never hardcoded. */
  version: string | null;
  /** Length of the translation in residues — the axis every `n` below indexes into. */
  protein_length: number;
  /** One entry per *modelled* residue, ascending `n`. A residue absent here is unmeasured. */
  residues: ProteinResidue[];
  /** Inclusive residue ranges the model covers; the complement is unmeasured, not "fine". */
  covered: [number, number][];
  /**
   * Helix / strand segments when the source file carries them (`_struct_conf`,
   * `_struct_sheet_range`); empty when it does not. Absence means "not annotated", never
   * "all coil".
   */
  secondary: SecondarySegment[];
  /** Phase 2: other chains in an experimental complex, for interface colouring. Empty today. */
  partners: ProteinPartner[];
}

/** One residue's position and confidence. */
export interface ProteinResidue {
  /** 1-based residue index on the translation — the same axis as `GeneCandidate.protein_pos`. */
  n: number;
  /** One-letter amino-acid code (`"K"`), `"X"` when the file names an unknown residue. */
  aa: string;
  /** Alpha-carbon coordinates in ångström, in the model's own frame. */
  ca: [number, number, number];
  /**
   * AlphaFold pLDDT (per-residue confidence, 0–100). Below 70 the position supports no
   * spatial claim; below 50 the region is likely disordered. `null` for an experimental
   * structure, where the B-factor column means something else.
   */
  plddt: number | null;
}

export interface SecondarySegment {
  kind: 'helix' | 'strand';
  /** Inclusive residue range. */
  start: number;
  end: number;
}

export interface ProteinPartner {
  chain: string;
  uniprot: string | null;
  label: string;
}

/**
 * GET /api/panel/structure-genes — the curated set of genes the structure explorer can
 * show, in display order. Owned by `ressources/reference/structure_genes.tsv`; the server
 * only reads it.
 *
 * **Groups are data, not a union.** `group` is a free-form id the reference table invents,
 * and it arrives with the words and the rank it should be displayed by, so a picker, a
 * legend, a badge and a bar colour are all built from the payload — nothing in the app
 * knows which groups this case happens to use. `in_panel` is the one *semantic* field:
 * it says the gene carries the proband's annotated alleles (the BED the callset was
 * annotated against). Every other gene carries **no patient data at all** — its fold can
 * be explored and compared, but no allele is painted, and the exhibit says so. Branch on
 * `in_panel` for that; never on a group id.
 */
export interface StructureGene {
  symbol: string;
  ensembl_id: string;
  /** Free-form display-group id (`panel`, `kinases`, …). Short enough to use as a badge. */
  group: string;
  /** The sentence a heading or legend shows for {@link group}; the id when none was given. */
  group_label: string;
  /**
   * The group's rank in the display, and what its colour tone is picked by — rank, never
   * id, so a renamed group keeps its place and its colour. Rows of one group share it.
   */
  group_order: number;
  /**
   * True when the gene carries the proband's annotated alleles — the one flag an exhibit
   * may branch on to decide what it claims about the patient. Derived server-side from the
   * panel BED, never stored in the reference table, so it cannot go stale against it.
   */
  in_panel: boolean;
  /** Ensembl biotype (`protein_coding`, `lncRNA`, …). */
  biotype: string | null;
  /** False for a non-coding gene: it has no protein, so `/protein-structure` answers 422. */
  coding: boolean;
  /** One line on why it is in the set, from the TSV. */
  note: string;
}
