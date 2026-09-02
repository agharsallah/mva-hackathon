#!/usr/bin/env sh
# Commit-message gate. One implementation, three callers: the .husky/commit-msg
# hook (a message file), CI (a range of already-written commits), and --self-test.
#
# POSIX sh with grep/sed only, deliberately: a contributor who only touches app/
# has node but no uv, and one who only touches src/ has uv but no node. A gate
# that needs either would be skipped by half the repo.
#
# The convention is not invented here — it is what `git log` has done for 120+
# commits, written down in CONTRIBUTING.md and now checked.
set -e

SUBJECT_HARD_MAX=90 # fails: longer than any subject the repo has needed
SUBJECT_SOFT_MAX=72 # warns: the width `git log --oneline` shows without wrapping
BODY_MAX=100        # warns: the repo's prose wrap

TYPES='feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert'

# A genomic position, in the spellings that actually occur: chr15:40142000,
# 15:40142000, chr15-40142000, g.40142000A>G. Kept in step with
# `mva.science.export.COORDINATE` — a commit message is as permanent as an
# exported file, so it is held to the same data-transfer-agreement rule.
# See docs/notes/no-patient-data-in-the-repository.md.
COORDINATE='(^|[^A-Za-z0-9_])(chr)?([1-9]|1[0-9]|2[0-2]|[XYMxym]|MT|mt)[:_-][0-9]{4,}([^0-9]|$)'
COORDINATE_HGVS='(^|[^A-Za-z0-9_])g\.[0-9]{4,} *[ACGTacgt]+ *> *[ACGTacgt]+'

# Attribution trailers this project does not carry (CLAUDE.md, global rules).
AI_TRAILER='^(Co-Authored-By: *Claude|.*Generated with \[?Claude Code)'

errors=0
warnings=0

err() {
  printf 'commit-msg: error: %s\n' "$1" >&2
  errors=$((errors + 1))
}

warn() {
  printf 'commit-msg: warning: %s\n' "$1" >&2
  warnings=$((warnings + 1))
}

# Strip comment lines (git's own template) and the diff `git commit -v` appends.
message_body() {
  sed -e '/^# *-\{8,\} *>8 *-\{8,\}/,$d' -e '/^#/d' "$1"
}

check_message() {
  file=$1
  label=$2
  clean=$(message_body "$file")

  subject=$(printf '%s\n' "$clean" | sed -n '1p')
  second=$(printf '%s\n' "$clean" | sed -n '2p')

  if [ -z "$(printf '%s' "$clean" | tr -d '[:space:]')" ]; then
    err "$label: empty commit message"
    return
  fi

  # Machine-written subjects git itself owns; the convention does not apply.
  case $subject in
    'Merge '* | 'Revert "'* | 'fixup!'* | 'squash!'* | 'amend!'*) return ;;
  esac

  if ! printf '%s' "$subject" | grep -Eq "^($TYPES)(\([a-z0-9][a-z0-9._/-]*\))?!?: .+"; then
    err "$label: subject must be '<type>(<scope>): <summary>' with type one of $TYPES
    got: $subject"
    return
  fi

  summary=$(printf '%s' "$subject" | sed -E "s/^($TYPES)(\([^)]*\))?!?: //")
  length=$(printf '%s' "$subject" | wc -c | tr -d ' ')

  if [ "$length" -gt "$SUBJECT_HARD_MAX" ]; then
    err "$label: subject is $length chars, over the $SUBJECT_HARD_MAX limit"
  fi
  if [ "$length" -gt "$SUBJECT_SOFT_MAX" ] && [ "$length" -le "$SUBJECT_HARD_MAX" ]; then
    warn "$label: subject is $length chars; $SUBJECT_SOFT_MAX keeps 'git log --oneline' unwrapped"
  fi

  case $summary in
    *.) err "$label: subject must not end with a period" ;;
  esac

  # Lowercase start, but never flag a real identifier: ClinVar, DuckDB, TypeScript.
  if printf '%s' "$summary" | grep -Eq '^[A-Z][a-z]+ '; then
    err "$label: subject summary starts with a capitalised word — use the imperative, lowercase
    got: $summary"
  fi

  if [ -n "$(printf '%s' "$second" | tr -d '[:space:]')" ]; then
    err "$label: line 2 must be blank — subject, blank line, then the body"
  fi

  if printf '%s\n' "$clean" | grep -Eqi "$COORDINATE|$COORDINATE_HGVS"; then
    offender=$(printf '%s\n' "$clean" | grep -Ein "$COORDINATE|$COORDINATE_HGVS" | head -1)
    err "$label: a genomic position must never enter git history — name the gene and the
    consequence instead (docs/notes/no-patient-data-in-the-repository.md)
    got: $offender"
  fi

  if printf '%s\n' "$clean" | grep -Eq "$AI_TRAILER"; then
    err "$label: remove the AI attribution trailer — this project does not carry them"
  fi

  if printf '%s\n' "$clean" | sed -n '3,$p' | awk -v m="$BODY_MAX" 'length>m{f=1} END{exit !f}'; then
    warn "$label: a body line is over $BODY_MAX chars — wrap it"
  fi

  body=$(printf '%s\n' "$clean" | sed -n '3,$p' | tr -d '[:space:]')
  if [ -z "$body" ]; then
    warn "$label: no body — say *why*, and cite any number the change measured"
  fi
}

