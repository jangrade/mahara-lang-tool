"""`next`: what to do now, read off the folder.

An agent should not have to plan a round. It runs `mahara-lang-tool next`, does the
one step printed, and runs `next` again. Everything the step depends on is visible in
the files, so the answer is always the same for the same folder:

    mahara-nl/                  the language folder, one per language
      profile-nl.json           written once, in the first-time setup
      analysis.md, .json        the analysis of the existing translations
      profile-nl.draft.json     the profile while the setup is running
      observations.md           what the agent saw in the pack and knows about the language
      decisions.md              questions for the person, with their answers
      26.04/                    a round: input/ work/ output/
      26.10/

First time (no profile yet): analyze, note observations, draft a profile, put the open questions to the
person, write the profile. Every round after that: refresh the analysis for the new
export, prepare, translate batch by batch, build, report.

Console output, so English. The texts speak to the agent. Every step has two parts:
TELL THE PERSON, what the agent explains to them in their language before it acts, and
DO, the work itself. The person should never have to read this output or know the
tool: the agent leads them through.
"""
import collections
import glob
import json
import os
import re

from . import batches as batch_module
from . import po
from . import profile as profile_module
from . import rounds
from .checks import run as check_run
from .errors import UsageError

ANALYSIS_MD = 'analysis.md'
ANALYSIS_JSON = 'analysis.json'
DECISIONS = 'decisions.md'
OPEN = re.compile(r'^\s*- \[ \]', re.M)

RULES = '''Rules for every step:
- You lead the person; they know neither this tool nor agents. They read along, even
  when they write nothing: this is a conversation, not an unattended job. Send every
  MESSAGE TO THE PERSON as your reply text, in English, before the next command.
  Planning to tell them is not telling them, and a message
  saved for a summary at the end is a message they never got. At NO MESSAGE, work without
  commentary. Show no commands or file formats unless they ask.
- Numbers for the person come from analysis.md or from `mahara-lang-tool find --source
  REGEX --target REGEX`, never from scripts of your own over the .po file.
- They can stop at any time: everything is saved here, and their first sentence to you
  continues the round.
- Stay in this folder; the export may come from the path they name. The rules for the
  language come from its existing translations and the person, not from other projects.
- Run `mahara-lang-tool next` after each step. If a command fails in a way the step does
  not cover, tell them plainly what happened and ask; never guess.
- Never edit input/, work/scaffold.json or work/round.json.'''

PHASES = ('export', 'rules for the language', 'translate and check', 'result')
PHASE = {'new round': 0, 'export': 0, 'choose round': 0,
         'setup': 1, 'choose profile': 1, 'refresh analysis': 1, 'new terms': 1,
         'fix questions': 1, 'decide': 1, 'bind rules': 1,
         'prepare': 2, 'translate': 2, 'fix': 2,
         'build': 3, 'report': 3, 'done': 4}

OVERVIEW = '''I will lead you through translating the new texts of Mahara into your language. It
has four parts:
1. Export: you give me the file with the texts from Weblate.
2. Rules: I read the existing translations, work out which conventions they follow, and
   ask you only where they are not clear. You decide. This happens once; later rounds
   reuse the rules.
3. Translating: I translate the open texts in portions, and a tool checks every portion.
   You have nothing to do there.
4. Result: you get a file with suggestions to upload to Weblate, where a reviewer
   accepts them one by one. Nothing that exists is overwritten.
You can stop at any time and continue later; everything is saved in this folder.'''

EXPORT_HOW = '''To start I need the export. In Weblate, open the Mahara component in your language,
then Files → Download translation, format "gettext PO" (the names differ a little
between Weblate versions). You do not have to create folders or move anything: tell me
where the file is, for example your Downloads folder, and which Mahara version it is,
for example 26.04.'''


def tell(message, do, after=False):
    """A step: what the agent writes to the person, and what it does. message None:
    nothing to say. after: the message is sent once the work is done, or, if a string,
    at the point it names."""
    if message is None:
        head = 'NO MESSAGE at this step: work on without commentary.'
    else:
        when = (after if isinstance(after, str) else 'when the DO part is finished'
                if after else 'now, before your next tool call')
        head = ('MESSAGE TO THE PERSON: write this to them %s, in English:\n\n%s'
                % (when, '\n'.join('    ' + line if line else ''
                                   for line in message.split('\n'))))
        if not after:
            do = 'First write the message above as your reply. Then:\n' + do
    return '%s\n\nDO:\n%s' % (head, do)


def progress(what):
    """The four parts of a round with a mark at the current one."""
    now = PHASE.get(what, 0)
    return ' · '.join('%d %s%s' % (i + 1, name, ' ✓' if i < now else ' ← now' if i == now else '')
                      for i, name in enumerate(PHASES))


OBSERVATIONS = 'observations.md'
SEEN, KNOWN, PROMPTED = 'Seen', 'Known', 'From the checklist'

