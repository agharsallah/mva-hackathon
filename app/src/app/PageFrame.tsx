/**
 * PageFrame — wraps whatever module the router mounted with the manifest-driven page
 * header above it and the journey hand-off below it. Reads the current module from the
 * URL, so pages stay free of any knowledge of where they sit in the app.
 */

import type { ReactNode } from 'react';
import { useLocation } from 'react-router-dom';

import { JumpToSection, OnThisPage } from '../components/OnThisPage';
import { JourneyFooter, type JourneyLink, PageHeader } from '../components/PageHeader';
import { useRailOpen } from '../lib/rail';
import { groupOf, moduleAt, neighbours, positionInGroup } from './modules/journey';
import type { FeatureModule } from './modules/types';

function link(
  m: FeatureModule | undefined,
): (JourneyLink & { description: string; eyebrow?: string }) | undefined {
  if (!m) return undefined;
  return {
    to: m.path,
    label: m.title,
    description: m.description,
    eyebrow: groupOf(m)?.label,
    preload: () => void m.load(),
  };
}

export function PageFrame({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const railOpen = useRailOpen();
  const m = moduleAt(pathname);
  if (!m) return <>{children}</>;

  const group = groupOf(m);
  const pos = positionInGroup(m);
  const { prev, next } = neighbours(m);

  return (
    <>
      <PageHeader
        eyebrow={group?.question}
        position={pos ? `${pos.index} of ${pos.total}` : undefined}
        title={m.title}
        description={m.description}
        prev={prev && { to: prev.path, label: prev.navLabel, preload: () => void prev.load() }}
        next={next && { to: next.path, label: next.navLabel, preload: () => void next.load() }}
      />
      <JumpToSection />
      <div
        className={
          railOpen
            ? 'xl:grid xl:grid-cols-[11rem_minmax(0,1fr)] xl:items-start xl:gap-10'
            : 'xl:grid xl:grid-cols-[auto_minmax(0,1fr)] xl:items-start xl:gap-6'
        }
      >
        <div className="sticky top-28 hidden xl:block">
          <OnThisPage />
        </div>
        <div className="min-w-0 space-y-6">
          {children}
          <JourneyFooter prev={link(prev)} next={link(next)} />
        </div>
      </div>
    </>
  );
}
