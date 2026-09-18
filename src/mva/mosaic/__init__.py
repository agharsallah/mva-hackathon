"""Is a chromosome present in the wrong number of copies in *some* of the cells?

The disease this repository is about is named for **mosaic variegated aneuploidy**: cells
carrying the wrong number of copies of a chromosome (*aneuploidy*), only some of the cells
(*mosaic*), and a different chromosome in different cells (*variegated*). This package
answers that question from an ordinary whole-genome callset, and — the part that matters
more — says how small an event it could have found.

Four things live here and nothing else does:

``tables``     the two histograms every model reads, and nothing but histograms
``betabinom``  the over-dispersed allele-balance distribution, and its one-parameter fit
``bdev``       the fold-over B-deviation statistic and the DANFIP fraction estimate
``models``     the five per-chromosome models, as data
``likelihood`` what each model says about the data: the allele mixture and the depth term
``madseq``     fitting those five, and ranking them by BIC
``verdict``    what that ranking is allowed to say -- and the three ways it is refused
``moments``    the null distribution of a folded mean, computed rather than sampled
``simulate``   detection limits: how small an event each arm could have shown
``variegated`` several chromosomes abnormal at once, which is what the disease name means
``baseline``   the leave-one-chromosome-out baseline, which is where *variegated* bites
``arms``       arm assignment, and the check that the reference geometry is the right one

**It knows nothing about this case.** Every function takes counts and returns numbers. It
never reads the warehouse, never sees a gene, and never learns which chromosome anybody
cares about — which is what makes it the reusable half of step 8.

**A negative result here is only as strong as its limit.** The statistic that says "flat"
is worthless without the smallest fraction it could have rejected, so :mod:`~.simulate` is
not an optional extra: nothing in this package should be quoted without it.
"""
