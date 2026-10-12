"""End to end: prepare -> fill batches -> check -> build -> report."""
import contextlib
import io
import json
import os
import shutil

from mahara_lang_tool import build, po, prepare, report, rounds
from mahara_lang_tool import profile as profile_module
from mahara_lang_tool.analyze import run as analyze_run
from mahara_lang_tool.checks import run as check_run
from mahara_lang_tool.errors import Error, UsageError

from helpers import TempDir, PLURAL_2, PLURAL_PL, fill, unit, write_export, write_profile

F = 'lang/en.utf8/view.php '


def quiet(fn, *args, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kw)


class Pipeline(TempDir):

    def setUp(self):
        TempDir.setUp(self)
        self.export = write_export(self.path('export.po'), [
            unit(F + 'title', 'Title', 'Titel'),
            unit(F + 'deletepage', 'Delete page %s', ''),
            unit(F + 'dryrun', 'DRY RUN: ', ''),
            unit(F + 'title_help', '<h1>Title</h1><p>The name of the page.</p>', ''),
            unit(F + 'files', '%d file', plural='%d files'),
            unit(F + 'save', 'Save', 'Speichern'),
        ])
        self.profile = write_profile(self.path('de.json'), language='de',
                                     glossary=[{'source': 'page', 'target': 'Seite'}],
                                     guidelines=['Anrede du.'])
        self.round = self.path('round')
        quiet(prepare.prepare, self.export, self.profile, self.round, lang='de')
        # From here on the round works with its own copy of the export.
        self.export = self.path('round', 'input', 'export.po')

    def load(self):
        return rounds.load(self.round)

    def good(self):
        return {1: 'Seite %s löschen', 2: 'TESTLAUF:',
                3: '<h1>Titel</h1><p>Der Name der Seite.</p>',
                4: ['%d Datei', '%d Dateien']}

    def test_prepare_numbers_untranslated_units_in_po_order(self):
        r = self.load()
        self.assertEqual([row['key'] for row in r.scaffold],
                         ['deletepage', 'dryrun', 'title_help', 'files'])
        self.assertEqual(r.by_nr[3]['label'], 'Titel')
        self.assertEqual(r.by_nr[1]['glossary'], [{'source': 'page', 'target': 'Seite'}])
        with open(self.path('round', 'work', 'brief.md'), encoding='utf-8') as f:
            brief = f.read()
        self.assertIn('Anrede du.', brief)
        self.assertIn('## So arbeitest du', brief)
        self.assertIn('check --round %s' % self.round, brief)
        # Paths in round.json are relative, so the round can move as a whole.
        self.assertEqual(r.config['export'], os.path.join('..', 'input', 'export.po'))
        self.assertTrue(os.path.isdir(self.path('round', 'output')))

    def test_prepare_does_not_overwrite_started_batches(self):
        fill(self.round, {1: 'Seite %s löschen'})
        quiet(prepare.prepare, self.export, self.profile, self.round)
        self.assertEqual(self.load().batches()[0], {1: 'Seite %s löschen'})

    def test_full_round(self):
        fill(self.round, self.good())
        self.assertEqual(quiet(check_run.check, self.round), 0)
        self.assertEqual(quiet(build.build, self.round), 0)

        out = dict((po.context(e), e) for e in po.units(self.load().suggestions_path()))
        self.assertEqual(len(out), 4)
        self.assertEqual(out[F + 'dryrun']['str'], 'TESTLAUF: ')  # edge restored
        self.assertEqual(po.translation(out[F + 'files']), ['%d Datei', '%d Dateien'])
        self.assertNotIn(F + 'title', out)  # already translated in the export

        self.assertEqual(quiet(report.write, self.round), 0)
        self.assertEqual(quiet(report.write, self.round, lang='en'), 0)
        with open(self.path('round', 'output', 'quality-en.md'), encoding='utf-8') as f:
            body = f.read()
        self.assertIn('0 mismatches', body)
        self.assertIn('## What is not checked', body)

    def test_disclosure_is_on_by_default(self):
        fill(self.round, self.good())
        quiet(build.build, self.round)
        with open(self.load().suggestions_path(), encoding='utf-8') as f:
            self.assertTrue(f.read().startswith('# '))
        quiet(build.build, self.round, disclosure=False)
        with open(self.load().suggestions_path(), encoding='utf-8') as f:
            self.assertTrue(f.read().startswith('msgid'))

    def test_errors_fail_the_check(self):
        good = self.good()
        good[1] = 'Seite löschen'  # placeholder lost
        fill(self.round, good)
        self.assertEqual(quiet(check_run.check, self.round), 1)
        with open(self.path('round', 'work', 'findings.json'), encoding='utf-8') as f:
            kinds = [x['kind'] for x in json.load(f)['findings'] if x['severity'] == 'error']
        self.assertEqual(kinds, ['placeholder'])

    def test_shifted_numbers_are_caught(self):
        fill(self.round, {1: {'source': 'DRY RUN: ', 'target': 'TESTLAUF:'}})
        translations, _, _, problems = self.load().batches()
        self.assertEqual(translations, {})
        self.assertIn('numbers shifted', problems[0])
        with self.assertRaises(Error):
            quiet(build.build, self.round)

    def test_duplicates_in_batches_are_reported_corrections_are_not(self):
        fill(self.round, self.good())
        fill(self.round, {1: 'Seite %s entfernen'}, name='extra.json')
        self.assertIn('filled twice', self.load().batches()[3][0])
        os.remove(self.path('round', 'work', 'batches', 'extra.json'))

        fill(self.round, {1: 'Seite %s entfernen'}, folder='corrections', name='fix.json')
        translations, _, messages, problems = self.load().batches()
        self.assertEqual(problems, [])
        self.assertEqual(translations[1], 'Seite %s entfernen')
        self.assertIn('overwrites 1', messages[0])

    def test_broken_json_is_a_problem_not_a_crash(self):
        with open(self.path('round', 'work', 'batches', 'b01.json'), 'w') as f:
            f.write('{"units": {"1": ')
        self.assertIn('not valid JSON', self.load().batches()[3][0])
        self.assertEqual(quiet(check_run.check, self.round), 1)

    def test_overwrite_guard(self):
        fill(self.round, self.good())
        # Someone translated a unit on the platform in the meantime.
        write_export(self.export, [
            unit(F + 'title', 'Title', 'Titel'),
            unit(F + 'deletepage', 'Delete page %s', 'Seite %s entfernen'),
            unit(F + 'dryrun', 'DRY RUN: ', ''),
            unit(F + 'title_help', '<h1>Title</h1><p>The name of the page.</p>', ''),
            unit(F + 'files', '%d file', plural='%d files'),
        ])
        with self.assertRaises(Error) as e:
            quiet(build.build, self.round)
        self.assertIn('already translated', str(e.exception))

    def test_round_can_be_moved(self):
        fill(self.round, self.good())
        moved = self.path('elsewhere')
        os.makedirs(moved)
        shutil.move(self.round, os.path.join(moved, 'round'))
        shutil.move(self.path('de.json'), os.path.join(moved, 'de.json'))
        self.assertEqual(quiet(build.build, os.path.join(moved, 'round')), 0)

    def test_check_errors_block_the_build(self):
        good = self.good()
        good[1] = 'Seite löschen'  # placeholder lost
        fill(self.round, good)
        with self.assertRaises(Error) as e:
            quiet(build.build, self.round)
        self.assertIn('--force', str(e.exception))
        self.assertFalse(os.path.exists(self.load().suggestions_path()))
        self.assertEqual(quiet(build.build, self.round, force=True), 0)

    def test_plural_shape_is_enforced_even_with_force(self):
        good = self.good()
        good[4] = '%d Datei'  # a string for a plural unit
        fill(self.round, good)
        with self.assertRaises(Error) as e:
            quiet(build.build, self.round, force=True)
        self.assertIn('plural forms', str(e.exception))

    def test_source_changed_in_the_export_since_prepare(self):
        fill(self.round, self.good())
        # The platform reworded a source; the export at the same path is re-downloaded.
        write_export(self.export, [
            unit(F + 'title', 'Title', 'Titel'),
            unit(F + 'deletepage', 'Remove page %s', ''),
            unit(F + 'dryrun', 'DRY RUN: ', ''),
            unit(F + 'title_help', '<h1>Title</h1><p>The name of the page.</p>', ''),
            unit(F + 'files', '%d file', plural='%d files'),
        ])
        self.assertIn('export changed', self.load().drift()[0])
        with self.assertRaises(Error) as e:
            quiet(build.build, self.round)
        self.assertIn('source texts changed', str(e.exception))

    def test_blocking_notes_are_errors_unless_explained(self):
        write_profile(self.path('de.json'), language='de', blocking=['form'],
                      forms=[{'name': 'Siezen', 'pattern': r'\bSie\b', 'wanted': False}])
        good = self.good()
        good[1] = 'Löschen Sie Seite %s'
        fill(self.round, good)
        self.assertEqual(quiet(check_run.check, self.round), 1)
        with self.assertRaises(Error):
            quiet(build.build, self.round)
        fill(self.round, {1: {'target': 'Löschen Sie Seite %s', 'note': 'Zitat aus dem UI.'}})
        self.assertEqual(quiet(check_run.check, self.round), 0)
        self.assertEqual(quiet(build.build, self.round), 0)

    def test_a_single_rule_can_block(self):
        write_profile(self.path('de.json'), language='de', forms=[
            {'name': 'formal', 'pattern': r'\bSie\b', 'wanted': False, 'blocking': True},
            {'name': 'shout', 'pattern': '!', 'wanted': False}])
        profile = profile_module.load(self.path('de.json'))
        self.assertEqual(profile.blocks(), [('form', 'formal')])
        r = self.path('r')
        quiet(prepare.prepare, self.export, profile, r)
        with open(os.path.join(r, 'work', 'brief.md')) as f:
            self.assertIn('"formal"', f.read())
        fill(r, {1: 'Seite %s löschen!'})  # only the rule that does not block
        self.assertEqual(check_run.collect(rounds.load(r))[2]['errors'], 0)
        fill(r, {1: 'Löschen Sie Seite %s'})
        self.assertEqual(check_run.collect(rounds.load(r))[2]['errors'], 1)
        fill(r, {1: {'target': 'Löschen Sie Seite %s', 'note': 'quoted from a letter'}})
        self.assertEqual(check_run.collect(rounds.load(r))[2]['errors'], 0)

    def test_find_counts_like_the_analysis(self):
        from mahara_lang_tool import find
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            find.run(self.export, target='Titel')
            find.run(self.export, source='delete', state='untranslated')
        text = out.getvalue()
        self.assertIn('1 units match (1 translated, 0 untranslated), 1 occurrences', text)
        self.assertIn(F + 'title', text)
        self.assertIn('1 units match (0 translated, 1 untranslated)', text)
        self.assertIn('target: (not translated)', text)
        with self.assertRaises(UsageError):
            find.run(self.export, target='(')

    def test_find_counts_targets_in_singular_units_only_like_the_analysis(self):
        from mahara_lang_tool import find
        export = write_export(self.path('p.po'), [
            unit(F + 'a', 'File', 'Datei'),
            unit(F + 'b', '%d file', plural='%d files', targets=['%d Datei', '%d Dateien'])])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            find.run(export, target='Datei')
        self.assertIn('1 units match', out.getvalue())

    def test_find_without_export_takes_the_newest_round(self):
        from mahara_lang_tool import cli
        for name, mtime in (('26.04', 1000), ('26.10', 2000)):
            os.makedirs(self.path('lang', name, 'input'))
            path = write_export(self.path('lang', name, 'input', 'x.po'),
                                [unit(F + 't', 'Title', 'Titel')])
            os.utime(path, (mtime, mtime))
        cwd = os.getcwd()
        os.chdir(self.path('lang'))
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(cli.main(['find', '--target', 'Titel']), 0)
        finally:
            os.chdir(cwd)
        self.assertIn(os.path.join('26.10', 'input', 'x.po'), out.getvalue())

    def test_check_says_what_to_do_next(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            check_run.check(self.round)
        self.assertIn('work/batches/b01.json (4 units open)', out.getvalue())
        good = self.good()
        good[1] = 'Seite löschen'
        fill(self.round, good)
        with contextlib.redirect_stdout(out):
            check_run.check(self.round)
        self.assertIn('NEXT: fix the 1 errors above', out.getvalue())

    def test_report_lists_the_places(self):
        good = self.good()
        good[3] = '<h1>Name</h1><p>Der Name der Seite.</p>'  # label is "Titel"
        fill(self.round, good)
        quiet(build.build, self.round)
        quiet(report.write, self.round)
        with open(self.path('round', 'output', 'quality-de.md'), encoding='utf-8') as f:
            body = f.read()
        self.assertIn('## Befunde im Einzelnen', body)
        self.assertIn('**#3** `view.php` · `title_help`', body)
        self.assertIn('Übersetzung: <h1>Name</h1>', body)

    def test_format_flags_travel_fuzzy_does_not(self):
        write_export(self.export, [
            dict(unit(F + 'deletepage', 'Delete page %s', ''), flags='fuzzy, php-format'),
            unit(F + 'dryrun', 'DRY RUN: ', ''),
            unit(F + 'title_help', '<h1>Title</h1><p>The name of the page.</p>', ''),
            unit(F + 'files', '%d file', plural='%d files'),
        ])
        fill(self.round, self.good())
        quiet(build.build, self.round)
        out = {po.context(e): e for e in po.units(self.load().suggestions_path())}
        self.assertEqual(out[F + 'deletepage']['flags'], 'php-format')
        self.assertNotIn('flags', out[F + 'dryrun'])


class InputFolder(TempDir):
    """The export goes into input/; prepare finds it there."""

    def test_prepare_takes_the_export_from_input(self):
        r = self.path('round')
        os.makedirs(os.path.join(r, 'input'))
        write_export(os.path.join(r, 'input', 'mahara.po'), [unit('f.php a', 'Open')])
        quiet(prepare.prepare, None, write_profile(self.path('de.json')), r)
        self.assertEqual(os.path.basename(rounds.load(r).export), 'mahara.po')

    def test_empty_input_is_explained(self):
        r = self.path('round')
        with self.assertRaises(UsageError) as e:
            quiet(prepare.prepare, None, write_profile(self.path('de.json')), r)
        self.assertIn('input', str(e.exception))
        self.assertTrue(os.path.isdir(os.path.join(r, 'input')))

    def test_a_second_export_is_refused(self):
        r = self.path('round')
        p = write_profile(self.path('de.json'))
        quiet(prepare.prepare, write_export(self.path('a.po'), [unit('f.php a', 'Open')]), p, r)
        with self.assertRaises(UsageError):
            quiet(prepare.prepare, write_export(self.path('b.po'), [unit('f.php b', 'Close')]),
                  p, r)


class WithoutContext(TempDir):
    """A PO without msgctxt: units are told apart by msgid, not by the #: line."""

    def test_same_reference_different_msgid(self):
        export = write_export(self.path('e.po'), [
            {'ref': 'main.c:12', 'id': 'Open', 'target': ''},
            {'ref': 'main.c:12', 'id': 'Close', 'target': ''},
        ])
        p = write_profile(self.path('de.json'))
        r = self.path('round')
        quiet(prepare.prepare, export, p, r)
        fill(r, {1: 'Öffnen', 2: 'Schließen'})
        self.assertEqual(quiet(build.build, r), 0)
        out = {e['id']: e['str'] for e in po.units(rounds.load(r).suggestions_path())}
        self.assertEqual(out, {'Open': 'Öffnen', 'Close': 'Schließen'})

    def test_duplicate_units_are_refused(self):
        export = write_export(self.path('e.po'), [
            {'ref': 'a.c:1', 'id': 'Open', 'target': ''},
            {'ref': 'b.c:2', 'id': 'Open', 'target': ''},
        ])
        p = write_profile(self.path('de.json'))
        with self.assertRaises(UsageError) as e:
            quiet(prepare.prepare, export, p, self.path('round'))
        self.assertIn('duplicate', str(e.exception))


class Polish(TempDir):
    """Three plural forms: nothing may assume two."""

    def test_three_forms(self):
        export = write_export(self.path('pl.po'), [
            unit('f.php files', '%d file', plural='%d files'),
            unit('f.php save', 'Save', 'Zapisz'),
        ], language='pl', plural_forms=PLURAL_PL)
        p = write_profile(self.path('pl.json'), language='pl', plural_forms=PLURAL_PL)
        r = self.path('round')
        quiet(prepare.prepare, export, p, r)
        with open(self.path('round', 'work', 'batches', 'b01.json'), encoding='utf-8') as f:
            self.assertEqual(json.load(f)['units']['1']['target'], ['', '', ''])

        fill(r, {1: ['%d plik', '%d pliki']})
        self.assertEqual(quiet(check_run.check, r), 1)
        fill(r, {1: ['%d plik', '%d pliki', '%d plików']})
        self.assertEqual(quiet(check_run.check, r), 0)
        self.assertEqual(quiet(build.build, r), 0)
        e = po.units(rounds.load(r).suggestions_path())[0]
        self.assertEqual(len(po.translation(e)), 3)

    def export(self):
        return write_export(self.path('pl.po'), [
            unit('f.php files', '%d file', plural='%d files'),
        ], language='pl', plural_forms=PLURAL_PL)

    def test_empty_profile_takes_language_and_plurals_from_the_export(self):
        export = self.export()
        with open(self.path('empty.json'), 'w') as f:
            f.write('{}')
        r = self.path('round')
        quiet(prepare.prepare, export, profile_module.load(self.path('empty.json')), r)
        with open(self.path('round', 'work', 'batches', 'b01.json'), encoding='utf-8') as f:
            self.assertEqual(json.load(f)['units']['1']['target'], ['', '', ''])

        fill(r, {1: ['%d plik', '%d pliki', '%d plików']})
        self.assertEqual(quiet(build.build, r), 0)
        path = rounds.load(r).suggestions_path()
        self.assertTrue(path.endswith('suggestions-pl.po'))
        fields = po.header_fields(po.header(path))
        self.assertEqual(fields['Language'], 'pl')
        self.assertEqual(fields['Plural-Forms'], PLURAL_PL)

    def test_profile_contradicting_the_export_is_refused(self):
        export = self.export()
        p = write_profile(self.path('two.json'), language='pl', plural_forms=PLURAL_2)
        with self.assertRaises(UsageError):
            quiet(prepare.prepare, export, p, self.path('round'))
        with self.assertRaises(UsageError):
            quiet(prepare.prepare, export, write_profile(self.path('de.json')),
                  self.path('round2'))


class Analyze(TempDir):

    def test_counts(self):
        export = write_export(self.path('e.po'), [
            unit('a.php x', 'People', 'Personen'),
            unit('b.php x', 'People', 'Nutzer/innen'),
            unit('a.php y', 'Entry', 'Eintrag'),
            unit('b.php y', 'Item', 'Eintrag'),
            unit('c.php z', 'Hello %s', 'Hallo'),
            unit('c.php w', 'Open', ''),
        ])
        p = profile_module.Profile({'forms': [{'name': 'slash', 'pattern': r'\w+/innen'}]})
        d, body = analyze_run(export, p)
        self.assertEqual(d['counts']['untranslated'], 1)
        self.assertEqual([u['source'] for u in d['inconsistent']], ['People'])
        self.assertEqual([c['target'] for c in d['collisions']], ['Eintrag'])
        self.assertEqual(len(d['defects']['placeholder']), 1)
        self.assertEqual(d['forms'][0]['units'], 1)
        self.assertIn('## 2. Collisions', body)

    def test_evidence_ids_and_unlisted_variants(self):
        export = write_export(self.path('e.po'), [
            unit('a.php x', 'People', 'Personen'),
            unit('b.php x', 'People', 'Nutzer/innen'),
        ])
        p = profile_module.Profile({'terms': [
            {'name': 'people', 'source': 'People', 'variants': ['Personen']}]})
        d, body = analyze_run(export, p)
        term = d['house_terms'][0]
        self.assertEqual(term['id'], 'T1')
        # Nobody listed "Nutzer/innen" as a variant; it still shows up.
        self.assertEqual(term['other'], 1)
        self.assertIn('### T1 · people', body)
        self.assertIn('Nutzer/innen', body)


class Sample(TempDir):

    def test_sample_keeps_the_translations_and_a_few_open_units(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('sample_export', os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'scripts', 'sample_export.py'))
        sample_export = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sample_export)
        units = [unit(F + 'done%d' % i, 'Done %d' % i, 'Fertig %d' % i) for i in range(5)]
        units += [unit(F + 'open%d' % i, 'Open %d' % i) for i in range(20)]
        units.append(unit(F + 'files', '%d file', plural='%d files'))
        export = write_export(self.path('x.po'), units)
        quiet(sample_export.main, [export, '-n', '4', '-o', self.path('x-sample4.po')])
        kept = po.units(self.path('x-sample4.po'))
        self.assertEqual(sum(1 for e in kept if po.is_translated(e)), 5)
        todo = [po.context(e) for e in kept if not po.is_translated(e)]
        self.assertEqual(len(todo), 4)
        self.assertIn(F + 'files', todo)  # plural units always stay
        self.assertIn(F + 'open0', todo)  # spread from the start of the export
