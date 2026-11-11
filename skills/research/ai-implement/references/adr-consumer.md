# ADR Consumer Reference

> Extracted from `agent-skills/.claude/skills/ai-skills-reference/adr-format.md` (§5, §6, §11 resolution/enumeration, §15) on 2026-09-16. That document is the normative parent; this extract covers only what a *consumer* of an existing decision log needs — resolving the log, reading a record's status, and mapping status onto planning authority. It excludes §11's record-creation rule: no skill in this domain writes a decision record.

## The five states

| State | Source |
|---|---|
| `Proposed` | AWS process — the owner "provides the ADR in the **Proposed** state at the beginning of the process" |
| `Accepted` | AWS process; also the literal adr-tools substitutes at creation |
| `Rejected` | AWS process |
| `Superseded` | AWS process |
| `Deprecated` | Nygard's template |

Every value is published vocabulary — this format adds no status of its own.

## Reading a status — four tolerances

Every consumer applies all four. Each prevents the same failure, a **retired decision read as live**, which under the tier table below holds work to a decision the team already replaced.

1. **Match both spellings of superseded.** adr-tools writes "Super**c**eded" — `adr-new`'s supersede path calls `_adr_add_link "$target" "Superceded by"`. Match `Superseded` and `Superceded`.
2. **A supersession link with no keyword is superseded.** `_adr_remove_status` deletes the old keyword outright, so the retired record's Status section holds only `Superceded by [Title](file.md)` — no `Accepted` and no `Superseded` token for a keyword lookup to find.
3. **Read status as the prose body of `## Status`,** not as a field.
4. **Take the keyword case-insensitively from the section's first non-blank line.** A correctly-written record legitimately holds more than one line there — a keyword plus a link, or a keyword plus a timestamp — so a reader requiring exactly one line misreads it.

An unrecognised keyword is **reported once, naming the file and the value, and loaded as no constraint**. Both silent defaults fail: reading it as `Accepted` turns a typo into a constraint on a decision nobody made, and reading it as absent lets a real decision quietly stop counting.

## Resolving the log path

**RESOLUTION — every consumer.** Walking up from the working directory and at each level:

1. **`.adr-dir` present** → its contents, resolved relative to the level that held it. Stop.
2. **an existing `doc/adr` directory** → that path. Stop.
3. otherwise ascend; at the filesystem root, **no log exists**.

Resolution ends at "no log exists", **not at a default path**. A consumer handed a directory holding no records gains nothing from one, so every consumer treats the third outcome as *skip*.

**ENUMERATION — every consumer.** Resolution hands back a directory; this rule turns it into a list of records. A record is any `*.md` file at the log root **or exactly one directory below it** whose filename begins with a digit:

```sh
find "$ADR_DIR" -mindepth 1 -maxdepth 2 -name '*.md' | grep -E '/[0-9][^/]*\.md$'
```

**Do not glob a single segment.** A consumer that globs `<log>/*.md` — files directly inside the log root only — still finds every `Accepted` record, because those are filed at the root. The failure this rule prevents is a **silent background tier**: `Proposed` records sit one level down, a single-segment glob loads none of them, and the consumer can never name one when it is relevant — indistinguishable from a project that has made no architectural decisions at all.

## Consumers: absence is normal, and authority comes in tiers

A project with **no log is the normal case**. A consumer skips **silently** when resolution finds none, because a warning on every run in a project that has made no architectural decisions is noise.

When a log resolves, map each record onto the table below. A record with no `+ Scope:` bullet is scoped to the repository that holds the log, one with no `+ Boundary:` bullet reads as `Boundary: no`, and one with no `+ Revisit when:` bullet has no trigger. So a record written before those bullets existed is a guardrail for the whole repository.

| Record | Tier | Consumer behaviour |
|---|---|---|
| `Accepted`, `Boundary: yes`, within scope | **Boundary** | Stop before acting against it, ask the person once, then follow their answer |
| `Accepted`, otherwise, within scope | **Guardrail** | Follow it and name it. When the person's request departs from it, name the record by filename and the Decision bullet in one line, do what was asked, and offer to amend or supersede the record |
| `Accepted`, outside its Scope or past its `Revisit when` trigger | **Background** | May inform a choice; never a reason not to proceed |
| `Proposed` | **Background** | Name it when relevant; no warning on every plan |
| `Rejected`, `Superseded`, `Deprecated`, log4brains' `draft` | Not a constraint | Load nothing, print nothing |
| anything else | Not a constraint | Report once with the filename and the value |

**What binds is the `## Decision` section, and nothing else.** A status sets the *authority* of a record; this rule sets its *extent*. Context is the situation that produced the decision, Consequences is what follows from it, and Compliance names how adherence is checked. A consumer that gates on any of the three gates on rationale.

**Compliance is derived, not additive.** Its bullets say how the Decision is verified, and add no obligation the Decision does not already carry.

**Stale proposals are not loaded.** Do not name a `Proposed` record dated more than 30 days before the run unless the person asks about it. Its filename date is its creation date.

**Precedence, when sources disagree:** the person's instruction in the current session wins; then the repository's own context files and `Accepted` records, newer before older; then the current change's own plan or design. `Proposed` records and other changes' plans are never constraints.

Name the record **by filename** whenever you name, follow, or stop for one — dated record filenames carry no short identifier to cite.

## What this extract omits

The record-creation rule (§11's CREATION branch, the record writer's first-run behavior, log initialization) is deliberately excluded. No skill in this domain creates, edits, moves, or deletes a decision record — each reads a status and nothing else. A consumer that finds an unrecorded decision names it, and leaves recording it to the person's request.
