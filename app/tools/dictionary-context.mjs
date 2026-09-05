/**
 * The `*Context:*` micro-format, and where a term was first written down.
 *
 * `docs/dictionary.md` gives every entry a definition and an `*Example:*` line. A third,
 * optional italic line records the *metadata* of the term — where it is used, which file owns
 * it, which entries it leans on, and what to look at. This module is the parser for that line
 * plus the git walk that dates every entry; `gen-dictionary.mjs` owns the markdown walk and
 * calls in here, so neither file grows past the size a reviewer can hold in their head.
 *
 * The micro-format, one italic line, segments separated by ` · ` (or `; `):
 *
 *   *Context: <where it is used> · source: <repo-relative path> · related: [term](#slug),
 *    [term](#slug) · see: [label](#anchor) · first seen 2026-09-05*
 *
 *   - the leading `Context:` label is mandatory; everything else is optional
 *   - a segment starting with `source:`, `related:`, `see:` or `first seen ` is structured;
 *     any other segment is free text and becomes the entry's one-line "where it is used"
 *   - `source:` is one repo-relative path or citation, backticks optional — the file that
 *     owns the term (a methodology entry, a module, a rules document)
 *   - `related:` and `see:` are comma-separated. An item is a markdown link or a bare term
 *     name; `related:` resolves to dictionary slugs, `see:` to anchors, paths relative to
 *     docs/ (like every other link in the file) or URLs
 *   - `first seen YYYY-MM-DD` overrides the git-derived date, for a term that existed in the
 *     work before it reached this file
 */

import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { join, normalize } from 'node:path';

/** Segment keys the parser understands; everything else is free text. */
const SEGMENT = /^(source|related|see)\s*:\s*(.+)$/is;
const FIRST_SEEN = /^first seen\s+(\d{4}-\d{2}-\d{2})$/i;

/** A line that opens an entry's Context block — a bare italic starting with `Context:`. */
export function isContextLine(line) {
  return /^\*(?!\*)\s*Context:/i.test(line);
}

/** Split a comma list without cutting inside a `[label](target)` link. */
function splitItems(value) {
  const out = [];
  let depth = 0;
  let cur = '';
  for (const ch of value) {
    if (ch === ',' && depth === 0) {
      out.push(cur.trim());
      cur = '';
      continue;
    }
    if (ch === '(' || ch === '[') depth++;
    if (ch === ')' || ch === ']') depth--;
    cur += ch;
  }
  out.push(cur.trim());
  return out.filter(Boolean);
}

/** `[label](target)` → `{ label, target }`; a bare name → `{ label, target: null }`. */
function parseItems(value) {
  return splitItems(value).map((part) => {
    const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    return link
      ? { label: link[1].trim(), target: link[2].trim() }
      : { label: part.replace(/^`|`$/g, '').trim(), target: null };
  });
}

/**
 * One `*Context: …*` line → its parts. `lead` comes back as markdown (the caller renders it
 * with the same remark pipeline the definitions use, so its links are checked too).
 */
export function parseContextLine(raw) {
  const body = raw
    .replace(/\s*\n\s*/g, ' ')
    .trim()
    .replace(/^\*(?!\*)/, '')
    .replace(/\*$/, '')
    .replace(/^\s*Context:\s*/i, '')
    .trim();

  const parsed = { lead: '', source: '', related: [], see: [], firstSeen: '' };
  // ` · ` always separates. `; ` only does when a key follows it, so an ordinary semicolon in
  // the free-text lead stays part of the sentence.
  const parts = body.split(/\s+·\s+|;\s+(?=(?:source|related|see|first seen)\b)/i);
  for (const segment of parts.map((s) => s.trim())) {
    if (!segment) continue;
    const date = segment.match(FIRST_SEEN);
    if (date) {
      parsed.firstSeen = date[1];
      continue;
    }
    const keyed = segment.match(SEGMENT);
    if (!keyed) {
      parsed.lead = parsed.lead ? `${parsed.lead} ${segment}` : segment;
      continue;
    }
    const [, key, value] = keyed;
    if (key.toLowerCase() === 'source') parsed.source = value.replace(/^`|`$/g, '').trim();
    else if (key.toLowerCase() === 'related') parsed.related = parseItems(value);
    else parsed.see = parseItems(value);
  }
  return parsed;
}

/**
 * Every bold marker in `docs/dictionary.md`, mapped to the author date of the earliest commit
 * whose diff added a line containing it.
 *
 * One `git log -p` walk, newest commit first, overwriting as it goes — so the value left
 * standing for a marker is the oldest commit that introduced it. That is ~2,100 lines of
 * patch and ~35 ms for this file's 30-commit history, where one `git log -S` per term would
 * be 445 subprocesses. `--follow` keeps the dates that predate the move out of `ideation/`;
 * it is deliberately used without `--reverse`, which silently truncates the walk at a rename.
 *
 * Returns an empty map when git cannot answer (a shallow clone, a tarball, no git binary) —
 * the caller falls back to the dates already committed in the generated JSON. A shallow clone
 * is refused rather than believed: with no parent commit the whole file reads as *added* by
 * the one commit present, which would date all 445 entries to the day of the checkout.
 */
