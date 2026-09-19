# `cases/` — one TOML per illness

**Standing:** added 2026-09-19 with the `[case]` config (`docs/notes/zoo-case-config.md`).
The folder holds this README and `mva-example.toml`, a copy of the shipped default
(`../zoo.example.toml`) with its comments. Nothing else belongs here.

## What a case file is

The zoo has no gene, no disease and no output folder written into its code. All of that is
one block of a TOML file:

```toml
[case]
label               = "…"              # printed in every report header
iteration           = "iteration4"     # docs/<iteration>/ is where the answers land
table_prefix        = "it4"            # <prefix>_model_reports, and the run id prefix
confirmed_gene      = "BUB1B"          # by symbol, never a coordinate; "" = none declared
confirmed_pair_rule = "lof+missense"   # or "all"
phenotype_term_set  = "with-parental"  # which HPO ranking section 5 quotes
hpo_table           = "hpo_gene_scores"
```

The run id is the sha256 of the whole file, so **editing a case file starts a new run** —
that is the point: a different case is a different run, never an overwrite of this one.

## Running a second case

```bash
cp src/mva/zoo/cases/mva-example.toml src/mva/zoo/cases/<name>.toml
$EDITOR src/mva/zoo/cases/<name>.toml          # edit [case]; [run] models if the lanes differ

uv run mva-zoo records --config src/mva/zoo/cases/<name>.toml
uv run mva-zoo score   --config src/mva/zoo/cases/<name>.toml --model alphamissense
uv run mva-zoo run     --config src/mva/zoo/cases/<name>.toml
```

`--case-gene` and `--iteration` override `[case]` for one invocation without editing the
file; `--iteration` also re-derives every default path to `docs/<value>/`.

The full walkthrough — what data a new case needs before any of this runs, and the honest
list of what is still fixed — is [`docs/iteration4/reusability.md`](../../../../docs/iteration4/reusability.md).
