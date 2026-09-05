#!/usr/bin/env node
// Render a Markdown report to PDF with a real browser, so Mermaid diagrams and PNG figures
// print exactly as they render on GitHub.
//
// Two stages: `uv run python tools/md_to_html.py` produces a self-contained HTML page (this
// script does not parse Markdown), then this script opens it in headless Chromium and prints.
// Playwright is taken from the global install; the headless shell path is explicit because
// the default one is missing on this machine (see the note in tools/md_to_html.py).
//
//   node tools/md_to_pdf.mjs <in.html> <out.pdf>
//
// Env: PLAYWRIGHT_MODULE (path to playwright/index.mjs), CHROMIUM_PATH (headless shell).

import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
import { homedir } from "node:os";

const [, , input, output] = process.argv;
if (!input || !output) {
  console.error("usage: node tools/md_to_pdf.mjs <in.html> <out.pdf>");
  process.exit(2);
}
const home = homedir();
const playwrightModule =
  process.env.PLAYWRIGHT_MODULE ??
  `${home}/.nvm/versions/node/v24.14.0/lib/node_modules/playwright/index.mjs`;
const executablePath =
  process.env.CHROMIUM_PATH ??
  `${home}/Library/Caches/ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-mac-arm64/chrome-headless-shell`;

const { chromium } = await import(playwrightModule);
const browser = await chromium.launch({ executablePath });
const page = await browser.newPage({ viewport: { width: 1100, height: 1400 } });
await page.goto(pathToFileURL(resolve(input)).href, { waitUntil: "networkidle" });
// Mermaid renders asynchronously after load; wait until every block has an SVG.
await page
  .waitForFunction(
    () => [...document.querySelectorAll("pre.mermaid")].every((el) => el.querySelector("svg")),
    null,
    { timeout: 20000 }
  )
  .catch(() => console.error("warning: some Mermaid blocks did not render within 20 s"));
await page.waitForTimeout(500);
await page.pdf({
  path: output,
  format: "A4",
  printBackground: true,
  margin: { top: "18mm", bottom: "18mm", left: "16mm", right: "16mm" },
  displayHeaderFooter: true,
  headerTemplate: "<span></span>",
  footerTemplate:
    '<div style="width:100%;font-size:9px;color:#666;text-align:center;font-family:sans-serif">' +
    '<span class="pageNumber"></span> / <span class="totalPages"></span></div>',
});
await browser.close();
console.log(`wrote ${output}`);
