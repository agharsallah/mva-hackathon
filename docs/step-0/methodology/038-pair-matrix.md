# 038 — The compound-het pair matrix: drawing the answer space, including the part that is unknown

**A step-0 platform entry, so it carries no hypothesis.** It records what was built, the
measurements that decided the design, and the cross-check against
[`006`](006-phasing-power-on-bub1b.md).

## Question

Track 1's answer is a **pair** — two different damaging variants in one gene, one on each
inherited copy (a *compound heterozygote*). Every exhibit built so far ranks *variants*.
Nothing shows the object that is actually being searched: the grid of candidate pairs, and
what the callset can say about **phase** (which copy each variant sits on).

The phase evidence is known to be thin. Entry `006` measured it on the canonical MVA gene:
of 1,653 possible pairs, physical phasing resolves 3 trans and 2 cis, leaving 99.7 %
unknown. So the question is not "can the grid be coloured" but:

**Can the pair space be materialised and drawn so that the emptiness is the finding rather
than a rendering failure — and does the pipeline reproduce `006`'s numbers?**

## Inputs

| Input | Shape as read |
|---|---|
| `pg.warehouse.variants_raw` | 5,012,204 all-text rows, the callset as delivered |
| `pg.warehouse.mva_panel_grch38` | 8 panel intervals, `chr`-prefixed |
| `pg.warehouse.panel_annotations` | VEP consequence + gnomAD AF per annotated panel allele |
| Phase rule | `mva.pipeline.compound_het.classify_phase`, unchanged since `006` |
| New code | `src/mva/warehouse/analysis_pairs.py`, `src/mva/viz/phase.py`, one query, one route, `app/src/pages/panel/PairMatrix.tsx` |

## Commands run

```bash
uv run mva-warehouse pg-derive --only panel_het_pairs
uv run mva-warehouse pg-query "SELECT gene, count(*) … FROM pg.results.panel_het_pairs GROUP BY gene"
uv run mva-warehouse pg-query "<the all-filters genotype census over the BUB1B interval>"
uv run mva-viz-api --port 8942
curl -s -w '%{time_total}' 'http://127.0.0.1:8942/api/panel/het-pairs?gene=<each of the 8>'
uv run pytest -q
cd app && npm run typecheck && npm run build
```

The API ran on a private port with its own cache directory, both removed afterwards; the
shared service on 8900 was not touched.

## The design decision: store the members, not the pairs

The grid is quadratic. Storing it would store `n(n−1)/2` copies of the same two rows —
13,203 rows for one gene of 163 alleles, and nothing in them that is not already in the
163. So `panel_het_pairs` holds **one row per heterozygous PASS ALT allele**, and the
cross product happens where the whole gene is already in hand: in `mva.viz.phase` for the
endpoint, and in the browser for the drawing. 484 rows cover all eight genes.

Two consequences follow, and both are deliberate:

* **A `1/2` multi-allelic record contributes two rows**, distinguished by `allele_ix`, so
  the two ALT alleles can face each other in the grid. This is the same split
  `mva.pipeline.vcf.iter_calls` performs, and it is why the axis counts *alleles*, not
  records.
* **The phase rule is not reimplemented.** `mva.viz.phase.as_call` adapts a warehouse row
  into the `Call` that `classify_phase` already takes. There is one owner of "same phase
  set, same phased genotype means cis", and it is the same one `006` measured with.

## Observed output

### Cost

| Step | Cost |
|---|---|
| `pg-derive --only panel_het_pairs` | **10 min 49 s**, 484 rows written |
| `GET /api/panel/het-pairs?gene=…` | **0.47–0.99 s**, live (no cache) |
| Payload | 2.0 KB (5 alleles) to 58.6 KB (163 alleles) |

The derivation is slow for the same reason `panel_candidates` is: it reads
`variants_raw` across the eight panel contigs. That cost is paid once, offline, which is
exactly the trade the viz API exists to make — the browser request that follows is under
a second and never touches the callset.

### Per gene, as measured

| Gene | het alleles | of which `1/2` | pairs | trans | of which auto | cis | unresolved |
|---|---|---|---|---|---|---|---|
| CENPE | 163 | 4 | 13,203 | 3 | 2 | 9 | 99.91 % |
| CEP192 | 104 | 6 | 5,356 | 4 | 3 | 1 | 99.91 % |
| TP53 | 57 | 6 | 1,596 | 4 | 3 | 3 | 99.56 % |
| **BUB1B** | **56** | **2** | **1,540** | **3** | **1** | **2** | **99.68 %** |
| SMC5 | 52 | 6 | 1,326 | 3 | 3 | 3 | 99.55 % |
| DICER1 | 41 | 2 | 820 | 2 | 1 | 0 | 99.76 % |
| CEP57 | 6 | 0 | 15 | 0 | 0 | 0 | 100 % |
| TRIP13 | 5 | 0 | 10 | 0 | 0 | 1 | 90 % |

Every one of the 484 alleles joined an annotation row, so the LEFT-join null path does not
fire on today's data. It is still a LEFT join, still nullable in the contract, and still
covered by tests and the fixture — VEP's coverage is a fact about this annotation run, not
a guarantee.

