"""The bait sweep and the FASTQ recovery, on a store small enough to check by hand.

A real pass is 1.07 billion reads against 40 million k-mers; everything that can go wrong
there — a read kept for the wrong reason, a mate written to the wrong line, a sequence
column decoded off by one — is invisible at that scale and obvious at this one.
"""

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from mva.kmer import encode
from mva.kmer.membership import Bait
from mva.reads import recover
from mva.reads.bait import Funnel, Shard, code_matrix, manifest, pair_keys, sweep
from mva.reads.schema import PREFIX, RunFacts

REGION = "ACGTTGCAGGCCAATTCCGGATCGTTAACCGGTTAAGGCCTTAACCGGTTAACCGGTTAACC"
NOISE = "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT"
K = 12


def _bait(sequence=REGION, k=K):
    kmers, valid = encode.window_kmers(encode.codes_of(sequence), k)
    return Bait.of(kmers[valid], k=k, bits=None)


def _rows(sequences, tiles=None):
    tiles = tiles or list(range(1, len(sequences) + 1))
    return pl.DataFrame(
        {
            "tile": pl.Series(list(tiles), dtype=pl.UInt16),
            "x": pl.Series([100 + i for i in range(len(sequences))], dtype=pl.UInt32),
            "y": pl.Series([200 + i for i in range(len(sequences))], dtype=pl.UInt32),
            "sequence": sequences,
            "quality": ["F" * len(s) for s in sequences],
            "is_filtered": [False] * len(sequences),
            "index_pair": ["AACCGGTT+TTGGCCAA"] * len(sequences),
        }
    )


def _store(tmp_path: Path, partitions: dict[tuple[int, int], list[str]]) -> tuple[str, list[Shard]]:
    """Write a miniature store with the real hive layout and companion tables."""
    root = tmp_path / PREFIX
    manifest_rows = []
    for (lane, read_num), sequences in partitions.items():
        directory = root / f"lane={lane}" / f"read={read_num}"
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "part-0.parquet"
        _rows(sequences).write_parquet(target)
        manifest_rows.append(
            {
                "key": f"{PREFIX}/lane={lane}/read={read_num}/part-0.parquet",
                "rows": len(sequences),
                "bytes": target.stat().st_size,
                "lane": lane,
                "read_num": read_num,
                "source": f"sample_L00{lane}_R{read_num}_001.fastq.gz",
            }
        )
    pl.DataFrame(manifest_rows).write_parquet(root / "manifest.parquet")
    pl.DataFrame(
        [
            {
                "source": row["source"],
                "instrument": "A00123",
                "run": "77",
                "flowcell": "HGWCNDSX7",
                "lane": row["lane"],
                "read_num": row["read_num"],
                "control": "0",
                "read_length": len(REGION),
            }
            for row in manifest_rows
        ]
    ).write_parquet(root / "runs.parquet")
    return str(root), manifest(str(root))


def test_code_matrix_decodes_a_uniform_column_without_copying():
    frame = _rows([REGION, NOISE])
    codes = code_matrix(frame["sequence"])
    assert codes.shape == (2, len(REGION))
    assert list(codes[0][:4]) == [0, 1, 2, 3]


def test_code_matrix_pads_ragged_input_with_an_uncallable_base():
    codes = code_matrix(pl.Series(["ACGT", "AC"]))
    assert codes.shape == (2, 4)
    assert codes[1][2] == encode.INVALID and codes[1][3] == encode.INVALID


def test_code_matrix_of_an_empty_column_is_empty():
    assert code_matrix(pl.Series([], dtype=pl.String)).shape == (0, 0)


def test_manifest_lists_every_shard_with_its_partition(tmp_path):
    _, shards = _store(tmp_path, {(1, 1): [REGION], (1, 2): [NOISE]})
    assert {(s.lane, s.read_num) for s in shards} == {(1, 1), (1, 2)}
    assert all(s.rows == 1 for s in shards)


def test_sweep_keeps_only_reads_that_touch_the_bait(tmp_path):
    root, shards = _store(tmp_path, {(1, 1): [REGION, NOISE, REGION]})
    swept, funnel = sweep(root, _bait(), stride=1, shards=shards)
    survivors = swept.collect()
    assert survivors.height == 2
    assert funnel.reads_scanned == 3 and funnel.reads_matched == 2
    assert funnel.by_partition == {"lane=1/read=1": 2}
    assert funnel.matched_fraction == pytest.approx(2 / 3)


def test_sweep_finds_a_read_sequenced_off_the_other_strand(tmp_path):
    revcomp = REGION[::-1].translate(str.maketrans("ACGT", "TGCA"))
    root, shards = _store(tmp_path, {(1, 1): [revcomp]})
    swept, _ = sweep(root, _bait(), stride=1, shards=shards)
    survivors = swept.collect()
    assert survivors.height == 1