OBSERVE = '''Before you draft any rule, write down what you find yourself, in %(file)s, in two
sections. This step gives you no list of topics, on purpose: what matters differs from
language to language, and you know this language better than this tool does.

## %(seen)s
What the existing translations do. Read %(analysis)s (source texts translated
inconsistently, translations that stand for several source texts). Then look at real
units with `mahara-lang-tool find`, spread over the kinds of text: short labels,
buttons, help texts, messages, e-mails, units with plural forms, units with
placeholders. Note the conventions the pack keeps throughout as well as the places
where it is split. Quote a unit with its key for every point.

## %(known)s
What you know about this language: the points where translations of software into it
typically differ between translators or go wrong, and what a careful reviewer of this
language would look for. Write them down whether or not you have seen them in the pack.

One point per line, starting with "- ". Decide nothing yet.''' % {
    'file': OBSERVATIONS, 'seen': SEEN, 'known': KNOWN, 'analysis': ANALYSIS_MD}

CHECKLIST = '''Start from %(file)s. Every point under "%(seen)s" and "%(known)s" becomes a
pattern in "forms" or "terms" wherever it can be counted, so that the next analysis
shows what the pack really does. Where the pack uses two forms for the same thing, add
both as forms, so both are counted. One term per meaning: do not put several source
words into one term unless the language translates them with the same word. Try a
pattern with `mahara-lang-tool find --target PATTERN` before you write it down.

Only then hold your observations against the dimensions below, as a cross-check. They
are prompts, not a list to fill: drop what this language does not have. Add a third
section to %(file)s, "## %(prompted)s", with what only the cross-check
brought up, or the one line "- nothing new". Those points get a pattern as well.

- how the user is addressed
- how people are referred to
- the form of verbs on buttons, labels and in messages
- what happens to words around placeholders: inflection, agreement, word order,
  plural categories
- borrowed words, words that stay in English, script
- typography: quotation marks, spacing, punctuation, numbers
- capitalisation of labels and buttons
- product terms: portfolio, page, collection, section, group, institution, artefact,
  journal, friend, share, account, and whatever the analysis lists as inconsistent.
  Add them to "terms", with every translation you find as a variant, so the analysis
  finds the house form.
- terms the English source has renamed: English words that are frequent in the
  untranslated units of the export but rare in the translated ones
- plural forms: must match the Plural-Forms line of the export header''' % {
    'file': OBSERVATIONS, 'seen': SEEN, 'known': KNOWN, 'prompted': PROMPTED}

OUTCOMES = '''Then say what became of every point in %(file)s: add " → " and one of these at
the end of the point (after its last line, if it runs over several).
  → F2, T1        the ids of the forms and terms that count it (from %(analysis)s)
  → guideline     the pack is consistent here; the rule goes into "guidelines"
  → question      it cannot be counted, the person has to decide (an "Observed:" question)
  → no rule: …    with the reason, e.g. it plays no part in this language pack
No point may be left without one: a point without an outcome is a point forgotten.
A point where the pack uses two or more variants for the same thing is not a
guideline unless one of them clearly prevails: count the variants and ask the person.
Choosing between variants yourself is deciding for them.''' % {
    'file': OBSERVATIONS, 'analysis': ANALYSIS_MD}

DECISIONS_FORMAT = '''Two kinds of question.

Counted: the analysis has numbers for it. Cite the evidence ids from analysis.md
(T… terms, F… forms, N… new terms) and write no numbers of your own. When you ask,
show those blocks as they are, every variant including "none of these":

    ## 1. <topic>
    - [ ] <the question, in one sentence>
      Evidence: F1, F2
      Recommendation: <one of the variants> because …
      Answer:

Observed: something you noticed that no pattern can count, e.g. a tone or a style
in one area. Mark it and quote units word for word with their key:

    ## 5. <topic>
    - [ ] <the question, in one sentence>
      Observed: <what you noticed>
      - `lang/en.utf8/view.php title_help`: "…"
      Recommendation: <one of the variants> because …
      Answer:

What can be counted is counted: add a pattern to "terms" or "forms" at the end of
the draft (so the ids stay stable), run the analysis again and cite its id.
Keep each question short. The person decides; you recommend, and a recommendation
names one variant: "pick one and keep to it" is no help to someone who knows the
conventions less well than you do.'''

WRITE_DECISIONS = '''Write decisions.md, one entry per question the existing translations do not
answer clearly: a split with no clear majority, a source term that changed, or a
rule the pack breaks often. Where the pack is clear, do not ask; write the rule into
the draft. Do not ask about a point because it is on a list either: a convention that
plays no part in this language is no question. Do not ask what wishes.md settles.

''' + DECISIONS_FORMAT


def _profile_files(workspace):
    return sorted(p for p in glob.glob(os.path.join(workspace, 'profile-*.json'))
                  if not p.endswith('.draft.json'))


