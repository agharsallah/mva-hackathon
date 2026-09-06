/**
 * The one control that switches the palette.
 *
 * A toggle button, not a three-way menu: the store already resolves "no stored choice" to the
 * OS `prefers-color-scheme`, so the reader only ever has to express a disagreement with it.
 * `aria-pressed` is what makes it a toggle to a screen reader rather than a button that does
 * something unnamed — pressed means light.
 *
 * The label names the theme that is on, so the button reads as a state rather than a command;
 * the `title` carries the command ("switch to …") for anyone who needs it spelled out.
 */

import { themeStore, useTheme } from '../lib/theme';

export function ThemeToggle() {
  const theme = useTheme();
  const light = theme === 'light';
  return (
    <button
      type="button"
      onClick={themeStore.toggle}
      aria-pressed={light}
      title={`Theme: ${light ? 'light' : 'dark'}. Switch to the ${light ? 'dark' : 'light'} theme.`}
      className="rounded-control border border-line bg-chrome-900 px-2 py-1 text-micro text-chrome-400 transition hover:text-chrome-200 focus:outline-none focus-visible:ring-1 focus-visible:ring-machinery-500"
    >
      {light ? 'Light' : 'Dark'}
    </button>
  );
}
