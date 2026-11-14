---
docType: reference
layer: project
project: amoeba
audience: [human, ai]
description: The rules files a member's questions are answered from, from the user's side: what is read, where it is set, defaults, duplicates, imports, missing files and the size cap.
dateCreated: 20261114
dateUpdated: 20261114
status: complete
---

# Rules

When a paused run asks a question, Amoeba answers it only from what the repo says:
its **rules files**, the slice's plan files, the program's concept and your earlier
answers. The answering model sees the rules as evidence for what the repo allows, and
every answer cites the passages it rests on. This file says which rules files a member
reads and how to change that.

## What is read

- **Only committed files, at the target.** Amoeba reads each file with `git` at the
  commit the run's target branch points at, once per question. An uncommitted edit, an
  untracked file and a merge that lands mid-read are all invisible. Commit a rules file
  before you expect it to count.
- **Whole files, cut into passages at headings.** Every selected file is sent whole,
  cut before each level 1 to 3 heading so a citation can name one section. Amoeba does
  not trim rules by a `paths:` front matter.
- **Rules and plan text are never trimmed.** What they take is what your earlier
  answers cannot have (see the size cap below).

## Where it is set

A member either **names** its rules or **uses the default**:

| You run | The member reads |
|---|---|
| `amoeba add` (a new member, no rules flag) | the default (`default_rules_paths` in `config.yaml`) |
| `amoeba add --rules PATH` (repeatable) | those entries, and nothing else (`named`) |
| `amoeba add --default-rules` | the default again |
| `amoeba add --no-rules` | no rules at all (`named`, empty) |

With none of the three flags, an existing member keeps what it has. An entry is a
repo-relative path; a `*` is allowed in the last segment only (`docs/rules-*.md`);
never an absolute path or a `..`.

`amoeba list members` shows what each member uses: `default (CLAUDE.md, AGENTS.md)` or
the named entries.

## The default

The default is `default_rules_paths` in `config.yaml`, example `[CLAUDE.md,
AGENTS.md]`: the two root files, which together are about 24 KB for a repo like this
one. Scoped language rules (for example everything under `.claude/rules/`, about 52 KB
here) are opt-in through `--rules`. The default is read when a question is answered, so
editing it changes every member that uses it, with no command to run.

## A file that is not there

- **Default entries are optional.** An entry that matches no file at the commit is
  skipped. A repo with `CLAUDE.md` and no `AGENTS.md` reads `CLAUDE.md`.
- **Nothing found waits on you.** If every default entry is skipped the question is not
  answered: it waits on you as `sources_missing`, with the detail `no rules file found;
  tried: CLAUDE.md, AGENTS.md`. Add one of the files, or run `amoeba add --rules PATH`.
- **A named entry must exist.** A named entry that matches nothing fails the whole
  selection (`sources_missing`, naming the entry), however many others matched. A named
  empty list reads no rules and is not a failure.
- **A failing `git` is never "absent".** Whether a subdirectory exists is read with
  `git ls-tree`; any other failure from `git` waits as `sources_unreadable`, naming it.

The waiting question is cleared by `amoeba answer` or `amoeba dismiss`, or closes when
its run moves on; the fix (a file, an entry, a larger cap) serves the next question.

## Duplicates

Repos often keep one set of rules in two files. A rule section whose text equals a
section of an earlier rules file (after cutting at headings, compared exactly) is
dropped, and the earlier file keeps it, so a citation names that file. A section edited
in one file but not the other is two different passages, and both stay: it costs size,
not correctness. Plan and program passages are never dropped. The size cap counts the
text after duplicates are dropped.

## Imports

A rules file ending `.md` can pull in another with an `@path` import, as `CLAUDE.md`
files do. An import is a token starting with `@` at the start of a line or after
whitespace, outside fenced code blocks and inline code, whose path has no whitespace and
ends in `.md` (trailing `.,;:)` is removed), and does not start with `/` or `~`.
`@types/node` and `@scope/package` are not imports: no `.md`.

- The path is read against the importing file's directory and must stay inside the repo.
  One that leaves it declines the question as `sources_unreadable`, naming the import
  and the file; the repo file is what to fix.
- The imported file is read at the same commit, as a rules file placed directly after
  its importer, and may import in turn, at most 3 imports deep (deeper declines as
  `sources_unreadable`, giving the chain).
- A file already read is not read twice, so a cycle ends quietly.
- A missing target is skipped when the chain began at a default entry, and is
  `sources_missing` (`import @x in F matches no file`) when it began at a named one.
- Imported text counts against the size cap like any rules text.

## The size cap

`passages_max_chars` in `config.yaml` is the most characters of passages one answering
run is sent. Rules and plan text are never cut to fit, so the cap must cover all of
them: the rules (after duplicates are dropped), the slice's plan files, the program
concept, and room for the precedent you want kept. When they alone do not fit, the
question waits as `sources_too_large`, with the detail giving the size and the limit;
raise `passages_max_chars` (the example is 250000) and the next question uses it. To
size it, add the byte sizes of the rules files, the slice's concept, plan, design and
task files, and the program concept, and leave room for a few dozen KB of earlier
answers. This repo's two root rules files are about 24 KB and one slice's plan files
about 143 KB, so 250000 leaves room for both and for precedent.
