import './learn/learn.css';

import { useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { Card } from '../components/Card';
import { Callout, Explainer } from '../components/Explainer';
import { ErrorCard, Skeleton } from '../components/QueryState';
import { type Chapter, chapterOfAnchor, type Dictionary } from '../lib/dictionary';
import { Blocks } from './learn/Blocks';
import { ChapterRail } from './learn/ChapterRail';
import { useProgress } from './learn/progress';
import { SeeItLinks } from './learn/SeeItLinks';
import { TermSearch } from './learn/TermSearch';
import { TrackList } from './learn/TrackList';
import { useDictionary } from './learn/useDictionary';

/**
 * Learn — `docs/dictionary.md` as a course.
 *
 * The dictionary is the one glossary in the repository and it is already a curriculum: its
 * fifteen chapters are ordered so every word uses only words defined before it. This page
 * does not restate it — the markdown is generated into the app at build time — it gives it
 * what a file cannot have: one chapter at a time, a search over every term, progress that
 * survives a reload, an anchor per word that the other pages can link to, the diagrams
 * drawn rather than shown as code, and under a word the app can show, a link to the exhibit
 * that shows it (`learn/seeIt.ts`) and to the methodology entry that measured it.
 *
 * The URL hash is the whole state: `#allele` opens the chapter that defines allele and
 * scrolls to it; `#4-inheritance--how-the-answer-is-shaped` opens chapter 4. Those are the
 * same anchors GitHub gives the markdown, so a link written for one works on the other.
 */
export default function LearnPage() {
  const { dictionary, error } = useDictionary();
  if (error) return <ErrorCard error={error as Error} title="The dictionary failed to load" />;
  if (!dictionary)
    return <Skeleton height={320} variant="block" framed label="Loading the dictionary" />;
  return <Course dictionary={dictionary} />;
}

const LAST_KEY = 'mva.learn.chapter';

function rememberedChapter(d: Dictionary): Chapter | undefined {
  try {
    const id = window.localStorage.getItem(LAST_KEY);
    return id ? d.chapters.find((c) => c.id === id) : undefined;
  } catch {
    return undefined;
  }
}

function Course({ dictionary }: { dictionary: Dictionary }) {
  const { hash } = useLocation();
  const navigate = useNavigate();
  const { read, markRead, toggle } = useProgress();

  const anchor = decodeURIComponent(hash.replace(/^#/, ''));
  const chapter =
    chapterOfAnchor(dictionary, anchor) ?? rememberedChapter(dictionary) ?? dictionary.chapters[0];
  const i = dictionary.chapters.indexOf(chapter);
  const prev = dictionary.chapters[i - 1];
  const next = dictionary.chapters[i + 1];
  const terms = chapter.blocks.filter((b) => b.kind === 'entry').length;

  // Remember where the reader is, and put the anchored entry on screen once it exists — a
  // hash change inside a single-page app does not scroll on its own. The first render is
  // left to the browser, which already handles the hash of a freshly loaded URL.
  const mounted = useRef(false);
  useEffect(() => {
    try {
      window.localStorage.setItem(LAST_KEY, chapter.id);
    } catch {
      /* fine */
    }
    if (!mounted.current) {
      mounted.current = true;
      return;
    }
    const frame = requestAnimationFrame(() => {
      const target = anchor && anchor !== chapter.id ? document.getElementById(anchor) : null;
      if (target) target.scrollIntoView();
      else window.scrollTo({ top: 0 });
    });
    return () => cancelAnimationFrame(frame);
  }, [anchor, chapter.id]);

  const goTo = (c: Chapter) => navigate({ hash: `#${c.id}` });
  const finish = () => {
    markRead(chapter.id);
    if (next) goTo(next);
  };

  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            One markdown file, <code>docs/dictionary.md</code>, defines every domain word this
            repository uses and is ordered so each word only uses words above it. That order is the
            course. Read the chapters left to right; use the search when a page elsewhere in the app
            uses a word you do not know.
          </>
        }
        terms={[
          {
            term: 'chapter',
            plain:
              'one of the fifteen sections of the dictionary; each is the prerequisite of the next',
          },
          {
            term: 'legend',
            plain:
              'the line under every figure decoding its colours and symbols — green is good or the goal, red is broken or lost points, yellow is a decision, blue is neutral machinery, purple is the raw input',
          },
          {
            term: 'anchor',
            plain:
              'the # in the URL naming one term or chapter; the same anchors GitHub gives the markdown, so a link works in both places',
          },
        ]}
      />

      <div className="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
          <TermSearch dictionary={dictionary} />
          <Card padding="sm">
            <ChapterRail
              chapters={dictionary.chapters}
              current={chapter}
              read={read}
              onToggleRead={toggle}
            />
          </Card>
          <Card padding="sm">
            <TrackList dictionary={dictionary} />
          </Card>
          <details className="text-xs text-chrome-500">
            <summary className="cursor-pointer hover:text-chrome-300">
              About this dictionary
            </summary>
            <div className="learn-prose mt-2 space-y-2 text-note">
              {dictionary.intro.map((b, k) => (
                <div key={k} dangerouslySetInnerHTML={{ __html: b.html }} />
              ))}
            </div>
          </details>
        </aside>

        <section aria-labelledby="learn-chapter-title" className="min-w-0 space-y-5">
          <header id={chapter.id} className="scroll-mt-28 border-b border-line pb-4">
            <p className="font-serif text-reading text-chrome-400 italic">
              Chapter {chapter.number} of {dictionary.chapters.length}
              <span className="ml-3 font-sans text-xs not-italic text-chrome-500">
                {terms} terms
              </span>
            </p>
            <h2
              id="learn-chapter-title"
              className="mt-1 font-serif text-title leading-tight font-medium tracking-tight text-chrome-50"
            >
              {chapter.title}
            </h2>
          </header>

          {chapter.number === 1 && (
            <Callout tone="good" title="Start here">
              Everything else in this app — every chart, every filter name, every gene — is written
              in the words of this chapter and the next two. Twenty minutes here pays for itself on
              the first page of data.
            </Callout>
          )}

          <Blocks blocks={chapter.blocks} aside={(e) => <SeeItLinks entry={e} />} />

          <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
            {prev ? (
              <button
                type="button"
                onClick={() => goTo(prev)}
                className="rounded-control border border-line px-3 py-2 text-left text-sm text-chrome-300 transition hover:border-line-strong hover:text-chrome-50"
              >
                <span className="block text-micro text-chrome-500">Previous chapter</span>
                {prev.number}. {prev.title}
              </button>
            ) : (
              <span />
            )}
            <button
              type="button"
              onClick={finish}
              className="rounded-control border border-good-800 bg-good-950/40 px-3 py-2 text-left text-sm text-good-300 transition hover:border-good-600 hover:text-good-100"
            >
              <span className="block text-micro text-good-500">
                {next ? 'Mark read, next chapter' : 'Mark read'}
              </span>
              {next ? `${next.number}. ${next.title}` : 'Course complete'}
            </button>
          </footer>
        </section>
      </div>
    </div>
  );
}
