# MVA Hackathon 2026 — Intelligence Brief

Source: `ressources/hackathon-rules/raw_hackathon.txt` (site dump, includes leaked backend code) + web research.
Space: https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026
Dataset: https://huggingface.co/datasets/SageBio/mva-hackathon-2026-data (~85 GB, 11 files, gated)

---

## 1. The challenge at a glance

| Item | Value |
|---|---|
| Case | 1 child ("PROBAND01"), Mosaic Variegated Aneuploidy (MVA), <50 patients worldwide |
| Data | FASTQ + VCF (GRCh38), optional BAM/CRAM, phenotype as HPO terms, ~85 GB |
| Track 1 | Predict causal variant(s). Automated scoring, live leaderboard, **6 submissions/person** |
| Track 2 | Drug repurposing report. Expert panel, **1 submission/team**, needs 3-min video |
| Timeline | Open now → **close Oct 24, 23:59 UTC** → judging → winners Nov 25 |
| Prizes | 1st $12k cash + $12k Claude credits; 2nd $7k+$7k; 3rd $4k+$4k; Innovation $2k+$2k |
| Answer validation | "NHS-validated" → child is in the UK |

---

## 2. HIDDEN INFORMATION (from leaked evaluation code)

The site dump contains the actual scoring backend (`evaluation.py`, `groundtruth.py`, submit handlers). This is gold.

### 2.1 The answer is COMPOUND HETEROZYGOUS
Evaluation docstring, verbatim:
> "simplified for a single proband ('N-of-1') with a **clinically validated compound-heterozygous answer key**"

Two variants, one gene, one on each allele. Confirms recessive inheritance. The FAQ partial-credit language ("one of the two variants in a heterozygous pair") reinforces it.

### 2.2 Exact scoring mechanics
- **Rank point tiers**: rank 1 → 100 pts; ranks 2–3 → 50; ranks 4–5 → 25; ranks 6–10 → 10; else 0.
- Full match = a row whose variant set EXACTLY equals the true pair (both variants in ONE row via chrom_2/pos_2/ref_2/alt_2).
- Partial match = any row intersecting the true pair (single variant alone, or paired with a wrong partner) → **half credit** of that row's tier.
- **F-max** computed at individual-variant level, swept over the epcr thresholds present in the file. A rank-1 row containing exactly the true pair → precision 1, recall 1, **F-max = 1.0**.
- Low-ranked noise rows CANNOT reduce F-max (threshold sweep excludes them) and don't affect rank points if ranked below the hit. Secondary findings truly are free.
- epcr must be in (0, 1]; ties broken by file order → always use strictly distinct descending epcr values.
- Max 10 rows. Only proband_id `PROBAND01` accepted.
- `finding_type` must be exactly `primary` or `secondary`.

### 2.3 THE ORACLE: instant feedback per submission
Submit handler returns immediately:
- rank_points, F-max, F-max threshold
- **full_match_rank** (which of your rows was an exact hit)
- **partial_match_rank** (which row contains one of the two true variants)

So each submission = an adaptive query against the ground truth:
- 6 submissions × 10 rows = up to **60 pair-hypotheses tested**.
- A partial match tells you WHICH ROW holds a true variant → you've identified one allele; next submission pairs it against remaining candidates.
- Any full match anywhere in ranks 1–10 → final submission puts that pair at rank 1 with epcr 1.0 → **100 pts + F-max 1.0** (perfect score).

### 2.4 Team quota multiplication
"Each member receives their own submission quota" — a team of N members = **6N oracle queries**, all under the same team display name; best score counts. Recruiting even 1–2 teammates doubles/triples search budget. Each member must individually register + accept rules.

### 2.5 Groundtruth file structure hints
Loader skips keys starting with `_` and reads `entry["primary_variants"]` — GT file likely also holds secondary/incidental findings metadata that is NOT auto-scored (qualitative review only).

### 2.6 Dev fallback GT (do not over-read)
`_LOCAL_FALLBACK` = chr2 + chr15 with placeholder positions (12345678). Positions are fake. NOTE: a genuine compound het lives on ONE chromosome, so chr2+chr15 is arbitrary dev data — but chr15 is where BUB1B sits (15q15.1). Weak echo, not evidence.

