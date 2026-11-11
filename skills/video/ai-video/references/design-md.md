# design.md

Each video bundle has a `design.md`: the recipe the deck follows. It uses Google Labs' DESIGN.md
"alpha" shape (https://github.com/google-labs-code/design.md), as frontend-slides' templates do:
YAML tokens in front matter, then prose rules. Nothing parses it; you read it and apply it. The
prose matters more than the tokens: use it to design any slide type the tokens do not cover.

`video_cli.py new` writes the skill's default (`assets/templates/design.md`). Replace it when the
person gives a brand, a reference deck or a style.

## Token blocks

| Block | How to apply it |
|---|---|
| `version` | Always `alpha`. |
| `name`, `description` | The look in words. Read first. |
| `colors` | CSS custom properties on `:root` in `deck.html`, named after the keys (`--primary`, `--bg`). `{colors.x}` elsewhere refers to them. |
| `charts` | `series` is the colour order for data series. Label directly instead of using legends. |
| `fonts` | Faces for `display`, `body` and `mono`. `source` says where they load from: `Google Fonts`, `Fontshare`, or `self-hosted: brand/<file>.woff2` in `deck/brand/`. |
| `typography` | One CSS rule per role (`hero-title`, `slide-heading`, `body`, …), at the stated px on the 1920×1080 stage. |
| `spacing` | Slide padding (`pad-x`, `pad-y`) and gaps. |
| `shape` | Corner radius, border weight, shadow. |
| `logo` | Paths are relative to `deck/` (so `brand/logo.svg`). `placement` says which slides carry which logo. Never stretch or recolour a logo. |
| `motion` | `style`, `entrance` and `avoid`. Entrances key on `[data-deck-active]` (the deck contract). `transition` is ignored: scenes are joined with cuts. |
| `components` | Reusable parts (card, accent rule, footer, quote). Their `description` says what marks them. |
| `canvas` | Sometimes present in frontend-slides templates. Always 1920×1080 here. |

## Local rules that differ from frontend-slides

- **Self-hosted fonts are allowed**, from `deck/brand/`. frontend-slides allows only Google Fonts and
  Fontshare. Self-hosted fonts make renders work offline and remove the silent fallback risk.
- **Motion is filmed.** Prefer entrances that finish within about a second. Avoid anything that is
  still moving when the narration starts, and anything that loops.
- **No slide transitions.** Each scene is its own clip.

## Diagrams on slides

Draw technical diagrams as inline SVG in the slide, so they animate with the slide and need no other
tool. For a technical look, use the dark slate tokens of the default design and these rules:

- one stroke colour per kind of component: front end `#22d3ee`, back end `#34d399`, database
  `#a78bfa`, cloud `#fbbf24`, security `#fb7185`, message bus `#fb923c`, external `#94a3b8`;
- boxes with `rx="8"`, a translucent fill and a 1.25 px stroke; edges 1.5 px in `#94a3b8`;
- the active edge in `#34d399`, drawn with a `stroke-dashoffset` animation in step with the line
  that talks about it;
- JetBrains Mono for labels.

## Changing the design

A change to `design.md` means rebuilding `deck.html` to match. The rebuilt deck changes every clip's
key, so `render` records every scene again. No audio is voiced again.
