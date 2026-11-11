#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = [
#     "playwright>=1.50",
#     "pyyaml>=6.0.2",
#     "ruamel.yaml>=0.18.10",
#     "jsonschema>=4.23.0",
#     "boto3>=1.35",
#     "imageio-ffmpeg>=0.6.0",
#     "nodejs-wheel-binaries>=22",
# ]
# ///
"""Render a video bundle: the deterministic half of ``ai-video``.

The agent running the skill writes the storyboard, the deck and the narration, and applies
steering. This script does everything that must be repeatable and cheap:

    check     Report every missing prerequisite in one run: uv, ffmpeg, Playwright's Chromium,
              the voice provider's credentials (AWS credentials for Amazon Polly, or
              ELEVENLABS_API_KEY, by name only), whether the voice is available, whether git ignores the bundle's media, Node for Archify scenes, and whether every
              live scene opens signed in.
    new       Create a dated video bundle in the working root: [video] output_path, else the
              top-level output_path, else docs/working. With --out, create it at that folder
              exactly; a folder outside the repository also needs --confirm-outside.
    validate  Check video.yaml against the schema and the deck, and report unapplied steering,
              hand-edited scene sources, a brief changed since the last build, warnings, and what
              stops DESCRIPTION.md from being pasted as it is.
    built     After the agent's rebuild: record each scene's source and a digest of the brief, and
              move applied steering notes to history.md.
    voice     Voice every line that has no cached audio. Without --confirm it only states the
              characters it would send.
    render    Record every scene that has no cached clip, then assemble build/<slug>.mp4, fading
              its end out, write build/<slug>.thumbnail.jpg and embed it as cover art, write its
              chapters into DESCRIPTION.md, and check In progress in README.md's Status. It never
              calls the voice service.
    auth      Save a sign-in for live scenes: a visible browser opens, the person signs in, and the
              sign-in is saved by profile name in the user's cache folder, readable only by them.

Run it with uv from anywhere::

    uv run <skill-dir>/scripts/video_cli.py check --repo . --bundle <bundle>

Every command prints one JSON object. Exit codes: 0 success (for ``voice``, also a plan); 1 the
command could not do its job, and the JSON says why; 2 the input is unusable.

Amazon Polly, the default, is called through boto3 with the standard AWS credential chain; no AWS
CLI is needed. The ElevenLabs key is read from ELEVENLABS_API_KEY and only ever sent as a request
header. No credential is ever printed or written. A saved sign-in is a secret too: it is only ever named by its profile, and
its contents are never printed. AI_VIDEO_ELEVENLABS_URL points the script at another server (the
tests' fake), AI_VIDEO_FFMPEG at a specific ffmpeg binary, AI_VIDEO_AUTH_DIR at another folder for
saved sign-ins, and AI_VIDEO_AUTH_HEADLESS=1 runs auth's browser headless (for the tests).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess  # nosec B404 # runs only ffmpeg and git, with argument lists
import sys
import tempfile
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ASSETS = SKILL_DIR / "assets"
CONFIG_FILE = ".ai-skills.toml"
SECTION = "video"
# output_path is the working root the collection's other skills use: [video] output_path, then the
# top-level output_path, then this default.
DEFAULTS = {
    "output_path": "docs/working",
    "provider": "polly",
}
# The top-level keys this skill reads. The rest of the file's top level belongs to other skills.
SHARED_KEYS = ("output_path",)
# Each voice provider's own table, [video.<provider>], and its defaults.
PROVIDER_DEFAULTS = {
    "polly": {"voice": "Stephen", "engine": "generative", "region": "us-east-1"},
    "elevenlabs": {"voice_id": "2KkUKn1TzEOhhKPCZGrT", "model": "eleven_v4"},
}
# Flat [video] keys of the ElevenLabs-only version, still read as [video.elevenlabs].
LEGACY_KEYS = ("voice_id", "model")
# Amazon Polly's limit on one SynthesizeSpeech request.
POLLY_MAX_CHARS = 3000
KEY_VAR = "ELEVENLABS_API_KEY"
API_URL = "https://api.elevenlabs.io"
SUPPORTED_SOURCES = {"slide", "live", "archify"}
ARCHIFY_DIR = SKILL_DIR / "vendor" / "archify"
ARCHIFY_TYPES = ("architecture", "workflow", "sequence", "dataflow", "lifecycle", "erd", "tree", "class",
                 "timeline", "waterfall")
ACTIONS = ("goto", "click", "hover", "fill", "type", "press", "scroll", "wait")
PROFILE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# How long a click target is outlined before the click, so a viewer sees what is clicked.
OUTLINE_MS = 300
# gap: seconds between one live step's line ending and the next step's line starting.
# fade_out: seconds the joined video fades to black and silence at its end.
RENDER_DEFAULTS = {"fps": 25, "lead_in": 0.3, "tail": 0.7, "gap": 1.0, "fade_out": 1.0}
# Bumped when a change to the recorder would change a clip's frames, so old clips are not reused.
RECORDER_VERSION = 2
STAGE = {"width": 1920, "height": 1080}
# Keys the recorder depends on; a bundle or setting may not override them.
OWNED_KEYS = ("record_video_dir", "record_video_size", "viewport", "storage_state", "reduced_motion")
ENV_REF = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
MEDIA_PROBES = ("build/probe.mp4", "probe.mp3", "probe.webm")
# How long the magenta cover stays up before the slide is shown; each retry waits longer.
COVER_HOLD_MS = (800, 2000, 4000)
# DESCRIPTION.md: the text a person pastes, section by section, to post and announce the video.
# The agent writes the authored sections; render writes Chapters.
DESCRIPTION_FILE = "DESCRIPTION.md"
AUTHORED_SECTIONS = ("Title", "Description", "Tags", "Call to action", "Announcement")
CHAPTERS = "Chapters"
# One item of README.md's `## Status`, the three-item list every working folder's README carries.
STATUS_ITEM = re.compile(r"- \[([ xX])\] (Research|In progress|Complete)\s*")
# Openings of a closing line that trails off. references/structure.md lists the same phrases.
TRAIL_OFFS = ("That's it", "That's all", "In summary", "To wrap up", "To sum up")
# Direct voice. references/structure.md lists the same phrases under these names. Each match is a
# warning, never an error, and each list is short and exact: a broad pattern such as "a sentence that
# starts with 'you'" would flag every correct how-to step.
# Sentence openings that assume the viewer's situation, matched at the start of a sentence.
SCENARIO_OPENERS = ("you've just", "you've finished", "you've ever", "you're working", "you're tired",
                    "you're stuck", "you know when", "imagine", "picture this", "if you've ever", "ever wondered",
                    "we've all")
# Phrases that hold the subject back for a reveal, matched anywhere in a sentence.
REVEALS = ("here's the idea", "here's the thing", "here's the catch", "here's where it gets",
           "the moment that matters", "the best part")
# A slogan ending: ", not" and one to four words that end the sentence, as in "send a link, not a file."
SLOGAN = re.compile(r",\s+not(?:\s+[\w'-]+){1,4}[.!?\"”]*$")
# Titles that tease rather than name the subject, matched in the lowercased title, plus two forms:
# "From X to Y", and a colon followed by "what", "how" or "why".
TEASER_TITLES = ("what we're building", "what's next", "what's new")
TEASER_COLON = re.compile(r":\s*(what|how|why)\b")
# Whole British words that steer a US voice towards a British accent, checked in the spoken text after
# say_as. references/narration.md lists the same words. No suffix pattern: "-ise" and "our" also match
# US words such as "promise", "exercise", "four" and "hour".
BRITISH_FORMS = ("organisation", "organisations", "organise", "organised", "organises", "organising", "colour",
                 "colours", "behaviour", "behaviours", "licence", "centre", "centres", "favourite", "favourites",
                 "analyse", "analysed", "recognise", "recognised", "recognises", "realise", "realised", "realises",
                 "prioritise", "prioritised", "prioritises", "utilise", "utilised", "utilises", "whilst", "amongst",
                 "learnt", "mustn't")
BRITISH_WORD = re.compile(r"\b(" + "|".join(map(re.escape, BRITISH_FORMS)) + r")\b", re.IGNORECASE)
# A sentence ends at ., ! or ? followed by whitespace.
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
# Spoken characters a second, for validate's estimate: about 150 words a minute, so the two-minute video
# of references/narration.md is about 1,800 characters.
CHARS_PER_SECOND = 15
# The title slide's date stamp: video.yaml's date_stamp, else a bundle folder named YYYY-MM-DD-<slug>.
DATED_FOLDER = re.compile(r"(\d{4})-(\d{2})-(\d{2})-")
# Dates validate looks for on the title slide besides the stamp: 2026-10-30, 2026.10.30, 2026/10/30,
# and a month name followed by a year, as in October 2026 or Oct 30, 2026.
OTHER_DATES = re.compile(
    r"\b\d{4}[-./]\d{1,2}[-./]\d{1,2}\b|\b(?:January|February|March|April|May|June|July|August|September"
    r"|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\.?\s+"
    r"(?:\d{1,2}(?:st|nd|rd|th)?,?\s+)?\d{4}\b", re.IGNORECASE)


class UsageError(Exception):
    """The input is unusable (exit 2)."""


class Failure(Exception):
    """The command could not do its job (exit 1)."""

    def __init__(self, status: str, message: str, **extra):
        super().__init__(message)
        self.payload = {"status": status, "message": message, **extra}


# ═══════════════════════════════════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════════════════════════════════


def string_keys(table: dict, known: dict, where: str | None, warnings: list[str]) -> dict:
    """The keys of `table` that `known` names and that hold a non-empty string; a warning for the rest.

    `where` names the table, or is None for the file's top level.
    """
    usable = {}
    for key, value in table.items():
        name = f"[{where}] {key}" if where else key
        if key not in known:
            warnings.append(f"{CONFIG_FILE}: {name} is not a video key and is ignored")
        elif not isinstance(value, str) or not value.strip():
            warnings.append(
                f"{CONFIG_FILE}: {name} must be a non-empty string, not {value!r}; "
                f"using {known[key]!r} this run"
            )
        else:
            usable[key] = value
    return usable


def load_section(root: Path) -> tuple[dict, dict, dict, dict, list[str]]:
    """Read `[video]` and the top-level keys it falls through to: (usable [video] values, usable
    top-level values, provider tables, [video.browser], warnings). Never written."""
    path = root / CONFIG_FILE
    if not path.is_file():
        return {}, {}, {}, {}, []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return {}, {}, {}, {}, [f"{CONFIG_FILE} cannot be parsed ({exc}); using the defaults"]
    warnings = []
    shared = string_keys({k: data[k] for k in SHARED_KEYS if k in data}, DEFAULTS, None, warnings)
    section = data.get(SECTION, {})
    if not isinstance(section, dict):
        return {}, shared, {}, {}, warnings + [f"{CONFIG_FILE}: [{SECTION}] is not a table; using the defaults"]
    browser = section.get("browser", {})
    if not isinstance(browser, dict):
        warnings.append(f"{CONFIG_FILE}: [{SECTION}.browser] is not a table and is ignored")
        browser = {}
    tables = {}
    for name, known in PROVIDER_DEFAULTS.items():
        table = section.get(name, {})
        if not isinstance(table, dict):
            warnings.append(f"{CONFIG_FILE}: [{SECTION}.{name}] is not a table and is ignored")
            table = {}
        tables[name] = string_keys(table, known, f"{SECTION}.{name}", warnings)
    flat = {k: v for k, v in section.items() if k != "browser" and k not in PROVIDER_DEFAULTS}
    usable = string_keys(flat, {**DEFAULTS, **shared, **{k: PROVIDER_DEFAULTS["elevenlabs"][k] for k in LEGACY_KEYS}},
                         SECTION, warnings)
    tables["elevenlabs"] = {**{k: usable.pop(k) for k in LEGACY_KEYS if k in usable}, **tables["elevenlabs"]}
    if "provider" in usable and usable["provider"] not in PROVIDER_DEFAULTS:
        warnings.append(f"{CONFIG_FILE}: [{SECTION}] provider must be one of {', '.join(PROVIDER_DEFAULTS)}, "
                        f"not {usable.pop('provider')!r}; using {DEFAULTS['provider']!r} this run")
    return usable, shared, tables, browser, warnings


def settings(root: Path) -> dict:
    """Resolve [video]: each key the file sets, else the top-level key of that name it sets, else its
    default. The file is never written."""
    given, shared, tables, browser, warnings = load_section(root)
    values = {key: given.get(key, default) for key, default in {**DEFAULTS, **shared}.items()}
    for name, defaults in PROVIDER_DEFAULTS.items():
        values[name] = {key: tables.get(name, {}).get(key, default) for key, default in defaults.items()}
    return {"values": values, "browser": browser, "warnings": warnings}


# ═══════════════════════════════════════════════════════════════════
# BUNDLE
# ═══════════════════════════════════════════════════════════════════


def resolve_bundle(root: Path, given: str) -> Path:
    """A bundle path, or a short name resolved under the output root (newest first)."""
    path = Path(given)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if (path / "video.yaml").is_file():
        return path
    base = root / settings(root)["values"]["output_path"]
    if base.is_dir():
        matches = sorted(
            (p for p in base.iterdir() if p.is_dir() and (p / "video.yaml").is_file()
             and (p.name == given or re.fullmatch(rf"\d{{4}}-\d{{2}}-\d{{2}}-{re.escape(given)}", p.name))),
            reverse=True,
        )
        if matches:
            return matches[0]
    raise UsageError(f"no video bundle at {given!r}, and none named so under {base}")


def in_working_root(root: Path, bundle: Path, conf: dict) -> bool:
    """Whether the bundle sits directly in the working root, so the working manifest has a row for it."""
    return bundle.resolve().parent == (root / conf["values"]["output_path"]).resolve()


def read_video(bundle: Path) -> dict:
    import yaml

    try:
        data = yaml.safe_load((bundle / "video.yaml").read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise UsageError(f"video.yaml cannot be parsed: {exc}") from exc
    if not isinstance(data, dict):
        raise UsageError("video.yaml must be a mapping")
    return data


def state_path(bundle: Path) -> Path:
    return bundle / "build" / "state.json"


def read_state(bundle: Path) -> dict:
    path = state_path(bundle)
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def write_state(bundle: Path, state: dict) -> None:
    path = state_path(bundle)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def brief_digest(video: dict) -> str:
    """A digest of the parsed brief, so re-indenting or commenting it changes nothing. No brief hashes null."""
    blob = json.dumps(video.get("brief"), sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def scene_source(scene: dict) -> str:
    return scene.get("source") or "slide"


def render_settings(video: dict) -> dict:
    return {**RENDER_DEFAULTS, **(video.get("render") or {})}


def keyed_render(render: dict, source: str) -> dict:
    """The render settings a scene's clip key covers. Only a live scene pauses between lines, and the
    end fade is applied when the clips are joined, so no clip key covers it."""
    left_out = ("fade_out",) if source == "live" else ("gap", "fade_out")
    return {k: v for k, v in render.items() if k not in left_out}


def voice_of(video: dict, conf: dict) -> dict:
    """The provider and its settings, the bundle's winning over [video], plus say_as."""
    voice = video.get("voice") or {}
    provider = voice.get("provider") or conf["provider"]
    say_as = voice.get("say_as") or {}
    if provider == "polly":
        own = voice.get("polly") or {}
        return {"provider": provider, "voice": own.get("voice") or conf["polly"]["voice"],
                "engine": own.get("engine") or conf["polly"]["engine"], "region": conf["polly"]["region"],
                "say_as": say_as}
    if provider == "elevenlabs":
        own = voice.get("elevenlabs") or {}
        return {"provider": provider, "id": own.get("id") or voice.get("id") or conf["elevenlabs"]["voice_id"],
                "model": own.get("model") or voice.get("model") or conf["elevenlabs"]["model"],
                "settings": own.get("settings") or voice.get("settings") or {}, "say_as": say_as}
    return {"provider": provider, "say_as": say_as}  # validate reports the unknown provider