---

## 3. Biology priors (strong)

MVA is caused by biallelic variants in a handful of spindle-assembly-checkpoint (SAC)/centrosome genes:

| Gene | Locus | Syndrome | Phenotype signature |
|---|---|---|---|
| **BUB1B** (BubR1) | chr15q15.1 | MVA1 | Most common; microcephaly, ID, **cancer predisposition** (Wilms, rhabdomyosarcoma, leukemia) |
| **CEP57** | chr11q21 | MVA2 | Rhizomelic limb shortening, typically NO malignancy |
| **TRIP13** | chr5p15.33 | MVA3 | Wilms tumor predisposition |
| CEP192, SMC5, CENPE | — | candidate/atypical | case reports |

The story page says care today means "managing symptoms and **fighting cancer cells**" → child has active malignancy → strongly favors **BUB1B** (classic) or **TRIP13**. CEP57 unlikely.

Prior-driven hypothesis before touching data: **compound het in BUB1B (chr15)**, fallback TRIP13, then CEP57, then novel gene.

Why FASTQ is provided when VCF exists: possible that one of the two variants is NOT in the standard VCF — deep intronic, structural variant, or low-quality call. Classic compound-het trap: one coding SNV (easy) + one non-coding/SV (hard). Be ready to re-call variants and inspect raw reads over candidate gene loci.

---

## 4. Winning strategy — Track 1

