# mahara-lang-tool

Translate the open texts of a [Mahara](https://mahara.org) language pack with an AI
coding agent, safely.

**All you need is an AI coding agent.** You talk to it; it runs this tool, which leads
it step by step and checks everything it writes. The better the model behind the agent,
the better the outcome: sharper questions about your language, better translations and
fewer corrections along the way. A small model gets through a round, but needs a closer
eye from you.

You download your language from Weblate. An AI agent works out the rules your existing
translations follow, asks you what they leave open, translates the rest, and the tool
checks every text. At the end you get a **suggestion file** for Weblate that contains
only texts that were empty, so nothing existing can be overwritten, and a quality
report that says what was checked and what was not.

The agent does the work; you make the decisions, and a reviewer accepts every
suggestion in Weblate. The tool itself calls no model and needs no account or key.
Everything about one language lives in a profile, so the code is the same for every
language.

- Python 3.9+, standard library only.
- Any AI coding agent that can read files and run commands.
- `msgfmt` (GNU gettext), if installed, for an extra check of the result.

## Install

```sh
pipx install git+https://github.com/jangrade/mahara-lang-tool.git
mahara-lang-tool --version
```

## Quick start

1. Make an empty folder for your language, e.g. `mahara-nl/`.
2. In Weblate, download your language: Files → Download translation, format gettext PO.
3. Open your AI coding agent in the folder and tell it:

   > Run `mahara-lang-tool next` and do what it says. I am here and will answer your
   > questions. Repeat until the round is done.

That is all you need to know. The agent leads you through the rest, in English, and
explains each part before it starts. What you do:

- **Give it the export.** You say where the download is; the agent puts it in place.
- **Name your own wishes, if you have any**, for example a form of address your
  university wants. They come before what the existing translations do. Keep in mind
  that the suggestions go to the shared Weblate pack: a wish that differs from it would
  change it for every Mahara site in your language, and a reviewer may decline it.
- **Answer questions about your language.** The first time, the agent reads the
  existing translations, notes which conventions they follow and where they are split,
  adds what it knows about your language, and counts all of it. Then it asks you, in
  one message, only what the existing translations leave open, each question with the
  numbers, an example per option and a recommendation. "All as recommended, except 3"
  and "I do not know" are fine answers. You need not know the conventions of your pack
  beforehand. At the end it sums up the rules for you to confirm.
- **Upload the result** to Weblate as suggestions; the agent tells you how, and what
  the quality report says.

In between, the agent translates portion by portion and the tool checks each one. You
have nothing to do there and can stop at any time; the same sentence continues where
you left off. In later rounds the rules are kept, and the agent only checks that they
still fit the new export.

```
mahara-nl/
  wishes.md         your own wishes, which come before the conventions of the pack
  profile-nl.json   the rules for your language
  observations.md   what the agent saw in the existing translations and knows about the language
  decisions.md      the questions you were asked, with your answers
  analysis.md       what the existing translations do
  26.04/
    input/          the export
    work/           the agent's workspace
    output/         suggestions-nl.po and the quality report
```

## Why you can trust the result

1. **Only empty texts go in.** The suggestion file takes only texts that were empty in
   the export, and only if their English text has not changed since. It cannot
   overwrite existing work.
2. **No result with errors.** Lost or reordered placeholders, broken HTML, lost
   numbers or URLs, wrong plural forms: as long as the check finds one, there is no
   suggestion file.
3. **Your decisions are enforced.** A rule you decided stops the build when a
   translation breaks it, unless the agent explains the exception in a note for the
   reviewer. Before a round starts, the tool checks that every decision of yours is
   such a rule.
4. **Numbers come from the tool.** Every number in a question is counted by the tool,
   not estimated by the agent.
5. **Read back.** The written file is read back and compared character by character,
   then checked by `msgfmt`.
6. **The report says what was not checked:** spelling, how a text looks in the running
   interface, and a review by a second person.

## Profiles

A profile is one JSON file per language: guidelines in plain words, a glossary, terms
whose house translation is counted and enforced, forms that are wanted or not. The agent
writes it in the first round, from the existing translations and your answers. Start
from [`TEMPLATE.json`](mahara_lang_tool/profiles/TEMPLATE.json), whose `_comment` keys
explain every field. An almost empty profile works too: then only the checks that need no
language knowledge run, which already catch the expensive mistakes.

Brief and quality report exist in English and German. To add a language, copy the `en`
block in [`messages.py`](mahara_lang_tool/messages.py) and translate it.

## Development

How the tool works inside, the commands, the batch format and the full list of checks
are in [AGENTS.md](AGENTS.md).

```sh
python3 -m unittest discover -s tests
```

To try a change with an agent cheaply, `scripts/sample_export.py EXPORT.po -n 40`
makes a small export: all translated texts and 40 open ones.

## How this was made

This tool was developed with the help of an AI coding assistant. Design decisions,
review and testing against real translation rounds were done by the author.

## License

MIT, see [LICENSE](LICENSE).

The license covers the tool. Files you produce with it (suggestion files, reports)
contain the texts and translations of the project you work on and fall under that
project's license.
