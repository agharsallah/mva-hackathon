# Lens: bioinformatics and computational biology

Use for computational methods applied to biological data: sequence/structure prediction, variant calling, single-cell analysis, phylogenetics, pipelines, databases and resources. This lens combines the ML/CS questions (read `lens-ml-cs.md` first) with the biology questions (`lens-bio.md` sections 1, 6, 7, 8) and adds the failure modes specific to this field. The core question: **is the evaluation free of leakage between biologically related items, and is the prediction validated against biological truth rather than only against a held-out split?**

## 1. Data leakage through biological similarity
The single most common flaw in the field. Random train/test splits leak because homologous sequences, similar structures, related patients, or cells from the same donor carry the same signal.
- Was redundancy reduced (sequence identity clustering with CD-HIT/MMseqs2 at a stated threshold, structural clustering, patient- or donor-level splits)?
- Is the threshold appropriate? 30% identity for protein function is stricter than 90%; the paper should justify its choice.
- Time-based splits for prediction tasks where the database grows (e.g. structures deposited after training cutoff, as CASP does).
- For single-cell: are cells from one sample in both train and test? Are batches split rather than cells?
- If the paper compares to a baseline trained on a different, leakier split, the comparison is invalid.

## 2. Benchmark validity
- Community benchmarks (CASP, CAFA, CAMI, DREAM challenges, GIAB truth sets) versus author-defined ones. Author-defined benchmarks need a reason.
- Label quality: are "true" annotations experimentally verified or computationally inferred (e.g. GO terms with IEA evidence codes)? Training on inferred labels and testing on inferred labels can measure agreement with an older tool rather than biology.
- Class imbalance and the metric: accuracy on rare-variant detection is meaningless; look for precision-recall, MCC, or F1 with the prevalence stated.
- Negative set construction: "random non-interacting pairs" as negatives often makes the task artificially easy.

## 3. Biological validation
- Was any prediction tested experimentally (in this paper or by cited follow-up)? Computational-only validation is a limitation to name explicitly.
- Do the predictions recover known biology (positive controls: known pathways, known binding sites)? Do they predict anything new and testable?
- Are error modes analysed by biological category (e.g. performance on membrane proteins, on low-coverage regions, on rare cell types)?

## 4. Preprocessing and pipeline choices
- Quality control steps, filtering thresholds, normalisation methods - stated with parameters? These often matter more than the model.
- Reference genome/proteome versions and annotation releases (GRCh37 vs GRCh38, Ensembl release, UniProt release) - unstated versions make results irreproducible.
- Batch correction: applied? Could it have removed real biological signal?
- Random seeds for stochastic steps (UMAP, clustering, tree search).

## 5. Comparison to existing tools
- Are the standard tools for the task included (the ones a practitioner would actually use), run with recommended settings and current versions?
- Are runtime and memory compared on the same hardware? Scalability to real dataset sizes (whole genomes, millions of cells)?
- Are default parameters of competitors used while the new tool is tuned?

## 6. Software and resource quality
Apply `code-and-data-assessment.md`, plus:
- Installation path: conda/bioconda recipe, container (Docker/Singularity), pip - or a dependency list that is already stale?
- Input/output formats standard (FASTA, BAM, VCF, h5ad, mmCIF)?
- Test data shipped with the tool; a documented example run.
- For databases: update frequency, versioning, bulk download, licence, API, whether it is still online.
- Long-term availability: institutional URL vs. archive (Zenodo DOI).

## 7. Statistics specific to omics
- Multiple testing correction across genes/features/variants; the number of tests stated.
- Enrichment analysis background set appropriate (all measured genes, not the whole genome).
- Effect sizes (fold changes) with variance, not only adjusted p-values.
- Replicate structure of the underlying experiments (see bio lens section 3) - a tool evaluated on n=1 biological samples inherits that weakness.

## 8. Interpretation
- Predictive performance is not mechanism. Watch for "our model reveals that X regulates Y" from feature importance alone.
- Generalisation across species, tissues, sequencing platforms, and ancestry groups - stated or tested?
- Failure to reproduce prior tools' published numbers: acknowledged and explained?

## Reproducibility score cues for this lens
- 5: code, container, exact data versions and accessions, trained models, documented example, independent use in other papers
- 4: code and data accessions, versions stated, no container or independent use
- 3: code released but data versions or preprocessing unspecified
- 2: method described, tool unavailable or "available on request"
- 1: unspecified reference versions, thresholds or splits

## Vocabulary a newcomer will need
Homology, sequence identity, redundancy reduction, held-out vs time-split, CASP/CAFA, GO evidence codes, precision-recall vs ROC, MCC, batch effect, normalisation, reference build, accession number, container, FASTA/BAM/VCF/h5ad, enrichment analysis, background set, fold change, FDR.