def _is_round(path):
    return any(os.path.isdir(os.path.join(path, d))
               for d in (rounds.INPUT, rounds.WORK))


def _rel(path, workspace):
    return os.path.relpath(path, workspace)


def _newest(paths):
    times = [os.path.getmtime(p) for p in paths if os.path.exists(p)]
    return max(times) if times else 0


def _finished(round_dir):
    """Built and reported after the last change to batches, corrections and export."""
    out = glob.glob(os.path.join(round_dir, rounds.OUTPUT, 'suggestions-*.po'))
    report = glob.glob(os.path.join(round_dir, rounds.OUTPUT, 'quality-*.md'))
    if not out or not report:
        return False
    return _fresh_build(round_dir, out) and _newest(report) >= _newest(out)


def _analysis(workspace):
    try:
        with open(os.path.join(workspace, ANALYSIS_JSON), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _same(a, b):
    return bool(a and b) and os.path.abspath(a) == os.path.abspath(b)


WISHES = 'wishes.md'

ASK_WISHES = (
    'Before I look at the existing translations: are there wishes for your language '
    'that I should follow, even where the existing translations do something else? '
    'For example from your university: a form of address, a term, a style. If not, '
    'just say so.\n'
    'One thing to know: the suggestions go to the shared Weblate pack that every Mahara '
    'site in your language uses. A wish that differs from that pack would change it '
    'for everyone, and a reviewer may decline it.')


def step(workspace, round_name=None):
    """(round or None, step name, instructions) for the folder as it is now."""
    return _step(workspace, round_name)


def _step(workspace, round_name):
    candidates = sorted(d for d in os.listdir(workspace)
                        if _is_round(os.path.join(workspace, d)))
    if round_name:
        if round_name not in candidates:
            raise UsageError('%s is not a round folder in %s' % (round_name, workspace))
        open_rounds = [round_name]
    else:
        open_rounds = [d for d in candidates if not _finished(os.path.join(workspace, d))]

    new_round = ('Wait for their answer. Create a folder named after the Mahara version, '
                 'e.g. 26.04/input/, and move or copy the export there from the path '
                 'they name.')
    if not open_rounds:
        if not candidates:
            first = not _profile_files(workspace)
            message = (OVERVIEW if first else
                       'A new round starts with a new export. The rules for your language '
                       'from last time are kept.') + '\n\n' + EXPORT_HOW
            return None, 'new round', tell(message, new_round)
        latest = max(candidates, key=lambda d: _newest(glob.glob(
            os.path.join(workspace, d, rounds.OUTPUT, '*'))))
        r = rounds.load(os.path.join(workspace, latest))
        return latest, 'done', (done_text(latest, r) + '\n\nFor the next Mahara version '
                                'they give you a new export: ' + new_round)
    if len(open_rounds) > 1:
        return None, 'choose round', tell(
            'There is more than one unfinished round in this folder: %s. Which one shall '
            'we work on?' % ', '.join(open_rounds),
            'Wait for their answer, then run `mahara-lang-tool next --round NAME`.')

    name = open_rounds[0]
    round_dir = os.path.join(workspace, name)
    try:
        export = rounds.find_export(round_dir)
    except UsageError as e:
        return name, 'export', tell(
            'For round %s I need exactly one export.\n\n%s' % (name, EXPORT_HOW),
            'Wait for their answer and put the export into %s/input/, from the path they '
            'name. %s' % (name, e))
    export_rel = _rel(export, workspace)

    profiles = _profile_files(workspace)
    if len(profiles) > 1:
        return name, 'choose profile', tell(
            'This folder holds rules for more than one language (%s), but a folder is '
            'for one language. Which one belongs here?'
            % ', '.join(os.path.basename(p) for p in profiles),
            'Wait for their answer and move the other profiles away.')
    if not profiles:
        return name, 'setup', setup(workspace, export, export_rel)
    profile_path = profiles[0]
    profile_rel = _rel(profile_path, workspace)

    if not os.path.exists(os.path.join(round_dir, rounds.WORK, rounds.SCAFFOLD)):
        analysis = _analysis(workspace)
        if not (analysis and _same(analysis.get('export'), export)
                and _same(analysis.get('profile'), profile_path)):
            return name, 'refresh analysis', tell(
                'I have the export for round %s. The rules for your language from last '
                'time are kept; I am checking that they still fit the new texts. You have '
                'nothing to do unless something needs a decision.' % name,
                'Check that the profile fits this export before the round starts.\n'
                '1. Run `mahara-lang-tool analyze --export %s --profile %s --out %s --json %s`.\n'
                '2. Compare the sections "House terms" and "Forms" in %s with the profile. '
                'If a house form has changed, or a term the profile does not cover shows '
                'up as inconsistent, add a question to %s, in the format of the questions '
                'already there; the next step puts it to the person.'
                % (export_rel, profile_rel, ANALYSIS_MD, ANALYSIS_JSON, ANALYSIS_MD,
                   DECISIONS))
        pending = decisions(workspace, analysis, apply_to=profile_rel)
        if pending:
            return (name,) + pending
        loose = binding_problems(workspace, analysis, profile_path)
        if loose:
            return name, 'bind rules', tell(None, binding_text(loose, profile_rel))
        earlier = [d for d in candidates if d < name and glob.glob(
            os.path.join(workspace, d, rounds.INPUT, '*.po'))]
        previous = (' --previous %s' % _rel(rounds.find_export(
            os.path.join(workspace, earlier[-1])), workspace)) if earlier else ''
        return name, 'prepare', tell(None, (
            'Run `mahara-lang-tool prepare --profile %s --round %s%s`.'
            % (profile_rel, name, previous)))

    r = rounds.load(round_dir)
    counts, missing = check_run.collect(r)[2:4]
    folder = name
    if counts['errors']:
        return name, 'fix', tell(None, (
            'Run `%s`: it lists %d errors. Fix them. Where an error comes from a blocking '
            'rule of the profile and the translation is right all the same, explain in '
            'the unit\'s "note" why; where a rule of the person seems wrong for many '
            'texts, stop and ask them. Fixes to finished batches go into a new file in '
            '%s/work/corrections/.'
            % (rounds.command('check', folder), counts['errors'], name)))
    if missing:
        brief = os.path.join(name, rounds.WORK, 'brief.md')
        batches = batch_module.per_file(r.work)
        done = sum(1 for _, numbers, filled in batches if not numbers - filled)
        if not counts['translated']:
            message = ('The rules are settled, now I translate: %d texts in %d portions. '
                       'This is the long part and can take hours. You have nothing to '
                       'do and need not stay. If we are interrupted, tell me the same '
                       'sentence again and I go on where I stopped. After each portion '
                       'I tell you in one line how far I am.'
                       % (counts['units'], len(batches)))
        else:
            message = ('%d of %d portions are done (%d of %d texts). '
                       '<one more line only if you noted something for the reviewer>'
                       % (done, len(batches), counts['translated'], counts['units']))
        return name, 'translate', tell(message, (
            'Read %s first if you have not yet: it holds the rules and the glossary. '
            'Then %s\nIf you hand batches to sub-agents, give each of them the whole of '
            '%s, and run the check yourself after every batch that comes back: a '
            'sub-agent that does not know the rules translates against them.'
            % (brief, check_run.next_step(r, folder, counts, missing), brief)))

    out = glob.glob(os.path.join(round_dir, rounds.OUTPUT, 'suggestions-*.po'))
    if not _finished(round_dir):
        if not out or not _fresh_build(round_dir, out):
            return name, 'build', tell(None, (
                'Run `%s`. If it reports a failed cross-check, stop and tell the person.'
                % rounds.command('build', folder)))
        return name, 'report', tell(None, 'Run `%s`.' % rounds.command('report', folder))
    return name, 'done', done_text(name, r)


def _fresh_build(round_dir, out):
    """Built after the last change to batches, corrections and export."""
    work = os.path.join(round_dir, rounds.WORK)
    inputs = (glob.glob(os.path.join(work, 'batches', '*.json'))
              + glob.glob(os.path.join(work, 'corrections', '*.json'))
              + glob.glob(os.path.join(round_dir, rounds.INPUT, '*.po')))
    return _newest(out) >= _newest(inputs)


def setup(workspace, export, export_rel):
    """The first-time setup of a language, in six steps."""
    header = po.header_fields(po.header(export))
    lang = header.get('Language') or 'xx'
    draft = os.path.join(workspace, 'profile-%s.draft.json' % lang)
    final = 'profile-%s.json' % lang
    draft_rel = os.path.basename(draft)
    analysis = _analysis(workspace)

    intro = ('FIRST-TIME SETUP for language "%s". There is no profile yet. The profile '
             'holds the rules for this language; the person decides them, you prepare '
             'the decisions. Step %%d of 6.\n\n' % lang)

    if not os.path.exists(draft):
        if not os.path.exists(os.path.join(workspace, WISHES)):
            return intro % 1 + tell(ASK_WISHES, (
                'Wait for their answer. Write each wish they name into %s in this folder '
                '(the language folder, next to the round folders, not inside one), one line '
                'starting with "- " each, in their words; if they have none, write the one '
                'line "- none". The wishes come before what the existing translations do: '
                'they become rules of the profile, and nothing they settle is asked again.'
                % WISHES))
        if not (analysis and _same(analysis.get('export'), export)):
            return intro % 1 + tell(
                'Thank you, I have the export. First I read the existing translations, to '
                'see which conventions they follow. That takes a few minutes; you have '
                'nothing to do yet.',
                'If the person has not had the overview of the four parts in this '
                'conversation, put it before the message:\n\n%s\n\n'
                'Then run `mahara-lang-tool analyze --export %s --out %s --json %s` and read '
                '%s: which source texts are translated inconsistently, which translations '
                'stand for several source texts.'
                % ('\n'.join('    ' + line for line in OVERVIEW.split('\n')),
                   export_rel, ANALYSIS_MD, ANALYSIS_JSON, ANALYSIS_MD))
        gaps = observation_gaps(workspace)
        if gaps:
            z = analysis.get('counts', {})
            return intro % 2 + tell(
                'The export has %d texts: %d are translated, %d are still open. I am now '
                'reading the translated ones closely. Nothing to do for you yet.'
                % (z.get('units', 0), z.get('translated', 0), z.get('untranslated', 0)),
                OBSERVE + ('\n\nStill empty in %s: %s.' % (OBSERVATIONS, ', '.join(gaps))
                           if os.path.exists(os.path.join(workspace, OBSERVATIONS)) else ''))
        write_draft(draft, lang, header.get('Plural-Forms'))
        return intro % 3 + tell(NOTICED, fill_text(draft_rel, created=True))
    try:
        with open(draft, encoding='utf-8') as f:
            unfinished = TODO in json.load(f)
    except ValueError as e:
        return intro % 3 + tell(None, '%s is not valid JSON: %s. Fix it.' % (draft_rel, e))
    if unfinished:
        return intro % 3 + tell(None, fill_text(draft_rel, created=False))

    if not (analysis and _same(analysis.get('profile'), draft)
            and os.path.getmtime(os.path.join(workspace, ANALYSIS_JSON))
            >= os.path.getmtime(draft)):
        return intro % 4 + tell(None, (
            'Count the draft against the existing translations: run `mahara-lang-tool '
            'analyze --export %s --profile %s --out %s --json %s`. If the profile does not '
            'load, fix the error it reports and run it again. Then look at the sections '
            '"Forms" and "House terms" in %s, and for every form at its sample hits under '
            '"forms" in %s. Every sample must mean exactly what a question will ask about: '
            'the numbers the person sees come from these patterns. A pattern that also '
            'hits something else (another meaning, another grammatical person) is refined, not '
            'deleted: narrow it (for instance, leave out the start of a sentence) and '
            'try it with `mahara-lang-tool find --target PATTERN`. A rule you cannot get '
            'clean stays in the draft and is simply not made blocking later.'
            % (export_rel, draft_rel, ANALYSIS_MD, ANALYSIS_JSON, ANALYSIS_MD, ANALYSIS_JSON)))

    loose = observation_problems(workspace, analysis)
    if loose:
        return intro % 5 + tell(None, (
            OUTCOMES + '\n\nStill to do in %s:\n%s\n\nIf a point needs a new pattern, '
            'add it at the end of "forms" or "terms" in %s and the analysis will be run '
            'again.' % (OBSERVATIONS, '\n'.join('- ' + x for x in loose[:12]), draft_rel)))
    pending = decisions(workspace, analysis)
    if pending:
        return intro % 5 + pending[1]
    return intro % 6 + tell(
        'The rules for your language are now written down:\n'
        '<the rules in four to eight short lines, in plain words of their language>\n'
        'Is that what you meant? You can change them at any time: just tell me.',
        'Finish the profile:\n'
        '1. Apply every answer from %s to %s: guidelines (in plain words, for the '
        'translator), glossary, terms, forms. Where the person chose one form over '
        'another, the rejected one must be in the profile as a form with "wanted": '
        'false, or as a variant of a term: a decision that is only a guideline is not '
        'checked.\n'
        '2. Make rules binding. A term or a form with "blocking": true stops the build '
        'until a deviating translation is fixed or explained in a note. Set it on every '
        'rule the person decided whose sample hits in the analysis are clean. A rule '
        'with false alarms you could not remove stays, without "blocking", and gets a '
        'line in %s: "Not binding: <rule name>: <why>". Before the round starts, next '
        'checks that every decided rule does one or the other. ("blocking" at '
        'the top of the profile switches whole kinds of notes: %s. Use it only for kinds '
        'you want blocked without exception.)\n'
        '3. Send the message and wait for their reply. If they correct a rule, change '
        'the draft. Do not go on before they have answered: the next point ends the '
        'setup.\n'
        '4. Rename %s to %s, then run `mahara-lang-tool analyze --export %s --profile %s '
        '--out %s --json %s`. It loads the profile and reports every error in it (unknown '
        'key, bad pattern, missing field); fix them until it runs.'
        % (DECISIONS, draft_rel, DECISIONS, ', '.join(profile_module.BLOCKABLE), draft_rel, final,
           export_rel, final, ANALYSIS_MD, ANALYSIS_JSON), after='at point 3 of the DO part')


def decisions(workspace, analysis, apply_to=None):
    """The questions for the person, the same in the setup and in later rounds:
    (step name, instructions) for what is still to do, or None.

    apply_to: the profile, in a later round; the answers then go into it at once.
    In the setup they are applied in the last step."""
    terms = unhandled_terms(workspace, analysis)
    if apply_to is None and not os.path.exists(os.path.join(workspace, DECISIONS)):
        return 'questions', tell(None, WRITE_DECISIONS + (
            '\n\n' + terms_text(terms) if terms else ''))
    if terms:
        return 'new terms', tell(None, terms_text(terms) + ' Use the format of the '
                                 'questions already in %s.' % DECISIONS)
    problems = question_problems(workspace, analysis)
    if problems:
        return 'fix questions', tell(None, problems_text(problems))
    open_count = _open_questions(workspace)
    if not open_count:
        return None
    do = ask_text(open_count)
    if apply_to:
        do += ('\nWhen all are answered: update %s with the answers (see its "_comment" '
               'keys; what the person rejected becomes a form with "wanted": false) and '
               'tell them in two or three lines what changed in the rules.' % apply_to)
    return 'decide', tell(ask_message(open_count), do)


NOTICED = '''I have read the existing translations. What I noticed:
<three to five short points, each with one real example from the translations>
Next I turn these notes into rules that can be counted. Nothing to do for you yet.'''


def observation_problems(workspace, analysis):
    """Points in observations.md that do not say what became of them, and a missing
    cross-check section."""
    try:
        with open(os.path.join(workspace, OBSERVATIONS), encoding='utf-8') as f:
            text = f.read()
    except OSError:
        return []
    known = _known_ids(analysis)
    problems = []
    if not re.search(r'^## %s' % re.escape(PROMPTED), text, re.M):
        problems.append('the section "## %s" is missing (write "- nothing new" if the '
                        'cross-check brought up nothing)' % PROMPTED)
    # A point is a line starting with "- " and every line after it up to the next point
    # or heading: agents write points as paragraphs, with quotes indented below. Its
    # outcome is the last "→" in it (quotes may use arrows of their own).
    points = []
    for line in text.split('\n'):
        if re.match(r'- \S', line):
            points.append(line)
        elif line.startswith('#'):
            points.append(None)
        elif points and points[-1] is not None:
            points[-1] += '\n' + line
    for block in filter(None, points):
        point = ' '.join(block.split())[2:62]
        if '→' not in block:
            if 'nothing new' not in block.lower():
                problems.append('no outcome: %s…' % point)
            continue
        outcome = block.rsplit('→', 1)[1]
        ids = EVIDENCE_ID.findall(outcome)
        unknown = [i for i in ids if i not in known]
        if unknown:
            problems.append('%s not in the current %s: %s…'
                            % (', '.join(unknown), ANALYSIS_MD, point))
        elif not ids and not re.search(r'guideline|question|no rule', outcome, re.I):
            problems.append('outcome not understood: %s…' % point)
    return problems


TODO = '_todo'


def observation_gaps(workspace):
    """The sections of observations.md that have no point yet. The draft profile, and
    with it the list of dimensions, comes only after the agent has written down what it
    saw and what it knows: a list read first decides what is found."""
    try:
        with open(os.path.join(workspace, OBSERVATIONS), encoding='utf-8') as f:
            text = f.read()
    except OSError:
        text = ''
    gaps = []
    for name in (SEEN, KNOWN):
        m = re.search(r'^## %s[^\n]*\n(.*?)(?=^## |\Z)' % re.escape(name), text, re.M | re.S)
        if not (m and re.search(r'^\s*- \S', m.group(1), re.M)):
            gaps.append('"## %s"' % name)
    return gaps


def write_draft(path, lang, plural_forms):
    """The template as the draft profile, with what the export already says."""
    with open(profile_module.TEMPLATE, encoding='utf-8') as f:
        data = json.load(f, object_pairs_hook=collections.OrderedDict)
    draft = collections.OrderedDict([(TODO, 'Fill in this draft as `mahara-lang-tool next` '
                                            'says, then delete this line.')])
    for key, value in data.items():
        draft[key] = value
        if key == 'language':
            draft[key] = lang
            if plural_forms:
                draft['plural_forms'] = plural_forms
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)
        f.write('\n')


