# `models.d/` — one fragment per lane, so two agents never edit one file

**Standing:** opened 2026-09-18 (iteration 4, wave 1, agent *registry*). Empty apart from this
README until the first lane is fetched.

`mva.zoo.registry.load()` reads [`../models.toml`](../models.toml) **plus** every `*.toml` in
this folder, in sorted filename order. A fragment either

- **adds** a model the shared roster does not have (it must then carry every required field), or
- **overrides** fields of one that is there: top-level fields replace, and `params` merges key by
  key — so a fragment can carry a measured `sha256` without restating the URL and the join key.

Two fragments claiming the same model key is an error, not a merge: that is two lanes
disagreeing rather than one lane being refined.

## Why the folder exists

`models.toml` is a shared hot spot (plan §7b): every new lane would otherwise edit the one file
and collide with every other agent doing the same. A fragment is one file, owned by one lane.

## The one rule about digests

A digest is **measured, never typed**. `tools/fetch_zoo_tables.py --fetch <key>` downloads the
table, hashes the bytes it actually wrote, and prints the fragment to paste here:

```toml
# models.d/esm1b.toml — written from the fetch on <date>, entry <n>
[models.esm1b]
params = { sha256 = "<64 hex chars the fetch printed>" }
```

Never edit `models.toml` for a digest, and never fill a `sha256` from a web page.

## After adding a fragment

```bash
uv run python -c "from mva.zoo import registry as r; r.write_cards(r.load(), 'docs/iteration4/cards')"
uv run pytest tests/test_zoo_registry.py -q
```

The first regenerates the JSON cards and the licence manifest; the second re-validates the roster.
