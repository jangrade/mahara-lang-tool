"""`next` walks a language folder from empty to done, one step at a time."""
import contextlib
import io
import json
import os
import re

from mahara_lang_tool import build, guide, prepare, report
from mahara_lang_tool import profile as profile_module
from mahara_lang_tool.analyze import run as analyze_run

from helpers import TempDir, fill, unit, write_export

F = 'lang/en.utf8/view.php '


def quiet(fn, *args, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kw)


class Walk(TempDir):

    def setUp(self):
        super().setUp()
        self.told = []

    def step(self):
        name, what, text = guide.step(self.dir)
        self.assertIn(what, guide.PHASE)
        self.told.append(text)
        return what, text

    def analyze(self, profile_file=None):
        p = profile_module.load(self.path(profile_file)) if profile_file \
            else profile_module.empty()
        analyze_run(self.export, p, self.path('analysis.md'), self.path('analysis.json'))

    def test_from_empty_folder_to_done(self):
        what, text = self.step()
        self.assertEqual(what, 'new round')
        self.assertIn('four parts', text)  # first time: the whole process is explained
        self.assertIn('MESSAGE TO THE PERSON: write this to them now', text)
        self.assertIn('Download translation', text)
        self.told.append(text)

        os.makedirs(self.path('26.04', 'input'))
        self.export = write_export(self.path('26.04', 'input', 'x.po'), [
            unit(F + 'title', 'Title', 'Titel'),
            unit(F + 'deletepage', 'Delete page %s', ''),
        ])
        what, text = self.step()  # first the person's own wishes, before any analysis
        self.assertEqual(what, 'setup')
        self.assertIn('Step 1 of 6', text)
        self.assertIn('are there wishes for your language', text)
        self.assertIn('shared Weblate pack', text)
        with open(self.path('wishes.md'), 'w') as f:
            f.write('- none\n')

        what, text = self.step()
        self.assertIn('Step 1 of 6', text)
        self.assertIn('mahara-lang-tool analyze', text)

        self.analyze()
        what, text = self.step()  # the agent notes what it finds before it sees any list
        self.assertIn('Step 2 of 6', text)
        self.assertIn('no list of topics', text)
        self.assertNotIn('how the user is addressed', text)
        self.assertFalse(os.path.exists(self.path('profile-de.draft.json')))
        with open(self.path('observations.md'), 'w') as f:
            f.write('## Seen\n- `view.php title`: "Titel"\n\n## Known\n')
        self.assertIn('Still empty in observations.md: "## Known"', self.step()[1])
        with open(self.path('observations.md'), 'a') as f:
            f.write('- compounds are written as one word\n')

        what, text = self.step()
        self.assertIn('Step 3 of 6', text)
        self.assertIn('how the user is addressed', text)
        self.assertIn('I wrote profile-de.draft.json', text)
        with open(self.path('profile-de.draft.json')) as f:
            data = json.load(f)
        self.assertEqual(data['language'], 'de')
        self.assertIn('Go on with profile-de.draft.json', self.step()[1])

        del data['_todo']  # the agent is done with step 3
        data['forms'] = [{'name': 'one word', 'pattern': 'Titel', 'wanted': True}]
        with open(self.path('profile-de.draft.json'), 'w') as f:
            json.dump(data, f)
        self.assertIn('Step 4 of 6', self.step()[1])

        self.analyze('profile-de.draft.json')
        what, text = self.step()  # every observation has to say what became of it
        self.assertIn('Step 5 of 6', text)
        self.assertIn('the section "## From the checklist" is missing', text)
        self.assertIn('no outcome: `view.php title`', text)
        with open(self.path('observations.md'), 'w') as f:
            f.write('## Seen\n- `view.php title`: "Titel" → F7\n\n## Known\n'
                    '- compounds are written as one word → no rule: nothing split\n\n'
                    '## From the checklist\n- nothing new\n')
        self.assertIn('F7 not in the current analysis.md', self.step()[1])
        with open(self.path('observations.md')) as f:
            fixed = f.read().replace('F7', 'F1')
        with open(self.path('observations.md'), 'w') as f:
            f.write(fixed)

        what, text = self.step()
        self.assertIn('Step 5 of 6', text)
        self.assertIn('Write decisions.md', text)

        with open(self.path('decisions.md'), 'w') as f:
            f.write('## 1. Anrede\n- [ ] du oder Sie?\n  Answer:\n')
        self.assertIn('no "Evidence:" ids', self.step()[1])

        with open(self.path('decisions.md'), 'w') as f:
            f.write('## 1. Anrede\n- [ ] du oder Sie?\n  Evidence: F9\n  Answer:\n')
        self.assertIn('F9 is not in the current analysis.md', self.step()[1])

        with open(self.path('decisions.md'), 'w') as f:
            f.write('## 1. Anrede\n- [ ] du oder Sie?\n  Observed: "Sie" in mails.\n'
                    '  Answer:\n')

        with open(self.path('decisions.md'), 'w') as f:
            f.write('## 1. Anrede\n- [ ] du oder Sie?\n  Observed: "Sie" in mails.\n'
                    '  Answer:\n')
        text = self.step()[1]  # all questions go to the person in one message
        self.assertIn('1 questions in decisions.md are still open', text)
        self.assertIn('You can answer all at once', text)

        with open(self.path('decisions.md'), 'w') as f:
            f.write('## 1. Anrede\n- [x] du oder Sie?\n  Observed: "Sie" in mails.\n'
                    '  Answer: du\n')
        self.assertIn('Step 6 of 6', self.step()[1])

        os.rename(self.path('profile-de.draft.json'), self.path('profile-de.json'))
        self.analyze('profile-de.json')  # step 6 ends with the analysis of the profile
        self.assertEqual(self.step()[0], 'prepare')

        r = self.path('26.04')
        quiet(prepare.prepare, None, profile_module.load(self.path('profile-de.json')), r)
        what, text = self.step()
        self.assertEqual(what, 'translate')
        self.assertIn(os.path.join('26.04', 'work', 'batches', 'b01.json'), text)
        self.assertIn('now I translate: 1 texts in 1 portions', text)

        fill(r, {1: 'Seite löschen'})  # placeholder lost
        self.assertEqual(self.step()[0], 'fix')

        fill(r, {1: 'Seite %s löschen'})
        self.assertEqual(self.step()[0], 'build')
        quiet(build.build, r)
        self.assertEqual(self.step()[0], 'report')
        quiet(report.write, r)
        what, text = self.step()
        self.assertEqual(what, 'done')
        self.assertIn('26.04/output/suggestions-de.po', text)
        self.assertIn('Add as suggestion', text)

        for text in self.told:  # every step says what to tell the person and what to do
            self.assertRegex(text, 'MESSAGE TO THE PERSON: write this|NO MESSAGE at this step')
            self.assertIn('\nDO:\n', text)

    def test_a_later_round_uses_the_previous_export_as_memory(self):
        for name in ('26.04', '26.10'):
            os.makedirs(self.path(name, 'input'))
            self.export = write_export(self.path(name, 'input', 'x.po'),
                                       [unit(F + 'a', 'Open', '')])
        os.makedirs(self.path('26.04', 'output'))  # 26.04 is done
        for out in ('suggestions-de.po', 'quality-de.md'):
            with open(self.path('26.04', 'output', out), 'w') as f:
                f.write('')
        with open(self.path('profile-de.json'), 'w') as f:
            json.dump({'language': 'de'}, f)
        self.analyze('profile-de.json')
        what, text = self.step()
        self.assertEqual(what, 'prepare')
        self.assertIn('--round 26.10 --previous ' + os.path.join('26.04', 'input', 'x.po'), text)

    def test_open_questions_block_prepare_in_later_rounds(self):
        os.makedirs(self.path('26.10', 'input'))
        self.export = write_export(self.path('26.10', 'input', 'x.po'),
                                   [unit(F + 'a', 'Open', '')])
        with open(self.path('profile-de.json'), 'w') as f:
            json.dump({'language': 'de'}, f)
        self.analyze('profile-de.json')
        with open(self.path('decisions.md'), 'w') as f:
            f.write('- [ ] section: Block oder Abschnitt?\n  Observed: see mails.\n')
        self.assertEqual(self.step()[0], 'decide')

    def test_new_terms_must_be_in_decisions(self):
        os.makedirs(self.path('26.04', 'input'))
        done = [unit(F + 'b%d' % i, 'Move the block %d up' % i, 'Block %d nach oben' % i)
                for i in range(40)]
        todo = [unit(F + 's%d' % i, 'Move the section %d up' % i) for i in range(4)]
        self.export = write_export(self.path('26.04', 'input', 'x.po'), done + todo)
        with open(self.path('profile-de.json'), 'w') as f:
            json.dump({'language': 'de'}, f)
        self.analyze('profile-de.json')
        with open(self.path('analysis.json')) as f:
            self.assertEqual([n['term'] for n in json.load(f)['new_terms']], ['section'])

        what, text = self.step()
        self.assertEqual(what, 'new terms')
        self.assertIn('section', text)
        with open(self.path('decisions.md'), 'w') as f:
            f.write('- [ ] "section": Block (like the pack) or Abschnitt?\n  Evidence: N1\n')
        self.assertEqual(self.step()[0], 'decide')
        with open(self.path('decisions.md'), 'w') as f:
            f.write('- [x] "section": Block or Abschnitt?\n  Evidence: N1\n  Answer: Block\n')
        self.assertEqual(self.step()[0], 'prepare')