def fill_text(draft_rel, created):
    first = ('I wrote %s: the template, with language and plural forms from the export. '
             % draft_rel if created else 'Go on with %s. ' % draft_rel)
    return first + (
        'Its "_comment" keys explain every field, and entries marked "_example" show the '
        'format (they are ignored; replace them). Fill it in:\n\n%s\n\nPut rules into '
        '"forms" and "terms" as patterns, so that the next analysis counts them. Do not '
        'decide anything the pack does not decide: those become questions in step 5. '
        'The wishes in %s come first: each becomes a rule of the draft (a guideline, a '
        'glossary entry, a form or term), also where the pack does something else. '
        'When the draft is filled in, delete its "%s" line.' % (CHECKLIST, WISHES, TODO))


def _decisions_text(workspace):
    try:
        with open(os.path.join(workspace, DECISIONS), encoding='utf-8') as f:
            return f.read()
    except OSError:
        return ''


def unhandled_terms(workspace, analysis):
    """New terms from the analysis that decisions.md does not mention yet."""
    text = _decisions_text(workspace)
    return [n['term'] for n in (analysis or {}).get('new_terms', [])
            if not re.search(r'\b%ss?\b' % re.escape(n['term']), text, re.I)]


def terms_text(terms):
    return ('The analysis (section "New terms" in %s, ids N…) lists source words that are '
            'frequent in the untranslated units and rare in the translated ones: %s. '
            'decisions.md must mention each of them. For every product term, and every '
            'word the source now uses instead of an older one: add a counted question '
            'with its N id. If it replaces an older word, show how the pack translates that '
            'older word: the source may no longer contain it, so count the translation '
            'side. Add a form (wanted) with the translated word(s) to the draft (forms '
            'count the translations, whatever the source says), run the analysis again '
            'and cite its F id as well. Ordinary words go on one line: "Not a term: …". Do '
            'not decide a product term yourself.' % (ANALYSIS_MD, ', '.join(terms)))


