# Steering and guidance

A person steers a video by writing notes in `video.yaml`. There are two kinds, and they behave
differently.

| | `steering` | `guidance` |
|---|---|---|
| Lifetime | Once. Applied on the next rebuild, then moved to `history.md`. | Standing. Applied on every rebuild, and stays. |
| Where | On a scene. | On a scene, or video-wide at the top level. |
| Example | "hold two seconds longer, larger title" | "say A-D-R, never 'adder'" |
| On screen or spoken | Never. | Never. |

## Applying steering

1. Run `video_cli.py validate`. Its `unapplied_steering` lists every scene with a note.
2. For each note, change what the note asks for and nothing else:
   - a slide change goes into that scene's `data-scene` element in `deck/deck.html`;
   - a narration change goes into the scene's `narration` (follow `references/narration.md`);
   - a timing change goes into the scene's `hold`, or into `render` when it names the whole video;
   - a source change goes into `source`, but only when the note asks for it. A note that asks for a
     technical explanation counts as asking for `source: archify` (`references/archify-scenes.md`).
3. Apply every guidance note that covers the scenes you touched, and the video-wide guidance.
4. If the rebuild succeeded, run `video_cli.py built --applied <scene> [<scene> …]`. The script empties
   each applied note in `video.yaml`, keeping the file's comments, and appends it to `history.md`
   with the date and the scene.
5. If the rebuild failed, do not run `built --applied`. The note stays, so the next attempt sees it.

`render` refuses to run while any steering is unapplied, because the person expects to see it.

## Notes that need judgement

- **A note that conflicts with guidance.** The steering is the newer instruction: apply it, keep the
  guidance, and say in the report which one you followed. Interactive: ask first if the conflict
  changes meaning, not just look.
- **A note you cannot apply** (it asks for something the deck contract forbids, or is unclear). Leave
  it in place, say why in the report, and do not run `built --applied` for that scene.
- **A note that asks for a technical diagram.** If it asks for a technical explanation, make the
  scene `source: archify` and write its diagram (`references/archify-scenes.md`). Otherwise draw it
  as an inline SVG in the slide. A scene whose source the person edited by hand keeps it (see
  *Hand-edited sources*).

## Hand-edited sources

`built` records each scene's `source`. When `validate` reports `hand_edited_sources`, the person
changed a source by hand since your last build. In an interactive run, ask before changing it back.
In a headless run, keep the person's value and say so in the summary.
