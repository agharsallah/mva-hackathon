# The ranked unit is a pair, not a variant

**Standing:** follows from the shape of the answer key, so it holds as long as the answer
is a compound-heterozygous pair. The scoring function inside is very much provisional.

The answer key is two variants, and rank points are awarded for a row whose variant set
equals it *exactly*. A pipeline that ranks single variants well can still score badly: two
correct variants split across two rows earn partial credit only, however highly they rank.

So `ranking.py` scores `(Variant, Variant)` hypotheses, and pairs must sit in one gene —
two damaging variants in different genes are two unrelated carrier findings, not a biallelic
diagnosis.

## Consequences

The candidate space is quadratic. BUB1B alone yields over a thousand pairs from its
heterozygous calls, and physical phasing resolves a handful
([measured](../../ideation/data-findings.md) §2.4), so the combinatorics cannot be escaped
through phasing. Rarity and consequence have to do the narrowing, which is what makes
[annotation as a port](annotation-as-a-port.md) the critical path rather than a refinement.
