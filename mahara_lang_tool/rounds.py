"""The round folder: what is in it and how far it has got.

    input/    the export from the platform (the one .po file you put there)
    work/     round.json, scaffold, brief, batches, corrections, findings
    output/   the suggestion PO and the quality report, written at the end

work/round.json records export, profile and previous version, so the commands need
only the folder (default: the current one). Paths in round.json are stored relative
to work/, so a round can be moved or shared as a whole.

round.json also records a checksum of export and profile. If either file changes
after prepare, the commands say so: the scaffold was made from the old version.
"""
import hashlib
import json
import os

from . import batches as batch_module
from . import po
from . import profile as profile_module
from .errors import UsageError

INPUT, WORK, OUTPUT = 'input', 'work', 'output'
CONFIG = 'round.json'
SCAFFOLD = 'scaffold.json'


def find_export(folder):
    """The one .po file in input/. Creates input/ so the user knows where it goes."""
    where = os.path.join(folder, INPUT)
    os.makedirs(where, exist_ok=True)
    found = sorted(n for n in os.listdir(where) if n.endswith('.po'))
    if len(found) != 1:
        raise UsageError('%s: put exactly one export (.po) there, found %d%s'
                         % (where, len(found), (': ' + ', '.join(found)) if found else ''))
    return os.path.join(where, found[0])


def command(name, folder):
    """How to call a command on this round from the current folder."""
    if os.path.abspath(folder) == os.path.abspath(os.curdir):
        return 'mahara-lang-tool %s' % name
    return 'mahara-lang-tool %s --round %s' % (name, folder)


def relative(path, base):
    """Store a path relative to work/ where possible."""
    if not path:
        return None
    try:
        return os.path.relpath(os.path.abspath(path), os.path.abspath(base))
    except ValueError:  # different drive on Windows
        return os.path.abspath(path)


def checksum(path):
    if not path or not os.path.exists(path):
        return None
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def key(row):
    """The gettext identity of a scaffold row — see po.key()."""
    return (row['ctxt'], row['source'])


class Round:

    def __init__(self, folder):
        self.folder = folder
        self.work = os.path.join(folder, WORK)
        with open(os.path.join(self.work, CONFIG), encoding='utf-8') as f:
            self.config = json.load(f)
        with open(os.path.join(self.work, SCAFFOLD), encoding='utf-8') as f:
            self.scaffold = json.load(f)
        self.by_nr = {r['nr']: r for r in self.scaffold}
        self.profile = profile_module.load(self.resolve(self.config.get('profile')))
        self._batches = None
        self._entries = None
        if not os.path.exists(self.export):
            raise UsageError('%s: export not found: %s (adjust "export" in %s/%s)'
                             % (folder, self.export, WORK, CONFIG))
        self.profile.adopt(self.header_fields())

    def resolve(self, path):
        if not path:
            return None
        if os.path.isabs(path):
            return path
        return os.path.normpath(os.path.join(self.work, path))

    @property
    def export(self):
        return self.resolve(self.config['export'])

    @property
    def lang(self):
        return self.config.get('lang', 'en')

    def _parsed(self):
        if self._entries is None:
            self._entries = po.parse(self.export)
        return self._entries

    def units(self):
        """The export's units, parsed once per run."""
        return [e for e in self._parsed() if e.get('id')]

    def header_fields(self):
        entries = self._parsed()
        return po.header_fields(entries[0] if entries and not entries[0].get('id') else {})

    def batches(self):
        """(translations, notes, messages, problems) — loaded once per run."""
        if self._batches is None:
            self._batches = batch_module.load(self.work, self.by_nr)
        return self._batches

    def drift(self):
        """Which inputs changed since prepare: a list of warnings, usually empty."""
        out = []
        for name, path in (('export', self.export),
                           ('profile', self.resolve(self.config.get('profile')))):
            recorded = self.config.get(name + '_sha256')
            if recorded and checksum(path) != recorded:
                out.append('the %s changed after prepare (%s) — the scaffold was made '
                           'from the old version' % (name, path))
        return out

    def path(self, *parts):
        """A file in work/."""
        return os.path.join(self.work, *parts)

    def output(self, name):
        """A file in output/; the folder is created on first use."""
        os.makedirs(os.path.join(self.folder, OUTPUT), exist_ok=True)
        return os.path.join(self.folder, OUTPUT, name)

    def suggestions_path(self):
        return self.output('suggestions-%s.po' % self.profile.language)

    def report_path(self, lang):
        return self.output('quality-%s.md' % lang)


def load(folder):
    work = os.path.join(folder, WORK)
    missing = [n for n in (CONFIG, SCAFFOLD) if not os.path.exists(os.path.join(work, n))]
    if missing:
        raise UsageError('%s is not a round folder (missing %s in %s/). Run "prepare" first.'
                         % (folder, ', '.join(missing), WORK))
    return Round(folder)


def print_drift(r):
    for w in r.drift():
        print('  WARNING: %s' % w)


def status(folder):
    r = load(folder)
    translations, notes, messages, problems = r.batches()
    total = len(r.scaffold)
    done = len(set(translations) & set(r.by_nr))

    print('%s — %d of %d units (%d %%)'
          % (folder, done, total, round(100.0 * done / total) if total else 0))
    print_drift(r)
    print()
    for name, numbers, filled in batch_module.per_file(r.work):
        missing = numbers - filled
        mark = 'done' if not missing else '%d open' % len(missing)
        print('  %-12s %4d of %4d   %s' % (name, len(filled), len(numbers), mark))

    corrections = batch_module.per_file(r.work, 'corrections')
    if corrections:
        print()
        for name, _, filled in corrections:
            print('  corrections/%-14s %d entries' % (name, len(filled)))
    if notes:
        print()
        print('  %d notes' % len(notes))
    for m in messages:
        print('  %s' % m)
    if problems:
        print()
        print('PROBLEMS')
        for p in problems:
            print('  %s' % p)
    unknown = set(translations) - set(r.by_nr)
    if unknown:
        print()
        print('  %d numbers are not in the scaffold: %s' % (len(unknown), sorted(unknown)[:10]))
    return 1 if problems else 0