def voice_report(voice: dict) -> dict:
    """What a command reports about the voice: everything but say_as and ElevenLabs settings."""
    return {k: v for k, v in voice.items() if k not in ("say_as", "settings")}


def spoken(text: str, say_as: dict) -> str:
    """Apply say_as, longest written form first, so '--headless' wins over '--'."""
    for written in sorted(say_as, key=len, reverse=True):
        text = text.replace(written, say_as[written])
    return text.strip()


def scene_lines(scene: dict, say_as: dict) -> list[tuple[str, int | None, str]]:
    """(line ID, step index or None, spoken text) for every voiced line of a scene.

    A slide scene has one line, named after the scene. A live scene has one per step with a say
    line, named <scene>-<n> from 1; a silent step has none.
    """
    if scene_source(scene) == "live":
        out = []
        for index, step in enumerate(scene.get("steps") or []):
            text = spoken((step or {}).get("say") or "", say_as) if isinstance(step, dict) else ""
            if text:
                out.append((f"{scene['id']}-{index + 1}", index, text))
        return out
    text = spoken(scene.get("narration") or "", say_as)
    return [(scene["id"], None, text)] if text else []


def audio_key(text: str, voice: dict) -> str:
    if voice["provider"] == "elevenlabs":
        # The key of the ElevenLabs-only version, unchanged, so its cached audio is still reused.
        fields = {"text": text, "voice": voice["id"], "model": voice["model"], "settings": voice["settings"]}
    else:
        fields = {"provider": voice["provider"], "text": text, "voice": voice["voice"], "engine": voice["engine"]}
    blob = json.dumps(fields, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ═══════════════════════════════════════════════════════════════════
# DESCRIPTION
# ═══════════════════════════════════════════════════════════════════


def description_spans(lines: list[str]) -> dict[str, tuple[int, int]]:
    """Each section of DESCRIPTION.md, by name: the (start, end) slice of `lines` holding its body.

    A section starts at a line that is exactly `## <name>` for a known name, and its body runs to
    the next line starting with `## `, or the end. Any other heading is the person's and is left
    alone; so is a known heading's second occurrence.
    """
    known = (*AUTHORED_SECTIONS, CHAPTERS)
    spans: dict[str, tuple[int, int]] = {}
    current = None
    for index, line in enumerate(lines):
        if not line.startswith("## "):
            continue
        if current is not None:
            spans[current[0]] = (current[1], index)
        name = line[3:].rstrip()
        current = (name, index + 1) if name in known and name not in spans else None
    if current is not None:
        spans[current[0]] = (current[1], len(lines))
    return spans


def description_bodies(text: str) -> dict[str, str]:
    """Each section's body, without its outer blank lines."""
    lines = text.splitlines(keepends=True)
    return {name: "".join(lines[start:end]).strip() for name, (start, end) in description_spans(lines).items()}


def description_problems(bundle: Path) -> list[str]:
    """What stops DESCRIPTION.md from being pasted as it is. Never a validation error."""
    path = bundle / DESCRIPTION_FILE
    if not path.is_file():
        return [f"{DESCRIPTION_FILE} does not exist; write it from the skill's assets/templates/{DESCRIPTION_FILE}"]
    bodies = description_bodies(path.read_text(encoding="utf-8"))
    problems = []
    for name in AUTHORED_SECTIONS:
        if name not in bodies:
            problems.append(f"{DESCRIPTION_FILE}: there is no line that is exactly '## {name}'")
        elif not bodies[name]:
            problems.append(f"{DESCRIPTION_FILE}: ## {name} is empty")
    for name, body in bodies.items():
        if "<!--" in body:
            problems.append(f"{DESCRIPTION_FILE}: ## {name} holds an HTML comment, which would be pasted with it")
    tags = bodies.get("Tags")
    if tags and "\n" in tags:
        problems.append(f"{DESCRIPTION_FILE}: ## Tags must be one line of comma-separated tags")
    elif tags and any(not tag.strip() for tag in tags.split(",")):
        problems.append(f"{DESCRIPTION_FILE}: ## Tags has an empty entry between commas")
    return problems


def chapter_label(scene: dict) -> str:
    chapter = scene.get("chapter")
    if isinstance(chapter, str) and chapter.strip():
        return chapter.strip()
    return scene["id"].replace("-", " ").capitalize()


def chapter_time(seconds: float) -> str:
    """A start, rounded down to whole seconds: M:SS, or H:MM:SS from one hour."""
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def chapter_lines(scenes: list[dict], starts: list[dict]) -> list[str]:
    """One `<time> <label>` line per chapter. A scene with the previous scene's label continues its chapter."""
    by_id = {s["id"]: s for s in scenes}
    lines, last = [], None
    for entry in starts:
        label = chapter_label(by_id[entry["scene"]])
        if label != last:
            lines.append(f"{chapter_time(entry['start'])} {label}")
            last = label
    return lines


def with_chapters(text: str, chapters: list[str]) -> str:
    """`text` with the ## Chapters body replaced by `chapters`, or the section appended. Nothing else changes."""
    lines = text.splitlines(keepends=True)
    body = "\n" + "".join(f"{line}\n" for line in chapters)
    span = description_spans(lines).get(CHAPTERS)
    if span is None:
        if text and not text.endswith("\n"):
            text += "\n"
        return text + ("\n" if text else "") + f"## {CHAPTERS}\n" + body
    start, end = span
    head = "".join(lines[:start])
    if not head.endswith("\n"):
        head += "\n"
    if end < len(lines):
        body += "\n"
    return head + body + "".join(lines[end:])


def write_chapters(bundle: Path, scenes: list[dict], starts: list[dict]) -> list[str]:
    """Rewrite DESCRIPTION.md's chapters after a render; a warning for each thing that stopped it."""
    path = bundle / DESCRIPTION_FILE
    if not path.is_file():
        return [f"{DESCRIPTION_FILE} does not exist, so no chapters were written"]
    tmp = path.with_suffix(".tmp")
    try:
        # newline="" keeps every line ending as it is, so only the chapters' bytes change.
        with open(path, encoding="utf-8", newline="") as handle:
            text = handle.read()
        with open(tmp, "w", encoding="utf-8", newline="") as handle:
            handle.write(with_chapters(text, chapter_lines(scenes, starts)))
        os.replace(tmp, path)
    except (OSError, UnicodeDecodeError) as exc:
        tmp.unlink(missing_ok=True)
        return [f"{DESCRIPTION_FILE}: the chapters could not be written ({exc})"]
    return []


# ═══════════════════════════════════════════════════════════════════
# README STATUS
# ═══════════════════════════════════════════════════════════════════


def check_in_progress(bundle: Path) -> tuple[bool, list[str]]:
    """After a render, check `In progress` under README.md's `## Status` unless it or `Complete` is
    checked already: (whether the README changed, a warning for each thing that stopped it).

    `Research` and `Complete` are never checked here; `Complete` is a person's to check. A README
    with no `In progress` item, such as one made before the README had a Status, is left alone.
    """
    path = bundle / "README.md"
    if not path.is_file():
        return False, []
    tmp = path.with_suffix(".tmp")
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            lines = handle.read().splitlines(keepends=True)
        start = next((i + 1 for i, line in enumerate(lines) if line.rstrip() == "## Status"), len(lines))
        end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
        items: dict[str, tuple[int, bool]] = {}
        for index in range(start, end):
            if match := STATUS_ITEM.fullmatch(lines[index]):
                items.setdefault(match.group(2), (index, match.group(1) != " "))
        checked = {name for name, (_, on) in items.items() if on}
        if "In progress" not in items or checked & {"In progress", "Complete"}:
            return False, []
        index = items["In progress"][0]
        lines[index] = lines[index].replace("[ ]", "[x]", 1)
        # newline="" keeps every line ending as it is, so only the checkbox's byte changes.
        with open(tmp, "w", encoding="utf-8", newline="") as handle:
            handle.write("".join(lines))
        os.replace(tmp, path)
    except (OSError, UnicodeDecodeError) as exc:
        tmp.unlink(missing_ok=True)
        return False, [f"README.md: In progress could not be checked ({exc})"]
    return True, []


# ═══════════════════════════════════════════════════════════════════
# BROWSER OPTIONS
# ═══════════════════════════════════════════════════════════════════


def load_browser_level(level: dict | None, base: Path, where: str, errors: list[str]) -> dict:
    """One level of browser options, with `file` loaded in place and the level's own keys on top."""
    if not level:
        return {}
    if not isinstance(level, dict):
        errors.append(f"{where}: browser must be a mapping")
        return {}
    merged: dict = {}
    if "file" in level:
        path = (base / str(level["file"])).resolve()
        if not path.is_file():
            errors.append(f"{where}: browser.file {level['file']} does not exist")
        else:
            try:
                if path.suffix == ".json":
                    loaded = json.loads(path.read_text(encoding="utf-8"))
                else:
                    import yaml

                    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (ValueError, Exception) as exc:  # noqa: BLE001 - any parse error is reported
                errors.append(f"{where}: browser.file {level['file']} cannot be parsed ({exc})")
                loaded = {}
            if isinstance(loaded, dict):
                merged = combine(merged, loaded)
            else:
                errors.append(f"{where}: browser.file {level['file']} must hold a mapping")
    return combine(merged, {k: v for k, v in level.items() if k != "file"})


def combine(lower: dict, upper: dict) -> dict:
    """Later wins key by key; `launch` and `extra_http_headers` merge one level deeper."""
    out = dict(lower)
    for key, value in upper.items():
        if key in ("launch", "extra_http_headers") and isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = {**out[key], **value}
        else:
            out[key] = value
    return out


def check_browser(options: dict, where: str, errors: list[str]) -> None:
    for key in OWNED_KEYS:
        if key in options:
            errors.append(f"{where}: browser.{key} is set by the recorder and cannot be changed")
    headers = options.get("extra_http_headers") or {}
    if not isinstance(headers, dict):
        errors.append(f"{where}: browser.extra_http_headers must be a mapping")
        return
    for name, value in headers.items():
        if not isinstance(value, str) or not ENV_REF.match(value):
            errors.append(
                f"{where}: browser.extra_http_headers.{name} must be a ${{ENV_VAR}} reference, "
                "so no token is written to the bundle"
            )
    launch = options.get("launch")
    if launch is not None and not isinstance(launch, dict):
        errors.append(f"{where}: browser.launch must be a mapping")


def browser_options(root: Path, bundle: Path, conf: dict, video: dict, scene: dict, errors: list[str]) -> dict:
    """Skill defaults, then [video.browser], then video.yaml's browser, then the scene's."""
    levels = [
        (conf["browser"], root, f"{CONFIG_FILE} [video.browser]"),
        (video.get("browser"), bundle, "video.yaml"),
        (scene.get("browser"), bundle, f"scene {scene.get('id')}"),
    ]
    merged: dict = {}
    for level, base, where in levels:
        loaded = load_browser_level(level, base, where, errors)
        check_browser(loaded, where, errors)
        merged = combine(merged, loaded)
    return merged


# ═══════════════════════════════════════════════════════════════════
# TOOLS
# ═══════════════════════════════════════════════════════════════════


def find_ffmpeg() -> tuple[str | None, str]:
    forced = os.environ.get("AI_VIDEO_FFMPEG")
    if forced:
        return (forced, "AI_VIDEO_FFMPEG") if Path(forced).is_file() else (None, "AI_VIDEO_FFMPEG")
    found = shutil.which("ffmpeg")
    if found:
        return found, "PATH"
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe(), "imageio-ffmpeg"
    except Exception:  # noqa: BLE001 - any failure means no bundled binary
        return None, "none"


def need_ffmpeg() -> str:
    exe, _ = find_ffmpeg()
    if not exe:
        raise Failure("missing", "ffmpeg was not found; run check for the install command")
    return exe


def run_ffmpeg(ffmpeg: str, args: list[str]) -> subprocess.CompletedProcess:
    proc = subprocess.run([ffmpeg, "-hide_banner", "-y", *args], capture_output=True)  # nosec B603 # argv list; ffmpeg path from find_ffmpeg()
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-8:]
        raise Failure("error", "ffmpeg failed", ffmpeg_stderr=tail)
    return proc


