"""Is each candidate drug safe *for this patient* — the CLI over :mod:`mva.drugs.patient_safety`.

Four verbs, each writing its own artifact under ``--work`` so a later verb never re-does an
earlier one's work:

    uv run python tools/patient_safety.py pharmcat --vcf <vcf> --work build/it4/track2-e56
    uv run python tools/patient_safety.py pgx      --work build/it4/track2-e56
    uv run python tools/patient_safety.py labels   --work build/it4/track2-e56 --onsides <dir>
    uv run python tools/patient_safety.py table    --work build/it4/track2-e56 \
        --out ressources/track2/candidate_safety.tsv

``pharmcat`` is the only verb that touches patient sequence, and everything it writes stays
under ``--work`` (which lives in ``build/``). ``pgx``, ``labels`` and ``table`` emit
actionability words and counts only.

Nothing here is clinical advice. A row is a question for a treating team.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mva.drugs import patient_safety as ps
from mva.drugs import patient_safety_labels as psl
from mva.drugs import patient_safety_run as psr

DEFAULT_WORK = Path("build/it4/track2-e56")
MAPPING = Path("ressources/track2/hpo_to_adverse_terms.tsv")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def do_pharmcat(args: argparse.Namespace) -> int:
    """Subset the callset to the PGx regions, then run PharmCAT strict and absent-to-ref."""
    stage = psr.run_pharmcat(Path(args.work), args.vcf, Path(args.pharmcat), args.java_home)
    print("PharmCAT done; outputs under", stage)
    return 0


def do_pgx(args: argparse.Namespace) -> int:
    """PharmCAT's two runs -> actionability words, callability counts, guideline text."""
    work = Path(args.work)
    payload = psr.pgx_summary(work, Path(args.pharmcat), args.vcf, args.genome_per_kb)
    out = work / "pgx_summary.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"wrote {out} ({len(payload['genes'])} genes)")
    return 0


# --------------------------------------------------------------------------------------
# labels — OnSIDES + the matched comparison set
# --------------------------------------------------------------------------------------


def read_drugs(args: argparse.Namespace) -> list[tuple[str, str]]:
    """(drug, direction) pairs from one or more TSVs, de-duplicated in first-seen order."""
    seen: dict[str, str] = {}
    for spec in args.drug_table:
        path, name_col, dir_col = [*spec.split(":"), "drug_name", "direction_id"][:3]
        with Path(path).open(newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                name = (row.get(name_col) or "").strip().lower()
                if not name or name in seen:
                    continue
                seen[name] = (row.get(dir_col) or "").strip() or "unassigned"
    for extra in getattr(args, "extra_drug", []) or []:
        name, _, direction = extra.partition("=")
        seen.setdefault(name.strip().lower(), direction.strip() or "unassigned")
    return list(seen.items())


def aliases(args: argparse.Namespace) -> dict[str, str]:
    """Candidate name → the RxNorm ingredient name OnSIDES uses for it.

    Needed because the shortlist speaks clinical English ("valproic acid", "nicotinamide")
    and OnSIDES speaks RxNorm ("valproate", "niacinamide"). Every alias is declared on the
    command line and recorded in the run's provenance, never guessed at query time.
    """
    out: dict[str, str] = {}
    for entry in getattr(args, "alias", []) or []:
        name, _, target = entry.partition("=")
        out[name.strip().lower()] = target.strip().lower()
    return out


def do_labels(args: argparse.Namespace) -> int:
    work = Path(args.work)
    drugs = [d for d, _ in read_drugs(args)]
    alias = aliases(args)
    queried = [alias.get(d, d) for d in drugs]
    mapping = ps.read_mapping(Path(args.mapping))
    terms = ps.active_terms(mapping)
    universe = psl.LabelUniverse(Path(args.onsides))
    connection = universe.connect()
    raw = psl.build_matches(connection, queried, list(terms))
    matches = {d: raw[alias.get(d, d)] for d in drugs}
    breadth_raw = psl.effect_breadth(connection)
    breadth = {d: breadth_raw.get(alias.get(d, d), 0) for d in drugs}
    held = [d for d in drugs if matches[d.lower()].labels_total > 0]
    comparison = psl.comparison_set(
        breadth_raw, [alias.get(d, d) for d in held], per_candidate=args.per_candidate
    )
    comparison = [c for c in comparison if c not in {alias.get(d, d) for d in drugs}]
    comparison_matches = psl.build_matches(connection, comparison, list(terms))

    def totals(rows: dict[str, ps.LabelMatch], keys: Sequence[str]) -> tuple[int, int]:
        flagged = sum(1 for k in keys if rows[k.lower()].labels_matched > 0)
        return flagged, len(keys)

    short_hit, short_n = totals(matches, held)
    comp_hit, comp_n = totals(comparison_matches, comparison)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "meddra_terms": {k: list(v) for k, v in terms.items()},
        "label_sources": list(universe.sources),
        "aliases": alias,
        "drugs": {
            drug: {
                "labels_total": matches[drug.lower()].labels_total,
                "labels_matched": matches[drug.lower()].labels_matched,
                "rate": round(matches[drug.lower()].rate, 4),
                "effects": list(matches[drug.lower()].effects),
                "per_effect_labels": dict(matches[drug.lower()].per_term),
                "effect_breadth": breadth.get(drug.lower(), 0),
                "onsides_ingredient": alias.get(drug.lower(), drug.lower()),
            }
            for drug in drugs
        },
        "comparison_set": {
            "rule": (
                f"{args.per_candidate} nearest approved ingredients per candidate, matched on "
                "the number of distinct adverse effects their labels carry; candidates excluded"
            ),
            "members": comparison,
            "ingredients_flagged": comp_hit,
            "ingredients": comp_n,
            "rate": round(comp_hit / comp_n, 4) if comp_n else 0.0,
            "ci95": [round(x, 4) for x in ps.wilson_interval(comp_hit, comp_n)],
            "per_drug": {
                drug: {
                    "labels_total": comparison_matches[drug.lower()].labels_total,
                    "labels_matched": comparison_matches[drug.lower()].labels_matched,
                    "effect_breadth": breadth_raw.get(drug.lower(), 0),
                }
                for drug in comparison
            },
        },
        "shortlist": {
            "members": held,
            "ingredients_flagged": short_hit,
            "ingredients": short_n,
            "rate": round(short_hit / short_n, 4) if short_n else 0.0,
            "ci95": [round(x, 4) for x in ps.wilson_interval(short_hit, short_n)],
        },
    }
    out = work / "label_summary.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    short_rate = short_hit / short_n if short_n else 0.0
    comp_rate = comp_hit / comp_n if comp_n else 0.0
    print(
        f"wrote {out}: shortlist {short_hit}/{short_n} ({short_rate:.2f}) "
        f"vs comparison {comp_hit}/{comp_n} ({comp_rate:.2f})"
    )
    return 0


