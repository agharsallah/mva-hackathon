"""The two LLM modes, behind one function signature.

A *mode* is the config key ``[llm] mode``. It selects a **transport**: something that takes a
prompt string and returns a :class:`Reply` — the text, the model id that actually answered,
what it cost and how long it took. Everything else in :mod:`mva.zoo.narrate` is written
against that one shape, so adding a third provider is a new class here and nothing else.

============  ==================================================================
``none``      no transport. The MVP: section 6 stays hand-written, nothing leaves
              the laptop, and the run is fully reproducible.
``claude-code`` the Claude Code CLI already on ``PATH``, headless:
              ``claude -p --output-format json``, prompt on stdin, reply parsed out
              of the JSON. No new key and no new dependency — which is why the plan
              makes it the first mode. It has **no temperature flag** (checked
              against Claude Code 2.1.278 ``--help``), so ``temperature = 0`` in the
              config is honoured by ``nebius`` and *recorded as not settable* here.
``nebius``    LiteLLM → Nebius AI Studio, an open-weights instruction model named in
              the config. Needs ``NEBIUS_API_KEY`` and the ``zoo-ml`` dependency
              group.
============  ==================================================================

Both transports are constructed by :func:`build_transport` and both are injectable: a test
passes its own callable and no process is spawned and no network is touched.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

__all__ = [
    "MODES",
    "ClaudeCodeTransport",
    "FakeTransport",
    "LlmSettings",
    "NebiusTransport",
    "Reply",
    "Transport",
    "build_transport",
]

#: The values ``[llm] mode`` accepts. ``none`` means "do not call an LLM at all".
MODES: tuple[str, ...] = ("none", "claude-code", "nebius")

#: The Nebius model id used when the config names none. Open item **O1** of the plan asks for
#: the largest open-weights instruction model listed on Nebius AI Studio *at run time*; the
#: run records what it actually got back, so this default is a starting point, not a claim.
DEFAULT_NEBIUS_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"

#: How long one headless call may take before it is abandoned. A narrative is ~200 words; a
#: call that has not answered in five minutes is stuck, not slow.
DEFAULT_TIMEOUT_S = 300.0


@dataclass(frozen=True)
class LlmSettings:
    """The config's ``[llm]`` block: which mode, which model, how hot, how long.

    Read from the case TOML rather than from :class:`mva.zoo.case_config.Config`, which
    carries only ``mode``. Keeping the other three keys here means this optional feature adds
    no field to the shared case dataclass — the run config stays one file, and a build
    without ``narrate`` parses it identically.
    """

    mode: str = "none"
    model: str = ""
    temperature: float = 0.0
    max_words: int = 200

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> LlmSettings:
        """Parse ``[llm]`` out of a case TOML. A missing block is mode ``none``."""
        import tomllib  # stdlib, imported where it is used

        with Path(path).open("rb") as handle:
            block = tomllib.load(handle).get("llm", {})
        return cls(
            mode=str(block.get("mode", "none")),
            model=str(block.get("model", "") or ""),
            temperature=float(block.get("temperature", 0.0) or 0.0),
            max_words=int(block.get("max_words", 200) or 200),
        )

    def transport(self) -> Transport | None:
        """The transport this block selects, or ``None`` for mode ``none``."""
        return build_transport(self.mode, model=self.model, temperature=self.temperature)


@dataclass(frozen=True)
class Reply:
    """What one LLM call returned, with everything needed to audit it later."""

    text: str
    model_id: str = ""
    seconds: float = 0.0
    dollars: float = 0.0
    raw: str = ""


class Transport(Protocol):
    """Anything that can answer a prompt. One method, so a test double is three lines."""

    @property
    def mode(self) -> str:
        """The mode name this transport implements — stored on the narrative row.

        Read-only in the protocol so a ``frozen=True`` dataclass satisfies it: a frozen
        field is a read-only attribute, and a protocol that declares a *writable* one would
        reject every transport in this module.
        """

    def __call__(self, prompt: str) -> Reply: ...


# ---------------------------------------------------------------------------------------
# claude-code
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ClaudeCodeTransport:
    """``claude -p --output-format json`` with the prompt on stdin.

    Three flags matter and each is there for a reason:

    ``--restricted``
        removes the command- and code-running tools. The task is "read this JSON and write a
        paragraph"; a writer that can run shell commands is a writer whose output is not a
        function of its prompt.
    ``--strict-mcp-config``
        ignores every MCP server configured on this machine, so the call does not depend on
        what happens to be installed today.
    ``cwd`` = a fresh empty directory
        Claude Code discovers a ``CLAUDE.md`` from its working directory. Running from the
        repository root would silently prepend this project's instructions to every prompt —
        the stored prompt would then not be the whole input, which is the one property the
        ``results.<prefix>_narratives`` row exists to guarantee.

    ``model`` pins ``--model``; empty means "whatever the CLI's own default is", and either
    way the id that answered is read back out of the reply's ``modelUsage`` block.
    """

    mode: str = "claude-code"
    model: str = ""
    binary: str = "claude"
    timeout_s: float = DEFAULT_TIMEOUT_S

    def __call__(self, prompt: str) -> Reply:
        executable = shutil.which(self.binary)
        if executable is None:
            raise RuntimeError(
                f"mode 'claude-code' needs the {self.binary!r} CLI on PATH; it is not there"
            )
        argv = [executable, "-p", "--output-format", "json", "--restricted", "--strict-mcp-config"]
        if self.model:
            argv += ["--model", self.model]
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="mva-narrate-") as sandbox:
            completed = subprocess.run(  # fixed argv, no shell, prompt on stdin
                argv,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                cwd=sandbox,
                check=False,
            )
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip()[-400:]
            raise RuntimeError(f"claude -p exited {completed.returncode}: {tail}")
        return _reply_from_claude_json(completed.stdout, time.monotonic() - started)


def _reply_from_claude_json(stdout: str, seconds: float) -> Reply:
    """Pull the text, the model id and the cost out of ``--output-format json``."""
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"claude -p did not return JSON: {error}") from error
    if payload.get("is_error"):
        raise RuntimeError(f"claude -p reported an error: {payload.get('result', '')[:400]}")
    usage = payload.get("modelUsage") or {}
    model_id = next(iter(usage), "") if isinstance(usage, dict) else ""
    return Reply(
        text=str(payload.get("result", "")).strip(),
        model_id=str(model_id),
        seconds=round(float(payload.get("duration_ms", seconds * 1000)) / 1000.0, 3),
        dollars=float(payload.get("total_cost_usd", 0.0) or 0.0),
        raw=json.dumps({key: payload.get(key) for key in ("session_id", "num_turns", "usage")}),
    )


# ---------------------------------------------------------------------------------------
# nebius
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class NebiusTransport:
    """LiteLLM → Nebius AI Studio. ``temperature`` is honoured here; the CLI has no such knob.

    LiteLLM is imported inside the call, not at module import, for the same reason every
    heavy import in this package is: ``mva.zoo`` must stay importable by the API, by a test
    and by a second case without a machine-learning stack installed.

    **Not run in iteration 4.** ``NEBIUS_API_KEY`` is not present on the machine this was
    built on, so the mode is exercised against :class:`FakeTransport` only, and the step-5
    entry records "nebius not run: no key" rather than a number.
    """

    mode: str = "nebius"
    model: str = DEFAULT_NEBIUS_MODEL
    temperature: float = 0.0
    max_tokens: int = 1024
    api_key_env: str = "NEBIUS_API_KEY"
    timeout_s: float = DEFAULT_TIMEOUT_S

    def __call__(self, prompt: str) -> Reply:
        key = os.environ.get(self.api_key_env, "")
        if not key:
            raise RuntimeError(
                f"mode 'nebius' needs {self.api_key_env} in the environment (.env); it is unset"
            )
        try:
            import litellm  # optional dependency, zoo-ml group
        except ImportError as error:  # pragma: no cover — depends on the install
            raise RuntimeError(
                "mode 'nebius' needs litellm: uv add --group zoo-ml litellm"
            ) from error
        started = time.monotonic()
        response = litellm.completion(
            model=f"nebius/{self.model}",
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            api_key=key,
            timeout=self.timeout_s,
        )
        return _reply_from_litellm(response, time.monotonic() - started, self.model)


def _reply_from_litellm(response: Any, seconds: float, fallback_model: str) -> Reply:
    """Read the one shape LiteLLM normalises every provider into (OpenAI chat completion)."""
    data = response if isinstance(response, dict) else getattr(response, "model_dump", dict)()
    choices = data.get("choices") or []
    text = ""
    if choices:
        text = str((choices[0].get("message") or {}).get("content") or "")
    usage = data.get("usage") or {}
    return Reply(
        text=text.strip(),
        model_id=str(data.get("model") or fallback_model),
        seconds=round(seconds, 3),
        dollars=float(data.get("response_cost") or 0.0),
        raw=json.dumps({"usage": usage, "id": data.get("id")}, default=str),
    )


# ---------------------------------------------------------------------------------------
# the test double, and the factory
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class FakeTransport:
    """A transport that answers from a function. Every test of both modes runs through it.

    It is shipped in the package rather than in the test file on purpose: "this mode works"
    is a claim about :mod:`mva.zoo.narrate`'s wiring, and the same double proves it for a
    provider whose key nobody has (``nebius``) and for one whose CLI is on PATH.
    """

    answer: Callable[[str], str]
    mode: str = "fake"
    model_id: str = "fake-model"

    def __call__(self, prompt: str) -> Reply:
        return Reply(text=self.answer(prompt), model_id=self.model_id, seconds=0.0, dollars=0.0)


def build_transport(
    mode: str,
    *,
    model: str = "",
    temperature: float = 0.0,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> Transport | None:
    """The transport for one ``[llm] mode``, or ``None`` for ``none``.

    Raises on an unknown mode rather than falling back: a typo in a config must stop the run,
    not quietly produce a hand-written report labelled as generated.
    """
    if mode not in MODES:
        raise ValueError(f"unknown llm mode {mode!r}; known: {', '.join(MODES)}")
    if mode == "none":
        return None
    if mode == "claude-code":
        return ClaudeCodeTransport(model=model, timeout_s=timeout_s)
    return NebiusTransport(
        model=model or DEFAULT_NEBIUS_MODEL, temperature=temperature, timeout_s=timeout_s
    )
