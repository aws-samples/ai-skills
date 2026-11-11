# The video bundle

A **video bundle** is one folder that holds everything needed to render one video again. It is
plain files, so a person can edit any of them by hand and ask for a new render. Always say "video bundle".

## Where it lives

`<output_path>/YYYY-MM-DD-<slug>/`, where `output_path` is the working root: `[video] output_path`
in `.ai-skills.toml` when it is set, else the top-level `output_path` the collection's other skills
read, else `docs/working`. `video_cli.py new` creates it, beside any research or document folders
in that root, and reports `exists` when a folder of that name is already there. The script finds a
bundle by its path, or by its slug alone: the newest folder with that slug that holds a
`video.yaml` wins, so a research folder of the same name never matches.

When the person names a folder, `new --out <folder>` creates the bundle in it exactly, with no date
added, and `output_path` is not used. The folder must be absent or empty; one that holds anything
makes `new` report `exists`. A folder that resolves outside the repository makes `new` report
`outside` with its absolute path, and only `--confirm-outside`, after the person approves that path,
creates it there. A named bundle is found by its path, not by its slug.

A bundle is a working folder. Its `README.md` follows the Folder Identity Template in
`references/manifest-update.md`, with its folder's name as the `title`. The working manifest,
`README.md` in the working root, has a row for a bundle directly in the working root, and none for a
bundle elsewhere; `new` and `render` report which as `working_root`.

## Layout

```text
2026-10-28-ai-skills-overview/
├── README.md         the folder's identity and Status, then a guide to these files
├── DESCRIPTION.md    the text to paste when posting and announcing the video (below)
├── video.yaml        the source of truth: voice, scenes, narration, steering, guidance
├── design.md         the look the deck follows (references/design-md.md)
├── history.md        applied steering notes, oldest first
├── scenes/           optional: scene scripts for live scenes (references/live-scenes.md)
├── diagrams/         optional: Archify diagrams for Archify scenes (references/archify-scenes.md)
├── deck/
│   ├── deck.html     one <deck-stage> with one data-scene element per slide scene
│   ├── deck-stage.js vendored; do not edit (VENDORED.md)
│   ├── viewport-base.css  vendored; do not edit
│   └── brand/        optional logos and self-hosted fonts that design.md names
├── .gitignore        ignores build/ and every audio and video file
└── build/            generated; safe to delete, but the next render pays to voice every line again
    ├── audio/        <line>-<key>.mp3, reused while the spoken text and voice are unchanged
    ├── archify/      <scene>-<key>.html, each Archify scene's rendered diagram
    ├── clips/        <scene>-<key>.mp4, reused while the slide, audio and settings are unchanged
    ├── state.json    audio and clip keys, durations, line starts, the sources and brief digest last written, the last render and whether it was compressed
    ├── <slug>.thumbnail.jpg  the thumbnail to upload: the first scene's last frame, 1920×1080
    └── <slug>.mp4    the finished video, with the thumbnail embedded as its cover art
```

## video.yaml

`assets/video.schema.json` checks it; `video_cli.py validate` runs the check. Every field:

| Field | Required | Meaning |
|---|---|---|
| `title` | yes | The video's title, for the README and the report. Not shown unless a slide shows it. |
| `slug` | yes | Kebab-case name; the finished file is `build/<slug>.mp4`. |
| `date_stamp` | no | The date `render` shows in the lower right corner of the title slide, written `YYYY.MM.DD`, or `false` for no stamp. `new` writes the date the bundle was made, so a later render shows the same date. Without the key, the date comes from a folder named `YYYY-MM-DD-<slug>`; a folder with no date gets no stamp, and `validate` and `render` warn. |
| `brief` | no | What the opening and closing are written from (references/structure.md). Every field in it is optional. Never shown or spoken as written. |
| `brief.outcome` | no | What a viewer can do or knows after watching. The opening is written from it. |
| `brief.takeaways` | no | At most three points the closing restates in new words. A fourth fails validation. |
| `brief.action` | no | The one thing a viewer should do next. The closing asks for it, and the end card shows it. |
| `brief.references` | no | Documents to cite. Each has a `name`, the short name the end card shows (required), and a `url` beginning `http://` or `https://` (optional), which the deck links and the report lists. |
| `voice.provider` | no | `polly` or `elevenlabs`. Wins over `[video] provider`. Default `polly`. |
| `voice.polly.voice` | no | Amazon Polly voice ID, such as `Stephen` or `Ruth`. Wins over `[video.polly] voice`. |
| `voice.polly.engine` | no | Amazon Polly engine: `generative`, `long-form`, `neural` or `standard`. Wins over `[video.polly] engine`. |
| `voice.elevenlabs.id` | no | ElevenLabs voice ID. Wins over `[video.elevenlabs] voice_id`. |
| `voice.elevenlabs.model` | no | ElevenLabs model ID. Wins over `[video.elevenlabs] model`. |
| `voice.elevenlabs.settings` | no | ElevenLabs `voice_settings`, sent as given (`stability`, `similarity_boost`, `style`, `use_speaker_boost`, `speed`). |
| `voice.id`, `voice.model`, `voice.settings` | no | Older names for the three ElevenLabs fields, still read. The `voice.elevenlabs` field wins. |
| `voice.say_as` | no | Written form → spoken form, applied to narration before voicing. The slide keeps the written form. |
| `render.fps` | no | Frames per second, 10–60. Default 25. |
| `render.lead_in` | no | Seconds from a slide appearing to its narration starting, at most 0.5. Default 0.3. |
| `render.tail` | no | Seconds a slide stays after its narration, at most 1.5. Default 0.7. |
| `render.gap` | no | Live scenes: seconds from one step's line ending to the next step's line starting, at most 5. Default 1.0. |
| `render.fade_out` | no | Seconds the finished video fades to black and silence at its end, 0–3. Default 1; 0 turns it off. The fade is the smaller of this and the time after the last spoken line, so it never fades a word. `render` reports the length applied as `fade`. |
| `guidance` | no | Video-wide guidance, applied on every rebuild of every scene. Never shown or spoken. A new video's guidance opens with `Narrator: … Story: …`, the narrator and the story it tells (references/story.md), then `Length: <seconds> seconds.`, the length the request stated or the default the run took. |
| `browser` | no | Recording browser options for every scene (see *Browser options*). |
| `scenes` | yes | The ordered list of scenes. |
| `scenes[].id` | yes | Stable kebab-case ID. The slide carries `data-scene="<id>"`. Never renumber IDs. |
| `scenes[].source` | no | What draws the scene: `slide` (the default), `live` (references/live-scenes.md) or `archify` (references/archify-scenes.md). |
| `scenes[].narration` | slide, archify | Exactly what the voice says, before `say_as`. Empty makes a silent scene, which needs `hold`. A live scene has none. |
| `scenes[].diagram` | archify | Archify: `diagrams/<name>.json`, one Archify diagram directly in the bundle's `diagrams/` folder. |
| `scenes[].theme` | no | Archify: `dark` (the default) or `light`. |
| `scenes[].url` | live | The start URL the recording browser opens. |
| `scenes[].auth` | no | Live: the profile name of a sign-in saved with `auth`. Only the name is in the bundle. |
| `scenes[].signed_in` | no | Live: a selector that only a signed-in page shows, for the sign-in test. |
| `scenes[].steps` | live | Live: the ordered steps. Each has `say` (its line, before `say_as`; empty for silence) and `do` (its actions). |
| `scenes[].script` | no | Live: `scenes/<name>.py`, run instead of the steps' actions. The steps then hold only `say`. |
| `scenes[].hold` | no | Extra seconds the scene stays after its narration and tail. Default 0. |
| `scenes[].chapter` | no | The scene's chapter label in `DESCRIPTION.md`. Consecutive scenes with the same label are one chapter. Without one, the label is the `id` with spaces for hyphens and a capital first letter (`live-demo` → `Live demo`). Never shown or spoken, and in no cache key. |
| `scenes[].steering` | no | A one-off change for the next rebuild (references/steering.md). |
| `scenes[].guidance` | no | A standing rule for this scene, applied on every rebuild. Never shown or spoken. |
| `scenes[].browser` | no | Browser options for this scene only. |

### Browser options

`browser` holds Playwright `new_context` options by their Python names (`color_scheme`, `locale`,
`timezone_id`, `device_scale_factor`, `extra_http_headers` and others), `launch` for launch options,
and `file`, a `.yaml` or `.json` file of the same options relative to the bundle. Levels merge, later
winning: the skill's defaults, `[video.browser]` in `.ai-skills.toml`, `browser` in `video.yaml`,
then the scene's `browser`.

The recorder owns `record_video_dir`, `record_video_size`, `viewport`, `storage_state` and
`reduced_motion`. Setting one is an error that names it. A header value must be a `${ENV_VAR}`
reference; the variable is read only while recording, so no token is written to the bundle.

## DESCRIPTION.md

The text a person copies, section by section: into a video platform's upload form, and into a chat
channel to announce the video. `new` writes it with six empty sections, in this order. A section is
a line that is exactly `## <name>`; keep the headings as they are, because `validate` finds the
sections by them.

