/**
 * `local/no-builtin-tailwind-color` — Tailwind's own hue names are not the app's vocabulary.
 *
 * The app paints with six semantic families (`chrome`, `good`, `broken`, `decision`,
 * `machinery`, `raw`, plus `severity` for chart ramps), generated into
 * `src/theme.generated.css` from the same numbers `lib/palette`'s `RAMP` gives Plotly. A class
 * like `text-emerald-400` renders a colour that exists in the DOM and nowhere in the palette,
 * so it can drift from the chart green forever without anything failing.
 *
 * The rule is a text check over string and template literals: `className` is a string, and by
 * the time it reaches the DOM there is nothing typed left to inspect. Prose that happens to
 * contain `blue-400` would trip it — no such prose exists in the app, and the fix (name the
 * family) is the same one the rule is asking for.
 */

const BUILTIN_FAMILIES = [
  'slate',
  'gray',
  'zinc',
  'neutral',
  'stone',
  'red',
  'orange',
  'amber',
  'yellow',
  'lime',
  'green',
  'emerald',
  'teal',
  'cyan',
  'sky',
  'blue',
  'indigo',
  'violet',
  'purple',
  'fuchsia',
  'pink',
  'rose',
];

/** Which semantic family replaces each Tailwind hue. A hue with no entry (teal, pink, ...)
 * has no single answer — the message then lists the families and lets the author choose. */
const REPLACEMENT = {
  slate: 'chrome',
  gray: 'chrome',
  zinc: 'chrome',
  neutral: 'chrome',
  stone: 'chrome',
  red: 'broken',
  orange: 'severity',
  amber: 'decision',
  yellow: 'decision',
  green: 'good',
  emerald: 'good',
  blue: 'machinery',
  sky: 'machinery',
  indigo: 'machinery',
  violet: 'raw',
  purple: 'raw',
};

const CLASS_RE = new RegExp(`\\b(${BUILTIN_FAMILIES.join('|')})-(50|[1-9]\\d{2})\\b`, 'g');

function check(context, node, text) {
  if (typeof text !== 'string') return;
  for (const [match, family] of text.matchAll(CLASS_RE)) {
    const instead = REPLACEMENT[family];
    context.report({
      node,
      messageId: 'builtinHue',
      data: {
        match,
        instead: instead
          ? `the \`${instead}\` family`
          : 'one of the semantic families (chrome/good/broken/decision/machinery/raw)',
      },
    });
  }
}

export default {
  meta: {
    type: 'problem',
    docs: {
      description:
        "disallow Tailwind's built-in colour families in class strings — the app paints with the generated semantic families",
    },
    schema: [],
    messages: {
      builtinHue:
        "`{{match}}` is a Tailwind built-in hue, not one of this app's colours. Use {{instead}} " +
        '(generated into src/theme.generated.css by tools/gen-theme.mjs, and the same numbers ' +
        "as lib/palette's RAMP).",
    },
  },
  create(context) {
    return {
      Literal(node) {
        if (typeof node.value === 'string') check(context, node, node.value);
      },
      TemplateElement(node) {
        check(context, node, node.value.cooked ?? node.value.raw);
      },
    };
  },
};
