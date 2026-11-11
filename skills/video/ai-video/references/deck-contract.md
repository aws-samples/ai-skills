# The deck contract

The recorder films one slide per scene. It finds each slide by its scene ID, starts its entrance from
the first frame, and films it at 1920×1080. The video's first scene, when it is a slide, is the
exception: it is filmed already drawn, so the video does not open on a blank slide. A deck must give
it what it needs. Where `references/frontend-slides/` disagrees with this file, this file wins.

## The rules

1. **One file, one folder.** The deck is `deck/deck.html`. It loads `deck-stage.js` and
   `viewport-base.css` from `deck/` by relative path, and references nothing else on disk outside
   `deck/`. Brand files go in `deck/brand/`.
2. **One `<deck-stage width="1920" height="1080">`.** Every slide is a direct child element of it.
   The deck has no other slide controller.
3. **One `data-scene` per slide scene.** Each slide carries `data-scene="<id>"`, equal to its scene's
   `id` in `video.yaml`. The order of slides does not matter to the recorder, so inserting a scene
   never shifts another scene's narration. Keep the order the same as `video.yaml` anyway, so the
   deck reads well on its own.
4. **Author at 1920×1080.** Use px on the fixed stage, not `vw`, `vh` or `clamp()`.
5. **Key entrances on `[data-deck-active]`.** Write entrance animations as CSS on
   `[data-deck-active] .thing`, or start them from a `slidechange` listener. The recorder calls the
   vendored `replay()`, which restarts both. An animation that runs on page load, or on a class the
   deck adds itself, has already finished when filming starts.
6. **Finish entrances within about one second.** The narration starts 0.3 s after the slide appears;
   a slide still moving while the voice explains it is hard to follow.
7. **Load fonts that will load.** Use Google Fonts or Fontshare with `display=block`, or self-hosted
   files in `deck/brand/` (which also work offline). `render` warns when a face fails to load, because
   the fallback was filmed.
8. **No chrome on camera.** No progress bars, edit buttons, slide numbers or hints. The recorder hides
   `deck-stage`'s own pill.
9. **Nothing from `video.yaml` but what a viewer should see.** Never put narration sentences,
   steering, guidance or process labels ("scene 3", "draft", "template") on a slide.
10. **Do not edit `deck-stage.js` or `viewport-base.css`.** They are vendored (see `VENDORED.md`).
11. **The end card names references; it never lists URLs.** The last slide shows the brief's `action`,
    then each reference by its `name` (references/structure.md). A reference with a `url` is a link,
    `<a href="<url>">name</a>`. Never write a URL as slide text, and never make a slide that is a list
    of URLs.
12. **The title slide shows no date.** `render` adds the date stamp, `date_stamp` in `video.yaml`,
    to the first slide's lower right corner while it films it, so keep that corner clear and write
    no other date on the slide. `deck.html` never contains the stamp. `validate` warns when the
    title slide's text holds a date, unless `date_stamp` is `false`.
13. **The headline is the takeaway; the body is its evidence.** A content slide's headline is the
    scene's takeaway as a sentence, not a topic label. Its body is the evidence for it in about 12
    words or fewer: a before and after, one command, one number, a small diagram. No list on a
    slide holds more than three items (`references/story.md`).

## The minimum deck

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Example</title>
<link rel="stylesheet" href="viewport-base.css">
<script src="deck-stage.js"></script>
<style>
  deck-stage > section { background: #020617; color: #fff; padding: 120px; }
  .reveal { opacity: 0; transform: translateY(24px); }
  [data-deck-active] .reveal { animation: reveal 600ms ease-out forwards; }
  @keyframes reveal { to { opacity: 1; transform: none; } }
</style>
</head>
<body>
<deck-stage width="1920" height="1080">
  <section data-scene="title"><h1 class="reveal">Example</h1></section>
  <section data-scene="why"><h2 class="reveal">Every merge cuts a release</h2></section>
</deck-stage>
</body>
</html>
```

`video_cli.py new` writes a starter in this shape. `validate` checks rules 2 and 3.

## How a scene is filmed

1. A fresh 1920×1080 browser opens `deck.html` with a magenta cover over the page.
2. Once fonts are ready, it goes to the slide with the scene's `data-scene`, behind the cover.
3. It calls `replay()` and removes the cover in the same frame.
4. It holds for `lead_in + narration + tail + hold`.
5. ffmpeg cuts the recording at the first frame after the cover, so the clip opens on the slide.

The first scene of the video, when it is a slide, differs at steps 2 and 3. At step 2, the recorder
adds the date stamp to the slide, behind the cover: small italic text in the deck's `--muted`
colour and `--font-display` face, 56 px in from the bottom and right edges, with no animation. At
step 3, it does not call `replay()`. Behind the cover, it waits for every CSS animation, CSS transition and Web Animation on
the page to finish, skipping any that loops forever, and then removes the cover. The video's first
frame therefore shows the slide fully drawn, as does the thumbnail `render` takes from the end of the
same clip. Every later slide keeps its entrance.

An entrance timed by JavaScript, such as a `setTimeout` that adds a class, is not waited for. On the
first slide it can be filmed part-way through, so write that slide's entrance as CSS (rule 5).