class Binding(TempDir):
    """A decision of the person is enforced by the profile, or decisions.md says why not."""

    def setUp(self):
        super().setUp()
        os.makedirs(self.path('26.10', 'input'))
        self.export = write_export(self.path('26.10', 'input', 'x.po'), [
            unit(F + 'a', 'Share page', 'Seite teilen'),
            unit(F + 'b', 'Share it', 'Freigeben'),
            unit(F + 'c', 'Open', '')])
        self.write_profile(blocking=False)
        with open(self.path('decisions.md'), 'w') as f:
            f.write('## 1. Share\n- [x] Teilen or Freigeben?\n  Evidence: T1\n'
                    '  Answer: Teilen\n')

    def write_profile(self, blocking):
        term = {'name': 'share', 'source': r'\bshare', 'variants': ['teilen', 'freigeben']}
        if blocking:
            term['blocking'] = True
        with open(self.path('profile-de.json'), 'w') as f:
            json.dump({'language': 'de', 'terms': [term]}, f)
        analyze_run(self.export, profile_module.load(self.path('profile-de.json')),
                    self.path('analysis.md'), self.path('analysis.json'))

    def test_a_decided_term_must_block_or_be_excused(self):
        what, text = guide.step(self.dir)[1:]
        self.assertEqual(what, 'bind rules')
        self.assertIn('term "share" (question', text)
        with open(self.path('decisions.md'), 'a') as f:
            f.write('\nNot binding: share: the pack uses both on purpose\n')
        self.assertEqual(guide.step(self.dir)[1], 'prepare')

    def test_an_excuse_may_name_the_rule_or_its_id_in_a_section(self):
        with open(self.path('decisions.md'), 'a') as f:
            f.write('\n## Not binding\n\n- the share term (T1) has no wrong variant to block\n')
        self.assertEqual(guide.step(self.dir)[1], 'prepare')

    def test_a_blocking_term_is_enough(self):
        self.write_profile(blocking=True)
        self.assertEqual(guide.step(self.dir)[1], 'prepare')

    def test_a_blocking_kind_is_enough(self):
        with open(self.path('profile-de.json')) as f:
            data = json.load(f)
        data['blocking'] = ['term']
        with open(self.path('profile-de.json'), 'w') as f:
            json.dump(data, f)
        self.assertEqual(guide.step(self.dir)[1], 'prepare')

    def test_a_blocking_term_covers_a_wanted_form_in_the_same_question(self):
        with open(self.path('profile-de.json')) as f:
            data = json.load(f)
        data['terms'][0]['blocking'] = True
        data['forms'] = [{'name': 'teilen', 'pattern': 'teilen', 'wanted': True}]
        with open(self.path('profile-de.json'), 'w') as f:
            json.dump(data, f)
        analyze_run(self.export, profile_module.load(self.path('profile-de.json')),
                    self.path('analysis.md'), self.path('analysis.json'))
        with open(self.path('decisions.md'), 'w') as f:
            f.write('- [x] Teilen or Freigeben?\n  Evidence: T1, F1\n  Answer: Teilen\n')
        self.assertEqual(guide.step(self.dir)[1], 'prepare')

    def test_messages_name_the_persons_language(self):
        text = guide.step(self.dir)[2]
        self.assertNotIn('MESSAGE TO THE PERSON', text)  # bind rules: nothing to say
        os.remove(self.path('decisions.md'))
        os.remove(self.path('profile-de.json'))
        text = guide.step(self.dir)[2]
        self.assertIn('write this to them now, before your next tool call, in English', text)
        self.assertIn('First write the message above as your reply. Then:', text)


