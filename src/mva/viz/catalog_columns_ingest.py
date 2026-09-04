"""Column semantics for the ingest schema: the delivery, the reference, the ledgers.

Split from :mod:`mva.viz.catalog_columns` for size alone — that module owns the columns
that recur across tables and the resolution order; this one owns the sentences that belong
to one ingested table. Same rule as
:mod:`mva.warehouse.analysis` / :mod:`mva.warehouse.analysis_reference`: one registry,
assembled from two files, so no caller has to know which half a key lives in.

Every sentence was read off the code that writes the column, never inferred from its name.
"""

#: ``(table, column) -> meaning`` for every table in the ingest schema.
INGEST_COLUMNS: dict[tuple[str, str], str] = {
    # ── warehouse: the delivered profile ──────────────────────────────────────────────
    ("contig_counts", "length"): "Length of the contig in bases, as the callset's header "
    "declares it.",
    ("contig_counts", "n_records"): "Variant records called on this contig.",
    ("vcf_fields", "kind"): "Which VCF header section declared the field: FILTER, INFO or FORMAT.",
    ("vcf_fields", "id"): "The field's identifier as records reference it, e.g. `DP`, "
    "`GT`, `LowQual`.",
    ("vcf_fields", "description"): "The header's own prose description of the field.",
    ("filter_gt_counts", "section"): "Which block of the source file the row came from: "
    "`FILTER counts` or `genotype counts`.",
    ("filter_gt_counts", "label"): "The FILTER value or the genotype string being "
    "counted, e.g. `PASS`, `LowQual`, `0/1`, `1/1`.",
    ("filter_gt_counts", "count"): "Records carrying that FILTER value or that genotype.",
    ("fastq_profile", "read_len"): "Read length in bases, as the first read in the file "
    "declares it.",
    ("fastq_qc_l001", "metric"): "Name of the fastp quality metric measured on the sampled lane.",
    ("fastq_qc_l001", "value"): "The metric's measured value on that lane.",
    ("fastq_read_headers", "read_name"): "The first read's name in the file, with the "
    "index barcode redacted — enough to identify "
    "the instrument and run, not the sample.",
    ("manifest", "sha256_first_1mb"): "SHA-256 over the file's first megabyte only — a "
    "cheap identity check the publisher shipped, not a "
    "whole-file digest.",
    ("mva_panel_grch38", "name"): "The candidate gene the interval belongs to. This is a "
    "BED file, where the fourth column is the feature name.",
    ("profile_scalars", "source"): "The source file the rollup line was found at the foot of.",
    ("profile_scalars", "key"): "Name of the rollup total, e.g. `est_raw_coverage_x`.",
    ("profile_scalars", "value"): "The rollup total itself.",
    ("stats_summary", "line"): "One line of `bcftools stats` output, verbatim — the "
    "section code is the first tab-separated field.",
    ("warehouse_catalog", "table_name"): "The staged table this catalogue row describes.",
    ("warehouse_catalog", "n_columns"): "How many columns that table was staged with.",
    ("warehouse_catalog", "columns"): "Its column names, comma-joined, as staging wrote them.",
    ("warehouse_catalog", "description"): "What the table holds, in one sentence, carried "
    "from the staging spec so the database "
    "describes itself.",
    # ── warehouse: the raw callset ────────────────────────────────────────────────────
    ("variants_raw", "line_no"): "The record's position among the VCF's data lines, "
    "1-based, header excluded. Ordering by it reproduces the "
    "original file byte for byte.",
    ("variants_raw", "id"): "The VCF's ID column — the dbSNP rsID, or `.` for a record "
    "with none. `.` is kept as the literal dot, never turned "
    "into a null.",
    ("variants_raw", "info"): "The whole INFO field as delivered, `;`-packed key=value "
    "pairs, unparsed.",
    ("variants_raw", "format"): "The FORMAT field: `:`-joined keys naming what each "
    "field of `sample_call` holds, e.g. `GT:AD:DP:GQ`.",
    ("variants_raw", "sample_call"): "The single sample's genotype column, `:`-joined "
    "values positionally matching `format`.",
    # ── warehouse: the annotations ────────────────────────────────────────────────────
    ("panel_annotations", "annotated_at"): "When VEP was asked, in UTC. An annotation is "
    "only as current as the release that answered "
    "it.",
    ("panel_annotations", "source"): "Which Ensembl VEP release and assembly answered, "
    "recorded on every row so a re-annotation is "
    "distinguishable from the previous one.",
    # ── warehouse: the public reference tables ────────────────────────────────────────
    ("gnomad_constraint", "ensembl_gene_id"): "Ensembl's stable gene identifier "
    "(`ENSG…`) — the key a symbol is not.",
    ("gnomad_constraint", "transcript"): "The Ensembl transcript the metrics were "
    "computed on; a gene can have several.",
    ("gnomad_constraint", "mane_select"): "Whether this is the MANE Select transcript — "
    "the one NCBI and EMBL-EBI agreed to treat as "
    "the gene's representative.",
    ("gnomad_constraint", "canonical"): "Whether Ensembl marks this transcript canonical.",
    ("gnomad_constraint", "transcript_type"): "Biotype of the transcript, e.g. `protein_coding`.",
    ("gnomad_constraint", "cds_length"): "Coding sequence length in bases — the "
    "denominator most constraint metrics are scaled "
    "by.",
    ("gnomad_constraint", "num_coding_exons"): "How many coding exons the transcript has.",
    ("gnomad_constraint", "loeuf_decile"): "Which tenth of all genes this gene's LOEUF "
    "falls in; 0 is the most constrained decile.",
    ("gnomad_constraint", "oe_lof_lower"): "Lower bound of the loss-of-function "
    "observed/expected confidence interval "
    "(LOEUF is the upper one).",
    ("gnomad_constraint", "lof_z"): "How many standard deviations the observed "
    "loss-of-function count sits from the expectation.",
    ("gnomad_constraint", "mis_obs"): "Missense variants observed in gnomAD for this gene.",
    ("gnomad_constraint", "mis_exp"): "Missense variants the mutation model expects.",
    ("gnomad_constraint", "oe_mis"): "Observed missense over expected.",
    ("gnomad_constraint", "syn_obs"): "Synonymous variants observed — the control class, "
    "since they do not change the protein.",
    ("gnomad_constraint", "syn_exp"): "Synonymous variants expected.",
    ("gnomad_constraint", "oe_syn"): "Observed synonymous over expected. Should sit near "
    "1; a value far off it means the model, not "
    "selection.",
    ("gnomad_constraint", "syn_z"): "Standard deviations between observed and expected "
    "synonymous counts — the sanity check on the other "
    "z-scores.",
    ("gnomad_constraint", "constraint_flags"): "gnomAD's own caveats about this gene's "
    "metrics; null means it raised none.",
    ("clinvar_panel", "variation_id"): "ClinVar's stable record identifier — the key "
    "here, because thousands of these rows carry no "
    "rsID.",
    ("clinvar_panel", "clnsig"): "ClinVar's germline classification, free text with `|`- "
    "and `/`-packed multi-values (`Pathogenic/"
    "Likely_pathogenic`). Null means no germline "
    "classification.",
    ("clinvar_panel", "clnrevstat"): "Review status — how much assertion backing the "
    "classification has, which is what ClinVar's star "
    "rating encodes.",
    ("clinvar_panel", "condition"): "The condition(s) the classification is asserted for, "
    "pipe-packed.",
    ("qc_norms", "metric"): "Name of the QC metric the published range applies to.",
    ("qc_norms", "source"): "The publication the range came from, as a PMID or DOI.",
    ("qc_norms", "url"): "Where that publication can be read.",
    ("qc_norms", "basis"): "A paraphrase of the sentence in the publication the range was "
    "taken from, so the number can be checked without refetching "
    "the paper.",
    ("hpo_term_ic", "hpo_id"): "The HPO term this row prices, e.g. `HP:0002859`.",
    ("hpo_term_ic", "name"): "The term's human-readable label.",
    ("hpo_term_ic", "depth"): "Longest path from the ontology root — a readable proxy for "
    "how specific the term is. Never used for scoring; "
    "information content is the real measure and the two "
    "disagree wherever curation is uneven.",
    ("hpo_term_ic", "gene_count"): "How many distinct genes carry this term anywhere in "
    "their ancestor closure. Counted over genes, never "
    "summed up the graph, so a gene annotated to both a "
    "term and its parent contributes once.",
    ("hpo_term_ic", "information_content"): "-log(gene_count / annotated genes), in nats. "
    "Higher means rarer and therefore more "
    "informative. 0.0 means no gene carries the "
    "term at all — an absence of curation, not a "
    "measurement that it is common.",
    ("hpo_gene_scores", "term_set"): "Which set of the child's terms produced this row: "
    "`with-parental` (all eight delivered) or "
    "`proband-only` (the seven describing the child).",
    ("hpo_gene_scores", "genes_considered"): "How many curated genes were scored for this "
    "term set - the denominator a rank is quoted "
    "against. Larger than the row count, because "
    "genes that scored zero carry no signal and are "
    "not written.",
    ("hpo_gene_scores", "gene_symbol"): "HGNC gene symbol, uppercased. The join key — "
    "everything upstream speaks symbols.",
    ("hpo_gene_scores", "entrez_id"): "NCBI gene id, kept only because the hosted "
    "cross-check services key on it.",
    ("hpo_gene_scores", "rank"): "Position in this term set's ranking, 1 = best match.",
    ("hpo_gene_scores", "score"): "The symmetric similarity divided by the best score the "
    "child's own term set could achieve, so 1.0 is a perfect "
    "match and the number is readable as a share.",
    ("hpo_gene_scores", "forward"): "Mean best-match similarity asking 'is each of the "
    "child's features explained by this gene?'. Ignores "
    "everything else the gene does.",
    ("hpo_gene_scores", "reverse"): "The same measure in the other direction, asking 'is "
    "each of the gene's features present in the child?'. "
    "Penalises heavily curated genes, which is why both "
    "directions are stored rather than only their mean.",
    ("hpo_gene_scores", "curated_terms"): "How many phenotype terms HPO curates for this "
    "gene. Context for `reverse`: a long list is "
    "charged for the features the child lacks.",
    ("hpo_gene_scores", "best_term"): "Which of the child's features matched most strongly.",
    ("hpo_gene_scores", "best_common_ancestor"): "The most informative term that feature "
    "and the gene's feature both descend "
    "from — where the match actually "
    "happened. Equal to `best_term` when the "
    "gene is curated to the feature itself.",
    ("hpo_gene_scores", "best_ic"): "The information content of that shared ancestor: how "
    "much the strongest single match is worth.",
    # ── warehouse: the ledgers ────────────────────────────────────────────────────────
    ("source_files", "uploaded_at"): "When this upload happened, in UTC. One row per "
    "upload, so a file uploaded twice has two rows.",
    ("source_files", "kind"): "Coarse label for the file: `fastq`, `vcf`, `index`, "
    "`document` or `other`.",
    ("source_files", "source_mtime"): "The local file's modification time when it was uploaded.",
    ("source_files", "verified"): "Whether the digest the store reported back matched the "
    "one computed locally before the bytes left.",
    ("source_objects", "checked_at"): "When the survey that wrote this inventory ran. The "
    "table is replaced wholesale each time.",
    ("source_objects", "bucket"): "The object store bucket the object lives in.",
    ("source_objects", "kind"): "Coarse label for the object: `fastq`, `vcf`, `index`, "
    "`document` or `other`.",
    ("source_objects", "role"): "What the object is to this pipeline, parsed from its "
    "name: `reads`, `variants`, `variant_index`, `document` "
    "or `other`.",
    ("source_objects", "sample"): "Sample identifier parsed out of the file name.",
    ("source_objects", "flowcell"): "Flowcell identifier parsed out of the file name.",
    ("source_objects", "read_num"): "Which mate of a paired-end read this file holds, 1 "
    "or 2. Null on anything that is not a FASTQ.",
    ("source_objects", "mate_key"): "`<flowcell>:L<lane>` — the key both mates of a pair "
    "share, so R1 and R2 can be matched without parsing "
    "names again.",
    ("source_objects", "last_modified"): "When the store last wrote these bytes.",
    ("source_objects", "content_type"): "MIME type the store records for the object.",
    ("source_objects", "sha256_source"): "Who the digest came from: `publisher` (matched "
    "against the manifest the publisher signed) or "
    "`upload` (our own, which proves only that our "
    "upload round-tripped).",
    ("source_objects", "hash_verified"): "Whether the stored digest and the reference "
    "digest are equal — the proof the copy is "
    "byte-for-byte the publisher's.",
    ("data_lineage", "produced_at"): "When the edge was appended, in UTC. The latest edge "
    "for a target is the one that describes it now.",
    ("data_lineage", "target_schema"): "Schema of the table this edge describes.",
    ("data_lineage", "target_table"): "The table this edge describes.",
    ("data_lineage", "target_rows"): "How many rows that table had when it was produced.",
    ("data_lineage", "source_kind"): "What the input was: `object`, `file`, `table` or `api`.",
    ("data_lineage", "source_ref"): "The input itself — an `s3://` URL, a repository "
    "path, a comma-joined table list, or a service URL.",
    ("data_lineage", "source_version"): "Which version of that input: an object-store "
    "version id, an upstream release, a VEP release "
    "string.",
    ("data_lineage", "source_sha256"): "Digest of the input where one exists, so the edge "
    "names bytes rather than a filename.",
    ("data_lineage", "transform"): "What was done to the input to produce the target, in words.",
    ("data_lineage", "tool"): "The command that did it, e.g. `mva-warehouse pg-derive`.",
    ("data_lineage", "notes"): "Free text — the genes annotated, the run it belongs to, "
    "or the marker saying this edge supersedes an earlier one.",
    ("probe_ledger", "probe_id"): "Sequential id of the submission, assigned on append.",
    ("probe_ledger", "logged_at"): "When the submission was recorded, in UTC.",
    ("probe_ledger", "track"): "Which challenge track the submission was spent on.",
    ("probe_ledger", "probe_type"): "What the probe was for, from the oracle protocol: "
    "`S`, `P`, `F`, `final` or `other`.",
    ("probe_ledger", "submitted_by"): "Which team member's allowance paid for it — the "
    "budget is per registered member.",
    ("probe_ledger", "submission_ref"): "The scorer's identifier for the submission.",
    ("probe_ledger", "payload"): "Exactly what was uploaded, kept in full so a reply can "
    "be decoded later.",
    ("probe_ledger", "n_rows"): "How many rows that payload carried.",
    ("probe_ledger", "response"): "What the oracle returned, verbatim.",
    ("probe_ledger", "score"): "The headline number from that reply.",
    ("probe_ledger", "rationale"): "Why this submission was worth one of the few.",
    ("probe_ledger", "hypothesis_ids"): "Comma-separated claims the probe was fired to "
    "test. Empty means it was not tied to the "
    "register.",
    # ── the research record ───────────────────────────────────────────────────────────
    ("hypotheses", "revision"): "Which revision of the claim this row is. The register is "
    "append-only, so a changed belief is a new revision, "
    "never an edit.",
    ("hypotheses", "step"): "The research step whose goal this claim serves.",
    ("hypotheses", "statement"): "The claim itself, in one sentence.",
    ("hypotheses", "prediction"): "What must be observed if the claim is true. Required — "
    "a claim without one cannot be tested.",
    ("hypotheses", "refuted_by"): "What observation would kill the claim. Required for "
    "the same reason.",
    ("hypotheses", "path"): "Which inheritance pattern the claim is about.",
    ("hypotheses", "gene"): "The gene the claim is about, named rather than positioned.",
    ("hypotheses", "status"): "Where the claim stands: open, supported, refuted or retired.",
    ("hypotheses", "confidence"): "The weighing's number for the claim. A transparent "
    "triage heuristic over the evidence rows, not a "
    "calibrated posterior.",
    ("hypotheses", "reasoning"): "Why the confidence was committed at that value.",
    ("evidence", "evidence_id"): "Sequential id of the observation, assigned on append.",
    ("evidence", "kind"): "What kind of evidence it is — a literature citation, a warehouse "
    "table, a probe reply, a methodology entry.",
    ("evidence", "direction"): "Whether the observation supports, refutes or is neutral "
    "toward the claim.",
    ("evidence", "strength"): "How much weight the observation carries in the weighing.",
    ("evidence", "claim"): "What was observed, in one sentence.",
    ("evidence", "source_ref"): "Where it came from — a PMID, a ClinVar id, a table, a "
    "methodology entry. Required: an unsourced observation is "
    "refused.",
    ("evidence", "lineage_ref"): "The lineage edge or run that produced the observation, "
    "where one exists.",
}