def _open_questions(workspace):
    try:
        with open(os.path.join(workspace, DECISIONS), encoding='utf-8') as f:
            return len(OPEN.findall(f.read()))
    except OSError:
        return 0


def ask_message(n):
    return (
        'I have %d questions about your language. The existing translations do not '
        'settle these points, so you decide. Each comes with what the translations do '
        'today and my recommendation. You can answer all at once, for example "all as '
        'recommended, except 3: …". "I do not know" is fine too; then I follow my '
        'recommendation.\n\n'
        '<every open question, numbered, each as a short block:\n'
        ' - the question in one sentence\n'
        ' - what it changes: one short example of how a text reads under each option\n'
        ' - what the translations do today: the numbers of its evidence blocks, as a '
        'small table, every variant including "none of these"\n'
        ' - your recommendation: one of the options, and why>\n\n'
        'And one more thing: is there anything about the existing translations that '
        'bothers you and that I did not ask about?' % n)


def ask_text(n):
    return ('%d questions in %s are still open ("- [ ]"). Put all of them into the one '
            'message above, as plain text: no multiple-choice tool, the person must see '
            'numbers and examples and be free in their answer. The numbers are the '
            'evidence blocks from %s as they are (or the observed examples). Then wait. '
            'From their reply, write each answer under "Answer:" and tick the box '
            '("- [x]"); where they did not know, write that down and use your '
            'recommendation. A question they did not answer stays open, and next asks '
            'again for those only. What they say to the last question goes under '
            '"## Anything else" in %s, as plain text.'
            % (n, DECISIONS, ANALYSIS_MD, DECISIONS))


