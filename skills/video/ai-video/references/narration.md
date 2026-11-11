# Writing narration to be spoken

Narration is heard once, at the speed of speech, by someone who cannot scroll back. Write it for the
ear. Apply these rules every time you write or revise a `narration`.

## Rules

1. **Use contractions.** "It's", "you'll", "don't", "that's". Uncontracted text sounds read aloud.
2. **One idea per sentence, about 20 words or fewer.** Split a long sentence rather than joining
   clauses with "and", "which" or a semicolon.
3. **Use plain spoken words.** "Use", not "utilise". "About", not "approximately".
4. **Write numbers as a person says them.** "Two minutes", "about eighteen hundred characters",
   "twenty twenty-six".
5. **No parentheses, no "e.g.", no "i.e.", no "etc.".** Say "for example", or make it a sentence.
6. **No lists read as runs of commas.** Three items at most in one sentence. More becomes two
   sentences, or the slide shows the list and the line names the point.
7. **Spell out what a voice would misread, through `say_as`.** Symbols, file names, flags, acronyms,
   version numbers and code. The slide keeps the written form, and `voice.say_as` maps it to the
   spoken form:

   ```yaml
   voice:
     say_as:
       "--headless": "dash dash headless"
       ".ai-skills.toml": "dot A I skills dot toml"
       "ADR": "A D R"
       "v2.1.0": "version two point one"
   ```

   Write the written form in the narration, exactly as on the slide. `say_as` replaces longest
   matches first. Prefer a guidance note ("say A-D-R, never 'adder'") for a rule the person gave.
8. **Don't read the slide.** The slide shows the fact; the narration says why it matters. Never
   speak a slide's sentences, and never walk its items in order, even in other words: name the
   point and at most one item. Hearing and reading the same words at once costs more attention
   than either alone.
9. **Read each line in your head.** If it sounds written, rewrite it.
10. **The first sentence states the scene's point.** A signpost may lead it ("Third, a cached query
    skips the database.") and never stands alone. "Here's", "Now", "Next", "So", "Let's" and a bare
    count ("Three tips.") are openers that fail: the viewer hears the opening words once, and these
    carry no point. `references/story.md` says what a scene's point is.
11. **One new term a scene, defined as it first appears.** A viewer who missed what a term means
    cannot scroll back to find out.
12. **Cut a fact the outcome does not need.** Every extra fact competes with the point for the
    viewer's attention.
13. **No idioms or comparisons.** Give one concrete case from the demo, the diagram or the data
    instead. A comparison makes the viewer translate it back while the next sentence plays.
14. **Write US English.** Use US spelling and US forms: "organization", "analyze", "must not". The
    voice takes accent cues from the text, and a British form such as "organisation" or "mustn't" can
    switch a US voice to a British accent in the middle of a sentence. `validate` warns on these whole
    words in the spoken text, after `say_as`, and never changes its status. They are listed as
    `BRITISH_FORMS`:

    `organisation`, `organisations`, `organise`, `organised`, `organises`, `organising`,
    `colour`, `colours`, `behaviour`, `behaviours`, `licence`, `centre`, `centres`, `favourite`,
    `favourites`, `analyse`, `analysed`, `recognise`, `recognised`, `recognises`, `realise`,
    `realised`, `realises`, `prioritise`, `prioritised`, `prioritises`, `utilise`, `utilised`,
    `utilises`, `whilst`, `amongst`, `learnt`, `mustn't`

    The list holds common, unambiguous forms only. It leaves out "towards", which US speakers use
    too, and "analyses", which is also the US plural of "analysis". To keep a British name on the
    slide, such as a product called "Organisation Hub", map it to its US spoken form in `say_as`.

## Length and cost

- About 150 words a minute. A two-minute video is about 300 words, or about 1,800 characters.
- Every character sent to the voice service is paid for, by Amazon Polly and by ElevenLabs alike.
  `voice` states the characters before any call, and only changed lines are sent again. Amazon Polly
  takes at most 3,000 characters in one line, after `say_as`; `validate` reports a longer one.
  Changing `say_as` or the voice re-voices the lines it touches.

## Example

Written: "video-skill (a new skill) generates .mp4 files from video.yaml, e.g. for demos."

Spoken: "Video skill turns an idea into a narrated video. You describe it, and you get an M P 4
back." with `say_as: {"video-skill": "video skill", ".mp4": "M P 4"}` when the slide shows them.
