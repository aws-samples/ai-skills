---
title: "ai-video"
sidebar_label: "ai-video"
sidebar_position: 2
---

# `ai-video`

| | |
|---|---|
| Invoke | `/ai-video "<idea>"`, `/ai-video render <bundle>`, either with `--headless`, or a request for a quick video |
| Activation | slash command, or a person's explicit request in the session; never on an agent's own initiative |
| Domain | [video](../) |
| Source | `skills/video/ai-video/SKILL.md` |

## Overview

The skill turns an idea into a narrated 1920×1080 MP4. The agent interviews the person, writes a
storyboard, an HTML deck and the narration, and applies steering notes. A bundled script,
`scripts/video_cli.py`, does everything that must be repeatable: it checks prerequisites, validates
the bundle, voices the narration, records each scene in Chromium and assembles the video with
ffmpeg.

The narration is voiced by Amazon Polly unless a repository or a bundle chooses ElevenLabs. The
default Polly voice is `Stephen` on the `generative` engine, in `us-east-1`. Polly is called through
boto3 with the person's AWS credentials, so the AWS CLI is not needed.

A scene is one of three kinds:

| Source | What it shows |
|---|---|
| `slide` | one slide of the bundle's HTML deck |
| `live` | a real web application, driven step by step, signed in with a saved sign-in |
| `archify` | an animated architecture, sequence, workflow or other diagram, drawn by the vendored Archify renderer |

## The video bundle

Every video lives in a folder, by default a dated one, `<output_path>/YYYY-MM-DD-<slug>/`. It
holds `video.yaml` (scenes, narration, steering and guidance), `design.md`, `deck/deck.html` and
`history.md`. A person can edit any of them by hand and render again. The bundle's `build/` folder
holds the generated audio, clips, MP4 and thumbnail image.

`<output_path>` is the working root the research and document skills use, `docs/working` unless
`.ai-skills.toml` sets another, so a bundle sits beside their folders. The bundle is a working folder
like theirs. Its `README.md` carries the same identity sections and `Status` list, followed by a
guide to the bundle's files, and the working manifest, `<output_path>/README.md`, has a row for it.
The row reads `🆕 Created` once the bundle is made and `🛠️ In progress` after the first render that
finishes. A person checks `Complete` in the bundle's `README.md` when the video is done.

To put a video somewhere else, name the folder in the request, such as "make it in
`docs/videos/demo-test-3`". The script's `new --out` makes the bundle in that folder exactly, with
no date added, when the folder is absent or empty, and refuses a folder that holds anything. A
folder inside the repository needs no confirmation; one outside it is shown to you to approve first.
A bundle in a named folder has no row in the working manifest, so nothing outside that folder is
written. Name a new folder for each new take, and an earlier one is never overwritten.

A render voices only lines whose spoken text or voice changed, and records only scenes that changed.
Deleting `build/` is safe, but the next render voices every line again and pays for it.

The finished video's audio is AAC, mono, at 96 kb/s, because both voices are mono. When the person
asks for a compressed, smaller or storage-friendly video, the agent runs `render --compress`, which
encodes the finished video at H.264 CRF 28 with 64 kb/s audio. Measured on one 5:11 video, that
file is 5.2 MB, against 10.1 MB for the default encode. Only that last encode changes: no line is
voiced and no scene is recorded again. The flag is not saved, so a later render without it writes
the full-quality file again, and `render` reports `compressed` and the file's `size` each time.

The bundle's `DESCRIPTION.md` holds the text to paste when the video is posted and announced, one
`##` section per field: `Title`, `Description`, `Tags`, `Call to action`, `Announcement` and
`Chapters`. The agent writes the first five once, as plain text, from the interview and the
narration. The `Announcement` is a short chat message with emoji, such as for Slack, whose last
line is where the person pastes the video's link once it is uploaded. Each render rewrites only
`Chapters`, from the finished video's scene start times, so a hand edit to any other section is
kept.

## Opening and closing

A video opens on what its subject is, then the problem as a fact or the result, and what the viewer
will be able to do. It closes by
tying back to it, restating the takeaways, and asking for one action, then an end card. The agent
writes both from the bundle's optional `brief` in `video.yaml`:

