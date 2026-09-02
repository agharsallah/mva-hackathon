"""The ``source-*`` verbs: put the delivery into the landing zone, unchanged.

These are deliberately separate from every other family in the tool. The rest of
``mva-warehouse`` moves *derived* data — things that can be rebuilt if they are wrong.
These move the delivery itself, which cannot be rebuilt, so they hash before sending,
verify after, record what happened, and never overwrite.

The verbs split into three groups by what they touch, and each group is its own module:

===================  ====================================================================
:mod:`.upload`       ``source-scan``, ``source-upload``, ``source-status`` — read and
                     write against the delivery directory already on this machine.
:mod:`.fetch`        ``source-fetch`` — streams the delivery from the publisher (a gated
                     Hugging Face dataset repo) straight into the bucket.
:mod:`.check`        ``source-check`` — audits what is already in the bucket against the
                     publisher's own hash, and refreshes the object inventory.
:mod:`.parser`       the command-line surface: every verb, its flags, its help.
:mod:`.context`      the two seams — ``context.attached`` (the database connection) and
                     ``context.object_store`` (the bucket client) — plus the progress
                     display, so a test replaces one name instead of patching three
                     handler modules.
===================  ====================================================================
"""

from .parser import register

__all__ = ["register"]
