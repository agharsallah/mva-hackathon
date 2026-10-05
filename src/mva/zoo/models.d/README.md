# `models.d/` — one fragment per lane

A fragment is a TOML file holding one model table, in the same shape as `models.toml`.
It **adds** a model, or **overrides** fields of one already in the roster: top-level
fields replace, `params` merges key by key.

Two fragments claiming the same key is an error, not a merge — that is two lanes
disagreeing rather than one lane being refined.

Why the split: the roster is edited only when the roster itself changes, so two people
adding two lanes never touch one file, and a measured `sha256` arrives as a fragment
rather than as an edit to a shared declaration.

Fragments are read in sorted filename order. Empty today.