| Section | Who writes it | What it holds |
|---|---|---|
| `Title` | you, at the build | The title viewers see. It may differ from `video.yaml`'s `title`, which stays the bundle's working title. |
| `Description` | you | One or two short paragraphs: what the viewer learns, and for whom. |
| `Tags` | you | One line of comma-separated tags. |
| `Call to action` | you | What a viewer should do after watching: the brief's `action`, then each of its references by name and URL. A URL only if the person gave one. |
| `Announcement` | you | A short chat message announcing the video, for a channel such as Slack: a few lines, each opening with a Unicode emoji (🎬, 🚀). The last line introduces the link and holds no URL, such as `▶️ Watch it here:`. The person pastes the video's link after it once the video is uploaded. |
| `Chapters` | `render` | One `M:SS <label>` line per chapter (`H:MM:SS` from one hour), from the scene start times of the finished video. Replaced on every successful render; change a label with `scenes[].chapter`, not here. |

A body is pasted exactly as it is written, so write plain text: no Markdown formatting, no HTML
comments, no notes to the person, and no chat formatting (`*bold*`, `<url|text>` links). Write
emoji as characters, never as shortcodes such as `:clapper:`, which show as text outside Slack.

You write the authored sections once, at the build of a new video. After that a person may have
edited them, so change one only when a request asks you to. `render` writes only the `Chapters`
body and leaves every other byte of the file as it is.

`validate` returns a `description` list of what stops the file from being pasted as it is: the file
is missing; an authored section is missing or empty; a body holds `<!--`; `Tags` is not one line, or
has an empty entry. The list never changes `status`, so it never blocks voicing or rendering.

## What validate reports about the brief

- **`brief_changed`.** `built` records a digest of the parsed brief, so re-indenting it or adding a
  comment changes nothing. When the brief differs from the one `built` last recorded, `validate`
  reports `brief_changed: true` and status `needs-build`, and nothing is voiced until the opening and
  closing are rewritten from the new brief and `built` runs again. A bundle built before the brief
  existed has no digest and reports `false`.
- **`warnings`.** A list that never changes the status, separate from `config.warnings`. It warns
  when the video has no brief, and when the closing line starts with a trail-off phrase, naming the
  scene (references/structure.md). The closing line is the first spoken line of the last scene that
  has any, so a silent end card after it is skipped. It also warns on a teaser title, on a sentence
  that assumes the viewer, holds the subject back or ends on a slogan (references/structure.md,
  Direct voice), and on a British form in the spoken text after `say_as` (references/narration.md).
- **`scenes`.** Each scene's `id`, `source`, spoken `characters` after `say_as`, and estimated
  `seconds`: the characters at about 15 a second, plus the scene's `hold`.

## Lines

A **line** is one voiced piece of text. A slide or Archify scene has one line, its `narration`, with
the scene's ID. A live scene has one line per step with a `say`, with the ID `<scene>-<n>`, where `n` counts the
scene's steps from 1. `voice` voices lines, and `state.json` keeps their audio by line ID.

## What the caches key on

- **Audio:** the spoken text after `say_as` and the voice. For Amazon Polly that is the provider, the
  voice and the engine, and not the region. For ElevenLabs it is the voice ID, the model and the
  voice settings. Any change re-voices that line; nothing else does.
- **Clip:** the scene's slide markup, the rest of `deck.html`, every other file in `deck/`, the audio
  and its length, the render settings except `gap` and `fade_out`, `hold`, the merged browser options,
  and the recorder version. A slide that is the video's first scene also keys on being first,
  because it is filmed already drawn (references/deck-contract.md). Reordering scenes records again
  each slide that moves into or out of first place, and no other.
  Rebuilding the deck from a changed `design.md` changes the shared markup, so every clip is recorded
  again, and no audio is.
- **Live clip:** the scene's `url`, `auth` name, `signed_in`, steps, the script's bytes, its lines'
  audio and lengths, the render settings with `gap` but not `fade_out`, `hold`, the merged browser
  options, and the recorder version. Never the sign-in itself, so renewing a sign-in records nothing again.
- **Archify clip:** the diagram's bytes, `theme`, a digest of the vendored `vendor/archify/` folder,
  the audio and its length, the render settings except `gap` and `fade_out`, `hold`, the merged browser
  options, and the recorder version. The rendered HTML in `build/archify/` is keyed by the first three alone.
- **The joined video:** made again on every `render`, from the clips. `fade_out` applies only here,
  so changing it records no scene and voices no line again.
- **The thumbnail:** `build/<slug>.thumbnail.jpg`, taken again on every `render` from the last frame
  of the first scene's clip, which has no end fade, and embedded in the finished video as cover art.
  It never records a scene. If it cannot be taken or embedded, the video is still written, `render`
  adds a warning, and it reports `thumbnail: null` when no image was written.
