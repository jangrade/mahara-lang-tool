"""The language profile: the wishes and guidelines for one language of one project.

Everything language-specific lives in a JSON file (see mahara_lang_tool/profiles/). The code below
knows no language. JSON rather than TOML because tomllib needs Python 3.11 and the
tool supports 3.9. JSON has no comments; keys starting with "_" are dropped on load
and serve as comments instead. List entries with "_example": true are dropped too,
so the template can show a filled-in sample without it counting.
"""
import gettext
import json
import os
import re

from . import po
from .errors import UsageError

# Shipped with the package, so an installed tool can point an agent to them.
SHIPPED = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'profiles')
TEMPLATE = os.path.join(SHIPPED, 'TEMPLATE.json')

# Defaults fit Mahara/PHP. Another project overrides them in its profile.
PLACEHOLDER_DEFAULTS = {
    'positional': r'%[sd]',
    'indexed': r'%\d+\$[sd]',
    'named': r'\{\$a(?:->\w+)?\}',
}

# How help texts relate to their field. Mahara: 'file.php key_help' belongs to the
# field 'file.php key'.
HELP_DEFAULTS = {'suffix': '_help'}


class Profile:
    """A loaded profile. Missing sections are empty, not errors: a new language
    starts with an almost empty profile and gets sharper as the analysis of the
    existing translations yields something.
    """

    def __init__(self, data, path=None):
        self.path = path
        self.data = data
        self.language = data.get('language', 'xx')
        self.language_name = data.get('language_name', self.language)
        self.project = data.get('project', '')
        self.plural_forms = data.get('plural_forms', 'nplurals=2; plural=n != 1;')
        self.guidelines = data.get('guidelines', [])
        self.glossary = data.get('glossary', [])
        self.terms = data.get('terms', [])
        self.collisions = data.get('collisions', [])
        self.forms = data.get('forms', [])
        self.repeated_word_ok = set(w.lower() for w in data.get('repeated_word_ok', []))
        self.title_normalize = data.get('title_normalize', [])
        self.batch_size = data.get('batch_size', 80)
        self.agent_notes = data.get('agent_notes', [])
        # Kinds of notes that block the build unless the unit explains itself in a
        # "note" — so an agent has to fix them or justify them, not skip them.
        self.blocking = list(data.get('blocking', []))
        # Files whose strings are not prose — the date formats in Mahara's
        # langconfig.php send every placeholder check astray.
        self.skip = [re.compile(m) for m in data.get('skip_files', [])]

        p = dict(PLACEHOLDER_DEFAULTS)
        p.update(data.get('placeholders', {}))
        self.positional = re.compile(p['positional'])
        self.indexed = re.compile(p['indexed'])
        self.named = re.compile(p['named'])
        # For display and number checks: all three kinds in one expression.
        self.placeholder = re.compile('|'.join(
            '(?:%s)' % p[k] for k in ('indexed', 'named', 'positional')))

        h = dict(HELP_DEFAULTS)
        h.update(data.get('help', {}))
        self.help_suffix = h['suffix']

    def adopt(self, header):
        """Take language and plural forms from the export header where the profile
        leaves them open; refuse where the two disagree.

        header: the export's header fields (po.header_fields). Without this an
        almost empty profile would build a file for language "xx" with two plural
        forms, whatever the export says.
        """
        where = self.path or 'profile'
        language = header.get('Language', '').strip()
        forms = header.get('Plural-Forms', '').strip()
        if language:
            if 'language' not in self.data:
                self.language = language
                if 'language_name' not in self.data:
                    self.language_name = language
            elif _base(language) != _base(self.language):
                raise UsageError('%s is for language "%s", the export for "%s"'
                                 % (where, self.language, language))
        if forms:
            if 'plural_forms' not in self.data:
                self.plural_forms = forms
            elif po.nplurals(forms) != self.nplurals:
                raise UsageError('%s has %d plural forms, the export %d (%s) — copy '
                                 'Plural-Forms from the export header into the profile'
                                 % (where, self.nplurals, po.nplurals(forms), forms))
        return self

    def blocks(self):
        """What stops the build unless a unit explains itself: (kind, rule name or None)
        for every blocking kind and every term or form with "blocking": true."""
        out = [(kind, None) for kind in self.blocking]
        out += [('term', t['name']) for t in self.terms if t.get('blocking')]
        out += [('form', f['name']) for f in self.forms
                if f.get('blocking') and not f.get('wanted', True)]
        return out

    @property
    def nplurals(self):
        return po.nplurals(self.plural_forms)

    def plural_numbers(self):
        """For each plural form, the numbers 0…999 it is used for, read off the
        Plural-Forms expression; None if the expression cannot be evaluated."""
        try:
            rule = gettext.c2py(self.plural_forms.split('plural=', 1)[1].strip().rstrip(';'))
        except (IndexError, ValueError):
            return None
        out = [set() for _ in range(self.nplurals)]
        for n in range(1000):
            form = rule(n)
            if form < len(out):
                out[form].add(n)
        return out

    def skipped(self, ctxt):
        return any(m.search(ctxt) for m in self.skip)

    def glossary_hits(self, text):
        """Glossary entries whose source term occurs in the text."""
        hits = []
        for g in self.glossary:
            pattern = g.get('pattern') or (r'\b%s\b' % re.escape(g['source']))
            if re.search(pattern, text, re.I):
                hits.append(g)
        return hits

    def __repr__(self):
        return '<Profile %s (%s)>' % (self.language, self.path or 'no file')


