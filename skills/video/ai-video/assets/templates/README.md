---
title: __NAME__
---

# __TITLE__

## Description
What this video is and why it exists, in one or two sentences.

## Requirements
What the video must show or explain when it is done.

## Scope
What the video covers, and what it leaves out.

## Affected Areas
The product, systems or subject areas the video covers.

## Audience
Who watches the video, and what they should know or do afterwards.

## Status
- [ ] Research
- [ ] In progress
- [ ] Complete

## Bundle

This folder is a **video bundle** made by the `ai-video` skill on __DATE__. It holds everything
needed to render the video again, as plain files you can edit by hand. The working manifest, the
`README.md` in the folder above this one, lists it with the other working folders.

| File | What it is |
|---|---|
| `video.yaml` | The source of truth: voice, scenes, narration, steering and guidance. |
| `design.md` | The look the slides follow: colours, type, layout and motion. |
| `deck/deck.html` | The slides, one `<section data-scene="<id>">` per scene. |
| `history.md` | Steering notes that have been applied, with their dates. |
| `DESCRIPTION.md` | The text to paste when you post and announce the video: title, description, tags, call to action, announcement and chapters. Each render rewrites only its chapters. |
| `build/` | Generated audio, clips and the finished `build/__SLUG__.mp4`. Git ignores it. |

To render again after an edit, ask your agent:

```text
/ai-video render __BUNDLE__
```

A render voices only lines whose text or voice changed, and records only scenes that changed. It
states the characters it will send to the voice service (Amazon Polly or ElevenLabs) before it sends any. Deleting `build/` is safe, but
the next render then voices every line again, and pays for it. The first render that finishes checks
`In progress` under Status. Check `Complete` yourself when the video is done.