```yaml
brief:
  outcome: New team members know what happens when they merge.
  takeaways:                      # at most three
    - Every merge to main cuts a release.
  action: Review the open release merge request by Friday.
  references:
    - name: Release guide         # what the end card shows
      url: https://example.com/release-guide
```

Say the takeaways, the action and any document to cite in the request. The skill asks only for the
takeaways or the action a request leaves out, each with a recommended answer, and never asks for
references. A headless run infers the outcome, the takeaways and the action, and lists what it
inferred. It never writes a reference, URL, ticket number or pull request number the request does
not contain.

The end card shows the action and each reference by name. In `deck/deck.html` a reference with a
`url` is a link. `DESCRIPTION.md`'s `Call to action` and the final report list each reference with
its URL.

`validate` reports a top-level `warnings` list that never changes its status. It warns when the
video has no brief, when the closing line starts with a trail-off phrase such as "That's it" or
"In summary", and on the direct-voice, title and US English checks below. `validate` also reports
each scene's estimated `seconds`. When the brief is edited by hand after a build, `validate` reports
`brief_changed: true` and status `needs-build`, so nothing is voiced until the opening and closing
are rewritten and the build is recorded again.

## Narrator and story

Every new video has a narrator and a story, recorded as the first line of the video-wide
`guidance` in `video.yaml`:

```yaml
guidance: |
  Narrator: explainer, speaking to the viewer as "you". Story: Problem, solution, proof, use.
```

