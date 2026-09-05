"""Track 2: from a mechanism card to a drug-candidate table, out of public APIs only.

The package is case-agnostic. Nothing here names a gene, a disease or a drug: every such
value is read from a **mechanism card** (:mod:`mva.drugs.mechanism`), a small JSON file
that Track 1 hands over. Point it at a different card and the same code answers a
different case.

Read :doc:`README.md` beside this file for the module map and the re-run recipe.
"""

from .mechanism import Direction, MechanismCard, load

__all__ = ["Direction", "MechanismCard", "load"]
