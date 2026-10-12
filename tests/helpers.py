"""Small PO exports built in the test itself — no large fixture files."""
import json
import os
import shutil
import tempfile
import unittest

from mahara_lang_tool import po
from mahara_lang_tool import profile as profile_module

PLURAL_2 = 'nplurals=2; plural=n != 1;'
PLURAL_PL = ('nplurals=3; plural=(n==1 ? 0 : n%10>=2 && n%10<=4 && '
             '(n%100<10 || n%100>=20) ? 1 : 2);')


def unit(ctxt, source, target='', plural=None, targets=None):
    """One export unit. For plurals give `plural` and `targets` (list)."""
    e = {'ctxt': ctxt, 'ref': ctxt, 'id': source}
    if plural:
        e['id_plural'] = plural
        e['target'] = targets or []
    else:
        e['target'] = target
    return e


def write_export(path, units, language='de', plural_forms=PLURAL_2):
    """Write an export like Weblate does: untranslated units have empty msgstr."""
    header = po.build_header({'Project-Id-Version': 'demo',
                              'PO-Revision-Date': '2026-07-24 14:01+0000'},
                             language, plural_forms)
    entries = []
    for u in units:
        e = dict(u)
        if e.get('id_plural') and not e['target']:
            e['target'] = [''] * po.nplurals(plural_forms)
        entries.append(e)
    po.write(path, header, entries)
    return path


def write_profile(path, **data):
    data.setdefault('language', 'de')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    return profile_module.load(path)


def fill(round_dir, targets, folder='batches', name=None):
    """Fill targets {nr: text} into the prefilled batch files (or a new file)."""
    round_dir = os.path.join(round_dir, 'work')
    if name:
        path = os.path.join(round_dir, folder, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {'units': {}}
        with open(os.path.join(round_dir, 'scaffold.json'), encoding='utf-8') as f:
            rows = dict((r['nr'], r) for r in json.load(f))
        for nr, t in targets.items():
            data['units'][str(nr)] = {'source': rows[nr]['source'], 'target': t}
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        return
    folder_path = os.path.join(round_dir, folder)
    for fname in sorted(os.listdir(folder_path)):
        path = os.path.join(folder_path, fname)
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        for key, u in data['units'].items():
            if int(key) in targets:
                t = targets[int(key)]
                if isinstance(t, dict):
                    u.update(t)
                else:
                    u['target'] = t
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)


class TempDir(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='mahara-lang-tool-test-')

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def path(self, *parts):
        return os.path.join(self.dir, *parts)
