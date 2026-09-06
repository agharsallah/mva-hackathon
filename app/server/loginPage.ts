/**
 * The password page, rendered by `middleware.ts` for a request with no valid session.
 *
 * Self-contained on purpose: inline CSS, inline script, no font file, no bundle. An
 * unauthenticated visitor must never receive the dashboard's JavaScript, so the gate
 * cannot be a route inside the SPA — the SPA is what is being gated.
 *
 * The colours are the dashboard's own tokens, copied as literals (`src/index.css`,
 * `src/theme.generated.css`) because this file is outside the Vite build and cannot
 * import the stylesheet. They are the *dark* half of the palette; this page does not
 * follow the theme mirror.
 */

const CHROME_950 = '#09090b';
const CHROME_900 = '#18181b';
const CHROME_800 = '#27272a';
const CHROME_400 = '#9f9fa9';
const CHROME_200 = '#e4e4e7';
const CHROME_50 = '#fafafa';
const MACHINERY = '#155dfc';
const BROKEN = '#ff6467';

export interface LoginPageOptions {
  /** Where to send the visitor after a successful login. Same-origin path only. */
  next: string;
  /** Shown in red above the field. */
  error?: string;
}

/** A same-origin path, or `/`. Guards the post-login redirect against an open redirect. */
export function safeNext(candidate: string | null | undefined): string {
  if (!candidate) return '/';
  // `//evil.example` and `/\evil.example` are both browser-absolute despite the leading
  // slash, and a `:` before the first `/` makes it a scheme. Reject all three.
  if (!candidate.startsWith('/')) return '/';
  if (candidate.startsWith('//') || candidate.startsWith('/\\')) return '/';
  return candidate;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

export function loginPage({ next, error }: LoginPageOptions): string {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>MVA dashboard — password</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh; display: grid; place-items: center;
    background: ${CHROME_950}; color: ${CHROME_200};
    font: 14px/1.5 ui-sans-serif, system-ui, -apple-system, sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  main {
    width: min(24rem, calc(100vw - 2rem));
    border: 1px solid ${CHROME_800}; border-radius: 0.5rem;
    background: ${CHROME_900}; padding: 1.75rem;
  }
  h1 { margin: 0 0 0.25rem; font-size: 1.0625rem; color: ${CHROME_50}; font-weight: 600; }
  p.lede { margin: 0 0 1.5rem; color: ${CHROME_400}; font-size: 0.8125rem; }
  label { display: block; margin-bottom: 0.375rem; font-size: 0.6875rem;
          letter-spacing: 0.06em; text-transform: uppercase; color: ${CHROME_400}; }
  input {
    width: 100%; padding: 0.5rem 0.625rem; font: inherit; color: ${CHROME_50};
    background: ${CHROME_950}; border: 1px solid ${CHROME_800}; border-radius: 0.375rem;
  }
  input:focus { outline: none; border-color: ${MACHINERY}; box-shadow: 0 0 0 1px ${MACHINERY}; }
  button {
    margin-top: 0.875rem; width: 100%; padding: 0.5rem; font: inherit; font-weight: 600;
    color: ${CHROME_50}; background: ${MACHINERY}; border: 0; border-radius: 0.375rem;
    cursor: pointer;
  }
  button[disabled] { opacity: 0.6; cursor: progress; }
  .error { margin: 0.875rem 0 0; color: ${BROKEN}; font-size: 0.8125rem; min-height: 1.2em; }
  footer { margin-top: 1.5rem; color: ${CHROME_400}; font-size: 0.6875rem; }
</style>
</head>
<body>
<main>
  <h1>MVA Hackathon 2026 — dashboard</h1>
  <p class="lede">This deployment is private. It shows patient-derived analysis, so it asks
  for the shared password before it loads anything.</p>
  <form id="f" method="post" action="/api/login">
    <label for="password">Password</label>
    <input id="password" name="password" type="password" autocomplete="current-password"
           autofocus required>
    <input type="hidden" name="next" value="${escapeHtml(next)}">
    <button type="submit">Enter</button>
    <p class="error" id="e" role="alert">${escapeHtml(error ?? '')}</p>
  </form>
  <footer>One shared password. A session lasts 12 hours.</footer>
</main>
<script>
// Submitted with fetch so a wrong password re-renders in place instead of replacing the
// page. The form's own method="post" is the no-JavaScript fallback and still works.
document.getElementById('f').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('button');
  const error = document.getElementById('e');
  button.disabled = true;
  error.textContent = '';
  try {
    const response = await fetch('/api/login', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        password: form.password.value,
        next: form.next.value,
      }),
    });
    if (response.ok) {
      window.location.assign((await response.json()).next || '/');
      return;
    }
    error.textContent = (await response.json()).detail || 'Wrong password.';
  } catch {
    error.textContent = 'Could not reach the server.';
  }
  button.disabled = false;
  form.password.select();
});
</script>
</body>
</html>`;
}
