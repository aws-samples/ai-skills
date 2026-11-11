# Narrator, story and scene

Read this page when you choose the story, write the storyboard, or write any narration. It covers
the body of a video: who speaks, which order the scenes take, and what each scene does.
`references/structure.md` still owns the opening, the closing and the end card, and
`references/narration.md` still owns how each sentence is worded. This page does not repeat them.

## The narrator

The narrator is someone who knows the subject well, explaining it to one capable colleague who does
not. The subject can be a tool, a system, a design, a change, a result or a failure. The viewer is
one person, not an audience.

The narrator has one relation to the subject, chosen from the request, and keeps it for the whole
video. A narrator who says "we" in one scene and "the team" in the next leaves the viewer asking who
is speaking.

| Relation | Speaks as | Use it |
|---|---|---|
| **Explainer** (the default) | "you" for the viewer, the subject in the third person, never "I" or "we" | Unless the request sets another relation. Fits how-tos, tool videos, and an explanation of a system or a change the narrator presents rather than owns. |
| **Team** | "we" for the people who built or decided the subject, "you" for the viewer | Only when the request comes from that team or speaks as "we". Fits a team presenting its own design, proposal or status. |
| **Author** | "I" for one person's view, "you" for the viewer | Only when the request says the video is that person's view. Fits a critique, a review or a recommendation. |

How the narrator sounds: calm, direct and friendly. Present tense, active voice, plain words, and
exact names and numbers. One point a scene, said first.

What the narrator does:

- Names the problem or the question before the answer.
- Shows, then explains. One concrete case from the demo, the diagram or the data, instead of a
  general claim.
- Says why a fact matters, once a scene.

What the narrator never does: reads the screen aloud, uses hype words ("powerful", "seamless",
"simply", "just") or hedges ("basically", "kind of", "might"), says "I" or "we" outside the
relation, or states the viewer's situation, feelings or wants. It says "you" only for something the
viewer will do (`references/structure.md`, Direct voice). `references/narration.md` holds the rules
for each sentence.

Never ask the person about the narrator. Take the relation from the request. A person changes it in
the request ("narrated by the platform team, as 'we'") or by editing the `Narrator:` line.

## Recording the narrator and the story

Write both as the first line of the video-wide `guidance` in `video.yaml`, in this form:

```yaml
guidance: |
  Narrator: explainer, speaking to the viewer as "you". Story: Problem, solution, proof, use.
  Audience: new team members who have merged one change.
```

Keep both on that one line: start it with `Narrator:`, and name the structure after `Story:`, on the
same line, exactly as this page names it. A `Story:` on a line of its own is not read as the story.
Any other standing rule, the audience included, goes on the lines after it. `guidance` keys no
cache, so writing or editing the line voices and records nothing. A changed story takes effect when
you next rewrite the scenes.

## Choosing the story

Take the first rule that matches the request:

1. The request names a structure: that structure.
2. It asks why something failed, or describes a failure to explain: **Investigation**.
3. It asks for a deep dive, an architecture or design explanation, or a tour of code:
   **Worked example**.
4. It is about a proposed or planned change, such as an issue, an epic, a proposal or a plan:
   **Situation, complication, resolution**.
5. It reports findings, results or status, its audience is expert or deciding, or it says "update"
   or "what changed": **Answer first**.
6. Its subject prevents a recurring problem or protects something: **Threat and defense**.
7. Its subject's output is visual and is the point: **Demo first**.
8. Otherwise: **Problem, solution, proof, use**.

"Quick" chooses no structure: it says how the video is made, without questions, not what it says.
The most specific signal comes first. "A deep dive into the access-control design" matches rule 3
before rule 6. In an interactive run, the next rule that also matches is a good alternative to
offer in the Story question.

The structure decides the order of the body's scenes and what each scene is for. Its first job is
the opening and its last job is the closing, both written by `references/structure.md`.

## The seven structures

Each structure is a sequence of scene jobs. A job may take one scene or several, and every scene
still follows the scene beat below. The examples are invented.

### Problem, solution, proof, use

The fallback. The problem, as an observed fact, the one idea that solves it, proof that it does, and
how to use it well. Fits how-tos, tool videos, announcements, and any request the other rules
do not match.

Jobs: the problem (10 to 15 seconds), the solution as one idea (15 to 20 seconds), the proof as a
demo, a trace or data (30 to 60 seconds), the use: when it applies and the one habit that matters
(20 to 30 seconds), then the callback and the action.

Example, how the docs link checker works: a broken link ships and nobody notices for weeks. The
checker follows every link on each push. A push with one broken link, and the failed check naming
the page. Run it before you push, because a failed check blocks the merge. Add the check to your own
docs repository.

### Worked example

Follow one concrete case through the system, then name the parts it touched. Fits architecture and
design explanations, code tours, and anything asked for as a deep dive.

Jobs: the answer in one sentence, one case followed end to end (a request, a record or a run), the
parts it crossed, a scene each in the order the case met them, the trade-off or the limit, then
what it means for the viewer's work.

