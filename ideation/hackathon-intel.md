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

## 7. Open questions (for us)

1. Team: solo or recruiting? (quota multiplication argues for teammates)
2. Data access requested yet? 85 GB — where do we compute (local disk? cloud)?
3. Both tracks? (Track 2 leverages Track 1's confirmed answer; recommended yes)
4. Budget for compute (FASTQ re-calling is the only expensive step; VCF-first strike is cheap)
