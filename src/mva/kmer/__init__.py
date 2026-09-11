"""Alignment-free k-mer arithmetic: encode, bait, filter, match.

The package is a **leaf**: it imports nothing from ``mva`` and knows nothing about the
read store, the warehouse or this case. Give it a reference FASTA and a list of intervals
and it gives back a sorted array of canonical k-mers; give it that array and a batch of
read sequences and it says which reads share at least one k-mer with it.

Why it exists. :mod:`mva.reads.scan` answers "does this one 31-mer appear in the reads"
with a multi-literal matcher, and it was measured at 20 literals. Iteration 2 step 2 needs
the opposite shape: ~40 million literals and ~15 million matching reads. An automaton over
40 M literals is not a slower version of that question, it is a different one, so this
package answers it a different way — pack every k-mer into one 64-bit integer and make
membership a sorted-array lookup behind a bitmap prefilter.

Nothing here ever writes patient sequence: the bait is cut from the public reference.
"""

from .encode import INVALID, K, codes_of, strided_kmers, window_kmers
from .membership import Bait, hits

__all__ = ["INVALID", "Bait", "K", "codes_of", "hits", "strided_kmers", "window_kmers"]
