"""Test-suite-wide isolation from the machine the tests run on.

A test that reads the developer's own configuration is not a test — it passes or fails
depending on whose laptop it is on. That is not hypothetical here: the reads API resolved
its shared token through the settings loader, the loader searches upward for a ``.env``,
and the repository root holds one. Eleven tests in ``test_reads_api.py`` failed locally
and passed in CI for exactly that reason, because CI has no ``.env``.

So every test runs with two things neutralised:

- the **env file**, pinned to "none" via :data:`mva.warehouse.settings.ENV_FILE_OVERRIDE`;
- the **real environment**, with every key in :data:`~mva.warehouse.settings.DEFAULTS`
  unset, because the real environment wins over the file by design and an exported
  ``PGHOST`` would otherwise still reach the code under test.

What is left is :data:`~mva.warehouse.settings.DEFAULTS` plus whatever the test sets
itself — the same on every machine. A test that wants to exercise env-file discovery
unsets the pin: ``TestSettings`` in ``test_warehouse_postgres.py`` is the one place that
does.
"""

import pytest

from mva.warehouse import settings


@pytest.fixture(autouse=True)
def hermetic_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cut every test off from the ambient configuration of the host."""
    for key in settings.DEFAULTS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(settings.ENV_FILE_OVERRIDE, "")
    settings.clear_env_cache()