class Details(TempDir):

    def test_a_new_term_is_handled_only_by_the_whole_word(self):
        with open(self.path('decisions.md'), 'w') as f:
            f.write('Not a term: user, tags\n')
        analysis = {'new_terms': [{'term': 'use'}, {'term': 'tag'}, {'term': 'user'}]}
        self.assertEqual(guide.unhandled_terms(self.dir, analysis), ['use'])

    def test_a_point_may_run_over_several_lines(self):
        with open(self.path('observations.md'), 'w') as f:
            f.write('## Seen\n- **"je" dominates.** e.g. "Journal deleted" → "Blog\n'
                    '  verwijderd", but "u" leaks in.\n  → F1, question\n\n'
                    '- **kan and kunt are split.** "Je kan" → "You can".\n\n'
                    '## From the checklist\n- nothing new\n')
        found = guide.observation_problems(self.dir, {'forms': [{'id': 'F1'}]})
        self.assertEqual(len(found), 1)  # only the second point: its arrow is a quote
        self.assertIn('kan and kunt', found[0])

    def test_quotes_under_a_point_need_no_outcome(self):
        with open(self.path('observations.md'), 'w') as f:
            f.write('## Seen\n- informal address → F1\n  - `view.php a`: "Du kannst"\n'
                    '## From the checklist\n- nothing new\n')
        self.assertEqual(guide.observation_problems(self.dir, {'forms': [{'id': 'F1'}]}), [])

    def test_a_newer_export_means_a_new_build_not_an_endless_report(self):
        os.makedirs(self.path('r', 'output'))
        os.makedirs(self.path('r', 'input'))
        for name, mtime in (('output/suggestions-de.po', 1000), ('input/x.po', 2000)):
            with open(self.path('r', name), 'w') as f:
                f.write('')
            os.utime(self.path('r', name), (mtime, mtime))
        self.assertFalse(guide._fresh_build(self.path('r'), [self.path('r', 'output',
                                                                       'suggestions-de.po')]))