def test_sweep_still_finds_a_read_carrying_a_substitution(tmp_path):
    middle = len(REGION) // 2
    mutated = REGION[:middle] + ("A" if REGION[middle] != "A" else "C") + REGION[middle + 1 :]
    root, shards = _store(tmp_path, {(1, 1): [mutated]})
    swept, _ = sweep(root, _bait(), stride=1, shards=shards)
    survivors = swept.collect()
    assert survivors.height == 1


def test_sweep_batches_do_not_change_the_answer(tmp_path):
    root, shards = _store(tmp_path, {(1, 1): [REGION, NOISE] * 5})
    whole, _ = sweep(root, _bait(), stride=1, shards=shards, batch_rows=1000)
    split, _ = sweep(root, _bait(), stride=1, shards=shards, batch_rows=3)
    assert whole.collect().height == split.collect().height == 5


def test_sweep_reports_progress_per_shard(tmp_path):
    root, shards = _store(tmp_path, {(1, 1): [REGION], (1, 2): [NOISE]})
    seen = []
    sweep(root, _bait(), stride=1, shards=shards, progress=lambda s, r, k: seen.append((r, k)))
    assert sorted(seen) == [(1, 0), (1, 1)]


def test_a_bait_nothing_matches_yields_an_empty_frame_not_an_error(tmp_path):
    root, shards = _store(tmp_path, {(1, 1): [NOISE]})
    swept, funnel = sweep(root, _bait(), stride=1, shards=shards)
    survivors = swept.collect()
    assert survivors.height == 0 and funnel.reads_matched == 0
    assert pair_keys(survivors).height == 0


def test_funnel_serialises_the_numbers_the_gate_reads():
    funnel = Funnel(shards=2, reads_scanned=10, reads_matched=4, seconds=1.234)
    assert funnel.as_dict()["matched_fraction"] == 0.4
    assert funnel.as_dict()["seconds"] == 1.2


def test_pair_keys_collapse_the_two_mates_of_one_fragment(tmp_path):
    root, shards = _store(tmp_path, {(1, 1): [REGION], (1, 2): [REGION]})
    swept, _ = sweep(root, _bait(), stride=1, shards=shards)
    survivors = swept.collect()
    assert survivors.height == 2
    assert pair_keys(survivors).height == 1


def test_orphans_name_the_missing_mate(tmp_path):
    root, shards = _store(tmp_path, {(1, 1): [REGION], (1, 2): [NOISE]})
    swept, _ = sweep(root, _bait(), stride=1, shards=shards)
    survivors = swept.collect()
    missing = recover.orphans(survivors)
    assert missing.height == 1
    assert int(missing["read"][0]) == 2


def test_no_orphans_when_both_mates_matched(tmp_path):
    root, shards = _store(tmp_path, {(1, 1): [REGION], (1, 2): [REGION]})
    swept, _ = sweep(root, _bait(), stride=1, shards=shards)
    survivors = swept.collect()
    assert recover.orphans(survivors).height == 0


def test_collect_mates_fetches_the_missing_half_by_key(tmp_path):
    root, shards = _store(tmp_path, {(1, 1): [REGION], (1, 2): [NOISE]})
    swept, _ = sweep(root, _bait(), stride=1, shards=shards)
    survivors = swept.collect()
    filled = recover.collect_mates(root, recover.orphans(survivors), shards)
    assert filled.height == 1
    assert filled["sequence"][0] == NOISE


def test_collect_mates_of_nothing_reads_nothing(tmp_path):
    root, shards = _store(tmp_path, {(1, 1): [REGION]})
    empty = recover.orphans(pl.DataFrame(schema={}).clear())
    assert recover.collect_mates(root, empty, shards).height == 0


def test_to_fastq_writes_aligned_pairs(tmp_path):
    root, shards = _store(tmp_path, {(1, 1): [REGION], (1, 2): [NOISE]})
    swept, _ = sweep(root, _bait(), stride=1, shards=shards)
    survivors = swept.collect()
    filled = recover.collect_mates(root, recover.orphans(survivors), shards)
    written = recover.to_fastq(
        pl.concat([survivors, filled], how="diagonal"), recover.runs(root), tmp_path / "out"
    )
    survivors = swept.collect()
    assert written.fragments == 1 and written.dropped == 0
    first = written.files[1].read_text().splitlines()
    second = written.files[2].read_text().splitlines()
    assert len(first) == len(second) == 4
    assert first[1] == REGION and second[1] == NOISE
    assert first[0].split(" ")[0] == second[0].split(" ")[0]