def media_duration(ffmpeg: str, path: Path) -> float:
    """Decode the file and read the last reported time: exact, and needs no ffprobe."""
    proc = subprocess.run(  # nosec B603 # argv list; ffmpeg path from find_ffmpeg()
        [ffmpeg, "-hide_banner", "-nostats", "-stats_period", "0.1", "-stats", "-i", str(path), "-f", "null", "-"],
        capture_output=True,
    )
    text = proc.stderr.decode("utf-8", "replace")
    times = re.findall(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not times:
        raise Failure("error", f"could not read the duration of {path.name}")
    h, m, s = times[-1]
    return int(h) * 3600 + int(m) * 60 + float(s)


def media_facts(ffmpeg: str, path: Path) -> dict:
    """Stream facts from `ffmpeg -i`, so ffprobe is never required."""
    proc = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True)  # nosec B603 # argv list; ffmpeg path from find_ffmpeg()
    text = proc.stderr.decode("utf-8", "replace")
    facts: dict = {}
    video = re.search(r"Stream #.*Video: (\w+)[^,]*, (\w+)[^,]*(?:\([^)]*\))?, (\d+)x(\d+)", text)
    if video:
        facts.update(video_codec=video.group(1), pix_fmt=video.group(2),
                     width=int(video.group(3)), height=int(video.group(4)))
    audio = re.search(r"Stream #.*Audio: (\w+)[^,]*(?:, (\d+) Hz, ([^,\n]+?)(?=,| \(|\n|$))?", text)
    if audio:
        facts["audio_codec"] = audio.group(1)
        if audio.group(2):
            facts.update(sample_rate=int(audio.group(2)), channel_layout=audio.group(3))
    return facts


def chromium_status() -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        return False, f"Playwright for Python is not importable ({exc})"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            version = browser.version
            browser.close()
        return True, f"Chromium {version}"
    except Exception as exc:  # noqa: BLE001 - the message names what is missing
        first = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        return False, first


def run_node(args: list[str]) -> subprocess.CompletedProcess:
    """Run Node from the nodejs-wheel-binaries package, so a person needs nothing beyond uv."""
    import nodejs_wheel

    return nodejs_wheel.node(args, return_completed_process=True, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")


def node_status() -> tuple[bool, str]:
    try:
        proc = run_node(["--version"])
    except Exception as exc:  # noqa: BLE001 - the message names what is missing
        first = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        return False, f"Node from nodejs-wheel could not run ({first})"
    if proc.returncode != 0:
        return False, f"Node from nodejs-wheel exited {proc.returncode}"
    return True, f"Node {proc.stdout.strip()} from nodejs-wheel"


def run_archify(args: list[str]) -> subprocess.CompletedProcess:
    return run_node([str(ARCHIFY_DIR / "bin" / "archify.mjs"), *args])


def playwright_version() -> str:
    from importlib.metadata import version

    try:
        return version("playwright")
    except Exception:  # noqa: BLE001
        return ""


# ═══════════════════════════════════════════════════════════════════
# ELEVENLABS
# ═══════════════════════════════════════════════════════════════════


def api_url() -> str:
    return os.environ.get("AI_VIDEO_ELEVENLABS_URL", API_URL).rstrip("/")


def api_request(method: str, path: str, body: dict | None = None, accept: str = "application/json"):
    key = os.environ.get(KEY_VAR, "")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(api_url() + path, data=data, method=method)
    request.add_header("xi-api-key", key)
    request.add_header("Accept", accept)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    # The URL is API_URL, an https constant, or AI_VIDEO_ELEVENLABS_URL, which only the person running
    # the script sets (the tests' fake server). Nothing in a bundle can choose it.
    return urllib.request.urlopen(request, timeout=120)  # nosec B310


def voice_available(voice_id: str) -> tuple[bool, str]:
    """A free GET of the voice. Never spends characters."""
    try:
        with api_request("GET", f"/v1/voices/{voice_id}") as response:
            info = json.loads(response.read() or b"{}")
        return True, f"voice {voice_id} ({info.get('name', 'unnamed')}) is available to the key"
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return False, f"the key in {KEY_VAR} was refused (HTTP 401)"
        return False, f"voice {voice_id} is not available to this key (HTTP {exc.code})"
    except urllib.error.URLError as exc:
        return False, f"ElevenLabs could not be reached ({exc.reason})"


class Refused(Exception):
    """A voice service refused one line, or could not be reached: (message, detail, whether it was sent)."""


def elevenlabs_speech(line: dict, voice: dict) -> bytes:
    body = {"text": line["text"], "model_id": voice["model"]}
    if voice["settings"]:
        body["voice_settings"] = voice["settings"]
    try:
        with api_request("POST", f"/v1/text-to-speech/{voice['id']}?output_format=mp3_44100_128",
                         body, accept="audio/mpeg") as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise Refused(f"ElevenLabs refused line {line['line']} (HTTP {exc.code})", detail, True) from exc
    except urllib.error.URLError as exc:
        raise Refused(f"ElevenLabs could not be reached ({exc.reason})", None, False) from exc


# ═══════════════════════════════════════════════════════════════════
# AMAZON POLLY
# ═══════════════════════════════════════════════════════════════════


def aws_session():
    """The one place boto3 is constructed: the standard credential chain, no AWS CLI needed."""
    import boto3

    return boto3.Session()


def polly_status(voice: dict) -> tuple[tuple[bool, str], tuple[bool, str]]:
    """(credentials, voice) for `check`. Two free calls; nothing is synthesized."""
    from botocore.exceptions import BotoCoreError, ClientError

    session = aws_session()
    if session.get_credentials() is None:
        return (False, "no AWS credentials resolve"), (False, "not checked: no AWS credentials resolve")
    try:
        session.client("sts", region_name=voice["region"]).get_caller_identity()
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "error")
        return (False, f"AWS refused the credentials ({code})"), (False, "not checked: the credentials were refused")
    except BotoCoreError as exc:
        return (False, f"AWS could not be reached ({exc})"), (False, "not checked: AWS could not be reached")
    where = f"{voice['voice']} on the {voice['engine']} engine in {voice['region']}"
    try:
        polly = session.client("polly", region_name=voice["region"])
        ids, token = set(), None
        while True:
            page = polly.describe_voices(Engine=voice["engine"], **({"NextToken": token} if token else {}))
            ids.update(v["Id"] for v in page.get("Voices", []))
            token = page.get("NextToken")
            if not token:
                break
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "error")
        return (True, "AWS credentials resolve"), (False, f"Amazon Polly refused to list voices for {where} ({code})")
    except BotoCoreError as exc:
        return (True, "AWS credentials resolve"), (False, f"Amazon Polly could not be reached ({exc})")
    if voice["voice"] not in ids:
        return (True, "AWS credentials resolve"), (False, f"Amazon Polly offers no voice {where}")
    return (True, "AWS credentials resolve"), (True, f"Amazon Polly offers {where}")


def polly_speech(polly, line: dict, voice: dict) -> bytes:
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        response = polly.synthesize_speech(Text=line["text"], VoiceId=voice["voice"], Engine=voice["engine"],
                                           OutputFormat="mp3")
        return response["AudioStream"].read()
    except ClientError as exc:
        error = exc.response.get("Error", {})
        raise Refused(f"Amazon Polly refused line {line['line']} ({error.get('Code', 'error')})",
                      str(error.get("Message", ""))[:300], True) from exc
    except BotoCoreError as exc:
        raise Refused(f"Amazon Polly could not be reached ({exc})", None, False) from exc


# ═══════════════════════════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════════════════════════


def fix_for(item: str) -> str:
    system = platform.system()
    if item == "uv":
        return "Install uv: https://docs.astral.sh/uv/getting-started/installation/"
    if item == "ffmpeg":
        return {
            "Darwin": "brew install ffmpeg",
            "Windows": "winget install --id Gyan.FFmpeg -e   (then open a new Git Bash)",
        }.get(system, "sudo apt-get install ffmpeg   (or your distribution's package manager)")
    if item == "chromium":
        pin = playwright_version()
        spec = f"playwright=={pin}" if pin else "playwright"
        extra = " --with-deps" if system == "Linux" else ""
        return f"uv run --with {spec} playwright install{extra} chromium"
    if item == "key":
        if system == "Windows":
            return f'setx {KEY_VAR} "<your key>"   (then open a new Git Bash)'
        return f"export {KEY_VAR}=<your key>   (add it to your shell profile; never commit it)"
    if item == "voice":
        return "Use a paid ElevenLabs key that can use this voice, or set another [video.elevenlabs] voice_id"
    if item == "credentials":
        return ("Make AWS credentials resolve: set AWS_PROFILE to a configured profile (sign in first if it "
                "uses SSO), or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY. Never put a key in the repository")
    if item == "polly-voice":
        return (f"Set voice, engine or region under [video.polly] in {CONFIG_FILE}, or voice.polly in "
                "video.yaml, to a voice Amazon Polly offers for that engine in that region")
    if item == "gitignore":
        return "Add the bundle's .gitignore back (copy it from the skill's assets/templates/gitignore)"
    if item == "node":
        return ("uv installs Node for Archify scenes from the nodejs-wheel-binaries package; check that "
                "https://pypi.org/project/nodejs-wheel-binaries/ has a wheel for this platform")
    return ""


def cmd_check(args) -> dict:
    root = Path(args.repo).resolve()
    conf = settings(root)
    bundle = None
    if args.bundle:
        bundle = resolve_bundle(root, args.bundle)
    voice = voice_of(read_video(bundle) if bundle else {}, conf["values"])
    items = []

    def item(name: str, ok: bool, detail: str, fix: str | None = None) -> None:
        items.append({"name": name, "ok": ok, "detail": detail, **({} if ok else {"fix": fix_for(fix or name)})})

    uv = shutil.which("uv")
    item("uv", bool(uv), "uv is on PATH" if uv else "uv is not on PATH")
    exe, where = find_ffmpeg()
    item("ffmpeg", bool(exe), f"ffmpeg from {where}" if exe else "no ffmpeg on PATH or bundled")
    ok, detail = chromium_status()
    item("chromium", ok, detail)
    if voice["provider"] == "polly":
        (ok, detail), (voice_ok, voice_detail) = polly_status(voice)
        item("credentials", ok, detail)
        item("voice", voice_ok, voice_detail, fix="polly-voice" if ok else "credentials")
    elif voice["provider"] == "elevenlabs":
        has_key = bool(os.environ.get(KEY_VAR))
        item("key", has_key, f"{KEY_VAR} is set" if has_key else f"{KEY_VAR} is not set")
        if has_key:
            ok, detail = voice_available(voice["id"])
            item("voice", ok, detail)
        else:
            item("voice", False, f"not checked: {KEY_VAR} is not set", fix="key")
    else:
        items.append({"name": "voice", "ok": False, "detail": f"unknown voice provider {voice['provider']!r}",
                      "fix": f"Set voice.provider to one of {', '.join(PROVIDER_DEFAULTS)}"})
    if bundle:
        inside = subprocess.run(["git", "-C", str(bundle), "rev-parse", "--is-inside-work-tree"],  # nosec B603 B607 # constant argv; git found on PATH
                                capture_output=True, text=True)
        if inside.returncode != 0:
            item("gitignore", True, "the bundle is not in a git repository")
        else:
            unignored = [p for p in MEDIA_PROBES if subprocess.run(  # nosec B603 B607 # constant argv; git found on PATH
                ["git", "-C", str(bundle), "check-ignore", "-q", p]).returncode != 0]
            item("gitignore", not unignored,
                 "git ignores the bundle's media" if not unignored
                 else f"git would track media in the bundle: {', '.join(unignored)}")
    scenes_ = [s for s in read_video(bundle).get("scenes") or [] if isinstance(s, dict)] if bundle else []
    if not bundle or any(scene_source(s) == "archify" for s in scenes_):
        ok, detail = node_status()
        item("node", ok, detail)
    signin = []
    if bundle:
        live = [s for s in scenes_ if scene_source(s) == "live"]
        chromium_ok = next(i["ok"] for i in items if i["name"] == "chromium")
        if live and chromium_ok:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                try:
                    signin = signin_report(root, bundle, live, browser)
                finally:
                    browser.close()
            items.append({"name": "signin", "ok": not signin,
                          "detail": "every live scene opens signed in" if not signin
                          else "; ".join(f"scene {p['scene']}: {p['reason']}" for p in signin),
                          **({"fix": signin[0].get("fix", "check the scene's url")} if signin else {})})
        elif live:
            items.append({"name": "signin", "ok": False, "detail": "not checked: Chromium is missing",
                          "fix": fix_for("chromium")})
    missing = [i["name"] for i in items if not i["ok"]]
    return {
        "status": "ok" if not missing else "missing",
        "platform": platform.system(),
        "items": items,
        "missing": missing,
        **({"signin": signin} if signin else {}),
        "voice": voice_report(voice),
        "config": {"values": conf["values"], "warnings": conf["warnings"]},
    }