QUESTION = re.compile(r'^\s*- \[[ xX]\]', re.M)
EVIDENCE = re.compile(r'Evidence:\s*([^\n]*)')
EVIDENCE_ID = re.compile(r'\b[TFN]\d+\b')


def _known_ids(analysis):
    """The evidence ids of the current analysis: T… terms, F… forms, N… new terms."""
    return {item.get('id'): item for key in ('house_terms', 'forms', 'new_terms')
            for item in (analysis or {}).get(key) or []}


def _questions(workspace):
    """The questions of decisions.md: (block, answered, cited ids, title) each."""
    text = _decisions_text(workspace)
    starts = [m.start() for m in QUESTION.finditer(text)] + [len(text)]
    out = []
    for a, b in zip(starts, starts[1:]):
        block = text[a:b].split('\n## ')[0]
        cited = [i for m in EVIDENCE.finditer(block) for i in EVIDENCE_ID.findall(m.group(1))]
        title = block.strip().split('\n')[0][6:76]
        out.append((block, bool(re.match(r'\s*- \[[xX]\]', block)), cited, title))
    return out


def question_problems(workspace, analysis):
    """Questions without evidence ids or "Observed:", or citing ids that do not exist."""
    known = _known_ids(analysis)
    problems = []
    for block, _, cited, title in _questions(workspace):
        if not cited and 'Observed:' not in block:
            problems.append('%s: no "Evidence:" ids and not marked "Observed:"' % title)
        for i in cited:
            if i not in known:
                problems.append('%s: %s is not in the current %s' % (title, i, ANALYSIS_MD))
    return problems