export function gitFirstSeen(repoDir, relPath) {
  let out;
  try {
    const shallow = execFileSync('git', ['-C', repoDir, 'rev-parse', '--is-shallow-repository'], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
    if (shallow === 'true') return new Map();
    out = execFileSync(
      'git',
      ['-C', repoDir, 'log', '--follow', '--format=%x00%as', '-p', '--unified=0', '--', relPath],
      { encoding: 'utf8', maxBuffer: 128 * 1024 * 1024, stdio: ['ignore', 'pipe', 'ignore'] },
    );
  } catch {
    return new Map();
  }

  const dates = new Map();
  let date = null;
  for (const line of out.split('\n')) {
    if (line.startsWith('\0')) {
      date = line.slice(1).trim();
      continue;
    }
    if (!date || !line.startsWith('+') || line.startsWith('+++')) continue;
    // Both spellings: the marker as written, and with the inline code ticks removed — a term
    // like ``**Entropy `H`**`` reaches the walk as `Entropy H` once remark has rendered it.
    for (const m of line.matchAll(/\*\*([^*\n]+)\*\*/g)) {
      dates.set(m[1], date);
      dates.set(m[1].replace(/`/g, ''), date);
    }
  }
  return dates;
}

/** Today, as `YYYY-MM-DD` — the date an entry that git has never seen is stamped with. */
export function today() {
  return new Date().toISOString().slice(0, 10);
}

// --- resolving what a Context line points at -------------------------------------------------

/** A `source:` that looks like a repository path rather than a free citation. */
const REPO_PATH = /^[\w.@-]+\/\S+$/;

/**
 * Turn the raw `related` / `see` items of every entry into slugs and hrefs, and complain about
 * anything that does not resolve. Runs once the whole document is parsed, because a Context
 * line may name an entry defined further down.
 *
 * Mutates the entry blocks in place: `related` gains slugs, `see` gains hrefs. `problems` is
 * the generator's error list — a `source:` naming a file that is not there, a `related:` naming
 * a term the dictionary does not define, a `see:` anchor with no owner all land in it, because
 * a metadata field nobody checks is a metadata field nobody can trust.
 */
export function resolveContextMeta({ entries, chapters, meta, problems, repo, repoBlob }) {
  const bySlug = new Set(entries.map((e) => e.slug));
  const byName = new Map();
  for (const e of entries)
    for (const name of [e.term, ...e.aliases]) {
      const key = name.toLowerCase();
      if (!byName.has(key)) byName.set(key, e.slug);
    }
  const anchors = new Set([
    ...chapters.map((c) => c.id),
    ...chapters.flatMap((c) => c.blocks.flatMap((b) => (b.kind === 'subheading' ? [b.id] : []))),
    ...bySlug,
  ]);

  for (const entry of entries) {
    const m = meta.get(entry.slug);
    if (!m) continue;
    const at = `${m.where}: ${entry.slug}`;
    if (entry.source && REPO_PATH.test(entry.source) && !existsSync(join(repo, entry.source)))
      problems.push(`${at} source: no such file ${entry.source}`);

    for (const item of m.related) {
      const slug = item.target?.startsWith('#')
        ? item.target.slice(1)
        : (byName.get(item.label.toLowerCase()) ?? '');
      if (bySlug.has(slug)) entry.related.push(slug);
      else problems.push(`${at} related: no dictionary entry for "${item.label}"`);
    }

    for (const item of m.see) {
      if (!item.target) {
        problems.push(`${at} see: "${item.label}" is not a link`);
      } else if (item.target.startsWith('#')) {
        if (!anchors.has(item.target.slice(1)))
          problems.push(`${at} see: unresolved anchor ${item.target}`);
        entry.see.push(item.target);
      } else if (/^[a-z]+:/.test(item.target)) {
        entry.see.push(item.target);
      } else {
        // A path is relative to docs/ — the same convention every other link in the file
        // follows, so the raw Markdown stays navigable on GitHub as well as in the app.
        const [file, hash] = item.target.split('#');
        const fromDocs = normalize(join('docs', file)).replace(/\\/g, '/');
        if (!existsSync(join(repo, fromDocs))) problems.push(`${at} see: no such file ${fromDocs}`);
        entry.see.push(repoBlob + fromDocs + (hash ? `#${hash}` : ''));
      }
    }
  }
}

// --- dating every entry ------------------------------------------------------------------------

/**
 * slug → the `firstSeen` already committed in the generated JSON. A first-seen date is a
 * ledger: once written it stays, which is also what keeps `--check` green on a fresh clone.
 */
export function committedDates(jsonPath) {
  if (!existsSync(jsonPath)) return new Map();
  try {
    const prev = JSON.parse(readFileSync(jsonPath, 'utf8'));
    return new Map(
      (prev.chapters ?? [])
        .flatMap((c) => c.blocks ?? [])
        .filter((b) => b.kind === 'entry' && b.firstSeen)
        .map((b) => [b.slug, { firstSeen: b.firstSeen, provisional: b.firstSeenProvisional }]),
    );
  } catch {
    return new Map();
  }
}

/** Stamp `firstSeen` on every entry: explicit, then carried, then git, then today. */
export function dateEntries({ entries, meta, previous, fromGit, now }) {
  for (const entry of entries) {
    const explicit = meta.get(entry.slug)?.firstSeen;
    const carried = previous.get(entry.slug);
    if (explicit) {
      entry.firstSeen = explicit;
    } else if (carried) {
      entry.firstSeen = carried.firstSeen;
      if (carried.provisional) entry.firstSeenProvisional = true;
    } else if (fromGit.has(entry.term)) {
      entry.firstSeen = fromGit.get(entry.term);
    } else {
      entry.firstSeen = now;
      entry.firstSeenProvisional = true;
    }
  }
}
