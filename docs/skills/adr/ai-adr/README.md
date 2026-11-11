---
title: "ai-adr"
sidebar_label: "ai-adr"
sidebar_position: 2
---

# `ai-adr`

| | |
|---|---|
| Invoke | `/ai-adr [--headless] ["<the decision>" \| <verb> <record>[, <record>…]]` |
| Activation | slash command, or a person's explicit request in the session; never from intent or keywords alone |
| Domain | [adr](../) |
| Source | `skills/adr/ai-adr/SKILL.md` |
| Effort | `high` |

## Overview

Keep a project's architecture decision log — stand it up on first run, then write records and move
them through propose, accept, and decline.

**Writing a record.** The interview asks between 0 and 3 questions, and only ones whose answer
changes the record — usually how far the decision reaches. An input that declares no alternatives
were weighed, or names its rejected alternatives with their reasons, gets no alternatives question.
When the skill does ask about alternatives, it offers "None were considered" and takes the rest in
the person's own words, never from a list it drafted. A gap left unasked is marked
` — *(inferred)*` or left out, never filled, and a record carries no bullet written to reach a count.
The closing report opens with what changed and the next command, then quotes every Decision
bullet, because those bullets are the whole of what a record binds.

**Record fields.** Four fields ride as prefixed bullets inside the existing sections, so the
section set and adr-tools compatibility are unchanged: `+ Scope:` (the first Context bullet, saying
which systems or kinds of work the decision covers and whether existing work migrates),
`+ Not decided here:` (Context), `+ Revisit when:` (Consequences), and `+ Boundary:` (Notes). The
interview asks for Scope when the input does not state it, and never asks whether a record is a
boundary: `Boundary: yes` is written only when the person says so. A record without the fields reads
as scoped to its repository, `Boundary: no`, with no review trigger. Existing records are never
migrated to add them.

**Changing a record.** `amend`, `correct`, and `narrow` edit an `Accepted` record in place. A
correction of a wrong fact, a typo fix, adding the record fields, a `Not decided here:` bullet, or
a Decision bullet narrowed to what the person meant is allowed. A narrowing asks one confirmation
that quotes the bullet before and after. The record stays `Accepted`, its minor version goes up
(`1.0` to `1.1`), and it gains one changelog row. Widening or reversing a Decision bullet, adding
one, or removing a rejected alternative or an accepted downside changes no file and names
supersession instead. A moved path is never a reason to amend.

**Accepting.** Accepting a `Proposed` record that still carries ` — *(inferred)*` bullets asks
about every marked bullet in one round — drop or confirm each — then revises the record and accepts
it in the same run. A verb followed by several records, `accept <slug>, <slug>, <slug>`, is a batch:
it quotes every Decision bullet, asks one confirmation, moves each record that can legally move,
reports each one that cannot with its reason, and writes the index once.

**Stale proposals.** A `Proposed` record more than 30 days old is listed under
`### Stale proposals` in the index, with its age, and every run's closing report names it with the
`accept` and `decline` commands. Stale is not a status — the record stays `Proposed` — and agents do
not name a stale proposal unless the person asks about it.

**The agent-context pointer.** The first run offers to add a fenced `<!-- ai-skills:adr-log -->`
block to the root `CLAUDE.md`. Every later run refreshes that block, in the root `CLAUDE.md` or the
root `AGENTS.md`, when its text differs from the current template: only the text between the fences
changes, and the run reports the diff. Re-running `/ai-adr` is how a repository picks up a newer
pointer. No run inserts a block without asking.

**Who may run it.** A person, by typing `/ai-adr`, or an agent the person asked in the session to
write, accept, decline, amend, supersede, or deprecate a record. An agent never runs it on its own
initiative: one that notices an unrecorded decision names it and the command in one line, and writes
nothing. The author of every record is the person, from `git config user.name`.

**Headless mode.** `--headless` asks nothing and takes every default. It can write a new record,
always `Proposed`, marking or leaving out anything the interview would have asked. It never changes
a status: a headless `accept`, `decline`, supersession, or deprecation changes no file and names the
interactive command instead. The closing report lists every default the run took.

**What a record's status means.** Only a record's Decision bullets bind; Context, Consequences, and
Compliance never stop work. An `Accepted` record is a **guardrail**: an agent follows it and names it,
and when the person asks for something it does not allow, the agent names the record, does what was
asked, and offers to amend or supersede it. Only an `Accepted` record marked `Boundary: yes` is a
**boundary** that stops work before it starts. `Proposed` records are background. When sources
disagree, the person's instruction in the session wins, then the repository's context files and
`Accepted` records, then the current change's own plan.

## Tool grants

**Denial set** — `WebFetch, WebSearch, Skill, NotebookEdit, Agent`

| Entry | Reason |
|---|---|
| `WebFetch`, `WebSearch` | No step fetches anything. |
| `Skill` | Step 8 *prints* the literal command for the next transition; it invokes nothing. |
| `NotebookEdit` | The files written are markdown records, the log's `README.md` index, `.adr-dir`, and the pointer block in the root `CLAUDE.md` or `AGENTS.md`. |
| `Agent` | No fan-out step. |

**Pre-approval set** — `Bash(date:*), Bash(git config user.name:*), Bash(git config user.email:*), Bash(git rev-parse:*), Bash(find:*), Bash(mkdir:*), Bash(git mv:*), Bash(mv:*)`

| Entry | Step behind it |
|---|---|
| `Bash(date:*)` | Context Loading obtains today's date with `date +%F` rather than recalling it. |
| `Bash(git config user.name:*)` | Context Loading obtains the record's author, who is never the agent. |
| `Bash(git config user.email:*)` | Context Loading offers its local part as a drafted author name when `user.name` is unset. |
| `Bash(git rev-parse:*)` | Steps 1 and 2a write `.adr-dir` at the repository root, and Step 5 uses `git mv` inside a repository and `mv` outside one. The body names no command for either lookup. |
| `Bash(find:*)` | The ENUMERATION rule in `references/adr-format.md` §11, `find "$ADR_DIR" -mindepth 1 -maxdepth 2 -name '*.md'`, which Step 7's index pass runs. |
| `Bash(mkdir:*)` | Step 2a creates `docs/adr`; Steps 5 and 6e create `proposed/` and `retired/` on demand. |
| `Bash(git mv:*)` and `Bash(mv:*)` | Step 5 moves a record to the directory its new status implies — `git mv` inside a repository, so git records a rename, and `mv` outside one. |

The rule Step 2d writes into the log's first record — `/ai-adr`, run by a person or at a person's
request, is the only route by which a record is written or moved — is **not expressible in either
key**. The skill
holds `Write` and `Edit` for the records themselves, and a declaration names capabilities, not the
files they may touch.

No denied capability is used by this body.

What these declarations do **not** bound, and how their behaviour was established, is in
[Tool Grant Bounds](../../../explanation/tool-grant-bounds.md).

## Pages

No page is specific to this skill yet — its behaviour is defined by its `SKILL.md`.
