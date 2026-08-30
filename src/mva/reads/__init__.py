"""The queryable read store: FASTQ → sharded Parquet in the object store.

``schema`` owns the row shape and shard layout; ``engines`` the two conversion paths;
``convert``/``store`` build it; ``verify`` proves it; ``scan`` queries it; ``bench``
races the engines. CLI: ``mva-reads``.
"""