def test_to_fastq_drops_a_fragment_that_never_found_its_mate(tmp_path):
    root, shards = _store(tmp_path, {(1, 1): [REGION], (1, 2): [NOISE]})
    swept, _ = sweep(root, _bait(), stride=1, shards=shards)
    survivors = swept.collect()
    written = recover.to_fastq(survivors, recover.runs(root), tmp_path / "out")
    assert written.fragments == 0 and written.dropped == 1


def test_rebuilt_name_matches_the_store_codec(tmp_path):
    root, shards = _store(tmp_path, {(1, 1): [REGION], (1, 2): [REGION]})
    swept, _ = sweep(root, _bait(), stride=1, shards=shards)
    survivors = swept.collect()
    written = recover.to_fastq(survivors, recover.runs(root), tmp_path / "out")
    line = written.files[1].read_text().splitlines()[0]
    facts = RunFacts(
        source="x",
        instrument="A00123",
        run="77",
        flowcell="HGWCNDSX7",
        lane=1,
        read_num=1,
        control="0",
        read_length=len(REGION),
    )
    survivors = swept.collect()
    assert line == facts.rebuild_name(1, 100, 200, False, "AACCGGTT+TTGGCCAA")


def test_stride_skips_a_read_that_only_grazes_the_bait(tmp_path):
    """The cost of a stride, made visible: a read sharing fewer bases than k + stride - 1
    with the bait can fall between sampled offsets. H021 measures this on real data."""
    graze = REGION[:K] + NOISE[: len(REGION) - K]
    root, shards = _store(tmp_path, {(1, 1): [graze]})
    close, _ = sweep(root, _bait(), stride=1, shards=shards)
    coarse, _ = sweep(root, _bait(), stride=len(REGION), shards=shards)
    assert close.collect().height == 1
    assert coarse.collect().height == 1  # offset 0 is always sampled
    shifted = NOISE[:5] + REGION[:K] + NOISE[: len(REGION) - K - 5]
    root2, shards2 = _store(tmp_path / "two", {(1, 1): [shifted]})
    assert sweep(root2, _bait(), stride=1, shards=shards2)[0].collect().height == 1
    assert sweep(root2, _bait(), stride=20, shards=shards2)[0].collect().height == 0


def test_spilling_gives_the_same_reads_as_holding_them(tmp_path):
    """The spill exists so a three-hour pass cannot die at the last shard. It must not
    change a single row, or the safe path and the tested path are different programs."""
    root, shards = _store(tmp_path, {(1, 1): [REGION, NOISE] * 4, (1, 2): [REGION] * 4})
    memory, _ = sweep(root, _bait(), stride=1, shards=shards)
    spilled, funnel = sweep(root, _bait(), stride=1, shards=shards, spill_dir=tmp_path / "spill")
    assert spilled.spilled and not memory.spilled
    assert len(spilled.parts) == 2
    assert (
        spilled.collect()
        .sort("lane", "read", "tile")
        .equals(memory.collect().sort("lane", "read", "tile"))
    )
    assert funnel.reads_matched == memory.collect().height


def test_workers_do_not_change_the_answer_or_the_counts(tmp_path):
    root, shards = _store(
        tmp_path, {(1, 1): [REGION, NOISE], (1, 2): [REGION], (2, 1): [NOISE, REGION]}
    )
    serial, one = sweep(root, _bait(), stride=1, shards=shards)
    parallel, many = sweep(root, _bait(), stride=1, shards=shards, workers=4)
    assert one.reads_matched == many.reads_matched == 3
    assert one.by_partition == many.by_partition
    assert (
        parallel.collect()
        .sort("lane", "read", "tile")
        .equals(serial.collect().sort("lane", "read", "tile"))
    )


def test_orphans_and_fastq_read_a_spilled_sweep_without_materialising_it(tmp_path):
    root, shards = _store(tmp_path, {(1, 1): [REGION], (1, 2): [NOISE]})
    spilled, _ = sweep(root, _bait(), stride=1, shards=shards, spill_dir=tmp_path / "spill")
    missing = recover.orphans(spilled)
    assert missing.height == 1 and int(missing["read"][0]) == 2
    filled = recover.collect_mates(root, missing, shards)
    written = recover.to_fastq(
        pl.concat([spilled.collect(), filled], how="diagonal"),
        recover.runs(root),
        tmp_path / "out",
    )
    assert written.fragments == 1 and written.dropped == 0


def test_bait_of_an_empty_kmer_set_matches_no_read(tmp_path):
    root, shards = _store(tmp_path, {(1, 1): [REGION]})
    empty = Bait.of(np.empty(0, dtype=np.uint64), k=K, bits=None)
    assert sweep(root, empty, stride=1, shards=shards)[0].collect().height == 0
