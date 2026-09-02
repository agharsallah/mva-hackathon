import { Section } from '../components/Controls';
import { Callout, Explainer } from '../components/Explainer';
import { PrimitiveGallery } from './styleguide/PrimitiveGallery';
import { RampGrid } from './styleguide/RampGrid';
import { ScaleStrips } from './styleguide/ScaleStrips';
import { TokenPipeline } from './styleguide/TokenPipeline';
import { ToneCatalog } from './styleguide/ToneCatalog';

/**
 * The design system, rendered as a page — living documentation, and the visual regression
 * anchor for every other page in the app.
 *
 * Nothing here is hand-listed. The grids iterate `RAMP` and `TONES`, the recipe cells render
 * `lib/ui.ts`'s own strings, and the gallery mounts the real components. A colour that changes
 * changes this page; a tone that is added appears on it without an edit. Screenshot it before
 * and after a styling change and the diff is the review.
 */
export default function StyleGuidePage() {
  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            Every colour in this app comes from one generated set of numbers, and every structural
            piece of a page comes from one set of components. This page renders both, live, so the
            system can be reviewed by eye instead of by reading four files. It is also the cheapest
            regression test there is: a screenshot before and after a styling change shows the whole
            blast radius in one image.
          </>
        }
        terms={[
          {
            term: 'design token',
            plain:
              'a named value used instead of a literal one — `--color-good-500` rather than a hex typed at the call site. Same idea as a constant, but readable by CSS',
          },
          {
            term: 'tone',
            plain:
              'what a colour means here (good, broken, a decision, machinery, raw input, or nothing). Components take a tone, never a hue',
          },
          {
            term: 'family',
            plain:
              'the hue ramp that renders a tone — `good` is drawn in green, `neutral` in the grey called `chrome`',
          },
          {
            term: 'shade',
            plain:
              'a step on a family, 50 (palest) to 950 (deepest). This app uses 300/400 for text, 800/900 for borders, 950 for a tinted background',
          },
          {
            term: 'colourscale',
            plain:
              'a list of `[position, colour]` stops handed to Plotly; it interpolates between them to colour a continuous range',
          },
          {
            term: 'oklch',
            plain:
              "a perceptual colour space: lightness, chroma, hue. Tailwind v4 ships its palette in it; the generator converts to hex because Plotly's colour parser cannot read it",
          },
        ]}
        caveat="Colours here are the sRGB hex the generator emits. On a wide-gamut display Tailwind's own oklch values would render slightly more vivid — we deliberately trade that for the DOM and the charts being byte-identical."
      />

      <Callout tone="good" title="What this page guarantees">
        There is no second colour system. A hex literal outside{' '}
        <code>lib/palette/ramps.generated.ts</code> is an eslint error, a bare Tailwind hue like{' '}
        <code>bg-emerald-400</code> is an eslint error, and <code>pnpm theme:check</code> fails if
        the hex the charts read ever stops matching the custom property the classes read.
      </Callout>

      <Section
        title="The token pipeline"
        subtitle="One dependency, one generator, two artifacts, four gates."
      >
        <TokenPipeline />
      </Section>

      <Section
        title="The colours"
        subtitle="Every generated value, and every meaning attached to one."
      >
        <div className="space-y-4">
          <RampGrid />
          <ToneCatalog />
          <ScaleStrips />
        </div>
      </Section>

      <PrimitiveGallery />
    </div>
  );
}
