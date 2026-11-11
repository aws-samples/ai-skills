---
# Design recipe for this video's slides, in Google's DESIGN.md "alpha" shape (YAML tokens, then
# prose rules), as frontend-slides' templates use it. The ai-video skill's references/design-md.md
# says how each block is applied. Replace these defaults with your brand's; delete any token or
# section your brand has no rule for. Sizes are px on the fixed 1920x1080 stage.

version: alpha
name: video default
description: "Calm technical: near-black slate background, white headlines, one green accent,
  Inter for words and JetBrains Mono for anything that is code or a diagram label."

colors:
  primary: "#34d399"
  primary-dark: "#059669"
  secondary: "#22d3ee"
  accent: "#fbbf24"
  bg: "#020617"
  surface: "#0f172a"
  ink: "#ffffff"
  body: "#cbd5e1"
  muted: "#94a3b8"
  dark-bg: "#000000"
  dark-ink: "#ffffff"

charts:
  series: ["{colors.primary}", "{colors.secondary}", "{colors.accent}", "{colors.muted}"]
  gridlines: "#1e293b"
  axis-text: "{colors.muted}"

fonts:
  display: "Inter"
  body: "Inter"
  mono: "JetBrains Mono"
  source: "Google Fonts"

typography:
  hero-title:
    fontFamily: "{fonts.display}"
    fontSize: "128px"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-2px"
  slide-heading:
    fontFamily: "{fonts.display}"
    fontSize: "72px"
    fontWeight: 800
    lineHeight: 1.1
  stat-numeral:
    fontFamily: "{fonts.display}"
    fontSize: "180px"
    fontWeight: 800
    lineHeight: 1
  eyebrow:
    fontFamily: "{fonts.mono}"
    fontSize: "22px"
    fontWeight: 600
    letterSpacing: "3px"
    textTransform: uppercase
  body:
    fontFamily: "{fonts.body}"
    fontSize: "36px"
    fontWeight: 400
    lineHeight: 1.45
  code:
    fontFamily: "{fonts.mono}"
    fontSize: "32px"
    fontWeight: 400

spacing:
  pad-x: "120px"
  pad-y: "96px"
  gap-lg: "64px"
  gap-md: "40px"
  gap-sm: "16px"
  card-pad: "40px"

shape:
  radius-card: "12px"
  border-weight: "1.5px"
  shadow: "none"

motion:
  style: restrained
  entrance: "fade up 24px, 600ms, cubic-bezier(.16,1,.3,1), 80ms stagger"
  avoid: "bounce, spin, parallax, anything still moving when the narration starts"

components:
  card:
    background: "{colors.surface}"
    padding: "{spacing.card-pad}"
    borderRadius: "{shape.radius-card}"
    description: "A surface panel with a 1.5px #1e293b border and no shadow."
  accent-rule:
    width: "96px"
    height: "6px"
    background: "{colors.primary}"
    description: "Under the heading of content slides."
---

## Overview

Slides support the narration; they do not repeat it. Each slide carries one idea, in as few words
as a person can read while the line plays. The look is a calm technical drawing: dark slate, thin
lines, one accent colour that marks what the narration is talking about.

**Key characteristics:**

- One idea per slide, and at most about 12 words of body text.
- The accent colour on at most one element per slide.
- Code, commands, file names and flags in JetBrains Mono, exactly as written.

## Colours

- **Primary** (`{colors.primary}`): the accent rule, the key number, the active edge in a diagram.
- **Background** (`{colors.bg}`): every slide.
- Text pairs: ink on bg for headings, body on bg for paragraphs, muted on bg for captions.

## Typography

- Sentence case for headings. At most eight words.
- Display weight 800 only; body 400 and 600.
- Emphasis is colour (primary), never italic.

## Layout

- **Title:** hero title bottom-left inside the padding, eyebrow above it.
- **Content:** eyebrow, the scene's takeaway as the heading, accent rule, then the evidence for
  it: one body block or two columns.
- **Big number:** one stat numeral centred, a caption below it.
- **Diagram:** a full-width inline SVG with JetBrains Mono labels, drawn in step with the narration.
- **Closing:** the end card: the action, then each reference by its name.

## Motion

Entrances key on `[data-deck-active]`, so they replay when the scene is recorded. Every entrance
finishes within one second, before the narration is well under way.

## Do's and Don'ts

- Do keep slides readable at a glance: a viewer hears the line once.
- Don't put the narration's sentences on the slide.
- Don't show steering or guidance notes, or any process label, on a slide.
