# Archify diagram scenes

An **Archify scene** films an animated technical diagram drawn by Archify, a diagram renderer
vendored in `vendor/archify/`. The diagram fills the 1920×1080 stage, its nodes enter as the scene
starts, and then a light runs along each edge while the narration plays.

## When to use one

Use `source: archify` only when the request, or a scene's `steering`, asks for a technical
explanation: how a system is built, how a request flows, how data moves, or how a state changes.
Never choose it on your own judgement. Any other diagram stays an inline SVG on a slide.

A quick explainer whose subject is one of those four counts as a request for a technical
explanation. For example, "a quick video explaining how a search request flows through the ingestion
service" may use Archify scenes. A quick tour of a team's jobs may not.

A person who asks for a tour, a pitch or an overview has not asked for a technical explanation, even
when a scene shows a system. The choice between an Archify scene and a slide, scene by scene, stays
the same.

## The scene in video.yaml

```yaml
- id: pipeline
  source: archify
  diagram: diagrams/render-pipeline.json   # Archify JSON, one diagram, in the bundle's diagrams/
  theme: dark                              # optional: dark (the default) or light
  narration: "A render films only the scenes that changed."
  hold: 1
```

An Archify scene has one line, its `narration`, voiced and timed exactly like a slide scene's: the
diagram appears, the line starts `render.lead_in` seconds later, and the scene stays `render.tail`
plus `hold` seconds after it. Write the line by `references/narration.md`. Give the entrance time:
open with the scene's point, a short sentence that states its takeaway (`references/story.md`),
before the line names any part of the diagram. A filler phrase such as "Here's how it works." takes
the same time and carries nothing. Narrate one path through the diagram a scene: name the parts in
the order their edges light, at most three in a sentence. A system that needs more is several
scenes.

An Archify scene has no slide in `deck/deck.html`. A video made only of Archify scenes needs no deck.

## The diagram file

`diagram` names one `.json` file directly in the bundle's `diagrams/` folder. Create the folder when
you write the first diagram.

Its `diagram_type` is one of these types:

| `diagram_type` | Use it for |
|---|---|
| `architecture` | Components, the boundaries around them, and how they connect. |
| `workflow` | Steps in lanes, with decisions and hand-offs. |
| `sequence` | Messages between participants, in time order. |
| `dataflow` | Data moving through stages, each flow labelled with what it carries. |
| `lifecycle` | States and the transitions between them. |
| `erd` | Entities, their keys and their relationships. |
| `tree` | A hierarchy, such as a folder tree or a breakdown. |
| `class` | Types, their members and their relationships. |
| `timeline` | Events in time, optionally in lanes. |
| `waterfall` | Timed spans, such as a request's trace. |

Archify's `explainer` type is a scrolling page, not a diagram. `validate` refuses it.

## Writing the diagram

1. Read the type's schema in `vendor/archify/schemas/<type>.schema.json`, and read
   `vendor/archify/schemas/common.schema.json`. The mode schemas use `$ref`, so the shared enums
   live in the common file. Never invent a field: every schema rejects unknown fields.
2. Read `vendor/archify/references/authoring-defaults.md` before the first diagram, for layout and
   routing. Read `vendor/archify/references/authoring-contract.md` when `validate` reports a layout
   or label error you cannot fix from its message.
3. Set `meta.title` to the scene's takeaway as a sentence ("A render films only the scenes that
   changed"), not a topic ("Render pipeline"). Archify shows it above the diagram, so the viewer
   reads it on screen.
4. Set `meta.output` to `<scene-id>.html`. The schema requires it. The script ignores it and writes
   the HTML to `build/archify/`.
5. Keep the diagram readable in one frame. A viewer cannot zoom or scroll a video, so prefer about
   twelve nodes or fewer, with labels of a few words.
6. Omit `meta.animation`, `meta.visual_preset` and `meta.subtitle`. The recorder turns the motion
   on, and the defaults suit a video.
7. Run `validate`. It checks the folder and the type, then runs Archify's own validation and lists
   each of its errors under the scene, with Archify's suggested fix when it has one.

The vendored references also describe Archify's `finalize`, `deliver`, preview and export commands,
and link to pages that are not vendored. Ignore those parts. `ai-video` uses none of them.

## Running Archify

Never run Archify's CLI (`vendor/archify/bin/archify.mjs`) or Node yourself. `video_cli.py` runs
Archify for you:

- `validate` runs Archify's validation on each Archify scene's diagram.
- `render` renders each Archify scene's diagram to HTML in `build/archify/`, then films it.

Node comes through uv, as a Python dependency of the script. `check` reports a `node` item when no
bundle is given, or when the bundle has an Archify scene. A slide-only video never needs Node.

## What the recording shows

- The diagram in Archify's presentation view, with its title, in the scene's `theme`.
- No Archify toolbar, guide, overview map or other control. The recorder hides them.
- No Archify branding. The vendored copy has it removed (`VENDORED.md`).

The recording makes no network request. The recorder blocks every request that is not a local file
or inline data.

## What makes an Archify scene record again

An Archify scene's clip is reused while the diagram's bytes, `theme`, the vendored Archify folder, its
line's audio and length, the render settings, `hold`, the merged browser options and the recorder
version are unchanged. Editing the diagram records the scene again and voices nothing.
