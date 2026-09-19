/**
 * The written half of a research step, as `GET /api/steps` serves it.
 *
 * Split out of `steps.ts` because that file is the *derived* record — the step map, the
 * register, the blind gate, the filesystem — and these four shapes are the opposite: the
 * judgements no query can produce. Owned by `mva.viz.steps_narrative` on the Python side and
 * enforced by `tools/check_step_narrative.py`, which fails the build when a step that has run
 * says nothing, or when a figure it drew has no caption.
 */

/**
 * One figure's caption: what it shows, and what it is evidence for.
 *
 * `reads` is checkable against the image; `means` is argued from the methodology entry that
 * produced it, which `source` names. They are separate fields so a reader can tell a
 * description from an interpretation.
 */
export interface FigureCaption {
  name: string;
  reads: string;
  means: string;
  /** The methodology entry or page this reading was written from. */
  source?: string;
}

/** What one step hands to, or takes from, its neighbours — the joint in the argument. */
export interface StepJoin {
  /** Slugs in the same iteration. */
  steps: string[];
  what: string;
}

/**
 * The written half of a step: the judgements that cannot be derived from the step map, the
 * register or the filesystem. Absent for a step nobody has written up yet, which the page
 * says rather than hiding.
 */
export interface StepNarrative {
  step: string;
  iteration: string;
  summary: string;
  /** Why the question had to be asked here. */
  why: string;
  /** What the run concluded, naming the claims it settled. */
  verdict: string;
  inherits: StepJoin;
  hands_to: StepJoin;
  figures: FigureCaption[];
  /** Every file this was written from; the gate refuses a path that does not exist. */
  sources: string[];
}