check_rev() {
  tmp=$(mktemp)
  git log -1 --format=%B "$1" >"$tmp"
  check_message "$tmp" "$(git log -1 --format=%h "$1")"
  rm -f "$tmp"
}

report() {
  if [ "$errors" -gt 0 ]; then
    printf '\ncommit-msg: %s error(s), %s warning(s). Convention: CONTRIBUTING.md#commit-convention\n' \
      "$errors" "$warnings" >&2
    printf 'commit-msg: fix the message and re-commit (git commit --amend for the last one).\n' >&2
    exit 1
  fi
  printf 'commit-msg: ok (%s warning(s))\n' "$warnings"
}

self_test() {
  pass=0
  fail=0
  case_check() {
    want=$1
    text=$2
    name=$3
    tmp=$(mktemp)
    printf '%s\n' "$text" >"$tmp"
    got=$("$0" "$tmp" >/dev/null 2>&1 && echo ok || echo bad)
    rm -f "$tmp"
    if [ "$got" = "$want" ]; then
      pass=$((pass + 1))
    else
      fail=$((fail + 1))
      printf 'self-test FAIL: %s (wanted %s, got %s)\n' "$name" "$want" "$got" >&2
    fi
  }

  case_check ok 'feat(viz): probe every dependency behind one health endpoint

Why it changed.' 'conventional with body'
  case_check ok 'docs: point every live quickstart at pnpm

Body.' 'no scope'
  case_check ok 'Merge branch main into topic' 'merge subject exempt'
  case_check ok 'fix(app): keep ClinVar labels on the tile

Body.' 'proper noun after type is fine'
  case_check bad 'cleaning up' 'no type'
  case_check bad 'Refactor code structure for improved readability' 'capitalised non-conventional'
  case_check bad 'fix(app): Correct the label

Body.' 'capitalised summary'
  case_check bad 'fix(app): correct the label.' 'trailing period'
  case_check bad 'fix(app): correct the label
body on line 2' 'missing blank line'
  case_check bad 'fix(app): show the variant

Found at chr15:40142000 in the callset.' 'genomic coordinate'
  case_check bad 'fix(app): show the variant

Seen as g.40142000A>G.' 'hgvs genomic coordinate'
  case_check bad 'fix(app): correct the label

Body.

Co-Authored-By: Claude <noreply@anthropic.com>' 'AI trailer'
  case_check bad "fix(app): $(printf 'x%.0s' $(seq 1 95))" 'over the hard subject limit'

  printf 'self-test: %s passed, %s failed\n' "$pass" "$fail"
  [ "$fail" -eq 0 ]
}

usage() {
  cat >&2 <<'USAGE'
usage: tools/check-commit-msg.sh <message-file>   # what .husky/commit-msg passes
       tools/check-commit-msg.sh --rev <sha>      # one existing commit
       tools/check-commit-msg.sh --range <A..B>   # every commit in a range (CI)
       tools/check-commit-msg.sh --self-test      # the gate's own cases
USAGE
  exit 2
}

case ${1:-} in
  --self-test) self_test ;;
  --rev)
    [ -n "${2:-}" ] || usage
    check_rev "$2"
    report
    ;;
  --range)
    [ -n "${2:-}" ] || usage
    revs=$(git rev-list --no-merges "$2")
    if [ -z "$revs" ]; then
      echo "commit-msg: no commits in range $2 — nothing to check"
      exit 0
    fi
    for rev in $revs; do check_rev "$rev"; done
    report
    ;;
  '' | -h | --help) usage ;;
  *)
    [ -f "$1" ] || usage
    check_message "$1" "$(basename "$1")"
    report
    ;;
esac
