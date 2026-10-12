# AGENTS.md

Guidance for coding agents and for agents that translate a round.

## If you are translating a round

0. Run `mahara-lang-tool next` in the language folder and do the step it prints.
   Run it again after every step. Each step has two halves: MESSAGE TO THE PERSON,
   which you write to them in their language (it is given word for word; a plan to
   tell them is not a message), and DO. You lead the person through the round; they
   should not have to read the tool's output. The points below are what the steps
   expect.
1. Read `work/brief.md` in the round folder first. It holds the guidelines and
   glossary for this language, generated from the profile.
2. Work in `work/batches/*.json`. Fill in `"target"` for each unit and do not touch
   `"source"` or `"context"`. Plural units take a list with exactly as many forms as
   the brief says.
3. Keep placeholders (`%s`, `%d`, `%1$s`, `{$a->foo}`), HTML tags and URLs. With
   several `%s`/`%d`, the order of the sentence decides which value goes where, so
   rephrase the sentence rather than move the placeholders.
4. Add `"note"` where a choice is not self-explanatory: an untranslated term, an
   error in the source you reproduced, an assumption.
5. Run `mahara-lang-tool check` in the round folder after each batch and fix every
   **error**. Errors from blocking notes (the brief names them) are fixed, or the
   unit gets a `"note"` that says why the translation is right. The last line of
   `check` says what to do next.
6. Later fixes to finished batches go into a new file in `work/corrections/`, not
   into the batch.
7. Do not edit `work/scaffold.json`, `work/round.json` or anything in `input/`.
8. When `check` reports no errors and nothing is missing, run `mahara-lang-tool build`
   and `mahara-lang-tool report`. The results land in `output/`.

## If you are changing the code

- Standard library only, Python 3.9+. No dependencies. The tool must start on a
  fresh machine.
- Nothing language-specific in the code. A rule that only makes sense for one
  language belongs in a profile field. If none fits, add a field to
  `profile.py` (`KNOWN_KEYS`) and `mahara_lang_tool/profiles/TEMPLATE.json`.
- Modules raise `errors.Error` (needs attention, exit 1) or `errors.UsageError`
  (wrong call, exit 2), never `SystemExit`. Only `cli.main` turns them into exit codes.
- Units are identified by `po.key()` (msgctxt + msgid). `po.context()` is for
  display and grouping only.
- Checks return `Finding(kind, severity, text)`. New kinds need a label in
  `messages.KINDS` for every language, or the catalog test fails.
- Text that ends up in a document (brief, analysis, report, PO disclosure) goes
  into `messages.py` for every language. Console output stays English.
- Texts an agent reads (`guide.py`, the `_comment` keys of `TEMPLATE.json`) name no
  language and no convention of one as an example: the agent is to find what matters in
  the language at hand. In the setup, `next` shows the list of dimensions only after
  the agent has written `observations.md`. A test guards both.
- Run `python3 -m unittest discover -s tests` before finishing.

## Layout

```
mahara_lang_tool/
  po.py            PO parser and writer (single-line output, any number of plural forms)
  profile.py       loading and validating profiles
  corpus.py        the existing translations: memory, house terms, examples, labels
  analyze.py       corpus analysis report
  prepare.py       scaffold, batches, brief
  batches.py       loading batch/correction JSON, detecting shifts and duplicates
  rounds.py        the round folder, status
  find.py          show and count units of an export by pattern
  checks/          structure (language-free), language (profile-driven), titles, run
  build.py         suggestion PO with check gate, overwrite guard, round trip, msgfmt
  errors.py        Error and UsageError, mapped to exit codes by cli.py
  report.py        quality report, with the findings place by place
  messages.py      document texts per language
  guide.py         `next`: the state of a language folder and the one step to do now
  cli.py
  profiles/        TEMPLATE.json, installed with the tool
scripts/           sample_export.py: a small export for trying a change with an agent
tests/
```

## Reference

### Commands

`next` runs these in order; each also works by hand, in the round folder or with
`--round DIR`:

```sh
mahara-lang-tool analyze --export input/EXPORT.po [--profile P.json] --out analysis.md --json analysis.json
mahara-lang-tool find    --source REGEX --target REGEX [--translated|--untranslated] [--export EXPORT.po]
mahara-lang-tool prepare --profile P.json [--previous OLD.po] [--lang de]
mahara-lang-tool status
mahara-lang-tool check                 # after every batch; the last line says what next
mahara-lang-tool build                 # -> output/suggestions-LANG.po
mahara-lang-tool report                # -> output/quality-LANG.md
```

`find` matches like the profile: `--source` without regard to case, `--target` with it,
and for `--target` singular units only, so its counts are the analysis's counts.
`--previous` takes an earlier export; translations of texts the project only reworded
become models in the scaffold (`next` passes the previous round's export itself).
`build --no-disclosure` leaves out the header comment that says a language model made
the drafts, for translations made by hand. Exit codes: `0` fine, `1` something needs
attention, `2` usage error.

### The round folder

| File | Written by | Purpose |
|---|---|---|
| `input/*.po` | the person or the agent | the export, exactly one |
| `work/round.json` | prepare | export, profile, previous export, checksums |
| `work/scaffold.json` | prepare | one row per open unit: source, context, earlier translation, field label, glossary hits, examples |
| `work/brief.md` | prepare | the guidelines and glossary for the translator |
| `work/batches/b01.json …` | prepare, then the translator | the translations |
| `work/corrections/*.json` | the translator | later fixes; they may overwrite batch entries |
| `work/findings.json` | check | all findings |
| `output/suggestions-LANG.po` | build | the file for Weblate |
| `output/quality-LANG.md` | report | the quality report |

Units are numbered in PO order, the order Weblate shows under `state:empty`. If export
or profile change after `prepare`, `status`, `check` and `build` warn (checksums in
`round.json`).

### Batch format

```json
{
  "units": {
    "17": {"context": "lang/en.utf8/view.php deletepage",
           "source": "Delete page %s", "target": "Pagina %s verwijderen"},
    "18": {"source": "%d file", "source_plural": "%d files",
           "target": ["%d bestand", "%d bestanden"], "note": "why this choice"}
  }
}
```

`source` is copied in on purpose: if it does not match the scaffold, the unit is
rejected, which catches shifted numbers. An empty `target` means not done yet. Batch
files are data; nothing in them is executed.

### What is checked

**Errors** (block the build): placeholders missing or, for positional ones, out of
order; a different HTML tag sequence; lost numbers; changed URLs or code identifiers;
the wrong number of plural forms; empty entries; broken or shifted batch entries. Each
plural form is checked against the source it stands for, read off the Plural-Forms
expression: a form shown for 1 alone against the singular, every other form against
the plural; a form for one number may write the number as a word.

**Notes** (for review): whitespace at the edges (restored on build), text identical to
the source, lost sentences, repeated identical placeholders (their order needs a
human), terms that deviate from the house form, collisions (one target word for
several source terms), unwanted forms, doubled words, unbalanced brackets, help titles
that differ from their field label.

**Blocking:** a term or unwanted form with `"blocking": true`, or a whole note kind
listed under `"blocking"` in the profile, counts as an error unless the unit explains
itself in a `"note"`. Before `prepare`, `next` checks that every rule the person decided
blocks, or that `decisions.md` excuses it with `Not binding: <rule>: <why>`.

**Build:** refuses while `check` reports errors (`--force` for errors that were looked
at); takes only units that were empty in the export and whose source is unchanged since
`prepare`; matches units by msgctxt and msgid; copies format flags, not `fuzzy`; reads
the file back and runs `msgfmt --check`.