def _excuses(text):
    """The lines of decisions.md that excuse a rule from blocking: any line with
    "Not binding:", and every line of a section headed "Not binding"."""
    out, section = [], False
    for line in text.split('\n'):
        if line.startswith('#'):
            section = 'not binding' in line.lower()
        elif section or 'not binding:' in line.lower():
            out.append(line.lower())
    return out


def binding_problems(workspace, analysis, profile_path):
    """Decided rules that the profile does not enforce and decisions.md does not excuse.

    A question the person answered and that cites a term (T…) or forms (F…) is a rule
    of theirs. It is enforced when a cited term blocks, or a cited unwanted form blocks,
    by its own "blocking": true or by its kind in the profile's "blocking" list.
    Otherwise decisions.md needs a line "Not binding: <rule name>: <why>". Without this
    check an agent may write a decision into the guidelines only, where nothing checks it.
    """
    if not analysis:
        return []
    try:
        profile = profile_module.load(profile_path)
    except UsageError:
        return []
    excuses = _excuses(_decisions_text(workspace))
    rules = {'term': {t['name']: t for t in profile.terms},
             'form': {f['name']: f for f in profile.forms}}
    known = _known_ids(analysis)

    def rule(i):
        kind = 'term' if i.startswith('T') else 'form' if i.startswith('F') else None
        name = (known.get(i) or {}).get('name')
        if name not in rules.get(kind, {}):
            return None
        excused = any(name.lower() in e or re.search(r'\b%s\b' % i.lower(), e)
                      for e in excuses)
        return kind, name, dict(rules[kind][name], excused=excused)

    problems = []
    for _, answered, cited, title in _questions(workspace):
        cited = [r for r in map(rule, cited) if r]
        if not answered or not cited:
            continue
        if any(r['excused'] for _, _, r in cited):
            continue
        terms = [name for kind, name, _ in cited if kind == 'term']
        unwanted = [(name, r) for kind, name, r in cited
                    if kind == 'form' and not r.get('wanted', True)]
        enforced = any(r.get('blocking') or kind in profile.blocking
                       for kind, _, r in cited
                       if kind == 'term' or not r.get('wanted', True))
        if enforced:
            continue
        if terms:
            problems.append('term "%s" (question "%s…") does not block' % (terms[0], title))
        elif unwanted:
            problems.append('form "%s" (question "%s…") is unwanted but does not block'
                            % (unwanted[0][0], title))
        else:
            problems.append('question "%s…" cites only wanted forms (%s): what the person '
                            'rejected is not in the profile as an unwanted form'
                            % (title, ', '.join(name for _, name, _ in cited)))
    return problems


