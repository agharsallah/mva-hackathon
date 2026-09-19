/**
 * The journey context's data half: types, the context object and its hook. Kept apart
 * from the components in `journey.tsx` so that file exports only components (react-refresh).
 */

import { createContext, useContext } from 'react';

export interface JourneyPage {
  to: string;
  label: string;
  title: string;
  description: string;
  preload?: () => void;
  /** Detail pages of this one. Listed under it rather than beside it. */
  children?: JourneyPage[];
}

export interface JourneyGroup {
  id: string;
  label: string;
  question: string;
  pages: JourneyPage[];
}

export const JourneyContext = createContext<readonly JourneyGroup[]>([]);

export function useJourney(): readonly JourneyGroup[] {
  return useContext(JourneyContext);
}
