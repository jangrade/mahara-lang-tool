import unittest

from mahara_lang_tool import profile as profile_module
from mahara_lang_tool.checks import language, structure, titles
from mahara_lang_tool.checks.structure import ERROR, NOTE


def kinds(findings, severity=None):
    return sorted(f.kind for f in findings if severity is None or f.severity == severity)


class Structure(unittest.TestCase):

    def setUp(self):
        self.p = profile_module.empty()

    def check(self, source, target, **kw):
        return structure.check_unit(source, target, self.p, **kw)

    def test_clean(self):
        self.assertEqual(self.check('Delete %s', '%s löschen'), [])

    def test_positional_order_matters(self):
        self.assertEqual(kinds(self.check('%s of %d', '%d von %s'), ERROR), ['placeholder'])

    def test_missing_placeholder(self):
        self.assertEqual(kinds(self.check('Hello %s', 'Hallo'), ERROR), ['placeholder'])

    def test_indexed_and_named_order_is_free(self):
        self.assertEqual(self.check('%1$s by %2$s', '%2$s: %1$s'), [])
        self.assertEqual(self.check('{$a->x} and {$a->y}', '{$a->y} und {$a->x}'), [])
        self.assertEqual(kinds(self.check('{$a->x}', '{$a->z}'), ERROR), ['placeholder'])

    def test_identical_placeholders_give_a_note(self):
        self.assertEqual(kinds(self.check('%s and %s', '%s und %s')), ['placeholder'])
        self.assertEqual(kinds(self.check('%s and %s', '%s und %s'), NOTE), ['placeholder'])

    def test_html_sequence(self):
        self.assertEqual(kinds(self.check('<b>a</b> <i>b</i>', '<i>b</i> <b>a</b>'), ERROR),
                         ['html'])

    def test_numbers(self):
        self.assertEqual(kinds(self.check('Max 1,000 files in 30 days', 'Max 1.000 Dateien'),
                               ERROR), ['numbers'])
        self.assertEqual(self.check('Max 1,000 files', 'Max. 1.000 Dateien'), [])

    def test_urls_and_code(self):
        found = self.check('See https://mahara.org and $cfg->wwwroot',
                           'Siehe mahara.org und wwwroot')
        self.assertEqual(kinds(found, ERROR), ['literal', 'literal'])

    def test_empty_and_unchanged(self):
        self.assertEqual(kinds(self.check('Save', ' ')), ['empty'])
        long = 'This sentence is long enough to be suspicious.'
        self.assertEqual(kinds(self.check(long, long)), ['unchanged'])

    def test_edges_are_a_note(self):
        self.assertEqual(kinds(self.check('DRY RUN: ', 'TESTLAUF:'), NOTE), ['edges'])

    def test_sentence_loss(self):
        self.assertEqual(kinds(self.check('One. Two. Three.', 'Eins, zwei, drei.')),
                         ['sentences'])

    def test_a_single_plural_form_follows_the_plural_source(self):
        found = self.check('1 file', ['%d ファイル'], source_plural='%d files', nplurals=1)
        self.assertEqual(kinds(found, ERROR), [])
        found = self.check('1 file', ['1 ファイル'], source_plural='%d files', nplurals=1)
        self.assertIn('placeholder', kinds(found, ERROR))

    def test_plural_forms_follow_the_numbers_they_are_shown_for(self):
        def check(plural_forms, targets):
            p = profile_module.Profile({'plural_forms': plural_forms})
            return structure.check_unit('1 file', targets, p, source_plural='%d files')
        russian = ('nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && '
                   '(n%100<10 || n%100>=20) ? 1 : 2);')
        # form 0 is also shown for 21, 31 …: it needs the %d, not the singular's "1"
        self.assertEqual(kinds(check(russian, ['%d файл', '%d файла', '%d файлов']), ERROR), [])
        self.assertIn('placeholder', kinds(check(russian, ['1 файл', '%d файла', '%d файлов']), ERROR))
        arabic = ('nplurals=6; plural=n==0 ? 0 : n==1 ? 1 : n==2 ? 2 : n%100>=3 && '
                  'n%100<=10 ? 3 : n%100>=11 ? 4 : 5;')
        # the forms for 0, 1 and 2 may write the number as a word
        found = check(arabic, ['لا ملفات', 'ملف واحد', 'ملفان', '%d ملفات', '%d ملفا', '%d ملف'])
        self.assertEqual(kinds(found, ERROR), [])

    def test_a_form_for_one_number_keeps_its_other_placeholders(self):
        p = profile_module.Profile({'plural_forms': 'nplurals=2; plural=n != 1;'})
        found = structure.check_unit('%s has 1 file', ['Eine Datei', '%s hat %d Dateien'], p,
                                     source_plural='%s has %d files')
        self.assertIn('placeholder', kinds(found, ERROR))  # the name is lost in form 0
        found = structure.check_unit('%s has 1 file', ['%s hat eine Datei', '%s hat %d Dateien'],
                                     p, source_plural='%s has %d files')
        self.assertEqual(kinds(found, ERROR), [])  # the number written as a word

    def test_sentence_marks_of_other_scripts(self):
        source = 'Save the page. Then share it. Done?'
        self.assertNotIn('sentences', kinds(self.check(
            source, 'ページを保存します。次に共有します。完了？')))
        self.assertNotIn('sentences', kinds(self.check(
            source, 'احفظ الصفحة. ثم شاركها. هل انتهيت؟')))
        self.assertIn('sentences', kinds(self.check(source, 'ページを保存して共有します')))

    def test_plural_count(self):
        found = self.check('%d file', ['%d plik', '%d pliki'], source_plural='%d files',
                           nplurals=3)
        self.assertEqual(kinds(found, ERROR), ['plural'])
        self.assertEqual(self.check('%d file', ['%d plik', '%d pliki', '%d plików'],
                                    source_plural='%d files', nplurals=3), [])
        self.assertEqual(kinds(self.check('%d file', '%d Datei', source_plural='%d files')),
                         ['plural'])
        self.assertEqual(kinds(self.check('file', ['a', 'b'])), ['plural'])

    def test_custom_placeholder_syntax(self):
        p = profile_module.Profile({'placeholders': {'positional': r'\{\d+\}',
                                                     'indexed': r'(?!)', 'named': r'(?!)'}})
        found = structure.check_unit('Hello {0}', 'Hallo', p)
        self.assertEqual(kinds(found, ERROR), ['placeholder'])