def binding_text(problems, profile_rel):
    return ('These decisions of the person are not enforced yet:\n%s\n\n'
            'For each: in %s, set "blocking": true on the term, or add what the person '
            'rejected as a form with "wanted": false and "blocking": true. Where a rule '
            'cannot block because its pattern also hits correct translations, or because '
            'the person accepted several variants, add a line to %s instead:\n'
            '    Not binding: <rule name>: <why>\n'
            'Then run the analysis with the profile again (`mahara-lang-tool analyze '
            '... --profile %s`) so that it loads. A form you added gets a new F id there: '
            'add it to the "Evidence:" line of its question. Then run next.'
            % ('\n'.join('- ' + p for p in problems[:12]), profile_rel, DECISIONS,
               profile_rel))


def problems_text(problems):
    return ('Some questions in %s do not say where their numbers come from:\n%s\n\n'
            'Fix them: cite evidence ids from the current %s, or mark the question '
            '"Observed:" with quoted units.\n\n%s'
            % (DECISIONS, '\n'.join('- ' + p for p in problems[:8]), ANALYSIS_MD,
               DECISIONS_FORMAT))


def done_text(name, r):
    lang = r.profile.language
    counts = check_run.collect(r)[2]
    return tell(
        'The round is done: %d texts are translated.\n\n'
        'The result is the file %s/output/suggestions-%s.po. To upload it: in Weblate, '
        'open the component, then Files → Upload translation, choose the file and set '
        'the upload method to "Add as suggestion", not as translation. Then a reviewer '
        'accepts each suggestion one by one, and nothing that exists is overwritten.\n\n'
        'The quality report (%s/output/quality-%s.md) lists %d places for a person to '
        'look at. The most important:\n'
        '<three to five places, each with the text and the reason>\n\n'
        'Nobody has checked: spelling, how the texts look in the running interface, '
        'and a review by a second person.\n\n'
        '<only if a wish in wishes.md differs from what the existing translations do: '
        'which one, and that these suggestions change the shared pack for every Mahara '
        'site in this language, so a reviewer may decline them>\n\n'
        'If you like, we go through the notes together, or I change translations you '
        'do not agree with.'
        % (counts['translated'], name, lang, name, r.lang, counts['hints']),
        'Read the quality report, then write the message. Changes the person asks '
        'for afterwards go into a new file in %s/work/corrections/; next then rebuilds '
        'the result.' % name, after=True)


def run(folder='.', round_name=None):
    workspace = os.path.abspath(folder)
    if _is_round(workspace):
        raise UsageError('run next in the language folder: cd %s'
                         % os.path.dirname(workspace))
    name, what, text = step(workspace, round_name)
    where = ' · round %s' % name if name else ''
    print('STEP: %s%s' % (what, where))
    print('PROGRESS: %s' % progress(what))
    print()
    print(text)
    print()
    print(RULES)
    return 0