def do_faers(args: argparse.Namespace) -> int:
    """openFDA paediatric report counts for named drug–reaction pairs."""
    work = Path(args.work)
    results: dict[str, dict[str, int]] = {}
    for pair in args.pair:
        drug, reaction = pair.split("=", 1)
        count = psl.faers_paediatric(drug, reaction)
        results.setdefault(drug.lower(), {})[reaction] = count
        print(f"  {drug:20} {reaction:25} {count}")
    out = work / "faers_summary.json"
    payload = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "query": "patient.patientonsetage 0-17 years, exact MedDRA PT, generic_name",
        "caveat": "spontaneous reports: a numerator with no denominator, never a rate",
        "counts": results,
    }
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print("wrote", out)
    return 0


# --------------------------------------------------------------------------------------
# table — the two-source deliverable
# --------------------------------------------------------------------------------------


def do_table(args: argparse.Namespace) -> int:
    work = Path(args.work)
    drugs = read_drugs(args)
    pgx_payload = json.loads((work / "pgx_summary.json").read_text())
    label_payload = json.loads((work / "label_summary.json").read_text())
    faers_path = work / "faers_summary.json"
    faers_payload = json.loads(faers_path.read_text()) if faers_path.exists() else {"counts": {}}

    calls = {
        gene: ps.GeneCall(
            gene=gene,
            phenotype=block["phenotype_observed"],
            assumed_phenotype=block["phenotype_with_absent_to_ref"],
            observed=bool(block["observed"]),
            positions_total=int(block["positions_total"]),
            positions_called=int(block["positions_called"]),
            note=str(block["callability_verdict"]),
        )
        for gene, block in pgx_payload["genes"].items()
    }
    drug_genes: dict[str, list[str]] = dict(pgx_payload["drug_genes"])
    for entry in args.extra_gene:
        drug, genes = entry.split("=", 1)
        drug_genes.setdefault(drug.lower(), []).extend(
            g for g in genes.split(",") if g not in drug_genes[drug.lower()]
        )
    matches = {
        drug.lower(): ps.LabelMatch(
            drug=drug,
            labels_total=int(block["labels_total"]),
            labels_matched=int(block["labels_matched"]),
            effects=tuple(block["effects"]),
            per_term=dict(block["per_effect_labels"]),
        )
        for drug, block in label_payload["drugs"].items()
    }
    faers = {
        drug: "; ".join(f"{r}={n} reports" for r, n in sorted(pairs.items()) if n > 0)
        or "no paediatric reports for the queried terms"
        for drug, pairs in faers_payload["counts"].items()
    }
    rows = ps.build_rows(
        drugs=drugs,
        drug_genes=drug_genes,
        calls=calls,
        matches=matches,
        recommendations=dict(pgx_payload["recommendations_absent_to_ref"]),
        comparison_rate=float(label_payload["comparison_set"]["rate"]),
        faers=faers,
        sources=args.sources,
        exact_effects=[
            row["meddra_name"]
            for row in ps.read_mapping(Path(args.mapping))
            if row.get("tier") == "exact" and row.get("used_for_flag") == "yes"
        ],
    )
    out = Path(args.out)
    written = ps.write_table(rows, out)
    provenance = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tool": "tools/patient_safety.py table",
        "entry": args.entry,
        "rows": written,
        "inputs": [
            {"file": str(p), "sha256": sha256(p)}
            for p in [work / "pgx_summary.json", work / "label_summary.json", Path(args.mapping)]
            + ([faers_path] if faers_path.exists() else [])
            + [Path(spec.split(":")[0]) for spec in args.drug_table]
        ],
        "parameters": {
            "comparison_rate": float(label_payload["comparison_set"]["rate"]),
            "comparison_rule": label_payload["comparison_set"]["rule"],
            "label_sources": label_payload["label_sources"],
            "extra_gene": list(args.extra_gene),
        },
        "wording": ps.UNFLAGGED_WORDING,
        "clinical_framing": (
            "research exercise; no row advises for or against giving any drug to any patient"
        ),
        "sources": {
            "genomic": (
                "the child's WGS callset, read only through PharmCAT phenotypes: this table "
                "carries actionability words and counts, never a diplotype or a position"
            ),
            "clinical": (
                "the proband's 7 own HPO terms (the 8th is parental history and is excluded), "
                "mapped to MedDRA in ressources/track2/hpo_to_adverse_terms.tsv"
            ),
        },
        "columns": {
            "genome_call": "actionability words per pharmacogene; 'no call' is a result",
            "genome_flag": "yes when a gene is actionable, uncallable, or outside the caller",
            "phenotype_flag": "yes on either trigger; phenotype_flag_reason says which",
            "comparison_set_rate": "share of matched comparison ingredients with any mapped effect",
            "combined_flag": "the two-source verdict; 'unflagged' is never 'safe'",
        },
        "assumptions": (
            "a label adverse effect on the same clinical axis as a patient phenotype is a "
            "potential collision; a pharmacogene the callset cannot answer is a question, not "
            "a normal result"
        ),
        "limitations": (
            "the callset is variant-only, so most PGx positions are no-calls and the "
            "absent-to-ref column is an assumption, not a measurement; OnSIDES v3.1.1 ships no "
            "paediatric ADE subset (its paediatric file is a 200-label annotation gold "
            "standard), so the paediatric view comes from FAERS, which has no denominator"
        ),
        "validation": (
            "furosemide and calcitriol carried as positive controls for the nephrocalcinosis "
            "arm of the mapping; both are matched"
        ),
    }
    (out.with_suffix("").with_name(out.stem + ".provenance.json")).write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n"
    )
    print(f"wrote {out} ({written} rows) and its provenance")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", default=str(DEFAULT_WORK))
    sub = parser.add_subparsers(dest="verb", required=True)

    run = sub.add_parser("pharmcat", help="subset the callset and run PharmCAT both ways")
    run.add_argument("--vcf", required=True)
    run.add_argument("--pharmcat", required=True, help="unpacked pharmcat-pipeline directory")
    run.add_argument("--java-home", default=shutil.which("java") and os.environ.get("JAVA_HOME"))
    run.set_defaults(handler=do_pharmcat)

    summary = sub.add_parser("pgx", help="PharmCAT output -> actionability words and callability")
    summary.add_argument("--pharmcat", required=True)
    summary.add_argument("--vcf", default="", help="callset, for the regional density proxy")
    summary.add_argument("--genome-per-kb", type=float, required=True)
    summary.set_defaults(handler=do_pgx)

    labels = sub.add_parser("labels", help="OnSIDES matched-rate vs a matched comparison set")
    labels.add_argument("--onsides", required=True, help="OnSIDES csv/ directory")
    labels.add_argument("--mapping", default=str(MAPPING))
    labels.add_argument(
        "--drug-table", action="append", required=True, help="path[:name_column[:direction_column]]"
    )
    labels.add_argument("--per-candidate", type=int, default=5)
    labels.add_argument("--extra-drug", action="append", default=[], help="name=direction")
    labels.add_argument(
        "--alias",
        action="append",
        default=[],
        help="candidate=onsides_ingredient, e.g. 'valproic acid=valproate'",
    )
    labels.set_defaults(handler=do_labels)

    faers = sub.add_parser("faers", help="openFDA paediatric report counts")
    faers.add_argument("--pair", action="append", required=True, help="drug=MEDDRA_PT")
    faers.set_defaults(handler=do_faers)

    table = sub.add_parser("table", help="assemble candidate_safety.tsv")
    table.add_argument("--drug-table", action="append", required=True)
    table.add_argument("--mapping", default=str(MAPPING))
    table.add_argument("--out", required=True)
    table.add_argument(
        "--extra-gene",
        action="append",
        default=[],
        help="drug=GENE,GENE for pairs no guideline covers (literature-sourced)",
    )
    table.add_argument("--extra-drug", action="append", default=[], help="name=direction")
    table.add_argument("--sources", default="")
    table.add_argument("--entry", default="")
    table.set_defaults(handler=do_table)

    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
