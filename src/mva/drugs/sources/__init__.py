"""One module per public API. Each is a thin adapter: HTTP shape in, row dicts out.

Every function here takes a :class:`mva.drugs.cache.Fetcher` as its first argument, so a
test hands it a fake and no adapter ever opens a socket of its own. No adapter knows the
case: the symbols, ids and search strings all arrive as arguments.
"""