class Neutral(TempDir):
    """What the agent reads must not point it at one language: it is to find the
    conventions of the language at hand, not those of the language the tool grew up with."""

    SPECIFIC = re.compile(
        r'\b(German|Dutch|French|Polish|English-speaking|du/Sie|je/u|tu/vous|ty/Pan|'
        r'masculine|gender|formal address|address form)\b', re.I)

    def test_agent_texts_name_no_language_and_no_topic_of_one(self):
        with open(profile_module.TEMPLATE, encoding='utf-8') as f:
            template = f.read()
        texts = [guide.RULES, guide.OVERVIEW, guide.EXPORT_HOW, guide.OBSERVE,
                 guide.CHECKLIST, guide.OUTCOMES, guide.WRITE_DECISIONS, guide.NOTICED,
                 guide.ask_message(3), guide.ask_text(3), template]
        for text in texts:
            self.assertIsNone(self.SPECIFIC.search(text), self.SPECIFIC.search(text))

    def test_progress_marks_one_part(self):
        for what in guide.PHASE:
            self.assertLessEqual(guide.progress(what).count('← now'), 1)
        self.assertIn('2 rules for the language ← now', guide.progress('decide'))
        self.assertEqual(guide.progress('done').count('✓'), 4)

    def test_a_later_round_gets_the_short_welcome(self):
        with open(self.path('profile-de.json'), 'w') as f:
            json.dump({'language': 'de'}, f)
        text = guide.step(self.dir)[2]
        self.assertNotIn('four parts', text)
        self.assertIn('Download translation', text)