def _base(language):
    """'pt_BR' -> 'pt': a profile for "de" fits an export for "de_DE"."""
    return re.split(r'[_@.-]', language.lower())[0]


def _strip_comments(obj):
    if isinstance(obj, dict):
        return {k: _strip_comments(v) for k, v in obj.items() if not k.startswith('_')}
    if isinstance(obj, list):
        return [_strip_comments(v) for v in obj
                if not (isinstance(v, dict) and v.get('_example'))]
    return obj


def load(path):
    if path is None:
        return empty()
    if not os.path.exists(path):
        raise UsageError('profile not found: %s' % path)
    with open(path, encoding='utf-8') as f:
        try:
            data = _strip_comments(json.load(f))
        except ValueError as e:
            raise UsageError('profile %s is not valid JSON: %s' % (path, e))
    p = Profile(data, os.path.abspath(path))
    try:
        validate(p)
    except ValueError as e:
        raise UsageError(str(e))
    return p


def empty():
    """A profile without language knowledge — enough for analysis and structure checks.
    Language and plural forms come from the export (Profile.adopt)."""
    return Profile({})


REQUIRED = (
    ('terms', ('name', 'source', 'variants')),
    ('collisions', ('target', 'pattern', 'sources')),
    ('forms', ('name', 'pattern')),
    ('glossary', ('source', 'target')),
)


def validate(p):
    """Complain early instead of failing with a regex error in the middle of a run."""
    errors = []
    for name, fields in REQUIRED:
        for i, entry in enumerate(getattr(p, name)):
            for f in fields:
                if f not in entry:
                    errors.append('%s[%d]: field "%s" is missing' % (name, i, f))
    for kind in p.blocking:
        if kind not in BLOCKABLE:
            errors.append('blocking: "%s" is not one of %s' % (kind, ', '.join(BLOCKABLE)))
    unknown = set(p.data) - KNOWN_KEYS
    if unknown:
        errors.append('unknown keys (typo?): %s' % ', '.join(sorted(unknown)))
    patterns = ([t.get('source') for t in p.terms]
                + [v for t in p.terms for v in t.get('variants', [])]
                + [c.get('pattern') for c in p.collisions]
                + [s.get('source') for c in p.collisions for s in c.get('sources', [])]
                + [f.get('pattern') for f in p.forms]
                + [g.get('pattern') for g in p.glossary]
                + list(p.title_normalize))
    for pattern in patterns:
        if not pattern:
            continue
        try:
            re.compile(pattern)
        except re.error as e:
            errors.append('unusable regular expression %r: %s' % (pattern, e))
    if errors:
        raise ValueError('profile %s:\n  %s' % (p.path, '\n  '.join(errors)))
    return p


KNOWN_KEYS = set([
    'language', 'language_name', 'project', 'plural_forms', 'guidelines', 'glossary',
    'terms', 'collisions', 'forms', 'placeholders', 'skip_files', 'repeated_word_ok',
    'title_normalize', 'batch_size', 'agent_notes', 'help', 'blocking',
])

# Note kinds a profile may turn into errors. The structural errors are errors anyway.
BLOCKABLE = ('term', 'form', 'title_material', 'title_cosmetic', 'craft', 'unchanged',
             'sentences')