class Language(unittest.TestCase):

    def test_craft_respects_allowed_repeats(self):
        p = profile_module.Profile({'repeated_word_ok': ['die']})
        self.assertEqual(language.craft('Die Seiten, die die Gruppe teilt', p), [])
        self.assertEqual(kinds(language.craft('Notizen Notizen', p)), ['craft'])
        self.assertEqual(kinds(language.craft('a (b', p)), ['craft'])
        self.assertEqual(kinds(language.craft('a  b', p)), ['craft'])

    def test_unwanted_forms(self):
        p = profile_module.Profile({'forms': [
            {'name': 'formal', 'pattern': r'\bu\b', 'wanted': False},
            {'name': 'informal', 'pattern': r'\bje\b', 'wanted': True}]})
        self.assertEqual(kinds(language.forms('Weet u het zeker?', p)), ['form'])
        self.assertEqual(language.forms('Weet je het zeker?', p), [])

    def test_house_terms(self):
        house = [{'name': 'collection', 'source': r'\bcollection', 'house': 'Sammlung',
                  'variants': {'Sammlung': 40, 'Kollektion': 2}}]
        self.assertEqual(kinds(language.house_terms('Delete collection', 'Kollektion löschen',
                                                    house)), ['term'])
        self.assertEqual(language.house_terms('Delete collection', 'Sammlung löschen', house), [])

    def test_collisions_across_drafts(self):
        p = profile_module.Profile({'collisions': [{
            'target': 'Freigabe', 'pattern': 'freigab|freigeb',
            'sources': [{'name': 'share', 'source': r'\bshare'},
                        {'name': 'release', 'source': r'\brelease'}]}]})
        pairs = [(1, 'Share page', 'Seite freigeben'), (2, 'Release page', 'Seite freigeben')]
        found = language.collisions(pairs, p)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][1], {'share': [1], 'release': [2]})
        self.assertEqual(language.collisions(pairs[:1], p), [])


class Titles(unittest.TestCase):

    def test_material_and_cosmetic(self):
        p = profile_module.Profile({'title_normalize': [r'/in(nen)?\b']})
        self.assertEqual(titles.check_unit('<h1>Titel</h1><p>..</p>', 'Titel', p), [])
        self.assertEqual(kinds(titles.check_unit('<h1>Nutzer</h1>', 'Nutzer/in', p)),
                         ['title_cosmetic'])
        self.assertEqual(kinds(titles.check_unit('<h1>Name</h1>', 'Titel', p)),
                         ['title_material'])
        self.assertEqual(titles.check_unit('<h1>Name</h1>', None, p), [])

    def test_only_where_the_english_title_is_the_english_label(self):
        p = profile_module.empty()
        # "Section title" as help for a field labelled "Overview": different on purpose.
        self.assertEqual(titles.check_unit('<h1>Blocktitel</h1>', 'Überblick', p,
                                           '<h1>Section title</h1><p>..</p>', 'Overview'), [])
        self.assertEqual(kinds(titles.check_unit('<h1>Titel des Blocks</h1>', 'Blocktitel', p,
                                                 '<h1>Section title</h1>', 'Section title:')),
                         ['title_material'])


if __name__ == '__main__':
    unittest.main()
