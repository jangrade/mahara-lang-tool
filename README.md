# mahara-lang-tool

Translate the empty texts of a [Mahara](https://mahara.org) language pack with an AI
coding agent, and check every result.

1. Download your language from Weblate.
2. Your agent runs this tool. It asks for your wishes, learns the rules of your existing
   translations, asks what they leave open, and translates the rest.
3. You get suggestions for Weblate and a quality report.

You need an AI coding agent, for example [opencode](https://opencode.ai) with a model
your university provides, or a commercial one such as Claude Code, OpenAI Codex or
GitHub Copilot. The agent brings the model; the tool has no AI of its own. The stronger
the model, the better the questions and translations.

Also needed: Python 3.9+, and optionally `msgfmt` (GNU gettext) for an extra check.

## Install

```sh
pipx install git+https://github.com/jangrade/mahara-lang-tool.git
mahara-lang-tool --version
```

## Quick start

1. Make an empty folder for your language, e.g. `mahara-nl/`.
2. In Weblate, download your language: Files → Download translation, format gettext PO.
3. Open your agent in the folder and tell it:

   > Run `mahara-lang-tool next` and do what it says. I am here and will answer your
   > questions. Repeat until the round is done.

The agent leads you through the round in English. Your part:

- **Give it the export.**
- **Name your own wishes**, if you have any, e.g. a form of address your university
  wants. The suggestions go to the shared pack, so a wish that differs from it changes
  it for every Mahara site in your language, and a reviewer may decline it.
- **Answer its questions** about what the existing translations leave open: all in one
  message, each with counts, examples and a recommendation. "As recommended" and
  "I do not know" are fine answers.
- **Upload the result** to Weblate as suggestions.

You can stop at any time; the same sentence continues. In later rounds the rules are
kept.

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

## Safeguards

The result is only suggestions; a reviewer in Weblate decides on each. Before that, the
tool makes sure that:

- **nothing is overwritten:** only texts that were empty in the export, with unchanged
  English text, go in;
- **nothing is broken:** lost or reordered placeholders, broken HTML, lost numbers or
  URLs and wrong plural forms block the result;
- **your rules hold:** a translation that breaks one blocks the result, unless the agent
  explains the exception in a note for the reviewer;
- **numbers are counted,** not guessed by the agent;
- **the file is read back** and checked with `msgfmt`.

The quality report names what was not checked: spelling, the look in the running
interface, and a second person's review.

## Profiles

The rules for a language live in one JSON profile, which the agent writes in the first
round. [`TEMPLATE.json`](mahara_lang_tool/profiles/TEMPLATE.json) explains every field.
An almost empty profile works too; then only the language-independent checks run.

Brief and quality report exist in English and German. To add a language, copy the `en`
block in [`messages.py`](mahara_lang_tool/messages.py) and translate it.

## Development

Internals, commands, batch format and the full list of checks: [AGENTS.md](AGENTS.md).

```sh
python3 -m unittest discover -s tests
```

`scripts/sample_export.py EXPORT.po -n 40` makes a small export (all translated texts,
40 open ones) for trying a change cheaply.

## How this was made

Developed with the help of an AI coding assistant. Design, review and testing by the
author.

## License

MIT, see [LICENSE](LICENSE). It covers the tool, not what you produce with it:
suggestions and reports contain texts of the project you translate and fall under its
license.

Not affiliated with or endorsed by the Mahara project or Weblate.