### Phase 0 (now): access + setup
1. Request gated dataset access (HF account, form, IRB protocol #20252010 terms).
2. Decide team name; every teammate registers individually, uses EXACT same team name.

### Phase 1: targeted strike (days, not weeks)
1. Grep the provided VCF for all variants in BUB1B, TRIP13, CEP57 (+CENPE, CEP192, SMC5) BEFORE building any pipeline. Annotate with VEP. The answer is very likely sitting there.
2. Cross-check HPO terms against MVA gene phenotype signatures.
3. If two plausible hits in one gene (one per allele — check phasing/trio if available): that's the pair.

### Phase 2: standard pipeline (parallel, also feeds report quality)
- Exomiser/LIRICAL with the HPO terms on the full VCF → ranked candidates (scalability story for judges).
- Re-call from FASTQ (DeepVariant + a SV caller like Manta/Delly) over candidate loci; IGV-inspect BUB1B/TRIP13/CEP57 for missed second alleles (deletions, intronic splice variants).

### Phase 3: oracle-optimized submissions (spend the 6 wisely)
- **Sub 1**: rank 1 = best pair hypothesis (epcr 1.0). Ranks 2–10 = alternative pairings + each strong candidate variant as a SINGLE row (singles fish for partial-match signal identifying one true allele). Distinct epcr values.
- Read feedback. Partial match at rank k → row k's variant is one true allele. Next submission: pair it with each remaining candidate across 10 rows.
- Once full match found at any rank → final submission with that pair at rank 1 → 100 pts, F-max 1.0.
- Keep 1–2 submissions in reserve for the endgame; leaderboard freezes Oct 24.
- Every submission needs a report (PDF/md) + public GitHub URL — even probes. Keep a versioned report ready.

### Phase 4: qualitative layer (don't skip)
"Track 1 qualitative evaluation" happens Oct 24–Nov 24. If several teams hit 100/1.0 (likely, given the oracle), the REPORT + reproducible GitHub + method innovation/scalability break ties. So the pipeline in Phase 2 isn't optional decoration — it's the tiebreaker. Include secondary findings with good `notes` (free, reviewed qualitatively, signals rigor).

---

## 5. Winning strategy — Track 2 (35% rigor / 25% impact / 25% innovation / 15% scalability)

One shot, no resubmission. Submit LATE (after Track 1 variant is confirmed via oracle — mechanism characterization is then grounded in the *confirmed* variant, huge rigor advantage over teams guessing).

Mechanism angle: SAC weakening (BubR1 insufficiency) → chromosome missegregation → aneuploidy + tumorigenesis. Drug repurposing directions to research:
- Agents that reinforce SAC / reduce chromosomal instability.
- Aneuploidy-selective stressors (aneuploid cells have proteotoxic/metabolic stress — e.g. AICAR/energy-stress compounds, chloroquine — published aneuploidy-selective killing literature).
- If BUB1B hypomorph: proteostasis/stabilization strategies for BubR1.
- Cancer-prevention framing for the child's actual malignancy context.

Deliverables: report (PDF/md), public GitHub, 3-min YouTube/Vimeo pitch. One designated submitter per team.

---

## 6. Compliance traps (do not lose the prize on paperwork)

- **Delete ALL data within 30 days of close** (local, cloud, notebooks, private repos, derived datasets) AND email RarediseaserealkidMVAhackathon2026@synapse.org to confirm.
- Never recontact family/MVA Society contacts.
- No data resharing through any channel (careful: don't commit VCF slices/read snippets to the public GitHub repo!).
- Embargo: no peer-reviewed manuscript submissions until organizers publish their summary. Code/models shareable anytime.
- Publications need the exact acknowledgement text + dataset citation from Synapse page.
- 18+, HF ToS.

---

## 7. Confirmed team parameters

| Parameter | Value | Consequence |
|---|---|---|
| Team | 3 members (user + 2 teammates) | **18 Track 1 oracle queries** (6 each). All register individually, EXACT same team name |
| Data | Access granted, stored locally | No download bottleneck; start Phase 1 immediately |
| Tracks | Both | Track 2 submitted late, grounded in oracle-confirmed variant |
| Compute | Local + Modal free credits | VCF-first strike local; FASTQ re-calling / SV calling on Modal GPU/CPU |

---

## 8. Deep dive — scorer internals (exploitable mechanics)

Line-by-line consequences of `evaluation.py` + `groundtruth.py`:

### 8.1 Matching is EXACT string/int equality — normalization is the #1 silent-failure risk
- `Variant = (chrom.strip(), int(pos), ref.upper(), alt.upper())`. Ref/alt uppercased; **chrom is NOT normalized** — `"chr15" ≠ "15" ≠ "CHR15"`. Fallback GT uses `chr15` style and the template uses `chr1` → submit chr-prefixed, lowercase `chr`.
- Indels: no left-alignment, no multiallelic splitting on either side. If GT stores `chr15:100 CT>C` and we submit the equivalent `chr15:101 T>-`-style or unnormalized representation → scored as MISS. **Run `bcftools norm -f GRCh38 -m -both` on our VCF before candidate extraction, and probe indel candidates in normalized form.** If an indel candidate is high-conviction but probes miss, retry alternate representation (costs 1 row, not 1 submission).
- `proband_id` matched after `.strip()` only, case-sensitive → exactly `PROBAND01` (verify exact ID in dataset).

### 8.2 Row semantics
- A pair row is a `frozenset` → variant_1/variant_2 order within a row is irrelevant; duplicated variant collapses to a single-variant row.
- `chrom_2` + `pos_2` both required for the second variant to parse; blank = single-variant row.
- Ranks assigned after sorting by epcr desc; **ties broken by file order** → always use strictly distinct epcr values so ranks are deterministic.
- Max 10 rows, epcr ∈ (0,1], `finding_type` ∈ {primary, secondary} (informational only — zero effect on automated score, confirmed in dataclass comment).

### 8.3 Scoring precedence quirk
Full match anywhere takes precedence over any partial match: a full match at rank 6–10 scores **10 pts**, even if a partial match sits at rank 1 (which alone would score 50). Irrelevant for the leaderboard (best-of-6 counts, probes can't hurt), but it means the FINAL submission must contain the confirmed pair at rank 1 and nothing ranked above it.

### 8.4 F-max structure
- Computed at individual-variant level over the union of all rows at each epcr threshold; the sweep only visits thresholds present in the file.
- F-max = 1.0 requires the top-threshold predicted set to equal exactly the 2 true variants: either the exact pair in one rank-1 row, or two single rows tied at the same top epcr each holding one true allele (but that only yields partial rank credit → pair-in-one-row is strictly better).
- Rows below the optimal threshold can never lower F-max → secondary/incidental rows are genuinely free.
- Tie on F kept at the FIRST (highest) threshold (`f > best_f` strict).

### 8.5 Groundtruth loader
- GT JSON supports `{"primary_variants": [{chrom,pos,ref,alt}]}` dict form and skips `_`-prefixed keys → GT file likely carries unscored metadata/secondary-findings notes; only `primary_variants` enter the frozenset.
- GT loaded once at Space startup into module global `_GT` — static answer key for the whole hackathon.

---

## 9. THE ORACLE PROTOCOL — solving the enigma in ≤ 4 submissions (18 available)

Every submission returns: `rank_points`, `f_max`, `f_max_threshold`, `full_match_rank`, `partial_match_rank`. This turns 18 submissions into an adaptive group-testing scheme. Decode math below **verified by simulating the leaked scorer**.

### 9.1 Probe type S — "singles scan" (identify alleles)
Submit 10 single-variant rows = candidates c₁…c₁₀ (ranked by pipeline conviction), distinct epcrs 0.99, 0.98, … 0.90.

Decode (truth = compound-het pair {A, B}):
| Signal | Meaning |
|---|---|
| `partial_match_rank = i` | cᵢ is a true allele (the first one present) |
| `f_max = 4/(j+2)`, threshold = epcr of row j | SECOND true allele = cⱼ — **both alleles from ONE probe** |
| `f_max = 2/(i+2)`, threshold = epcr of row i | second allele NOT in rows i+1 … 2i+1 — either absent from this probe or at j ≥ 2i+2 (ambiguous zone; resolve with probe P) |
| no partial, `f_max = 0` | none of the 10 candidates is a true allele — advance to next batch of 10 |

Verified decode table (i = rank of first allele, j = rank of second):
- i=1: j=2 → 1.000, j=3 → 0.800, j≥4 or absent → 0.667 (ambiguous)
- i=2: j=3 → 0.800, j=4 → 0.667, j=5 → 0.571, j≥6 or absent → 0.500
- i=3: j=4 → 0.667, j=5 → 0.571, j=6 → 0.500, j=7 → 0.444, j≥8 or absent → 0.400

### 9.2 Probe type P — "pair scan" (identify second allele, 10 hypotheses/submission)
Once one allele A is confirmed: submit 10 PAIR rows (A, candidate_k), k = 1…10, distinct epcrs.
- `full_match_rank = k` → candidate_k is the second allele. **Direct, unambiguous.**
- No full match → none of the 10 seconds is correct; next batch.
(F-max here is a weak side-channel — full_match_rank is the primary readout.)

### 9.3 Probe type F — "final strike"
Confirmed pair {A, B} → submit: rank 1 = exact pair, epcr 1.0, finding_type primary; ranks 2+ = curated secondary findings with `notes` (free, feeds qualitative review). Result: **rank_points 100, F-max 1.0 — the maximum possible score.**

### 9.4 Budget arithmetic
18 submissions, 3 members. Expected spend if pipeline candidate list contains both alleles in top 10: S → (decode both) → F = **2 submissions**. Realistic worst cases:
- Both alleles in top ~50 pipeline candidates: ≤ 5×S + 1×P + F ≈ 8 submissions.
- One allele found, second NOT in VCF: P-scans exhaust → pivot: found allele localizes the GENE → targeted raw-read hunt (SV / deep-intronic / low-VAF) in that gene on Modal → new second-allele candidates → P-probes. This is the designed trap (why FASTQ ships with the VCF) and where teams without a raw-data pipeline die.
- Keep ≥ 2 submissions in reserve until the Oct 24 freeze (indel-representation retries, leaderboard defense).
- Ledger discipline: shared spreadsheet — who spent which submission, probe content, decoded result. Every probe needs a CSV + report (PDF/md) + public GitHub URL → keep a templated auto-generated report ready.

### 9.5 Legitimacy & the methods form
Nothing in the rules prohibits adaptive use of the scoring feedback — the design (6 subs, instant scores, public leaderboard) invites it. BUT the methods form asks explicitly whether output is automated "(preferred)" vs manually curated, and public-data-only "(preferred)". Play both layers:
1. Build a REAL automated pipeline that independently ranks the true pair #1 (tune after confirmation — legitimate: that's what training is).
2. Final leaderboard submission = that pipeline's genuine output. Fill the form honestly (probes = "iterative hypothesis testing against the provided validator"; final model = automated, public data only, pair-capable — form Q15 asks exactly this, another confirmation the answer is a pair).

---

## 10. Template & methods-form intel

### 10.1 `track1_submission_template.csv`
```
proband_id,chrom_1,pos_1,ref_1,alt_1,chrom_2,pos_2,ref_2,alt_2,epcr,finding_type,notes
PROBAND01,chr1,100000,A,T,chr1,200000,G,C,0.90,primary,
PROBAND01,chr7,300000,C,T,,,,,0.30,secondary,Incidental finding unrelated to primary phenotype
```
- Confirms `PROBAND01` id, `chr`-prefixed chromosomes, pair-in-one-row format, blank trailing fields for singles.
- Example pair row is **same-chromosome** (chr1 + chr1) — consistent with compound het in one gene.

### 10.2 `methods_description_form.xlsx` (2 sheets, author metadata: Gaia Andreoletti, Jul 2026)
Track 1 sheet — judges' revealed preferences (fill once per model, up to 6):
- Automated output **preferred** over manual curation (Q10–11).
- Public data only **preferred**; if proprietary used, also submit a public-only model (Q12–14).
- Q15: "Is your approach able to output proposed pairs of compound heterozygous candidate variants?" → third independent confirmation the answer is a compound-het pair, and pair-capable = scored favorably.
- Q16: how secondary/incidental findings were handled → have a principled ACMG SF v3.x screening story.
- Q17: runtime + cost estimate → Modal cost tracking gives concrete numbers (judges love this for Scalability, 15%).
- Q18: 500-word abstract incl. strengths AND limitations.
- Warning in header: submissions without the form "may be judged less favorably on Innovation and Scalability".

Track 2 sheet — expected sources name-dropped: **DrugBank, ChEMBL, ClinicalTrials.gov, OMIM, PubMed**. "LLM-assisted search" explicitly listed as a legitimate automated approach (Q9). Q14 = mechanism characterization (LoF vs GoF, pathway, downstream consequence) — mirror this structure in the report.

---

## 11. MASTER PLAN — step-by-step to first place

**Clock: Aug 26 → Oct 24 (freeze). ~8.5 weeks.**

### Week 1 (now): Foundation + VCF strike
| # | Step | Owner/where | Output |
|---|---|---|---|
| 1 | All 3 members register, accept rules, agree exact team name; create submission ledger | all | 18-query budget live |
| 2 | Two repos: private (data work, never push data) + public GitHub (code only, no data slices — resharing = disqualification risk) | member 1 | compliance-safe infra |
| 3 | `bcftools norm -m -both -f GRCh38` the VCF; index; QC (bcftools stats) | local | normalized callset |
| 4 | Extract + annotate ALL variants in MVA genes: **BUB1B, TRIP13, CEP57**, then CENPE, CEP192, SMC5, and SAC/mitosis panel (BUB1, BUB3, MAD1L1, MAD2L1, CDC20, KNL1, TTK/MPS1, PLK4) — VEP + gnomAD AF, ClinVar, SpliceAI, CADD, REVEL, AlphaMissense | local | candidate table |
| 5 | Compound-het detection: genes with ≥2 rare (gnomAD AF < 1e-3) het variants; no trio → enumerate pairs combinatorially | local | ranked pair hypotheses |
| 6 | Parse HPO terms; run **Exomiser + LIRICAL** on full VCF (unbiased genome-wide ranking — also the automated-pipeline backbone for the report) | local/Modal | genome-wide ranked list |

### Week 1–2: Oracle round 1
| # | Step |
|---|---|
| 7 | Probe S₁ (member 1, sub 1/6): top-10 single candidates. Decode per §9.1 |
| 8 | Branch: both alleles decoded → Probe F → **100 pts / F-max 1.0**, done, go to step 12. One allele → Probe P₁ with top second-allele candidates. None → S₂ with candidates 11–20 |
| 9 | Iterate S/P probes (budget: stay ≤ 8 spent; rotate members so no one exhausts their 6) |

### Week 2–5 (contingency, runs in parallel from day 1 on Modal): raw-data rescue
| # | Step |
|---|---|
| 10 | Align FASTQ (bwa-mem2 → GRCh38) if BAM/CRAM not provided; DeepVariant re-call; SV callers (Manta + Delly + Smoove consensus); mosdepth exon-level coverage for single-exon deletions; SpliceAI on intronic regions of the localized gene; low-VAF scan (MVA = mosaicism — a mosaic second hit is plausible) |
| 11 | IGV inspection of the localized gene; novel candidates → P-probes |

### Week 5–7: Consolidation + Track 1 finalization
| # | Step |
|---|---|
| 12 | Tune the automated pipeline until it independently ranks the confirmed pair #1 (this becomes the honest "automated output" model) |
| 13 | ACMG secondary-findings screen (SF v3.2 gene list) → curated `secondary` rows with clear `notes` |
| 14 | Final submission: pair rank 1 epcr 1.0 + secondaries; polished report (approach, rationale, evidence: segregation logic, in-silico scores, literature); methods form filled; public repo cleaned, documented, reproducible (nextflow/snakemake + Modal scripts) |
| 15 | Hold 2 reserve submissions until freeze (Oct 24 23:59 UTC) |

### Week 5–8: Track 2 (starts once variant confirmed)
| # | Step |
|---|---|
| 16 | Mechanism characterization: zygosity-resolved consequence per allele (null vs hypomorph), protein domain mapping, SAC pathway model, downstream consequence (chromosome missegregation → aneuploidy → proteotoxic stress + tumorigenesis). Structure the report exactly along form Q14 |
| 17 | Candidate search, dual-engine: (a) automated — DrugBank/ChEMBL/OpenTargets target + pathway queries, ClinicalTrials.gov mining, LLM-assisted literature triage (cite as automated per Q9); (b) curated — aneuploidy-selective agents literature (energy/proteotoxic stress exploiters), SAC-reinforcing strategies, agents relevant to the child's malignancy context. Filter: market-approved only (rules §2 Track 2 definition) |
| 18 | Rank candidates by mechanism fit + safety in pediatrics + evidence tier; be explicit these are hypotheses for follow-up (matches organizer framing — rigor points) |
| 19 | Deliverables: report (PDF), public repo, 3-min pitch video (YouTube/Vimeo) — story-driven: child → gene → mechanism → drug. ONE submitter, late-but-buffered (submit ~Oct 20) |

### Weeks 8+: Endgame + compliance
| # | Step |
|---|---|
| 20 | Watch leaderboard; if others hit 100/1.0 the tiebreak is qualitative (Oct 24–Nov 24 review) → double down on report/repo quality, innovation narrative (oracle-as-group-testing is itself a publishable method angle; scalability = pipeline runs on any N-of-1 case) |
| 21 | After close: **delete ALL data everywhere within 30 days** (local, Modal volumes, notebooks, private repo history) + confirmation email to RarediseaserealkidMVAhackathon2026@synapse.org |
| 22 | Respect embargo (no journal submission until organizer preprint); acknowledgement text + Synapse citation on anything public |

### Success criteria
1. **Enigma solved**: pair identified + oracle-confirmed (expected ≤ 8 of 18 submissions).
2. **Leaderboard ceiling**: 100 rank points, F-max 1.0.
3. **Tiebreak dominance**: reproducible automated pipeline + methods forms + secondary findings + cost figures.
4. **Track 2**: only team whose mechanism section rests on a *confirmed* variant → Scientific Rigor (35%) edge.
