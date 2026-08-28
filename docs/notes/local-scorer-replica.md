# We keep a local replica of the challenge scorer

**Standing:** settled for the duration of the challenge.

The team has eighteen submissions in total and each returns `rank_points`, `f_max`,
`full_match_rank` and `partial_match_rank`. Those replies are the only window onto the
answer key, which makes each one a measurement worth designing before it is spent.

`scorer.py` transcribes the published evaluation code so a candidate submission can be
replayed offline: we can confirm what a probe would return under each hypothesis, and
verify the decode table rather than trusting it. Doing so surfaced the ambiguous zone —
because the F-max sweep keeps the *first* threshold that strictly improves the score, a
second allele ranked far down is indistinguishable from one that is absent.

## Consequences

The replica must track the real scorer. It is transcribed, not reimplemented from the
description, and the tests assert values derived by hand from the scoring rules — for a
singles probe the F-score reduces to `2·tp/(k+2)` — rather than values recomputed the way
the code computes them.

A replica agreeing with itself proves nothing. It is a rehearsal tool, and the leaderboard
remains the only authority.
