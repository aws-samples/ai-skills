# Opening, body and closing

A viewer decides in the first seconds whether to keep watching, and remembers the last seconds best.
Write both on purpose, from the video's `brief` (`references/video-bundle.md`): the opening from
`outcome`, the closing from `takeaways`, `action` and `references`. Read this page when you write a
storyboard, and when `validate` reports `brief_changed`, a closing that trails off, a teaser title, or
a sentence that assumes the viewer. `references/narration.md` still governs how every line is worded.

## The three parts

| Part | What it holds | Length |
|---|---|---|
| Opening | What the subject is, in plain words, in the first sentence. Then the problem as an observed fact, or the result on a real screen. Then what the viewer will be able to do by the end: the `outcome`. | About a tenth of the runtime, at most 15 to 20 seconds in a two-minute video. The problem is stated within about 30 seconds, whatever the length. |
| Body | The chosen story's scene jobs, in its order, one takeaway a scene (`references/story.md`). A signpost may lead a scene's point where the story turns ("First, every merge starts a release."), and never replaces it. | The rest. |
| Closing | A tie back to the opening's problem or result. At most three `takeaways`, restated in one or two sentences in new words rather than repeated from the body. One specific `action`. Then the end card. | About a tenth of the runtime, at most 15 to 20 seconds in a two-minute video. |

For an expert audience, shorten the opening's preview to one sentence, the result, and start the
body.

Promise a length in the opening ("in four minutes") only when it is true. It is optional.

Never end on a recall prompt or a quiz ("Can you remember the three steps?"). Restate the takeaways
yourself.

Never save the subject for later in the video. A viewer who does not know what the subject is cannot
follow anything said about it.

## The end card

The end card is the last slide. It shows the `action`, then each reference by its short `name`. A
reference with a `url` is a link in `deck/deck.html` (`references/deck-contract.md`), and never a URL
written on the slide. No slide is a list of URLs. Say that the links are with the video, in the post
or the page that shares it, only when the brief has references and the action needs one of them,
such as "read the release guide". Never read a URL aloud.

A closing has one of two shapes:

- **The closing line on the end card.** The closing scene's slide is the end card. Set its `hold` to
  about 1.8, so with the 0.7-second `tail` the card stays about 2.5 seconds after the last word.
- **A silent end card after the closing line.** The closing scene has its own slide, and a last scene
  with empty `narration` shows the end card. That scene needs `hold` above 0. A `hold` of about 0.8
  keeps the card up about 2.5 seconds after the last word: the closing scene's 0.7-second `tail`,
  then the end card's 0.3-second `lead_in`, its 0.7-second `tail` and its `hold`.

Either way, hold the end card about 2.5 seconds after the last word. The video's end fade
(`render.fade_out`, one second by default) runs inside that hold and never over a word.

## Trail-off phrases

A closing line that opens with one of these sounds like the video ran out rather than ended.
`validate` warns when the closing line starts with one, ignoring case and leading spaces:

- "That's it"
- "That's all"
- "In summary"
- "To wrap up"
- "To sum up"

The closing line is the first spoken line of the last scene that has any. Open it with the tie back
to the opening instead, and end it on the action.

## Examples

| Field | Weak | Good |
|---|---|---|
| Takeaway | "Releases are important." | "Every merge to main cuts a release, so nobody tags by hand." |
| Action | "Check it out." | "Review the open release merge request by Friday." |
| Reference | `name: https://docs.example.com/release/v2/index.html` | `name: Release guide`, with that address in `url` |

A takeaway is a claim the viewer can repeat. An action is one thing one person can do, with a time
when there is one. A reference's `name` is what a viewer reads on the end card; its `url` is where
the link goes.

## Direct voice

The narrator reports. It never claims to know the viewer. A viewer who is not in the situation the
first sentence describes stops trusting the video there, and an AI voice that claims to know the
viewer sounds fake. Apply these rules to every scene, not only to the opening and the closing:

1. State facts about the subject, the organization or the code.
2. Never state the viewer's situation, feelings, wants or habits.
3. Say "you" only for something the viewer will do: the closing action, or a step in a how-to or a
   demo ("You run the render command").
4. Say "we" only as the team narrator (`references/story.md`).
5. Never cast the viewer as the main character of a story.
6. Never hold back what the subject is for a later reveal.
7. When you compare the subject with another tool, say what that tool does. Never say that the
   viewer uses it.

Never open on an invented persona ("Meet Sarah, a developer who…") or on a second-person scenario
("You've just finished…"). The second is the same invented persona, with the viewer put in its
place.

| Opening | Example |
|---|---|
| Weak | "You've finished a pull request, and you want to walk the team through it. … So here's the idea." |
| Good | "Reelkit turns a pull request into a narrated video, shared as a link. Today, the video is written to one laptop, and sharing it means uploading the file." |

The good opening names its subject in its first sentence, and states the problem as a fact about the
world. It still sounds spoken: the rules in `references/narration.md` for contractions and plain
words still apply.

A title names the subject, and the kind of video when that helps: "Reelkit product definition", or
"Deploy pipeline issue 42: three decisions". A title is never a teaser, such as "Reelkit: what we're
building". A colon is fine when a plain phrase follows it.

`validate` warns on the phrases below, naming the scene and the phrase, and never changes its status.
A warning on a correct sentence, such as "imagine" inside a quote, takes seconds to dismiss. Each list
is short and exact on purpose. Matching ignores case and reads `’` as `'`.

### `SCENARIO_OPENERS`

At the start of a sentence:

- "you've just"
- "you've finished"
- "you've ever"
- "you're working"
- "you're tired"
- "you're stuck"
- "you know when"
- "imagine"
- "picture this"
- "if you've ever"
- "ever wondered"
- "we've all"

### `REVEALS`

Anywhere in a sentence:

- "here's the idea"
- "here's the thing"
- "here's the catch"
- "here's where it gets"
- "the moment that matters"
- "the best part"

### `SLOGAN`

At the end of a sentence: ", not" followed by one to four words, as in "send a link, not a file."
State the fact instead: "The video is shared as a link."

### `TEASER_TITLES`

In the title:

- "what we're building"
- "what's next"
- "what's new"

The title also warns in two forms: the "From X to Y" form, a title that starts with "from " and
contains " to ", and a colon followed by "what", "how" or "why".