Exactly **two** alleles in the whole panel are both rare (gnomAD AF < 1 %, the recessive
cutoff) and protein-altering (VEP HIGH or MODERATE), and both are in BUB1B. Every other
gene collapses to zero under that filter.

### The cross-check against entry 006 — and why one number differs

`006` measured **58 het / 3 trans / 2 cis of 1,653 pairs** on BUB1B. This derivation
reports **56 het / 3 trans / 2 cis of 1,540 pairs**. The phase verdicts agree exactly; the
allele count does not, and the difference is fully accounted for.

A genotype census over the same interval, over **all** filters:

| FILTER | GT | records | alleles |
|---|---|---|---|
| PASS | 0/1 | 54 | 54 |
| PASS | 1/1 | 21 | 21 |
| PASS | 1/2 | 1 | 2 |
| MQ40 | 0/1 | 1 | 1 |
| MQ40 | 1/1 | 2 | 2 |
| LowQual;QD2 | 0/1 | 1 | 1 |

That reproduces `006` line by line: **58** het alleles across all filters (54 + 2 + 1 + 1),
**23** hom-alt (21 + 2), **4** non-PASS records, and 81 alleles from 80 records because the
one `1/2` site splits in two.

**The two missing alleles are the two non-PASS heterozygous records** — one `MQ40`, one
`LowQual;QD2`. This derivation is PASS-only by design: a suppressed call is not evidence,
and a pair matrix that offers suppressed alleles as candidates invites a submission built
on a call the caller itself rejected. `006` deliberately did not filter, because its
question was how far phasing reaches, not what is submittable.

Neither dropped allele participates in any resolved pair, which is why trans and cis are
untouched at 3 and 2. The pair count falls from 1,653 to 1,540 purely as arithmetic:
C(58,2) → C(56,2).

**Verdict: agreement.** The one discrepancy is a stated filtering choice, not a defect, and
its size is exactly the two records the choice removes.

### What the grid actually looks like

On BUB1B: 1,540 cells, 5 of them coloured. One of the three trans pairs is the `1/2`
site — trans proven by the genotype itself, with no phasing involved — and the other two
are read-backed. The remaining 1,535 cells are unknown and are shaded by **pair rarity**
instead of being left blank.

Rarity is scored as decades below AF 1, floored at 1e−6, and a *pair* is scored by its
**more common** half (the minimum of the two scores). A compound heterozygote needs both
alleles rare, so the commoner one is the binding constraint; taking the rarer one would
make a rare-plus-common pair look like a candidate.

Under the "rare + protein-altering only" toggle BUB1B collapses to a 2 × 2 grid with a
single off-diagonal cell — the one pair of alleles in the gene that could disable both
copies — and that cell is **unknown**. Neither proven nor excluded, so it stays live. Every
other gene collapses to an empty grid, which the exhibit says in words rather than drawing
as a blank panel.

## Conclusions

1. **The emptiness is the exhibit.** 99.7 % of BUB1B's pairs carry no phase evidence, and
   the honest rendering is a wall of unknown with five lit cells. Drawing only the five
   would have implied phasing did work; leaving the rest grey would have implied nothing
   distinguishes them. Shading the unknown by rarity says both true things at once.
2. **Phasing is confirmatory, not discriminatory — reconfirmed on PASS-only data.** The
   three trans and two cis of `006` survive the PASS filter intact. Nothing about that
   conclusion depended on the suppressed records.
3. **Store the members, cross them at the edge.** 484 stored rows carry a 22,000-pair
   answer space across eight genes, and the endpoint stays under a second because the
   quadratic step happens on data already in memory.
4. **One owner for the phase rule.** The derivation carries `PGT`/`PID` raw and decides
   nothing; `classify_phase` decides everything. The SQL and the classifier cannot drift,
   and the browser can check the server's verdict because the evidence travels with it.
5. **Null is not false.** An allele VEP never saw gets `annotated = false` and **null**
   rarity and null protein-altering — not `false`, which would read as "measured and
   harmless". The path is untaken today and is still tested and fixtured.

## Tests

`tests/test_warehouse_pairs.py`, 21 tests, hermetic: the real derivation SQL runs against
an in-memory DuckDB warehouse whose rows exercise a phased pair, an unphased record, a
`1/2` site, a suppressed record, a hom-alt record, an out-of-interval record, a record on
an unnamed contig, a FORMAT in a different key order, and an unannotated allele.

`tests/test_viz_pairs.py`, 21 tests, hermetic: all four phase states directly (shared phase
set with equal and with differing phased genotypes, different phase sets, absent phase
set, empty-string phase set, `1/2` auto-trans), the index remapping, the summary
arithmetic including the no-pairs case, and the HTTP surface — the envelope, the payload
shape, the raw phase fields reaching the client, a panel gene with no het allele answering
an empty matrix rather than a 404, an unknown gene answering 404, and the missing
parameter answering 422.

`uv run pytest -q` → **925 passed**, 11 failures, all pre-existing in
`tests/test_reads_api.py` and unrelated to this change. `npm run typecheck` and
`npm run build` both clean.
