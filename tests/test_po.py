from mahara_lang_tool import po

from helpers import TempDir, PLURAL_PL


class ParseWrite(TempDir):

    def test_continuation_lines_and_escapes(self):
        path = self.path('a.po')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('msgid ""\nmsgstr ""\n"Language: de\\n"\n"Plural-Forms: nplurals=2; plural=n != 1;\\n"\n\n'
                    '#: f.php key\n#, php-format\nmsgctxt "f.php key"\nmsgid ""\n"Hello "\n"\\"world\\"\\n"\n'
                    'msgstr "Hallo \\"Welt\\"\\n"\n\n'
                    '#~ msgid "obsolete"\n#~ msgstr "alt"\n')
        units = po.units(path)
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]['id'], 'Hello "world"\n')
        self.assertEqual(units[0]['str'], 'Hallo "Welt"\n')
        self.assertEqual(units[0]['flags'], 'php-format')
        self.assertEqual(po.context(units[0]), 'f.php key')
        fields = po.header_fields(po.header(path))
        self.assertEqual(fields['Language'], 'de')
        self.assertEqual(po.nplurals(fields['Plural-Forms']), 2)

    def test_round_trip_of_tricky_strings(self):
        """The three cases that break in practice, plus tabs and backslashes."""
        tricky = ['DRY RUN: ', '- removed', 'first\\nsecond', 'line\nbreak',
                  'tab\there', 'back\\slash "quoted"', '  both sides  ']
        entries = [{'ctxt': 'f.php k%d' % i, 'id': 'src %d' % i, 'target': t}
                   for i, t in enumerate(tricky)]
        path = self.path('b.po')
        po.write(path, 'Language: de', entries)
        back = po.units(path)
        self.assertEqual([po.translation(e) for e in back], tricky)

    def test_plural_forms_of_any_length(self):
        path = self.path('c.po')
        po.write(path, 'Language: pl\nPlural-Forms: ' + PLURAL_PL,
                 [{'ctxt': 'f.php files', 'id': '%d file', 'id_plural': '%d files',
                   'target': ['%d plik', '%d pliki', '%d plików']}])
        e = po.units(path)[0]
        self.assertTrue(po.is_translated(e))
        self.assertEqual(po.translation(e), ['%d plik', '%d pliki', '%d plików'])
        self.assertEqual(po.nplurals(PLURAL_PL), 3)

    def test_plural_forms_beyond_nine(self):
        path = self.path('d.po')
        forms = ['f%d' % i for i in range(12)]
        po.write(path, 'Language: xx', [{'ctxt': 'k', 'id': 'a', 'id_plural': 'b',
                                         'target': forms}])
        self.assertEqual(po.translation(po.units(path)[0]), forms)

    def test_singular_with_list_is_rejected(self):
        with self.assertRaises(ValueError):
            po.write(self.path('e.po'), 'Language: de',
                     [{'ctxt': 'k', 'id': 'a', 'target': ['x', 'y']}])

    def test_header_keeps_dates_and_drops_generator(self):
        h = po.build_header({'POT-Creation-Date': '2026-04-30', 'X-Generator': 'Weblate'},
                            'nl', 'nplurals=2; plural=n != 1;')
        self.assertIn('POT-Creation-Date: 2026-04-30', h)
        self.assertIn('Language: nl', h)
        self.assertNotIn('X-Generator', h)


class Helpers(TempDir):

    def test_match_edges(self):
        self.assertEqual(po.match_edges('DRY RUN: ', 'TESTLAUF:'), 'TESTLAUF: ')
        self.assertEqual(po.match_edges('\nText', '  Text '), '\nText')

    def test_split_context(self):
        self.assertEqual(po.split_context('lang/en.utf8/view.php title'),
                         ('lang/en.utf8/view.php', 'title'))
        self.assertEqual(po.split_context('plain'), ('', 'plain'))
