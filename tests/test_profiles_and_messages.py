import contextlib
import io
import glob
import os
import unittest

from mahara_lang_tool import cli
from mahara_lang_tool import profile as profile_module
from mahara_lang_tool.errors import UsageError
from mahara_lang_tool.messages import KINDS, MESSAGES

from helpers import TempDir, write_profile


class ShippedProfiles(unittest.TestCase):

    def test_every_shipped_profile_loads(self):
        paths = glob.glob(os.path.join(profile_module.SHIPPED, '*.json'))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(profile=os.path.basename(path)):
                profile_module.load(path)

    def test_template_examples_do_not_count(self):
        p = profile_module.load(profile_module.TEMPLATE)
        self.assertEqual(p.terms, [])
        self.assertEqual(p.glossary, [])


class Validation(TempDir):

    def test_typo_in_key_is_reported(self):
        with self.assertRaises(UsageError) as e:
            write_profile(self.path('p.json'), glosary=[])
        self.assertIn('glosary', str(e.exception))

    def test_bad_regex_is_reported(self):
        with self.assertRaises(UsageError) as e:
            write_profile(self.path('p.json'), forms=[{'name': 'x', 'pattern': '(unclosed'}])
        self.assertIn('unusable regular expression', str(e.exception))

    def test_missing_field_is_reported(self):
        with self.assertRaises(UsageError) as e:
            write_profile(self.path('p.json'), glossary=[{'source': 'page'}])
        self.assertIn('"target" is missing', str(e.exception))

    def test_unknown_blocking_kind_is_reported(self):
        with self.assertRaises(UsageError) as e:
            write_profile(self.path('p.json'), blocking=['placeholder'])
        self.assertIn('blocking', str(e.exception))

    def test_broken_profile_is_a_usage_error_on_the_command_line(self):
        with open(self.path('p.json'), 'w') as f:
            f.write('{"glosary": []}')
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code = cli.main(['prepare', '--export', 'x.po', '--profile', self.path('p.json'),
                             '--round', self.path('round')])
        self.assertEqual(code, 2)
        self.assertIn('glosary', err.getvalue())


class Catalogs(unittest.TestCase):


    def test_every_language_has_every_key(self):
        for lang, catalog in MESSAGES.items():
            with self.subTest(lang=lang):
                self.assertEqual(set(catalog), set(MESSAGES['en']))
                self.assertEqual(set(KINDS[lang]), set(KINDS['en']))

    def test_placeholders_match_english(self):
        import string
        fmt = string.Formatter()
        for lang, catalog in MESSAGES.items():
            for key, text in catalog.items():
                want = set(f for _, f, _, _ in fmt.parse(MESSAGES['en'][key]) if f)
                got = set(f for _, f, _, _ in fmt.parse(text) if f)
                self.assertEqual(got, want, '%s/%s' % (lang, key))
