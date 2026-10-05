"""Test-suite-wide isolation from the machine the tests run on.

A test that reads the developer's own configuration is not a test — it passes or fails
depending on whose laptop it is on. That is not hypothetical: the settings loader searches
upward for a ``.env`` and the repository root may hold one, so a test would see a
developer's values locally and the defaults in CI.

So every test runs with two things neutralised:

- the **env file**, pinned to "none" via :data:`mva.settings.ENV_FILE_OVERRIDE`;
- the **real environment**, with every key in :data:`mva.settings.DEFAULTS` unset, because
  the real environment wins over the file by design and an exported value would otherwise
  still reach the code under test.

What is left is :data:`mva.settings.DEFAULTS` plus whatever the test sets itself — the same
on every machine. A test that wants to exercise env-file discovery unsets the pin.
"""

import pytest

from mva import settings


@pytest.fixture(autouse=True)
def hermetic_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cut every test off from the ambient configuration of the host."""
    for key in settings.DEFAULTS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(settings.ENV_FILE_OVERRIDE, "")
    settings.clear_env_cache()