Example, the ingestion service: an uploaded file is searchable within a minute. Follow one file
from upload to search result. The queue, the parser and the index, each when the file reaches it.
The limit: a file over 50 MB waits for the nightly batch. Split a large upload to keep it fast.

### Situation, complication, resolution

The facts everyone agrees on, what changed or is missing, what will be done, and what is needed
from the viewer. Fits change proposals, issue and epic overviews, design proposals and plans.

Jobs: the situation, the complication, the question it raises, the resolution (the change), the
plan as steps or child issues, then what the viewer decides or does.

Example, an epic to add caching to the search service: every query reads the database. Traffic
doubled this quarter, and slow queries now time out at peak. How does search stay fast as traffic
grows? Cache popular queries for five minutes. Three stories: the cache, a hook that clears it on
an edit, and a hit-rate dashboard. Review the cache story's design by Thursday.

### Answer first

The conclusion in the first sentence, then the reasons, then the evidence. Fits findings, results,
evaluations and status updates, an expert or deciding audience, and a request that says "update" or
"what changed".

Jobs: the answer, up to three reasons with the evidence for each (a scene each, or a part each in a
long video), what is still uncertain, then the action.

Example, a search ranking test: the new ranking puts the right document first in seven queries of
ten, up from five. It reads titles, it weights recent edits, and it ignores duplicates, each shown
on one query. Only English queries were tested. Approve the rollout to every team.

### Investigation

Open on a symptom, follow the clues, reveal the cause, then state the rule. Fits diagnostic topics,
incidents and debugging stories.

Jobs: the symptom, the question said aloud, two or three clues, the reveal, the rule, then the
action. Reveal the cause within about a minute of the question: a viewer who came to learn the
subject loses patience with a long mystery. Revealing the cause is this structure's job. Holding back
the subject is not: say what the subject is in the first sentence (`references/structure.md`). When
`validate` warns on a reveal phrase such as "here's the catch", reword the sentence, not the
structure.

Example, nightly builds that fail on Mondays: the build fails at 2 a.m. every Monday. What is
different about Monday? Only Monday fails, the cache is empty, and a cleanup job runs on Sunday
night. The cleanup deletes the cache the build expects. A build never assumes a warm cache. Add the
cache step to your own build.

### Threat and defense

Something the organization values faces a threat that keeps coming back, and the subject is the
defense.
Fits guardrails, security, consistency, and review and approval processes.

Jobs: what the organization protects, what keeps threatening it, the defense as one idea, the defense at
work, what is true now, then the action.

Example, a second reviewer for production settings: one settings file runs the service. A mistyped
value took the service down twice this year. Two people approve every change to that file. The
check blocks a change that has one approval. No single person can change a setting alone now.
Ask for a second review before Friday's change.

### Demo first

Open on the finished result, then show how to get it. Fits a subject whose output is visual and is
the point: a site, a report, a dashboard, a video.

Jobs: the result on screen (about 10 seconds), the command or the run that made it, one or two
choices that shaped it, when to use it, then the action.

Example, a status page from health checks: the finished status page, live. One command made it.
Two choices shaped it: which checks count, and how often the page refreshes. Use it for any service
with an on-call rotation. Run the command on your own service today.

### The tactic each structure adapts

Each structure adapts a general storytelling tactic, named here so a catalogue of tactics can refer
to the same structure by its general name:

| Structure | General tactic |
|---|---|
| Problem, solution, proof, use | Problem, Solution, Benefit, with Teach a Procedure's demonstration as its proof |
| Worked example | Explain Something Complex, opened on its worked example |
| Situation, complication, resolution | Situation, Complication, Question, Answer |
| Answer first | Answer First, and Findings, Implications, Recommendations |
| Investigation | Investigation, opened on an Open Question |
| Threat and defense | Threat to What We Value |
| Demo first | Start in the Middle, applied to a result |

## A source document is material, not the order

When the request supplies a document to explain, such as a design document, an issue, a plan or a
research document, draw the video's content from it and order the scenes by the chosen structure,
not by the document's sections. Map each section to the scene job it serves. A section that no
takeaway needs gets no scene: an appendix, a glossary, a revision history, a list of open tasks.

Example: a design document runs overview, goals, tenets, components, data, operations, risks,
appendix. As a worked example, the answer comes from the overview and the goals, the one case from
the components and the data, and the limit from the risks. The appendix has no scene.

## The scene beat

Every scene, in every structure, follows one beat:

| Beat | What it does | Slide scene | Archify scene | Live scene |
|---|---|---|---|---|
| **Point** | The scene's takeaway as a full sentence, spoken first | The headline states it in writing | `meta.title` states it in writing | The first line says what is about to happen and why it matters |
| **Proof** | One concrete thing that shows it | The slide body | One path through the diagram | The screen, as the action happens |
| **Payoff** | Why it matters to the viewer, once | Spoken only | Spoken only | Spoken while the screen shows the result |
| **Pass** (optional) | A question the next scene answers, or a fact planted for a later scene | Spoken only | Spoken only | Spoken only |

