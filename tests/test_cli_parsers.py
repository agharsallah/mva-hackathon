"""Every registered verb parses and reaches a callable handler.

Both CLIs dispatch through ``set_defaults(handler=...)``, so a verb that is registered
twice — or registered pointing at a name that a later definition rebound — still shows up
in ``--help`` while doing something else entirely. Walking the parser and calling nothing
catches that class of bug without touching a database, a bucket or the network.
"""

import argparse
import ast
from pathlib import Path

import pytest

import mva

from mva.explore import cli as explore_cli
from mva.warehouse import cli as warehouse_cli

PARSERS = {"mva-explore": explore_cli._parser(), "mva-warehouse": warehouse_cli._parser()}


def _verbs(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    """Every subcommand name mapped to its own parser."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def _minimal_argv(verb: str, sub: argparse.ArgumentParser) -> list[str]:
    """The shortest command line that satisfies this verb's required arguments."""
    argv = [verb]
    for action in sub._actions:
        if isinstance(action, argparse._HelpAction):
            continue
        if not action.option_strings:  # positional
            argv.extend(["x"] * (1 if action.nargs in (None, "?", "*", "+") else action.nargs))
        elif action.required:
            argv.append(action.option_strings[0])
            if action.nargs != 0:
                argv.append("x")
    return argv


CASES = [(tool, verb) for tool, parser in PARSERS.items() for verb in _verbs(parser)]


def test_both_clis_register_verbs():
    for tool, parser in PARSERS.items():
        assert _verbs(parser), f"{tool} registered no subcommands"


@pytest.mark.parametrize("tool,verb", CASES, ids=[f"{t}:{v}" for t, v in CASES])
def test_verb_parses_to_a_callable_handler(tool, verb):
    parser = PARSERS[tool]
    args = parser.parse_args(_minimal_argv(verb, _verbs(parser)[verb]))
    handler = getattr(args, "handler", None)
    assert callable(handler), f"{tool} {verb} has no callable handler"


@pytest.mark.parametrize("tool", list(PARSERS))
def test_verb_names_are_unique(tool):
    """argparse silently keeps the last registration of a repeated name."""
    action = next(a for a in PARSERS[tool]._actions
                  if isinstance(a, argparse._SubParsersAction))
    names = [choice.dest for choice in action._choices_actions]
    assert len(names) == len(set(names)), f"{tool} registers a verb twice: {names}"


SOURCES = sorted(Path(mva.__file__).parent.rglob("*.py"))


@pytest.mark.parametrize("path", SOURCES, ids=[p.name for p in SOURCES])
def test_no_shadowed_top_level_definitions(path):
    """A name bound twice at module level means the first definition is dead code.

    This is how a newer ``do_fetch`` came to sit above an older one that silently won:
    both were exported, ``--help`` described the new flags, and the old body ran.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            names.extend(t.id for t in node.targets if isinstance(t, ast.Name))
    duplicates = {n for n in names if names.count(n) > 1}
    assert not duplicates, f"{path.name} binds {sorted(duplicates)} more than once"