def fill(template: str, values: dict) -> str:
    for key, value in values.items():
        template = template.replace(f"__{key}__", value)
    return template


def cmd_new(args) -> dict:
    import yaml

    root = Path(args.repo).resolve()
    conf = settings(root)
    slug = args.slug
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug):
        raise UsageError(f"--slug {slug!r} must be kebab-case: lowercase letters, digits and hyphens")
    date = args.date or dt.date.today().isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise UsageError(f"--date {date!r} must be YYYY-MM-DD")
    if args.out:
        # A folder the person named: used exactly, with no date added. An empty one is accepted,
        # since a person may make the folder first; one outside the repository needs their approval.
        bundle = (Path.cwd() / args.out).resolve()
        if not bundle.is_relative_to(root) and not args.confirm_outside:
            raise Failure("outside", f"{bundle} is outside the repository at {root}; nothing was created. "
                          "Rerun with --confirm-outside once the person approves this path", bundle=str(bundle))
        if bundle.exists() and (not bundle.is_dir() or any(bundle.iterdir())):
            raise Failure("exists", f"{bundle} already exists and is not an empty folder", bundle=str(bundle))
    else:
        bundle = root / conf["values"]["output_path"] / f"{date}-{slug}"
        if bundle.exists():
            raise Failure("exists", f"{bundle} already exists", bundle=str(bundle))
    title = args.title or slug.replace("-", " ").capitalize()
    templates = ASSETS / "templates"
    rel = os.path.relpath(bundle, Path.cwd()).replace(os.sep, "/")
    values = {"TITLE": title, "SLUG": slug, "DATE": date, "BUNDLE": rel, "NAME": bundle.name}
    yaml_values = {**values, "TITLE": yaml.safe_dump(title, default_style='"').strip(),
                   "STAMP": date.replace("-", ".")}
    (bundle / "deck").mkdir(parents=True)
    files = {
        "video.yaml": fill((templates / "video.yaml").read_text(encoding="utf-8"), yaml_values),
        "design.md": (templates / "design.md").read_text(encoding="utf-8"),
        "README.md": fill((templates / "README.md").read_text(encoding="utf-8"), values),
        DESCRIPTION_FILE: (templates / DESCRIPTION_FILE).read_text(encoding="utf-8"),
        ".gitignore": (templates / "gitignore").read_text(encoding="utf-8"),
        "history.md": "# History\n\nSteering notes applied to this video, oldest first.\n",
        "deck/deck.html": fill((templates / "deck.html").read_text(encoding="utf-8"),
                               {"TITLE": title.replace("&", "&amp;").replace("<", "&lt;")}),
        "deck/deck-stage.js": (ASSETS / "deck" / "deck-stage.js").read_text(encoding="utf-8"),
        "deck/viewport-base.css": (ASSETS / "deck" / "viewport-base.css").read_text(encoding="utf-8"),
    }
    for name, text in files.items():
        with open(bundle / name, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    return {
        "status": "ok",
        "bundle": str(bundle),
        "working_root": in_working_root(root, bundle, conf),
        "files": sorted(files),
        "config": {"values": conf["values"], "warnings": conf["warnings"]},
    }


def schema_errors(video: dict) -> list[str]:
    import jsonschema

    schema = json.loads((ASSETS / "video.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = []
    for err in sorted(validator.iter_errors(video), key=lambda e: list(e.absolute_path)):
        where = ""
        for part in err.absolute_path:
            where += f"[{part}]" if isinstance(part, int) else (f".{part}" if where else str(part))
        scene = ""
        path = list(err.absolute_path)
        if len(path) >= 2 and path[0] == "scenes" and isinstance(path[1], int):
            scenes = video.get("scenes") or []
            sid = scenes[path[1]].get("id") if isinstance(scenes[path[1]], dict) else None
            scene = f" (scene {path[1] + 1}{', ' + sid if sid else ''})"
        errors.append(f"{where or 'video.yaml'}{scene}: {err.message}")
    return errors


def deck_scene_ids(bundle: Path) -> tuple[set[str] | None, bool]:
    deck = bundle / "deck" / "deck.html"
    if not deck.is_file():
        return None, False
    html = deck.read_text(encoding="utf-8")
    return set(re.findall(r"""data-scene\s*=\s*["']([^"']+)["']""", html)), "<deck-stage" in html


def live_errors(bundle: Path, scene: dict) -> list[str]:
    """What the schema cannot say about a live scene."""
    sid = scene.get("id")
    errors = []
    script = scene.get("script")
    if script:
        path = (bundle / script).resolve()
        if path.parent != (bundle / "scenes").resolve() or path.suffix != ".py":
            errors.append(f"scene {sid}: script must be a .py file directly in the bundle's scenes/ folder")
        elif not path.is_file():
            errors.append(f"scene {sid}: script {script} does not exist")
    auth = scene.get("auth")
    if auth is not None and not (isinstance(auth, str) and PROFILE.match(auth)):
        errors.append(f"scene {sid}: auth must be a kebab-case profile name, not {auth!r}")
    for index, step in enumerate(scene.get("steps") or []):
        if not isinstance(step, dict):
            continue
        for action in step.get("do") or []:
            if not isinstance(action, dict) or len(action) != 1 or next(iter(action)) not in ACTIONS:
                errors.append(f"scene {sid}: step {index + 1} has an unknown action {action!r}; "
                              f"use one of {', '.join(ACTIONS)}")
    return errors


def archify_errors(bundle: Path, scene: dict) -> list[str]:
    """What the schema cannot say about an Archify scene, Archify's own validation included."""
    sid = scene.get("id")
    diagram = scene.get("diagram")
    if not isinstance(diagram, str):
        return []
    path = (bundle / diagram).resolve()
    if path.parent != (bundle / "diagrams").resolve() or path.suffix != ".json":
        return [f"scene {sid}: diagram must be a .json file directly in the bundle's diagrams/ folder"]
    if not path.is_file():
        return [f"scene {sid}: diagram {diagram} does not exist"]
    try:
        kind = json.loads(path.read_text(encoding="utf-8")).get("diagram_type")
    except (json.JSONDecodeError, AttributeError) as exc:
        return [f"scene {sid}: diagram {diagram} is not a JSON object ({exc})"]
    if kind not in ARCHIFY_TYPES:
        return [f"scene {sid}: diagram {diagram} has diagram_type {kind!r}; use one of {', '.join(ARCHIFY_TYPES)}"]
    try:
        proc = run_archify(["validate", kind, str(path), "--json"])
    except Exception as exc:  # noqa: BLE001 - a missing Node is a prerequisite, reported by check
        return [f"scene {sid}: Archify could not run to check {diagram} ({str(exc).strip().splitlines()[0]}); "
                "run check"]
    if proc.returncode == 0:
        return []
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return [f"scene {sid}: Archify rejected {diagram}: {(proc.stderr or proc.stdout).strip()[:300]}"]
    errors = []
    for diag in result.get("diagnostics") or []:
        if diag.get("severity") == "error":
            fix = (diag.get("supportedFixes") or [""])[0]
            errors.append(f"scene {sid}: {diagram}: {diag.get('message')}" + (f" (fix: {fix})" if fix else ""))
    return errors or [f"scene {sid}: Archify rejected {diagram}: {str(result.get('error'))[:300]}"]


def first_spoken(scene: dict) -> str:
    """A scene's first spoken text as written: its narration, or a live scene's first non-empty say."""
    if scene_source(scene) == "live":
        says = [(step.get("say") or "").strip() for step in scene.get("steps") or [] if isinstance(step, dict)]
        return next((say for say in says if say), "")
    return (scene.get("narration") or "").strip()


def stamp_text(bundle: Path, video: dict) -> tuple[str | None, str | None]:
    """The title slide's date stamp, or None, and a warning when there is none because no date is known."""
    if "date_stamp" in video:
        value = video["date_stamp"]
        return (value if isinstance(value, str) else None), None
    match = DATED_FOLDER.match(bundle.name)
    if match:
        return ".".join(match.groups()), None
    return None, ("video.yaml has no date_stamp and the folder name has no date, so the title slide has no date "
                  "stamp; set date_stamp to a date YYYY.MM.DD, or to false for none")


class SlideText(HTMLParser):
    """The text of one slide: from its data-scene start tag to the next slide's, or the deck's end.

    Slides are siblings, so the next data-scene marks the end even where an end tag is left out.
    """

    def __init__(self, scene: str):
        super().__init__()
        self.scene, self.inside, self.skip, self.text = scene, False, 0, []

    def handle_starttag(self, tag, attrs):
        scene = dict(attrs).get("data-scene")
        if scene is not None:
            self.inside = scene == self.scene
        elif tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("deck-stage", "body"):
            self.inside = False
        elif tag in ("script", "style"):
            self.skip = max(self.skip - 1, 0)

    def handle_data(self, data):
        if self.inside and not self.skip:
            self.text.append(data)


def stamp_warnings(bundle: Path, video: dict, scenes: list[dict]) -> list[str]:
    """No date for the title slide's stamp, and a date on the title slide besides the stamp."""
    if not scenes or scene_source(scenes[0]) != "slide" or not scenes[0].get("id"):
        return []
    warnings = []
    missing = stamp_text(bundle, video)[1]
    if missing:
        warnings.append(missing)
    deck = bundle / "deck" / "deck.html"
    if video.get("date_stamp") is not False and deck.is_file():
        parser = SlideText(scenes[0]["id"])
        parser.feed(deck.read_text(encoding="utf-8"))
        parser.close()
        other = OTHER_DATES.search(" ".join(" ".join(parser.text).split()))
        if other:
            warnings.append(f"scene {scenes[0]['id']}: the title slide shows a date besides the date stamp "
                            f"(\"{other.group(0)}\"); remove it, or set date_stamp: false for no stamp "
                            "(references/deck-contract.md)")
    return warnings


def sentences(text: str) -> list[str]:
    """Text split into sentences, each lowercased, with a curly apostrophe read as a straight one."""
    text = text.lower().replace("\u2019", "'")
    return [s.strip() for s in SENTENCE_END.split(text) if s.strip()]


def written_lines(scene: dict) -> list[str]:
    """A scene's spoken text as written, before say_as: its narration, or each live step's say."""
    if scene_source(scene) == "live":
        return [str(step.get("say") or "") for step in scene.get("steps") or [] if isinstance(step, dict)]
    return [str(scene.get("narration") or "")]


def direct_voice_warnings(scenes: list[dict]) -> list[str]:
    """One warning a sentence that assumes the viewer, holds the subject back, or ends on a slogan."""
    warnings = []
    for scene in scenes:
        for line in written_lines(scene):
            for sentence in sentences(line):
                start = sentence.lstrip("\"'\u201c\u2018(")
                opener = next((p for p in SCENARIO_OPENERS if re.match(re.escape(p) + r"\b", start)), None)
                reveal = next((p for p in REVEALS if re.search(r"\b" + re.escape(p) + r"\b", sentence)), None)
                slogan = SLOGAN.search(sentence)
                if opener:
                    warnings.append(f"scene {scene.get('id')}: a sentence opens with \"{opener}\", which assumes the "
                                    "viewer's situation; state the fact instead (references/structure.md)")
                elif reveal:
                    warnings.append(f"scene {scene.get('id')}: \"{reveal}\" holds the subject back for a reveal; "
                                    "say what it is instead (references/structure.md)")
                elif slogan:
                    warnings.append(f"scene {scene.get('id')}: a sentence ends on a slogan (\"{slogan.group(0)}\"); "
                                    "state the fact instead (references/structure.md)")
    return warnings


def title_warnings(title) -> list[str]:
    """One warning when the title teases rather than names its subject."""
    if not isinstance(title, str):
        return []
    text = title.lower().replace("\u2019", "'")
    phrase = next((p for p in TEASER_TITLES if p in text), None)
    colon = TEASER_COLON.search(text)
    if phrase:
        form = f"\"{phrase}\""
    elif text.startswith("from ") and " to " in text:
        form = "the \"From X to Y\" form"
    elif colon:
        form = f"a colon followed by \"{colon.group(1)}\""
    else:
        return []
    return [f"title: {form} teases rather than names the subject; name the subject, and the kind of video when "
            "that helps (references/structure.md)"]


def british_warnings(scenes: list[dict], say_as: dict) -> list[str]:
    """One warning a British word in a scene's spoken text, after say_as, since that is what the voice reads."""
    warnings = []
    for scene in scenes:
        if not scene.get("id"):
            continue
        text = " ".join(text for _, _, text in scene_lines(scene, say_as)).replace("\u2019", "'")
        for word in dict.fromkeys(m.group(1).lower() for m in BRITISH_WORD.finditer(text)):
            warnings.append(f"scene {scene['id']}: \"{word}\" is a British form, and the voice takes accent cues "
                            "from the text; write the US form, or map it in say_as (references/narration.md)")
    return warnings


def video_warnings(video: dict, scenes: list[dict], say_as: dict) -> list[str]:
    """What validate warns about without changing its status: no brief, a closing that trails off, a teaser
    title, narration that assumes the viewer, and British forms."""
    warnings = []
    if video.get("brief") is None:
        warnings.append("video.yaml has no brief, so the opening and closing have no outcome, takeaways or action "
                        "to be written from (references/structure.md)")
    closing = next((s for s in reversed(scenes) if first_spoken(s)), None)
    if closing:
        line = first_spoken(closing).lower().replace("\u2019", "'")
        phrase = next((p for p in TRAIL_OFFS if re.match(re.escape(p.lower()) + r"\b", line)), None)
        if phrase:
            warnings.append(f"scene {closing.get('id')}: the closing line starts with \"{phrase}\", which trails "
                            "off; close on the action instead (references/structure.md)")
    warnings += title_warnings(video.get("title"))
    warnings += direct_voice_warnings(scenes)
    warnings += british_warnings(scenes, say_as)
    return warnings


def estimated_seconds(characters: int, hold) -> int:
    """About how long a scene runs: its spoken characters at CHARS_PER_SECOND, plus its hold."""
    extra = hold if isinstance(hold, (int, float)) and not isinstance(hold, bool) and hold > 0 else 0
    return round(characters / CHARS_PER_SECOND + extra)


def validate(root: Path, bundle: Path) -> dict:
    video = read_video(bundle)
    conf = settings(root)
    errors = schema_errors(video)
    stamp = video.get("date_stamp")
    if isinstance(stamp, str) and re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", stamp):
        try:
            dt.date(*map(int, stamp.split(".")))
        except ValueError:
            errors.append(f"date_stamp: {stamp!r} is not a calendar date")
    scenes = [s for s in (video.get("scenes") or []) if isinstance(s, dict)]
    ids = [s.get("id") for s in scenes]
    for sid in sorted({i for i in ids if i and ids.count(i) > 1}):
        errors.append(f"scene id {sid} is used more than once")
    unsupported = [
        {"scene": s.get("id"), "source": scene_source(s)}
        for s in scenes if scene_source(s) not in SUPPORTED_SOURCES
    ]
    for u in unsupported:
        errors.append(f"scene {u['scene']}: source {u['source']!r} is not supported by this version of video")
    deck_ids, has_stage = deck_scene_ids(bundle)
    if any(scene_source(s) == "slide" for s in scenes):
        if deck_ids is None:
            errors.append("deck/deck.html does not exist")
        else:
            if not has_stage:
                errors.append("deck/deck.html has no <deck-stage>; see the deck contract")
            for s in scenes:
                if scene_source(s) == "slide" and s.get("id") and s["id"] not in deck_ids:
                    errors.append(f"scene {s['id']}: deck/deck.html has no element with data-scene=\"{s['id']}\"")
    for s in scenes:
        if scene_source(s) in ("slide", "archify") and not (s.get("narration") or "").strip() and not s.get("hold"):
            errors.append(f"scene {s.get('id')}: a scene with no narration needs hold > 0")
        if scene_source(s) == "live":
            errors.extend(live_errors(bundle, s))
        if scene_source(s) == "archify":
            errors.extend(archify_errors(bundle, s))
    for s in scenes:
        browser_options(root, bundle, conf, video, s, errors)
    voice = voice_of(video, conf["values"])
    if voice["provider"] == "polly":
        for s in scenes:
            if not s.get("id"):
                continue
            for line_id, _, text in scene_lines(s, voice["say_as"]):
                if len(text) > POLLY_MAX_CHARS:
                    errors.append(f"scene {s['id']}: line {line_id} is {len(text)} characters after say_as; "
                                  f"Amazon Polly takes at most {POLLY_MAX_CHARS} in one request")
    errors = list(dict.fromkeys(errors))
    steering = [{"scene": s.get("id"), "note": s["steering"]} for s in scenes if (s.get("steering") or "").strip()]
    state = read_state(bundle)
    recorded = state.get("sources", {})
    hand_edited = [
        {"scene": s.get("id"), "recorded": recorded[s.get("id")], "now": scene_source(s)}
        for s in scenes if s.get("id") in recorded and recorded[s.get("id")] != scene_source(s)
    ]
    chars = {s.get("id"): sum(len(text) for _, _, text in scene_lines(s, voice["say_as"]))
             for s in scenes if s.get("id")}
    # A bundle built before the brief existed has no digest, and reports no change.
    brief_changed = "brief" in state and state["brief"] != brief_digest(video)
    status = "invalid" if errors else ("needs-build" if steering or brief_changed else "ok")
    return {
        "status": status,
        "bundle": str(bundle),
        "errors": errors,
        "unsupported_sources": unsupported,
        "unapplied_steering": steering,
        "hand_edited_sources": hand_edited,
        "brief_changed": brief_changed,
        "description": description_problems(bundle),
        "warnings": video_warnings(video, scenes, voice["say_as"]) + stamp_warnings(bundle, video, scenes),
        "scenes": [{"id": s.get("id"), "source": scene_source(s), "characters": chars.get(s.get("id"), 0),
                    "seconds": estimated_seconds(chars.get(s.get("id"), 0), s.get("hold"))} for s in scenes],
        "voice": voice_report(voice),
        "config": {"values": conf["values"], "warnings": conf["warnings"]},
    }


def cmd_validate(args) -> dict:
    root = Path(args.repo).resolve()
    return validate(root, resolve_bundle(root, args.bundle))


def cmd_built(args) -> dict:
    from ruamel.yaml import YAML

    root = Path(args.repo).resolve()
    bundle = resolve_bundle(root, args.bundle)
    rt = YAML(typ="rt")
    rt.preserve_quotes = True
    rt.width = 4096
    path = bundle / "video.yaml"
    data = rt.load(path.read_text(encoding="utf-8"))
    scenes = data.get("scenes") or []
    known = {s.get("id") for s in scenes}
    unknown = [a for a in args.applied if a not in known]
    if unknown:
        raise UsageError(f"--applied names scenes video.yaml does not have: {', '.join(unknown)}")
    today = args.date or dt.date.today().isoformat()
    applied = []
    for scene in scenes:
        if scene.get("id") in args.applied and (scene.get("steering") or "").strip():
            applied.append({"scene": scene["id"], "note": str(scene["steering"]).strip()})
            scene["steering"] = ""
    if applied:
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            rt.dump(data, handle)
        history = bundle / "history.md"
        text = history.read_text(encoding="utf-8") if history.is_file() else "# History\n"
        if not text.endswith("\n"):
            text += "\n"
        text += "".join(f"\n## {today} · scene {a['scene']}\n\n{a['note']}\n" for a in applied)
        with open(history, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    state = read_state(bundle)
    state["sources"] = {s.get("id"): scene_source(s) for s in scenes}
    state["brief"] = brief_digest(read_video(bundle))
    write_state(bundle, state)
    return {"status": "ok", "bundle": str(bundle), "applied": applied, "sources": state["sources"]}


def voice_plan(root: Path, bundle: Path) -> tuple[dict, dict, list[dict]]:
    report = validate(root, bundle)
    if report["status"] != "ok":
        raise Failure(report["status"], "video.yaml must validate, with no unapplied steering and no brief "
                      "changed since the last build, before voicing", validate=report)
    conf = settings(root)
    video = read_video(bundle)
    voice = voice_of(video, conf["values"])
    lines = []
    for scene in video["scenes"]:
        for line_id, step, text in scene_lines(scene, voice["say_as"]):
            key = audio_key(text, voice)
            file = bundle / "build" / "audio" / f"{line_id}-{key[:12]}.mp3"
            lines.append({"line": line_id, "scene": scene["id"], "step": step, "text": text, "key": key,
                          "file": file, "characters": len(text), "cached": file.is_file()})
    return report, voice, lines


def cmd_voice(args) -> dict:
    root = Path(args.repo).resolve()
    bundle = resolve_bundle(root, args.bundle)
    _, voice, lines = voice_plan(root, bundle)
    todo = [line for line in lines if not line["cached"]]
    plan = {
        "voice": voice_report(voice),
        "to_voice": [{"line": l["line"], "scene": l["scene"], "characters": l["characters"]} for l in todo],
        "reused": [l["line"] for l in lines if l["cached"]],
        "characters": sum(l["characters"] for l in todo),
    }
    if not args.confirm or not todo:
        return {"status": "plan" if todo else "ok", "bundle": str(bundle), **plan, "requests": 0}
    polly = None
    if voice["provider"] == "polly":
        session = aws_session()
        if session.get_credentials() is None:
            raise Failure("missing", "no AWS credentials resolve; nothing was sent", fix=fix_for("credentials"), **plan)
        polly = session.client("polly", region_name=voice["region"])
    elif not os.environ.get(KEY_VAR):
        raise Failure("missing", f"{KEY_VAR} is not set; nothing was sent", **plan)
    live = [s for s in read_video(bundle)["scenes"] if scene_source(s) == "live"]
    if live:
        require_signed_in(root, bundle, live, "nothing was voiced or spent", plan)
    ffmpeg = need_ffmpeg()
    state = read_state(bundle)
    audio_state = state.setdefault("audio", {})
    sent, requests = 0, 0
    for line in todo:
        try:
            audio = polly_speech(polly, line, voice) if polly else elevenlabs_speech(line, voice)
        except Refused as exc:
            message, detail, was_sent = exc.args
            write_state(bundle, state)
            raise Failure("error", message, **({} if detail is None else {"detail": detail}),
                          requests=requests + int(was_sent), characters_sent=sent, **plan) from exc
        requests += 1
        sent += line["characters"]
        line["file"].parent.mkdir(parents=True, exist_ok=True)
        tmp = line["file"].with_suffix(".part")
        tmp.write_bytes(audio)
        os.replace(tmp, line["file"])
        audio_state[line["line"]] = audio_entry(ffmpeg, bundle, line)
        write_state(bundle, state)
    return {"status": "ok", "bundle": str(bundle), **plan, "requests": requests, "characters_sent": sent}


def audio_entry(ffmpeg: str, bundle: Path, line: dict) -> dict:
    return {
        "key": line["key"],
        "file": line["file"].relative_to(bundle).as_posix(),
        "duration": round(media_duration(ffmpeg, line["file"]), 3),
        "characters": line["characters"],
    }


def line_durations(ffmpeg: str, bundle: Path, state: dict, lines: list[dict]) -> None:
    """Fill each line's `duration`, from state.json when its key matches, else by decoding."""
    audio_state = state.setdefault("audio", {})
    for line in lines:
        entry = audio_state.get(line["line"])
        if not entry or entry.get("key") != line["key"]:
            entry = audio_entry(ffmpeg, bundle, line)
            audio_state[line["line"]] = entry
        line["duration"] = entry["duration"]


# ═══════════════════════════════════════════════════════════════════
# SIGN-INS
# ═══════════════════════════════════════════════════════════════════


def auth_dir() -> Path:
    """The user's cache folder for saved sign-ins: outside every repository."""
    forced = os.environ.get("AI_VIDEO_AUTH_DIR")
    if forced:
        return Path(forced)
    system = platform.system()
    if system == "Darwin":
        base = Path.home() / "Library" / "Caches"
    elif system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "ai-video" / "auth"


def profile_path(profile: str) -> Path:
    if not PROFILE.match(profile):
        raise UsageError(f"profile {profile!r} must be kebab-case: lowercase letters, digits and hyphens")
    return auth_dir() / f"{profile}.json"


def load_profile(profile: str) -> dict | None:
    path = profile_path(profile)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def context_options(options: dict) -> dict:
    """Playwright new_context keyword arguments from merged browser options, headers expanded."""
    opts = {k: v for k, v in options.items() if k not in ("launch", "extra_http_headers")}
    headers = {name: os.environ.get(ENV_REF.match(ref).group(1), "")
               for name, ref in (options.get("extra_http_headers") or {}).items()}
    if headers:
        opts["extra_http_headers"] = headers
    return opts


def signed_out_reason(page, scene: dict, profile: dict | None) -> str | None:
    """Why a loaded live scene is not signed in, or None when it is."""
    start = urllib.parse.urlsplit(scene["url"])
    now = urllib.parse.urlsplit(page.url)
    if now.netloc != start.netloc:
        return f"the application sent the browser to {now.netloc}, a sign-in"
    if profile:
        signin = urllib.parse.urlsplit(profile.get("signin_url") or "")
        if signin.netloc == now.netloc and signin.path and signin.path.rstrip("/") == now.path.rstrip("/") \
                and signin.path.rstrip("/") != start.path.rstrip("/"):
            return "the application showed its sign-in page"
    if scene.get("signed_in"):
        try:
            page.locator(scene["signed_in"]).first.wait_for(timeout=5000)
        except Exception:  # noqa: BLE001 - a timeout means not signed in
            return f"the page never showed {scene['signed_in']}"
    return None


def signin_report(root: Path, bundle: Path, scenes: list[dict], browser) -> list[dict]:
    """Open every live scene's start URL with its saved sign-in, without recording."""
    conf = settings(root)
    video = read_video(bundle)
    problems = []
    for scene in scenes:
        profile = None
        if scene.get("auth"):
            profile = load_profile(scene["auth"])
            if profile is None:
                problems.append({"scene": scene["id"], "profile": scene["auth"],
                                 "reason": f"no saved sign-in named {scene['auth']}"})
                continue
        options = browser_options(root, bundle, conf, video, scene, [])
        context = browser.new_context(**context_options(options), viewport=STAGE,
                                      storage_state=(profile or {}).get("storage_state"))
        try:
            page = context.new_page()
            page.goto(scene["url"], wait_until="load")
            reason = signed_out_reason(page, scene, profile)
        except Exception as exc:  # noqa: BLE001 - an unreachable app is reported
            reason = f"{scene['url']} could not be opened ({str(exc).strip().splitlines()[0]})"
        finally:
            context.close()
        if reason:
            problems.append({"scene": scene["id"], "profile": scene.get("auth"), "reason": reason})
    for problem in problems:
        if problem["profile"]:
            problem["fix"] = (f"uv run <skill-dir>/scripts/video_cli.py auth {problem['profile']} "
                              f"--url <sign-in URL> --confirm")
    return problems


def require_signed_in(root: Path, bundle: Path, scenes: list[dict], nothing: str, extra: dict | None = None) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as exc:  # noqa: BLE001
            raise Failure("missing", f"Playwright's Chromium could not be launched; {nothing}",
                          detail=str(exc).strip().splitlines()[0], fix=fix_for("chromium")) from exc
        try:
            problems = signin_report(root, bundle, scenes, browser)
        finally:
            browser.close()
    if problems:
        raise Failure("signed-out", f"a live scene is not signed in; {nothing}", scenes=problems, **(extra or {}))


def cmd_auth(args) -> dict:
    from playwright.sync_api import sync_playwright

    path = profile_path(args.profile)
    target = urllib.parse.urlsplit(args.url)
    if target.scheme not in ("http", "https"):
        raise UsageError("--url must be an http or https URL")
    if not args.confirm:
        return {"status": "plan", "profile": args.profile, "path": str(path),
                "message": "A visible browser will open at the sign-in URL. After you sign in, the sign-in "
                           "is saved here, readable only by you. Rerun with --confirm to do it."}
    headless = os.environ.get("AI_VIDEO_AUTH_HEADLESS") == "1"
    deadline = time.monotonic() + args.timeout
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=headless)
        except Exception as exc:  # noqa: BLE001
            raise Failure("missing", "Playwright's Chromium could not be launched; nothing was saved",
                          detail=str(exc).strip().splitlines()[0], fix=fix_for("chromium")) from exc
        try:
            context = browser.new_context()
            page = context.new_page()
            page.goto(args.url)
            settled = None
            while True:
                if time.monotonic() > deadline:
                    raise Failure("error", f"no sign-in finished within {args.timeout} s; nothing was saved")
                try:
                    now = urllib.parse.urlsplit(page.url)
                    if args.signed_in:
                        done = page.locator(args.signed_in).count() > 0
                    else:
                        done = now.netloc == target.netloc and now.path.rstrip("/") != target.path.rstrip("/")
                    if done:
                        settled = settled or time.monotonic()
                        if time.monotonic() - settled >= 2:
                            break
                    else:
                        settled = None
                    page.wait_for_timeout(250)
                except Exception as exc:  # noqa: BLE001 - a navigation mid-poll is retried; a closed window is not
                    if page.is_closed():
                        raise Failure("error", "the browser was closed before the sign-in finished; "
                                               "nothing was saved") from exc
            storage = context.storage_state()
        finally:
            browser.close()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)  # owner-only: the directory holds a saved sign-in
    except OSError:
        pass
    saved_at = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    data = json.dumps({"signin_url": args.url, "saved_at": saved_at, "storage_state": storage})
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(data)
    os.chmod(path, 0o600)
    return {"status": "ok", "profile": args.profile, "path": str(path), "saved_at": saved_at,
            "cookies": len(storage.get("cookies", [])), "origins": len(storage.get("origins", []))}


# ═══════════════════════════════════════════════════════════════════
# RECORDING
# ═══════════════════════════════════════════════════════════════════

# A full-screen magenta cover the cut finder looks for. It is added as early as the page allows,
# and again when the scene is chosen, so it is up however late the recorder's first frame arrives.
# Frames from before it appears are cut away with it.
COVER_FN = """
window.__devVideoCover = () => {
  if (document.getElementById('ai-video-cover')) return;
  const root = document.head || document.documentElement;
  if (!root) return;
  const style = document.createElement('style');
  style.id = 'ai-video-cover';
  style.textContent = 'html:not([data-ai-video-shown])::after{content:"";position:fixed;inset:0;'
    + 'background:#ff00ff;z-index:2147483647;pointer-events:none}';
  root.appendChild(style);
};
"""

COVER_JS = COVER_FN + """
if (document.documentElement) window.__devVideoCover();
else new MutationObserver((_, observer) => {
  if (document.documentElement) { window.__devVideoCover(); observer.disconnect(); }
}).observe(document, {childList: true});
"""

GOTO_JS = """
async (sceneId) => {
  window.__devVideoCover();
  await document.fonts.ready;
  const stage = document.querySelector('deck-stage');
  if (!stage) throw new Error('no <deck-stage> in the deck');
  stage.setAttribute('recording', '');
  const slides = Array.from(stage.children).filter(e => !['TEMPLATE','SCRIPT','STYLE'].includes(e.tagName));
  const index = slides.findIndex(e => e.getAttribute('data-scene') === sceneId);
  if (index < 0) throw new Error('no slide with data-scene=' + sceneId);
  stage.goTo(index);
  if (typeof stage.replay !== 'function') throw new Error('deck-stage.js has no replay(); copy the vendored one');
  const failed = [];
  document.fonts.forEach(f => { if (f.status === 'error') failed.push(f.family); });
  return failed;
}
"""

SHOW_JS = """
() => new Promise(resolve => requestAnimationFrame(() => {
  document.querySelector('deck-stage').replay();
  document.documentElement.setAttribute('data-ai-video-shown', '');
  requestAnimationFrame(() => resolve(true));
}))
"""

# The first slide scene is uncovered already drawn, so the video's first frame is not a blank slide.
# Its entrance is not restarted, and only finite animations are waited for: a looping one never
# finishes.
SHOW_SETTLED_JS = """
() => Promise.allSettled(document.getAnimations()
    .filter(a => a.effect && Number.isFinite(a.effect.getComputedTiming().iterations))
    .map(a => a.finished))
  .then(() => new Promise(resolve => requestAnimationFrame(() => {
    document.documentElement.setAttribute('data-ai-video-shown', '');
    requestAnimationFrame(() => resolve(true));
  })))
"""

# The title slide's date stamp, added behind the cover. Its styles are inline, so only an
# !important rule in the deck overrides them; a deck without --font-display or --muted gets the
# slide's own font and colour. It has no animation, so it is drawn from the first uncovered frame.
STAMP_JS = """
({scene, text}) => {
  const stage = document.querySelector('deck-stage');
  const slide = Array.from(stage.children).find(e => e.getAttribute('data-scene') === scene);
  const stamp = document.createElement('div');
  stamp.id = 'ai-video-date-stamp';
  stamp.textContent = text;
  Object.assign(stamp.style, {position: 'absolute', right: '56px', bottom: '56px', zIndex: '2147483646',
                              margin: '0', fontFamily: 'var(--font-display)', fontSize: '26px',
                              fontStyle: 'italic', fontWeight: '400', lineHeight: '1', letterSpacing: '0',
                              color: 'var(--muted)', opacity: '0.85', pointerEvents: 'none'});
  slide.appendChild(stamp);
}
"""

FRAGMENTS_JS = """
() => {
  const out = {};
  document.querySelectorAll('[data-scene]').forEach(e => { out[e.getAttribute('data-scene')] = e.outerHTML; });
  const copy = document.documentElement.cloneNode(true);
  copy.querySelectorAll('[data-scene]').forEach(e => e.remove());
  return {slides: out, shared: copy.outerHTML};
}
"""


def deck_files_digest(bundle: Path) -> str:
    digest = hashlib.sha256()
    deck = bundle / "deck"
    for path in sorted(p for p in deck.rglob("*") if p.is_file() and p.name != "deck.html"):
        digest.update(path.relative_to(deck).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def find_cut(ffmpeg: str, webm: Path, fps: int) -> int:
    """Index of the first frame after the magenta cover, on the fps timeline."""
    w, h = 8, 8
    x, y = STAGE["width"] // 2 - w // 2, STAGE["height"] // 2 - h // 2
    proc = subprocess.run(  # nosec B603 # argv list; ffmpeg path from find_ffmpeg()
        [ffmpeg, "-hide_banner", "-i", str(webm), "-vf", f"fps={fps},crop={w}:{h}:{x}:{y},format=rgb24",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True,
    )
    raw = proc.stdout
    size = w * h * 3
    seen_cover = False
    for index in range(len(raw) // size):
        frame = raw[index * size:(index + 1) * size]
        r = sum(frame[0::3]) / (w * h)
        g = sum(frame[1::3]) / (w * h)
        b = sum(frame[2::3]) / (w * h)
        magenta = r > 200 and g < 70 and b > 200
        if magenta:
            seen_cover = True
        elif seen_cover:
            return index
    raise Failure("error", f"the recording {webm.name} never showed the slide after the cover")


def record_scene(browser, deck_url: str, scene_id: str, options: dict, seconds: float, workdir: Path,
                 cover_ms: int = COVER_HOLD_MS[0], first: bool = False,
                 stamp: str | None = None) -> tuple[Path, list[str]]:
    context_opts = {k: v for k, v in options.items() if k not in ("launch", "extra_http_headers")}
    headers = {name: os.environ[ENV_REF.match(ref).group(1)] for name, ref in (options.get("extra_http_headers") or {}).items()}
    if headers:
        context_opts["extra_http_headers"] = headers
    context = browser.new_context(
        **context_opts,
        viewport=STAGE,
        record_video_dir=str(workdir),
        record_video_size=STAGE,
        reduced_motion="no-preference",
    )
    try:
        context.add_init_script(COVER_JS)
        page = context.new_page()
        page.goto(deck_url, wait_until="load")
        failed_fonts = page.evaluate(GOTO_JS, scene_id)
        if stamp:
            page.evaluate(STAMP_JS, {"scene": scene_id, "text": stamp})
        # The recorder's first frame can arrive late; the cover must still be up when it does.
        page.wait_for_timeout(cover_ms)
        page.evaluate(SHOW_SETTLED_JS if first else SHOW_JS)
        page.wait_for_timeout(int(seconds * 1000) + 500)
        video = page.video
    finally:
        context.close()
    return Path(video.path()), failed_fonts


def encode_clip(ffmpeg: str, webm: Path, audio: list[tuple[Path, float]], cut: int, fps: int,
                duration: float, out: Path) -> None:
    """Cut the recording at `cut`, and lay each (audio file, delay in seconds) under it."""
    video_chain = (f"[0:v]fps={fps},trim=start_frame={cut},setpts=PTS-STARTPTS,"
                   f"tpad=stop_mode=clone:stop_duration=2,trim=duration={duration:.3f},format=yuv420p[v]")
    inputs = ["-i", str(webm)]
    if audio:
        chains, labels = [], ""
        for index, (path, delay) in enumerate(audio, start=1):
            inputs += ["-i", str(path)]
            chains.append(f"[{index}:a]aresample=48000,aformat=channel_layouts=stereo,"
                          f"adelay={int(round(delay * 1000))}:all=1[l{index}]")
            labels += f"[l{index}]"
        mix = f"{labels}amix=inputs={len(audio)}:normalize=0:duration=longest," if len(audio) > 1 else f"{labels}"
        audio_chain = ";".join(chains) + f";{mix}apad,atrim=duration={duration:.3f}[a]"
    else:
        inputs += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        audio_chain = f"[1:a]atrim=duration={duration:.3f}[a]"
    tmp = out.with_suffix(".part.mp4")
    run_ffmpeg(ffmpeg, [
        *inputs, "-filter_complex", f"{video_chain};{audio_chain}", "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", str(fps), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(tmp),
    ])
    os.replace(tmp, out)


def final_encode(fps: int, compress: bool) -> list[str]:
    """The final join's encoder arguments. Every voice is mono, so the finished audio is too.

    Clips keep their own encode (`encode_clip`): their keys do not cover encoder arguments.
    """
    crf, preset, bitrate = ("28", "slow", "64k") if compress else ("18", "medium", "96k")
    return [
        "-c:v", "libx264", "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "aac", "-b:a", bitrate, "-ar", "48000", "-ac", "1", "-movflags", "+faststart",
    ]


# A live scene's cover is an element styled through the CSSOM, which a page's Content Security
# Policy does not block. It is added after the page loads, never as an init script, so pages the
# steps open later are not covered.
LIVE_COVER_JS = """
() => {
  if (document.getElementById('ai-video-cover')) return;
  const cover = document.createElement('div');
  cover.id = 'ai-video-cover';
  Object.assign(cover.style, {position: 'fixed', inset: '0', background: '#ff00ff',
                              zIndex: '2147483647', pointerEvents: 'none'});
  document.documentElement.appendChild(cover);
}
"""

LIVE_SHOW_JS = """
() => new Promise(resolve => requestAnimationFrame(() => {
  const cover = document.getElementById('ai-video-cover');
  if (cover) cover.remove();
  requestAnimationFrame(() => resolve(true));
}))
"""

OUTLINE_JS = """
(el, ms) => {
  const before = [el.style.outline, el.style.outlineOffset];
  el.style.outline = '4px solid #ffb000';
  el.style.outlineOffset = '2px';
  setTimeout(() => { el.style.outline = before[0]; el.style.outlineOffset = before[1]; }, ms);
}
"""


def resolve_url(base: str, value: str) -> str:
    """A step's URL resolved against the scene's url; a glob pattern is kept as written."""
    return value if "*" in value else urllib.parse.urljoin(base, value)


def run_action(page, scene: dict, action: dict) -> None:
    name, value = next(iter(action.items()))
    if name == "goto":
        page.goto(resolve_url(scene["url"], value), wait_until="load")
    elif name == "click":
        target = page.locator(value).first
        target.scroll_into_view_if_needed()
        target.evaluate(OUTLINE_JS, OUTLINE_MS + 200)
        page.wait_for_timeout(OUTLINE_MS)
        target.click()
    elif name == "hover":
        page.locator(value).first.hover()
    elif name == "fill":
        page.locator(value["selector"]).first.fill(value["text"])
    elif name == "type":
        page.locator(value["selector"]).first.press_sequentially(value["text"], delay=60)
    elif name == "press":
        if value.get("selector"):
            page.locator(value["selector"]).first.press(value["key"])
        else:
            page.keyboard.press(value["key"])
    elif name == "scroll":
        if isinstance(value, str):
            page.locator(value).first.scroll_into_view_if_needed()
        else:
            page.mouse.move(STAGE["width"] / 2, STAGE["height"] / 2)
            page.mouse.wheel(0, value["y"])
        page.wait_for_timeout(500)
    elif name == "wait":
        if isinstance(value, (int, float)):
            page.wait_for_timeout(int(value * 1000))
        elif "selector" in value:
            page.locator(value["selector"]).first.wait_for()
        else:
            page.wait_for_url(resolve_url(scene["url"], value["url"]))


class LineClock:
    """Starts a live scene's lines in order, a gap after the line before has finished."""

    def __init__(self, page, durations: dict[int, float], lead_in: float, gap: float):
        self.page = page
        self.durations = durations
        self.lead_in = lead_in
        self.gap = gap
        self.start = time.monotonic()
        self.free_at = 0.0  # seconds after the reveal when the next line may start
        self.offsets: dict[int, float] = {}
        self.last = -1

    def now(self) -> float:
        return time.monotonic() - self.start

    def settle(self, gap: float | None = None) -> None:
        gap = self.gap if gap is None else gap
        wait = self.free_at + (gap if self.free_at else 0) - self.now()
        if wait > 0:
            self.page.wait_for_timeout(int(wait * 1000))

    def line(self, step: int) -> None:
        if step <= self.last:
            raise UsageError(f"line({step}) was started after line({self.last}); start lines in order")
        if step not in self.durations:
            raise UsageError(f"line({step}) names no step with a say line")
        self.settle()
        self.offsets[step] = self.now()
        self.free_at = self.offsets[step] + self.lead_in + self.durations[step]
        self.last = step


def record_live(browser, scene: dict, options: dict, profile: dict | None, durations: dict[int, float],
                render: dict, script: Path | None, workdir: Path, cover_ms: int) -> tuple[Path, dict[int, float], float]:
    """Film one live scene; return the recording, each line's start after the reveal, and the length."""
    context = browser.new_context(
        **context_options(options),
        viewport=STAGE,
        record_video_dir=str(workdir),
        record_video_size=STAGE,
        reduced_motion="no-preference",
        storage_state=(profile or {}).get("storage_state"),
    )
    try:
        page = context.new_page()
        page.goto(scene["url"], wait_until="load")
        reason = signed_out_reason(page, scene, profile)
        if reason:
            raise Failure("signed-out", f"scene {scene['id']} is not signed in: {reason}; nothing was encoded",
                          scenes=[{"scene": scene["id"], "profile": scene.get("auth"), "reason": reason}])
        page.evaluate(LIVE_COVER_JS)
        page.wait_for_timeout(cover_ms)
        page.evaluate(LIVE_SHOW_JS)
        clock = LineClock(page, durations, float(render["lead_in"]), float(render["gap"]))
        if script:
            import runpy

            module = runpy.run_path(str(script))
            if not callable(module.get("run")):
                raise UsageError(f"{script.name} defines no run(page, line)")
            module["run"](page, clock.line)
            unstarted = sorted(set(durations) - set(clock.offsets))
            if unstarted:
                raise UsageError(f"{script.name} never started line(s) {', '.join(map(str, unstarted))}")
        else:
            for index, step in enumerate(scene.get("steps") or []):
                if index in durations:
                    clock.line(index)
                for number, action in enumerate(step.get("do") or [], start=1):
                    try:
                        run_action(page, scene, action)
                    except Exception as exc:  # noqa: BLE001 - a failed action names its step
                        first = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
                        raise Failure("error", f"scene {scene['id']}: step {index + 1}, action {number} failed",
                                      scene=scene["id"], action=action, detail=first) from exc
        clock.settle(gap=0)
        page.wait_for_timeout(int((float(render["tail"]) + float(scene.get("hold") or 0)) * 1000))
        length = clock.now()
        video = page.video
    finally:
        context.close()
    return Path(video.path()), clock.offsets, length


# Archify's viewer controls, hidden so only the title and the diagram are filmed.
ARCHIFY_INIT_JS = """
try { localStorage.setItem('archify-motion', 'live'); } catch (e) {}
(() => {
  const css = '.toolbar,.diagram-nav,.overview-map,.focus-chip,.route-probe,.semantic-lens,.diagram-guide,'
    + '.node-finder,.node-outline{display:none!important}';
  const add = () => {
    const style = document.createElement('style');
    style.id = 'ai-video-archify';
    style.textContent = css;
    (document.head || document.documentElement).appendChild(style);
  };
  if (document.documentElement) add();
  else new MutationObserver((_, observer) => {
    if (document.documentElement) { add(); observer.disconnect(); }
  }).observe(document, {childList: true});
})();
"""

REVEAL_JS = """
() => new Promise(resolve => requestAnimationFrame(() => {
  document.documentElement.setAttribute('data-ai-video-shown', '');
  requestAnimationFrame(() => resolve(true));
}))
"""

_vendor_digest: str | None = None


def archify_digest() -> str:
    """A digest of the vendored Archify folder, so a changed copy renders every diagram again."""
    global _vendor_digest
    if _vendor_digest is None:
        digest = hashlib.sha256()
        for path in sorted(p for p in ARCHIFY_DIR.rglob("*") if p.is_file()):
            digest.update(path.relative_to(ARCHIFY_DIR).as_posix().encode())
            digest.update(path.read_bytes())
        _vendor_digest = digest.hexdigest()
    return _vendor_digest


def archify_html(bundle: Path, scene: dict) -> tuple[str, Path]:
    """The key and path of an Archify scene's rendered page."""
    source = (bundle / scene["diagram"]).read_bytes()
    key = scene_key({"diagram": hashlib.sha256(source).hexdigest(), "theme": scene.get("theme") or "dark",
                     "archify": archify_digest()})
    return key, bundle / "build" / "archify" / f"{scene['id']}-{key[:12]}.html"


def render_archify(bundle: Path, scene: dict, html: Path) -> None:
    if html.is_file():
        return
    diagram = bundle / scene["diagram"]
    kind = json.loads(diagram.read_text(encoding="utf-8"))["diagram_type"]
    html.parent.mkdir(parents=True, exist_ok=True)
    tmp = html.with_suffix(".part.html")
    proc = run_archify(["render", kind, str(diagram), str(tmp)])
    if proc.returncode != 0 or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        raise Failure("error", f"scene {scene['id']}: Archify could not render {scene['diagram']}",
                      scene=scene["id"], detail=(proc.stderr or proc.stdout).strip().splitlines()[-8:])
    os.replace(tmp, html)


def record_archify(browser, html: Path, theme: str, options: dict, seconds: float, workdir: Path,
                   cover_ms: int) -> tuple[Path, list[str]]:
    """Film an Archify diagram in Presentation Stage, its animations held still until the reveal."""
    context = browser.new_context(
        **context_options(options),
        viewport=STAGE,
        record_video_dir=str(workdir),
        record_video_size=STAGE,
        reduced_motion="no-preference",
    )
    try:
        # A diagram scene is offline: anything but the page itself and its data URLs is refused.
        context.route("**/*", lambda route: route.continue_()
                      if route.request.url.startswith(("file:", "data:")) else route.abort())
        context.add_init_script(COVER_JS)
        context.add_init_script(ARCHIFY_INIT_JS)
        page = context.new_page()
        cdp = context.new_cdp_session(page)
        cdp.send("Animation.enable")
        cdp.send("Animation.setPlaybackRate", {"playbackRate": 0})
        page.goto(f"{html.resolve().as_uri()}?present=1&theme={theme}", wait_until="load")
        page.evaluate("async () => { window.__devVideoCover(); await document.fonts.ready; }")
        page.wait_for_timeout(cover_ms)
        cdp.send("Animation.setPlaybackRate", {"playbackRate": 1})
        page.evaluate(REVEAL_JS)
        page.wait_for_timeout(int(seconds * 1000) + 500)
        video = page.video
    finally:
        context.close()
    return Path(video.path()), []


def scene_key(parts: dict) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode("utf-8")).hexdigest()


def record_with_cover(record, ffmpeg: str, fps: int, bundle: Path, sid: str, tmp: Path):
    """Run `record(workdir, cover_ms)` until the cut is found, holding the cover longer each time."""
    for attempt, cover_ms in enumerate(COVER_HOLD_MS):
        try:
            result = record(tmp / str(attempt), cover_ms)
        except (Failure, UsageError):
            raise
        except Exception as exc:  # noqa: BLE001 - a broken deck or app is reported, not a crash
            message = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
            raise Failure("error", f"scene {sid} could not be recorded", scene=sid, detail=message) from exc
        webm = result[0]
        try:
            return result, find_cut(ffmpeg, webm, fps)
        except Failure as exc:
            if attempt + 1 < len(COVER_HOLD_MS):
                continue
            kept = bundle / "build" / f"failed-{sid}.webm"
            kept.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(webm, kept)
            exc.payload.update(scene=sid, recording=str(kept))
            raise


def last_line_end(item: dict, render: dict, clips_state: dict) -> float:
    """Seconds from a planned scene's start to the end of its last line."""
    last = item["lines"][-1]
    if scene_source(item["scene"]) != "live":
        return float(render["lead_in"]) + last["duration"]
    entry = clips_state.get(item["sid"]) or {}
    offset = (entry.get("lines") or {}).get(last["line"]) if entry.get("key") == item["key"] else None
    if offset is None:
        # No recorded start: a live clip ends tail + hold after its last line, or later.
        return item["duration"] - float(render["tail"]) - float(item["scene"].get("hold") or 0)
    return float(render["lead_in"]) + offset + last["duration"]


def end_fade(plan: list[dict], render: dict, clips_state: dict) -> dict:
    """The end fade: the smaller of fade_out and the time after the last spoken line, so it never
    fades a word. `start` is in seconds from the start of the video."""
    total, end = 0.0, None
    for item in plan:
        if item["lines"]:
            end = total + last_line_end(item, render, clips_state)
        total += item["duration"]
    after = total - end if end is not None else total
    length = round(max(0.0, min(float(render["fade_out"]), after)), 3)
    return {"start": round(total - length, 3), "length": length}


def join_clips(ffmpeg: str, listing: Path, fps: int, compress: bool, fade: dict, out: Path) -> None:
    """Join the clips in `listing` into one video, fading picture and sound out at its end."""
    filters = []
    if fade["length"] > 0:
        span = f"t=out:st={fade['start']:.3f}:d={fade['length']:.3f}"
        filters = ["-vf", f"fade={span}", "-af", f"afade={span}"]
    run_ffmpeg(ffmpeg, ["-f", "concat", "-safe", "0", "-i", str(listing), *filters, *final_encode(fps, compress), str(out)])


def extract_thumbnail(ffmpeg: str, clip: Path, out: Path) -> None:
    """Write the last frame of `clip` as a JPEG. A clip has no end fade, so neither has the image.

    The seek lands half a second before the end, and `-update 1` overwrites `out` with each frame
    decoded after it, so the last one is kept.
    """
    run_ffmpeg(ffmpeg, ["-sseof", "-0.5", "-i", str(clip), "-update", "1", "-q:v", "2", str(out)])


def embed_cover(ffmpeg: str, video: Path, image: Path, out: Path) -> None:
    """Copy `video` with `image` added as cover art. The H.264 stream stays first, so players and
    `media_facts` read the same picture as before."""
    run_ffmpeg(ffmpeg, ["-i", str(video), "-i", str(image), "-map", "0:v:0", "-map", "0:a", "-map", "1:v",
                        "-c", "copy", "-disposition:v:1", "attached_pic", "-movflags", "+faststart", str(out)])


def cmd_render(args) -> dict:
    root = Path(args.repo).resolve()
    bundle = resolve_bundle(root, args.bundle)
    report, voice, lines = voice_plan(root, bundle)
    missing = [l for l in lines if not l["cached"]]
    if missing:
        raise Failure("needs-voice", "some lines have no audio yet; run voice first",
                      scenes=list(dict.fromkeys(l["scene"] for l in missing)), lines=[l["line"] for l in missing])
    ffmpeg = need_ffmpeg()
    conf = settings(root)
    video = read_video(bundle)
    render = render_settings(video)
    fps = int(render["fps"])
    state = read_state(bundle)
    line_durations(ffmpeg, bundle, state, lines)
    by_scene: dict[str, list[dict]] = {}
    for line in lines:
        by_scene.setdefault(line["scene"], []).append(line)
    errors: list[str] = []  # already reported by validate, which voice_plan ran
    options = {s["id"]: browser_options(root, bundle, conf, video, s, errors)
               for s in video["scenes"]}
    unset = sorted({ENV_REF.match(ref).group(1) for o in options.values()
                    for ref in (o.get("extra_http_headers") or {}).values() if not os.environ.get(ENV_REF.match(ref).group(1))})
    if unset:
        raise Failure("missing", "header variables are not set; nothing was recorded", variables=unset)

    from playwright.sync_api import sync_playwright

    deck_url = (bundle / "deck" / "deck.html").resolve().as_uri()
    clips_state = state.setdefault("clips", {})
    plan = []
    warnings: list[str] = []
    stamp, missing = stamp_text(bundle, video)
    if missing and scene_source(video["scenes"][0]) == "slide":
        warnings.append(missing)
    with sync_playwright() as pw:
        try:
            probe = pw.chromium.launch()
        except Exception as exc:  # noqa: BLE001 - a missing browser is a prerequisite, not a crash
            raise Failure("missing", "Playwright's Chromium could not be launched; nothing was recorded",
                          detail=str(exc).strip().splitlines()[0], fix=fix_for("chromium")) from exc
        try:
            fragments, files_digest = {"slides": {}, "shared": ""}, ""
            if any(scene_source(s) == "slide" for s in video["scenes"]):
                ctx = probe.new_context(java_script_enabled=False)
                page = ctx.new_page()
                page.goto(deck_url, wait_until="domcontentloaded")
                fragments = page.evaluate(FRAGMENTS_JS)
                ctx.close()
                files_digest = deck_files_digest(bundle)
            for index, scene in enumerate(video["scenes"]):
                sid = scene["id"]
                scene_lines_ = by_scene.get(sid, [])
                common = {
                    "lines": [[l["key"], l["duration"]] for l in scene_lines_],
                    "render": keyed_render(render, scene_source(scene)),
                    "hold": scene.get("hold") or 0,
                    "browser": options[sid],
                    "recorder": RECORDER_VERSION,
                }
                if scene_source(scene) == "live":
                    script = bundle / scene["script"] if scene.get("script") else None
                    key = scene_key({
                        **common, "url": scene["url"], "auth": scene.get("auth"),
                        "signed_in": scene.get("signed_in"), "steps": scene.get("steps") or [],
                        "script": hashlib.sha256(script.read_bytes()).hexdigest() if script else None,
                    })
                    duration = None
                else:
                    script = None
                    if scene_source(scene) == "archify":
                        key = scene_key({**common, "archify": archify_html(bundle, scene)[0]})
                    else:
                        parts = {**common, "slide": fragments["slides"].get(sid, ""),
                                 "shared": fragments["shared"], "files": files_digest}
                        # Only the first slide is filmed settled, and stamped. Every other slide's key is
                        # unchanged, and so is an unstamped first slide's.
                        if index == 0:
                            parts["first"] = True
                            if stamp:
                                parts["date_stamp"] = stamp
                        key = scene_key(parts)
                    audio = scene_lines_[0]["duration"] if scene_lines_ else 0.0
                    duration = render["lead_in"] + audio + render["tail"] + float(scene.get("hold") or 0)
                clip = bundle / "build" / "clips" / f"{sid}-{key[:12]}.mp4"
                cached = clip.is_file()
                if cached and duration is None:
                    entry = clips_state.get(sid) or {}
                    duration = entry["duration"] if entry.get("key") == key else round(media_duration(ffmpeg, clip), 3)
                plan.append({"scene": scene, "sid": sid, "clip": clip, "duration": duration, "key": key,
                             "lines": scene_lines_, "script": script, "cached": cached})
            live = [item["scene"] for item in plan if not item["cached"] and scene_source(item["scene"]) == "live"]
            if live:
                problems = signin_report(root, bundle, live, probe)
                if problems:
                    raise Failure("signed-out", "a live scene is not signed in; nothing was recorded", scenes=problems)
        finally:
            probe.close()
        launched: dict[str, object] = {}
        try:
            for item in plan:
                if item["cached"]:
                    continue
                sid, scene, opts = item["sid"], item["scene"], options[item["sid"]]
                launch_key = json.dumps(opts.get("launch") or {}, sort_keys=True)
                if launch_key not in launched:
                    launched[launch_key] = pw.chromium.launch(**(opts.get("launch") or {}))
                browser = launched[launch_key]
                with tempfile.TemporaryDirectory(prefix="ai-video-") as tmp:
                    if scene_source(scene) == "live":
                        profile = load_profile(scene["auth"]) if scene.get("auth") else None
                        durations = {l["step"]: l["duration"] for l in item["lines"]}
                        (webm, offsets, length), cut = record_with_cover(
                            lambda workdir, cover_ms: record_live(browser, scene, opts, profile, durations, render,
                                                                  item["script"], workdir, cover_ms),
                            ffmpeg, fps, bundle, sid, Path(tmp))
                        item["duration"] = round(length, 3)
                        by_step = {l["step"]: l for l in item["lines"]}
                        audio = [(by_step[step]["file"], render["lead_in"] + offset) for step, offset in offsets.items()]
                    elif scene_source(scene) == "archify":
                        html = archify_html(bundle, scene)[1]
                        render_archify(bundle, scene, html)
                        (webm, failed), cut = record_with_cover(
                            lambda workdir, cover_ms: record_archify(browser, html, scene.get("theme") or "dark", opts,
                                                                     item["duration"], workdir, cover_ms),
                            ffmpeg, fps, bundle, sid, Path(tmp))
                        audio = [(item["lines"][0]["file"], render["lead_in"])] if item["lines"] else []
                    else:
                        (webm, failed), cut = record_with_cover(
                            lambda workdir, cover_ms: record_scene(browser, deck_url, sid, opts, item["duration"],
                                                                   workdir, cover_ms, first=item is plan[0],
                                                                   stamp=stamp if item is plan[0] else None),
                            ffmpeg, fps, bundle, sid, Path(tmp))
                        for family in failed:
                            warnings.append(f"scene {sid}: font {family} failed to load; a fallback was filmed")
                        audio = [(item["lines"][0]["file"], render["lead_in"])] if item["lines"] else []
                    item["clip"].parent.mkdir(parents=True, exist_ok=True)
                    encode_clip(ffmpeg, webm, audio, cut, fps, item["duration"], item["clip"])
                entry = {"key": item["key"], "file": item["clip"].relative_to(bundle).as_posix(),
                         "duration": round(item["duration"], 3)}
                if scene_source(scene) == "live":
                    entry["lines"] = {by_step[step]["line"]: round(offset, 3) for step, offset in offsets.items()}
                clips_state[sid] = entry
                write_state(bundle, state)
        finally:
            for browser in launched.values():
                browser.close()
    slug = video["slug"]
    final = bundle / "build" / f"{slug}.mp4"
    partial = bundle / "build" / f"{slug}.partial.mp4"
    listing = bundle / "build" / "clips.txt"
    listing.write_text("".join(f"file '{item['clip'].resolve().as_posix()}'\n" for item in plan), encoding="utf-8")
    fade = end_fade(plan, render, clips_state)
    join_clips(ffmpeg, listing, fps, args.compress, fade, partial)
    # The thumbnail and its cover art never block the video. An image from an earlier render is
    # removed first, so it is never reported as this render's.
    thumbnail = bundle / "build" / f"{slug}.thumbnail.jpg"
    cover = bundle / "build" / f"{slug}.cover.mp4"
    thumbnail.unlink(missing_ok=True)
    try:
        extract_thumbnail(ffmpeg, plan[0]["clip"], thumbnail)
    except (Failure, OSError):
        thumbnail.unlink(missing_ok=True)
    if not thumbnail.is_file():
        thumbnail = None
        warnings.append("the thumbnail image could not be written, so the video has no cover art")
    if thumbnail:
        try:
            embed_cover(ffmpeg, partial, thumbnail, cover)
            os.replace(cover, partial)
        except (Failure, OSError):
            cover.unlink(missing_ok=True)
            warnings.append(f"the cover art could not be embedded in the video; {thumbnail.name} was still written")
    os.replace(partial, final)
    starts, t = [], 0.0
    for item in plan:
        starts.append({"scene": item["sid"], "start": round(t, 3), "duration": round(item["duration"], 3),
                       "recorded": not item["cached"]})
        t += item["duration"]
    state["last_render"] = {"at": dt.datetime.now().isoformat(timespec="seconds"), "video": final.name,
                            "compressed": args.compress, "scenes": starts}
    write_state(bundle, state)
    warnings.extend(write_chapters(bundle, video["scenes"], starts))
    status_checked, problems = check_in_progress(bundle)
    warnings.extend(problems)
    return {
        "status": "ok",
        "bundle": str(bundle),
        "video": str(final),
        "thumbnail": str(thumbnail) if thumbnail else None,
        "compressed": args.compress,
        "size": final.stat().st_size,
        "status_checked": status_checked,
        "working_root": in_working_root(root, bundle, conf),
        "duration": round(t, 3),
        "fade": fade["length"],
        "recorded": [s["scene"] for s in starts if s["recorded"]],
        "reused": [s["scene"] for s in starts if not s["recorded"]],
        "scenes": starts,
        "facts": media_facts(ffmpeg, final),
        "warnings": warnings,
    }


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="video_cli.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check", help="report every missing prerequisite")
    p.add_argument("--repo", default=".")
    p.add_argument("--bundle")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("new", help="create a dated video bundle in the working root, or at --out")
    p.add_argument("--repo", default=".")
    p.add_argument("--slug", required=True)
    p.add_argument("--title")
    p.add_argument("--date")
    p.add_argument("--out", help="create the bundle at this folder exactly, absent or empty, instead of the working root")
    p.add_argument("--confirm-outside", dest="confirm_outside", action="store_true",
                   help="allow an --out folder outside the repository, once the person approves it")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("validate", help="check video.yaml and the deck")
    p.add_argument("--repo", default=".")
    p.add_argument("--bundle", required=True)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("built", help="record sources and move applied steering to history.md")
    p.add_argument("--repo", default=".")
    p.add_argument("--bundle", required=True)
    p.add_argument("--applied", nargs="*", default=[], metavar="SCENE")
    p.add_argument("--date")
    p.set_defaults(func=cmd_built)

    p = sub.add_parser("voice", help="voice lines with no cached audio")
    p.add_argument("--repo", default=".")
    p.add_argument("--bundle", required=True)
    p.add_argument("--confirm", action="store_true", help="send the requests; without it, only plan")
    p.set_defaults(func=cmd_voice)

    p = sub.add_parser("render", help="record changed scenes and assemble the video")
    p.add_argument("--repo", default=".")
    p.add_argument("--bundle", required=True)
    p.add_argument("--compress", action="store_true",
                   help="encode the finished video smaller (CRF 28, 64 kb/s audio); clips are unchanged")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("auth", help="save a sign-in for live scenes, by profile name")
    p.add_argument("profile")
    p.add_argument("--url", required=True, help="the application's sign-in URL")
    p.add_argument("--signed-in", dest="signed_in", help="a selector only a signed-in page shows")
    p.add_argument("--timeout", type=int, default=600, help="seconds to wait for the sign-in (default 600)")
    p.add_argument("--confirm", action="store_true", help="open the browser and save; without it, only plan")
    p.set_defaults(func=cmd_auth)

    args = parser.parse_args(argv)
    try:
        result = args.func(args)
        code = 0 if result.get("status") in ("ok", "plan") else (2 if result.get("status") == "invalid" else 1)
    except UsageError as exc:
        result, code = {"status": "invalid", "message": str(exc)}, 2
    except Failure as exc:
        result, code = exc.payload, 1
    print(json.dumps(result, indent=2, default=str))
    return code


if __name__ == "__main__":
    sys.exit(main())