A scene is two to four sentences, about 12 to 25 seconds. A scene that needs more is two scenes.

The written point and the spoken point say the same thing in different words. A signpost ("Third,")
may lead the point sentence and never replaces it: "Third, a cached query skips the database."
states a point, and "Third, caching." does not. `references/narration.md` lists the openers that
fail.

**Plant, then pay off.** A fact set up in one scene and used in a later one ties the video
together. The pass is where a scene plants it: "Remember the queries that time out at peak" in a
later scene lands only if an earlier scene said it.

### A slide scene

- **Headline:** the takeaway as a sentence in sentence case, in about eight words. "Finished work
  leaves the list, not the repository", not a topic label such as "What it is".
- **Body:** evidence for the headline in about 12 words or fewer: a before and after, one command or
  line of code, one number, a small diagram, or cards of one to three words. No list of more than
  three items, no paragraph, and no sentence the narration speaks.
- **Eyebrow:** optional, a chapter or part label.
- **Narration:** states the point and at most one item from the slide. Walking a slide's items in
  order, even in other words, is reading the slide.
- **The glance test:** the slide's point comes through in about three seconds.

### An Archify scene

- **Title:** `meta.title` is the takeaway as a sentence, such as "Uploads never leave the customer's
  account", not a topic such as "Architecture" or a process label such as "One upload".
- **One path a scene:** the narration names the parts in the order their edges light, at most three
  in a sentence. A system that needs more is several scenes, each one path through the same diagram
  or a smaller one.
- **Opening:** the point sentence gives the diagram's entrance its time
  (`references/archify-scenes.md`). A filler phrase such as "Here's how it works." carries nothing.

### A live scene

- **First line:** what is about to happen and why it matters ("Watch a search post to the create
  route"), not what is on screen ("Here's the book list").
- **Later lines:** what the screen cannot show: why it happened, or what it means. A line that
  describes the screen is a live scene reading its slide.
- Keep each line about as long as its step's actions (`references/live-scenes.md`).

## The storyboard and the headline test

Write the storyboard as one takeaway a scene, in story order, before you write any narration. Then
read only the takeaways, as the slide headlines and diagram titles will show them, in order:

- the video's argument comes through as a sequence of claims;
- a topic label ("Inputs", "How it works") is rewritten as a claim;
- two scenes with the same takeaway become one;
- a scene whose takeaway the outcome does not need is cut.

## Long videos: parts

A video planned at more than about six minutes is built from parts, ordered by its structure:

- Each part opens on a slide whose eyebrow names the part and whose headline states the part's
  takeaway. An Archify scene has no eyebrow, so without that slide a viewer cannot tell which part
  they are in.
- Each part holds two to six scenes on the scene beat, and ends on one sentence that says what the
  part established and what the next part answers.
- The scenes of a part share a `chapter` label that names the part's takeaway in a few words.
- An agenda appears only for more than three parts, as one takeaway sentence a part, never a list
  of topic labels.
- The opening states its problem within about 30 seconds, whatever the length
  (`references/structure.md`).
- The closing restates at most three takeaways.

In an interactive run, the Length question offers one video in parts, or a short overview plus one
video per part, and the person chooses. A headless run builds one video in parts and lists the
parts under **Inferred**.

## Sets of videos

When one request asks for several videos:

- They share one design, one voice, one narrator relation and the same spoken forms in `say_as`.
- Each video chooses its own structure from its own subject and purpose, and its `guidance` names
  its own story.
- No two videos open a scene, or their closing, with the same sentence, and no recurring line
  appears in every video.
- Only the first video carries the set's framing, such as what the set covers. A later video opens
  on its own problem. When the videos are meant to be watched in order, it adds one line on where
  the previous video left off.
- A video may copy a sibling's deck styles and live-scene actions, and never its narration.
- Chapter labels may repeat across the set, so a viewer finds the same section in any video. The
  sentences under them do not.

## Sources

- Richard E. Mayer, *Multimedia Learning*: words on screen that repeat the narration, and detail
  the lesson does not need, both lower what a viewer learns; signals and short parts raise it.
- John Sweller, cognitive load theory: reading a sentence while hearing it costs more attention
  than either alone.
- John Sweller and Graham Cooper, "The Use of Worked Examples as a Substitute for Problem Solving in
  Learning Algebra": a worked example teaches a newcomer faster than a general description.
- Michael Alley, *The Craft of Scientific Presentations*: a sentence headline stating the claim,
  over visual evidence.
- Nancy Duarte, *slide:ology* and *Resonate*: the glance test, and contrasting what is with what
  could be.
- Barbara Minto, *The Pyramid Principle*: the answer first, and situation, complication, question,
  answer.
- Chip Heath and Dan Heath, *Made to Stick*: one concrete case beats a general claim, and an expert
  over-explains mechanism.
- George Loewenstein, "The Psychology of Curiosity": curiosity rises when a gap in what a person
  knows is pointed out.
- Philip Guo, Juho Kim and Rob Rubin, "How Video Production Affects Student Engagement":
  engagement falls after about six minutes, whatever the video's length.
