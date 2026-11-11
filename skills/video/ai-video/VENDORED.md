# Vendored files

`ai-video` copies a few files, and one folder, from other projects instead of depending on them at
run time. This
file records where each one came from, the exact version, its licence, and every local change, so an
agent can merge a newer upstream version without losing a change or bringing back something that was
removed on purpose.

## The convention

1. **One row per upstream** in the table below: name, upstream URL, version, full commit, licence,
   files taken, and how to update.
2. **A header in every vendored file**, in the file's own comment syntax: the source path at the
   commit, the commit, the licence, and `Modified locally: yes` or `no`. A **vendored folder** is the
   exception: it is byte-identical to its upstream folder at the commit, except the files left out
   and the files changed that its section below lists. Only the changed files carry a header. A
   header in every file would itself change every file, and JSON has no comment syntax.
3. **Inline markers around every local change**, in the file's comment syntax:
   `video MODIFIED begin — <reason>` and `video MODIFIED end`. A deletion leaves a one-line
   marker that says what was removed, so an update cannot quietly bring it back.
4. **Every change is listed** under its upstream below, with its reason.

### Updating an upstream

1. Fetch the upstream at the recorded commit (the base) and at the new version, into two scratch
   folders.
2. For each vendored file with local changes, run
   `git merge-file <vendored file> <base copy> <new copy>`. The merge keeps the marked local changes
   and takes the upstream changes.
3. Resolve each conflict, keeping the markers around local changes.
4. For a vendored folder, copy every other file from the new version over the old, delete files the
   new version no longer has, and remove the left-out files again.
5. Update the headers' commit, the table row and the section below. For Archify, also update the
   vendor test's notice hashes after checking what changed in them.
6. Run the skill's tests. The recording tier exercises the deck files and an
   Archify scene.

## Upstreams

| Name | Upstream | Version | Commit | Licence |
|---|---|---|---|---|
| frontend-slides | https://github.com/zarazhangrui/frontend-slides | 2.1.0 | `24e420e4acef9850505142c449415ac867e43633` | MIT |
| Archify | https://github.com/tt-a1i/archify | 3.2.0 (`main` after `v3.2.0`) | `d6059331abbddb49bca380ff46dca8ce33158b04` | Apache-2.0 |

### frontend-slides 2.1.0

Paths are relative to `plugins/frontend-slides/skills/frontend-slides/` upstream.

| Vendored file | Upstream file | Modified locally |
|---|---|---|
| `assets/deck/deck-stage.js` | `bold-template-pack/deck-stage.js` | yes |
| `assets/deck/viewport-base.css` | `viewport-base.css` | yes |
| `references/frontend-slides/html-template.md` | `html-template.md` | no |
| `references/frontend-slides/animation-patterns.md` | `animation-patterns.md` | no |

Local changes:

- `deck-stage.js`, **recording mode.** A `recording` attribute on `<deck-stage>` hides the
  slide-counter pill and the tap zones. Upstream shows the pill for 1.8 s on every navigation,
  `goTo` included, which would film it on every scene.
- `deck-stage.js`, **`replay()`.** Restarts the active slide's entrance animations and dispatches
  `slidechange` again with `reason: 'replay'`. The recorder needs every scene to start from its first
  animation frame, and upstream's `goTo` to the current slide does nothing.
- `viewport-base.css`, **`data-deck-active`.** Adds `.slide[data-deck-active]` to the shown-slide
  rule. Upstream's stage CSS shows `.slide.active` and `.slide.visible` only, so a `.slide` inside
  `<deck-stage>` would stay hidden.

Not taken: `SKILL.md` (its interactive flow, preview pages, `open` calls and Vercel deploy do not
fit an unattended render), `STYLE_PRESETS.md`, the bold template pack's templates (their upstream
licence is unconfirmed), and `scripts/`.

Licence text, from the upstream `LICENSE`:

```text
MIT License

Copyright (c) 2025 Zara Zhang

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Archify 3.2.0

`vendor/archify/` is the upstream `archify/` folder at `d6059331abbddb49bca380ff46dca8ce33158b04`
(2026-10-28), the base commit for merges. `package.json` there says 3.2.0. The `v3.2.0` tag itself
is older and MIT only. Archify moved to Apache-2.0 on 2026-10-25 (upstream commit `9c306ee`), so the
pin is a later `main` commit. Its `archify/` folder has not changed since the relicensing merge
`51a2917`. `video_cli.py` runs it on Node from the `nodejs-wheel-binaries` Python package.

Left out:

| Upstream path | Why |
|---|---|
| `examples/` | 13 MB of samples. |
| `SKILL.md` | It tells the agent to add a rule to the person's global rules file so Archify runs unasked, and to pass on update notices. `references/archify-scenes.md` replaces it. |
| `skill-release.json`, `scripts/check-update.mjs`, `scripts/update-contract.mjs`, `scripts/delivery-update-child.mjs` | The update check, which fetches `https://tt-a1i.github.io/archify/skill-updates/archify/stable.json`. |
| `references/update-awareness.md` | How the agent passes on update notices. |
| `references/delivery-contract.md`, `references/explainer-authoring.md` | Archify's delivery workflow and explainers, which `ai-video` does not use. |
| `scripts/generate-brand-marks.mjs`, `scripts/generate-validators.mjs`, `scripts/render-examples.mjs`, `package-lock.json` | Upstream build tooling. |

Kept byte-identical: `NOTICE`, `LICENSE` (Apache-2.0), `LICENSE-MIT` (the historical MIT grants) and
`THIRD_PARTY_NOTICES.md`, with every other file not listed under local changes.

Local changes, each file with a header notice:

- `assets/template.html`, **no generator meta.** Removes `<meta name="generator">`, so a rendered
  diagram does not name Archify.
- `assets/template.html`, **no star link.** Removes the guide's "A star on GitHub helps" link to the
  Archify repository.
- `explainer/render.mjs`, **no colophon.** The explainer footer's Archify mark and repository link
  become an empty string. `ai-video` refuses the explainer type, but `scripts/check-render-output.mjs`
  imports the explainer checks, so the folder ships.
- `bin/delivery-update.mjs`, **no update check.** `startDeliveryUpdateCheck` reports the check as
  disabled and spawns nothing. `bin/finalize.mjs` imports it, so the file stays.

Brand marks: `THIRD_PARTY_NOTICES.md` lists the logos Archify can draw and their licences. Vue's mark
is CC-BY-NC-SA-4.0, a non-commercial licence. A diagram in a commercial video should not show it.

## Credited, not copied

- **demos-not-memos** (https://github.com/markng/demos-not-memos, v0.2.0, commit `9cb026c`) is the source
  of the approach: a narrated browser recording whose lines play while actions run. No code is
  copied. Its repository has no LICENSE file, and its timing design caused the defects
  `ai-video`'s renderer avoids by voicing every line before recording and cutting at a frame it
  finds itself.
