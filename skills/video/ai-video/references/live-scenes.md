# Live application scenes

A **live scene** films a real web application in the recording browser. It opens a start URL,
already signed in when it names a saved sign-in, and runs its steps while their lines play. Use one
when the person wants to show a product working, not a picture of it.

## The scene in video.yaml

```yaml
- id: billing
  source: live
  url: https://staging.acme.test/billing    # the start URL
  auth: acme-staging                         # optional: a saved sign-in, by profile name
  signed_in: "text=Invoices"                 # optional: a selector only a signed-in page shows
  steps:
    - say: "Watch the invoices tab catch an unpaid bill."
      do: []
    - say: "It lists only bills unpaid after thirty days, so nobody chases one that's paid."
      do:
        - click: "text=Invoices"
        - wait: {selector: "table.invoices"}
  hold: 1
```

A live scene has no `narration`. Its lines are its steps' `say`, and `say_as` applies to them. A
step with an empty `say` is silent: it runs its actions and has no line. Write each `say` by
`references/narration.md`. The first line says what is about to happen and why it matters, not
what is on screen. Each later line says what the screen cannot show: why it happened, or what it
means. A line that describes the screen reads it aloud (`references/story.md`).

## Actions

Each action is a mapping with one key. Selectors are Playwright locator strings (`text=Invoices`,
`#search`, `role=button[name="Save"]`). When a selector matches several elements, the first is used.

| Action | Value | What it does |
|---|---|---|
| `goto` | a URL | Opens the URL, resolved against the scene's `url`, and waits for it to load. |
| `click` | a selector | Outlines the target for 300 ms, so a viewer sees it, then clicks it. |
| `hover` | a selector | Moves the pointer over the target. |
| `fill` | `{selector, text}` | Puts the text in a field at once. |
| `type` | `{selector, text}` | Types the text key by key, so a viewer sees it typed. |
| `press` | `{key}` or `{selector, key}` | Presses a key (`Enter`, `Control+K`), on the target when given. |
| `scroll` | `{y}` or a selector | Scrolls by `y` pixels, or until the target is in view. |
| `wait` | seconds, `{selector}` or `{url}` | Waits that long, or until the selector appears, or the URL matches. |

The recording has no visible pointer. The click outline is what shows a viewer where the click is.

## Timing

1. The recorder opens `url` and checks the sign-in (see *Signing in*).
2. A magenta cover hides the page, then lifts. The video starts at the first frame after it, so no
   loading or sign-in frame is filmed.
3. Each step starts its line, then runs its actions. The line plays `render.lead_in` seconds after
   its step starts.
4. The next step's line starts `render.gap` seconds (default 1.0) after the line before it has
   finished. A step whose actions take longer than its line starts the next step late, never early.
5. After the last line, the scene stays `render.tail` plus `hold` seconds.

Write each line so it is about as long as its actions. A line much shorter than slow actions leaves
silence in the video.

## Scene scripts

When steps cannot express the demo (a loop, a condition, a value read from the page), the person can
ask for a scene script. Write one only on request: it is code that runs with the person's own rights.

- Put it in the bundle's `scenes/` folder, and name it in the scene: `script: scenes/compare_plans.py`.
- Keep `steps` with `say` only. They are the script's lines, so `voice` can voice them.
- Define `run(page, line)`. `page` is the Playwright page. `line(n)` starts the line of step `n`,
  counted from 0, and returns at once. It waits first until the line before has finished.
- Start every line, in order. A script that skips one fails the render.

```python
def run(page, line):
    line(0)
    page.click("text=Plans")
    page.wait_for_selector(".plan-card")
    line(1)
    for card in page.locator(".plan-card").all()[:3]:
        card.hover()
        page.wait_for_timeout(600)
```

## Signing in

A saved sign-in is a secret. Treat it like a password.

1. Use a staging or test account, never a production account. If the person names a production
   application, say so and ask for a staging URL or a test account before you save a sign-in.
2. Interactive only: ask the person before you save a sign-in. Say a visible browser opens, they
   sign in there (SSO and MFA work), and the sign-in is saved on this computer only.
3. Run `auth` without `--confirm` first. It saves nothing and returns `path`, where the sign-in
   would go. That path is outside the repository, so state it to the person in full and ask them to
   approve saving there.
4. Only after the person approves that path, run it with `--confirm`:

   ```bash
   uv run <skill-dir>/scripts/video_cli.py auth <profile> --url <sign-in URL> --confirm
   ```

5. Name the profile in the scene's `auth`. Name nothing else about the sign-in anywhere.

A headless run never runs `auth`. It stops and names the command for the person to run.

`auth` waits until the browser has been back on the sign-in URL's host, away from its path, for 2
seconds. For an application whose sign-in page keeps the same URL, add `--signed-in <selector>`. It
then waits for that selector instead. It gives up after 600 seconds (`--timeout`).

### Where a sign-in is saved

`<cache>/ai-video/auth/<profile>.json`, readable only by the person:

| System | `<cache>` |
|---|---|
| macOS | `~/Library/Caches` |
| Linux | `$XDG_CACHE_HOME`, or `~/.cache` |
| Windows | `%LOCALAPPDATA%` |

It is outside every repository, so git never sees it. On Windows, file permissions are not changed.
The per-user folder is what keeps other users out.

### When a sign-in has expired

`check --bundle`, `voice --confirm` and `render` each open every live scene's `url` with its saved
sign-in before they spend or record anything. A scene is signed out when:

- the application sends the browser to another host (an SSO page);
- it lands on the saved sign-in URL's path;
- the scene's `signed_in` selector does not appear within 5 seconds;
- the profile was never saved.

The command then stops with `status: signed-out`, and `scenes` names each scene, its profile and the
`auth` command that renews it. Nothing was voiced, recorded or spent. Interactive: ask the person to
sign in again with that command. Headless: stop, and give them the command.

`render` checks only the live scenes it will record. A scene whose clip is cached is not run again,
so an expired sign-in does not stop a render that changes nothing live.

## What makes a live scene record again

A live scene's clip is reused while its `url`, `auth` name, `signed_in`, steps, script, lines,
render settings, `hold` and browser options are unchanged. Renewing a sign-in changes none of
these, so it records nothing again.

Recording a scene again repeats its actions in the application. Make steps that are safe to repeat:
search and open records, do not create or delete them. If a step must create something, use a test
account whose data can be thrown away.