The default narrator is an explainer: someone who knows the subject, speaking to the viewer as
"you" and never as "I" or "we". A request that comes from a team ("narrated by the platform team,
as 'we'") gets the team as narrator, and a request for one person's view gets that person as "I".
The skill never asks about the narrator.

The story is one of seven structures, chosen from what the video is for:

| Structure | Chosen when the request |
|---|---|
| Investigation | asks why something failed, or describes a failure to explain |
| Worked example | asks for a deep dive, an architecture or design explanation, or a tour of code |
| Situation, complication, resolution | is about a proposed or planned change: an issue, an epic, a proposal, a plan |
| Answer first | reports findings, results or status, or says "update" or "what changed" |
| Threat and defense | is about something that prevents a recurring problem or protects something |
| Demo first | is about a subject whose visual output is the point |
| Problem, solution, proof, use | matches none of the above |

The first row that matches wins, and a request that names a structure gets that structure. An
interactive run asks which story to tell only when the request names none, with the chosen
structure as the recommended answer. A document the request supplies is material for the video:
the story decides the order, not the document's sections.

Each scene states one takeaway. The slide's headline, or the diagram's title, says it in writing,
and the scene's first sentence says it aloud in other words. The slide shows the evidence, and the
narration never reads it. Reading the headlines alone, in order, gives the video's argument.

A video planned at more than about six minutes is built in parts. Each part opens on a slide that
names it and states its takeaway, and its scenes share one chapter. An interactive run offers one
video in parts, or a short overview plus one video per part.

To change the narrator or the story, name it in the request ("tell it as an investigation"), or
edit the `Narrator:` line and ask for the scenes to be rewritten. Editing the line alone voices and
records nothing.

## Direct voice and US English

The narration states facts about the subject, the organization or the code. It never states what
the viewer feels, wants or has just done, and it says "you" only for something the viewer will do:
the closing action, or a step in a how-to or a demo. The first sentence says what the subject is,
and no scene holds it back for a reveal. A title names its subject, such as "Reelkit product
definition", and is never a teaser, such as "Reelkit: what we're building".

The narration is written in US English, because the voice takes accent cues from the text: a British
form such as "organisation" or "mustn't" can switch a US voice to a British accent in the middle of a
sentence.

`validate` warns, naming the scene and the phrase, on five short exact lists. They are kept in the
skill's `references/structure.md` and `references/narration.md` under the names `validate` uses:

| List | Matched | Example |
|---|---|---|
| `SCENARIO_OPENERS` | at the start of a sentence | "You've just finished…", "Imagine…" |
| `REVEALS` | anywhere in a sentence | "So here's the idea." |
| `SLOGAN` | at the end of a sentence | "send a link, not a file." |
| `TEASER_TITLES` | in the title | "what's new", "From X to Y", a colon followed by "what", "how" or "why" |
| `BRITISH_FORMS` | whole words in the spoken text, after `say_as` | "organisation", "whilst", "mustn't" |

A warning never fails a run. A false match, such as "imagine" inside a quote, takes seconds to
dismiss. The British check reads the text after `say_as`, so a British product name can stay on the
slide and be mapped to its US spoken form.

A new bundle's `video.yaml` shows `settings: {stability: 0.7}` in its commented ElevenLabs example.
A higher stability keeps an ElevenLabs voice's accent steadier from line to line, and can make the
delivery flatter. The value is a starting point that nobody has yet listened to. Amazon Polly has no
such setting. An existing bundle keeps its settings and its cached audio.

## Quick videos and length

A request for a quick video, a quick explainer, or anything with the same meaning, runs as
`--headless`: it asks nothing and lists every default it took. "Quick" says how the video is made. It
never makes the video shorter.

A length the request states ("90s", "three minutes", "a two-minute video") always wins. The run
writes it in seconds as the second line of `guidance`, `Length: 90 seconds.`, and sizes the
storyboard at about 15 seconds a scene. A headless or quick request that states no length targets 300
seconds, about 20 scenes. That is a target, not a minimum: a short subject is never padded. An
interactive run still recommends a length by purpose.

A quick explainer about how a system is built, how a request flows, how data moves or how a state
changes counts as a request for a technical explanation, so it may use Archify scenes. A quick tour
or overview draws its diagrams on slides.

## The end fade

`render` fades the finished video to black and silence over its last second. `render.fade_out` sets
the length, from 0 to 3 seconds; 0 turns it off. The fade never covers the last spoken line: it is
the smaller of `fade_out` and the time after that line, and `render` reports the length it applied
as `fade`. The fade is applied when the clips are joined, so changing it records no scene and
voices no line again.

## The thumbnail

A video whose first scene is a slide opens on that slide fully drawn: the first slide is filmed
after its entrance animations finish, and every later slide keeps its entrance. Each render also
writes `build/<slug>.thumbnail.jpg`, a 1920×1080 image of the first scene's last frame, never
faded, and embeds it in the MP4 as cover art, which Finder shows as the file's icon. The final
report names the image to upload where a platform accepts a custom thumbnail. The image is taken
from the first scene's clip, so writing it records no scene again. If it cannot be written or
embedded, the video is still written and `render` warns.

## The date stamp

The title slide shows the date the bundle was made, `YYYY.MM.DD`, in small italic text in its lower
right corner, and so does the thumbnail. `new` writes the date to `date_stamp` in `video.yaml`, so
a later render shows the same date. Edit it to show another date, or set it to `false` to show none.
`render` adds the stamp while it films the first slide, so `deck/deck.html` never contains it, and
changing it records only the first scene again. A bundle made before the key existed takes the date
from its `YYYY-MM-DD-<slug>` folder name. The stamp is the only date on the title slide: `validate`
warns when the slide's own text holds one. A video whose first scene is a live or Archify scene has
no title slide and no stamp.

## Money

Amazon Polly and ElevenLabs both charge per character. Only `voice --confirm` sends text to the
voice service. `voice` without `--confirm` states the lines and the characters it would send. Every
run states that count, then voices without asking: each line is cached, and a later edit voices only
the lines it changes. When nothing needs voicing, the report says nothing was spent.

The final report shows the storyboard as a table, one row a scene, with its estimated seconds. To
check a video before anything is spent, ask for it to be built but not voiced ("build it, but don't
voice it yet"). The run stops after `validate` and shows the storyboard and the character count.

## Sign-ins for live scenes

A saved sign-in is stored outside the repository, in the person's cache folder, readable only by
them: `~/Library/Caches/ai-video/auth/` on macOS, `%LOCALAPPDATA%\ai-video\auth\` on Windows, and
`$XDG_CACHE_HOME/ai-video/auth/` (default `~/.cache/ai-video/auth/`) elsewhere. The skill states that
path and saves a sign-in only after the person approves it. A headless run never saves one.

## Configuration

The skill reads `[video]`, and the top-level `output_path`, from `.ai-skills.toml` at the repository
root and never writes the file. A key the file does not set takes its default. For example, to voice every video with ElevenLabs:

```toml
[video]
provider = "elevenlabs"
```

| Key | Default | Meaning |
|---|---|---|
| `output_path` | the top-level `output_path`, else `"docs/working"` | where video bundles are created; set it under `[video]` only to keep videos apart from the other skills' working root |
| `provider` | `"polly"` | who voices the narration, `polly` or `elevenlabs`; a bundle's `voice.provider` wins |
| `[video.polly]` `voice` | `"Stephen"` | the Amazon Polly voice; a bundle's `voice.polly.voice` wins |
| `[video.polly]` `engine` | `"generative"` | the Amazon Polly engine; a bundle's `voice.polly.engine` wins |
| `[video.polly]` `region` | `"us-east-1"` | the AWS Region Amazon Polly is called in |
| `[video.elevenlabs]` `voice_id` | `"2KkUKn1TzEOhhKPCZGrT"` | the ElevenLabs voice; a bundle's `voice.elevenlabs.id` wins |
| `[video.elevenlabs]` `model` | `"eleven_v4"` | the ElevenLabs model; a bundle's `voice.elevenlabs.model` wins |
| `[video.browser]` | none | Playwright browser options for every bundle |

## Requirements

- `uv`, which installs the script's Python 3.14 and its packages on first run.
- ffmpeg on `PATH`, or the copy the `imageio-ffmpeg` package bundles.
- Playwright's Chromium.
- For Amazon Polly: AWS credentials that resolve through the standard chain (`AWS_PROFILE`, SSO,
  or environment variables), allowed `polly:SynthesizeSpeech` and `polly:DescribeVoices`.
- For ElevenLabs: `ELEVENLABS_API_KEY`.

`check` reports every missing item in one run, each with the command that fixes it.

## What it never does

- Run on an agent's own initiative.
- Spend before stating the lines and characters it will send.
- Print, store or send a credential anywhere but the request that needs it.
- Fall back to a silent video when the voice service cannot be reached.
- Commit, or put media in git.
- Edit its vendored files (`deck-stage.js`, `viewport-base.css`, `vendor/archify/`).

## Tool grants

**Denial set** — `WebFetch, WebSearch, Skill, NotebookEdit`

| Entry | Reason |
|---|---|
| `WebFetch`, `WebSearch` | The agent fetches no URL. A live scene's web application is opened by the script's Playwright browser, not by the agent. |
| `Skill` | The skill invokes no other skill. The Archify renderer is vendored under `vendor/archify/`. |
| `NotebookEdit` | The files it writes are `video.yaml`, `design.md`, `deck/deck.html`, `history.md`, the bundle's `README.md`, its row in the working manifest, and diagram JSON. |

`Agent` is **not** denied, as for `ai-research`.

**Pre-approval set** — `Bash(uv run:*), Bash(uv --version), Bash(date:*)`

| Entry | Step behind it |
|---|---|
| `Bash(uv run:*)` | Every `video_cli.py` command: `check`, `new`, `built`, `validate`, `voice`, `render`, and `auth`. |
| `Bash(uv --version)` | "Locate the skill", the check that `uv` is installed before anything else runs. It has no `:*`, so it matches that exact command only. |
| `Bash(date:*)` | Step 3's manifest update, which takes the manifest's `Last updated` date from `date +%F`. `video_cli.py new` dates the bundle folder itself. |

`Bash(uv run:*)` also pre-approves `voice --confirm`, the one command that spends money, and
`auth --confirm`, which saves a sign-in. Neither is gated by a prompt from the harness. The body's
rules are the only gate: state the characters before voicing, and save a sign-in only after the
person approves its path.

No denied capability is used by this body.

What these declarations do **not** bound, and how their behaviour was established, is in
[Tool Grant Bounds](../../../explanation/tool-grant-bounds.md).

## Pages

No page is specific to this skill yet — its behaviour is defined by its `SKILL.md`.
