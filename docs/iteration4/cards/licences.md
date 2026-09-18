# Model licences — what this repository may ship

**Generated**, not written: `uv run python -c "from mva.zoo import registry as r; r.write_cards(r.load(), 'docs/iteration4/cards')"`. Edit `src/mva/zoo/models.toml` (or a `models.d/*.toml` fragment), never this file.

Hackathon use is non-commercial, so a non-commercial licence is not a blocker for *running* a model. It is a blocker for *shipping its file*: no score table, no weights and no derived dump of either is ever committed. The last column says what is committed instead.

| model | version | scope | licence | non-commercial | this repo ships | terms |
|---|---|---|---|---|---|---|
| AlphaMissense | AlphaMissense hg38 2023 | mvp | CC-BY-NC-SA-4.0 | **yes** | nothing to fetch — the score is already a warehouse column | [terms](https://zenodo.org/records/8208688) |
| Boltz-2 | boltz-2 (tag recorded at fetch) | opt-b (off) | MIT | no | no weights — the remote image pulls them; digest and venue recorded per run | [terms](https://github.com/jwohlwend/boltz) |
| CADD v1.7 | CADD v1.7 via VEP REST | mvp (off) | CADD non-commercial (free for academic use, licence required otherwise) | **yes** | no file — scores are fetched per allele from the public REST service | [terms](https://cadd.gs.washington.edu/download) |
| ClinPred | ClinPred via VEP REST | opt-a (off) | ClinPred academic use — verify on fetch | **yes** | no file — scores are fetched per allele from the public REST service | [terms](https://sites.google.com/site/clinpred/) |
| ESM1b variant effects (Brandes 2023) | Brandes 2023 ESM1b | mvp | MIT | no | fetch script + digest, never the score file | [terms](https://github.com/ntranoslab/esm-variants/blob/main/LICENSE) |
| ESM2 650M | esm2_t33_650M_UR50D | opt-a (off) | MIT | no | no weights — the model's own installer fetches them; digest per run | [terms](https://github.com/facebookresearch/esm) |
| ESM-C 600M | esmc_600m (github.com/evolutionaryscale/esm, tag recorded at fetch) | opt-b (off) | EvolutionaryScale Cambrian non-commercial licence | **yes** | no weights — the remote image pulls them; digest and venue recorded per run | [terms](https://www.evolutionaryscale.ai/policies/cambrian-non-commercial-license-agreement) |
| EVE | EVE precomputed scores (v1, ~3k genes) | opt-b (off) | MIT — verify on fetch | no | fetch script + digest, never the score file | [terms](https://evemodel.org/) |
| Evo 2 1B | evo2_1b_base | opt-b (off) | Arc Institute open weights — verify on fetch | no | no weights — the remote image pulls them; digest and venue recorded per run | [terms](https://github.com/ArcInstitute/evo2) |
| GPN-MSA | GPN-MSA hg38 precomputed scores (songlab) | opt-a (off) | check on fetch (Hugging Face dataset card) — verify on fetch | no | fetch script + digest, never the score file | [terms](https://huggingface.co/datasets/songlab/gpn-msa-hg38-scores) |
| Nucleotide Transformer v2 500M | InstaDeepAI/nucleotide-transformer-v2-500m-multi-species | opt-b (off) | CC-BY-NC-SA-4.0 | **yes** | no weights — the remote image pulls them; digest and venue recorded per run | [terms](https://huggingface.co/InstaDeepAI/nucleotide-transformer-v2-500m-multi-species) |
| Pangolin | Pangolin (local, CPU) | opt-a (off) | Apache-2.0 — verify on fetch | no | no weights — the model's own installer fetches them; digest per run | [terms](https://github.com/tkzeng/Pangolin) |
| PrimateAI-3D | PrimateAI-3D hg38 precomputed scores | opt-a (off) | Illumina academic/non-commercial, registration required — verify on fetch | **yes** | fetch script + digest, never the score file | [terms](https://primad.basespace.illumina.com/download) |
| PrimeKG | PrimeKG v1 (Harvard Dataverse) | opt-b (off) | MIT | no | fetch script + digest, never the score file | [terms](https://github.com/mims-harvard/PrimeKG) |
| RaSP | RaSP (local, CPU) | opt-b (off) | open — verify on fetch | no | no weights — the model's own installer fetches them; digest per run | [terms](https://github.com/KULL-Centre/_2022_ML-ddG-Blaabjerg) |
| REVEL | REVEL 1.3 via VEP REST | mvp | REVEL non-commercial (free for non-commercial use; other uses by arrangement) | **yes** | no file — scores are fetched per allele from the public REST service | [terms](https://sites.google.com/site/revelgenomics/) |
| SpliceAI | SpliceAI via VEP plugin (iteration 2 annotation pass) | mvp | Illumina SpliceAI non-commercial (academic use) | **yes** | nothing to fetch — the score is already a warehouse column | [terms](https://github.com/Illumina/SpliceAI) |
| ThermoMPNN | ThermoMPNN (local, CPU) | opt-b (off) | MIT — verify on fetch | no | no weights — the model's own installer fetches them; digest per run | [terms](https://github.com/Kuhlman-Lab/ThermoMPNN) |
| TxGNN | TxGNN (pretrained checkpoint, tag recorded at fetch) | opt-b (off) | MIT | no | no weights — the model's own installer fetches them; digest per run | [terms](https://github.com/mims-harvard/TxGNN) |

19 models declared, 4 enabled, 8 under non-commercial terms, 3 catalogue-adjacent (trained on a variant catalogue, so the merge is printed with and without them).
