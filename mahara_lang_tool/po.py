"""Reading and writing PO files.

Deliberately without third-party libraries: the tool has to start on a fresh machine
without any pip install.

Output is always single-line per field (like `msgcat --no-wrap`). That is the
lossless form: no question where a line was wrapped, no question whether a space at
the edge belongs to the text.
"""
import re

ESCAPES = {'n': '\n', 't': '\t', 'r': '\r', '"': '"', '\\': '\\', '/': '/'}


def decode(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == '\\' and i + 1 < len(s):
            out.append(ESCAPES.get(s[i + 1], s[i + 1]))
            i += 2
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def encode(s):
    return (s.replace('\\', '\\\\').replace('"', '\\"')
             .replace('\n', '\\n').replace('\t', '\\t').replace('\r', '\\r'))


def _unquote(line):
    line = line.strip()
    return decode(line[line.index('"') + 1:line.rindex('"')])


# Order matters: longer prefixes first, otherwise "msgid " swallows "msgid_plural ".
_FIELDS = (
    ('id_plural', 'msgid_plural '),
    ('ctxt', 'msgctxt '),
    ('id', 'msgid '),
    ('str', 'msgstr '),
)


def parse(path):
    """Read a PO file into a list of dicts.

    Fields: ctxt, id, id_plural, str, str0..strN, ref (#:), flags (#,),
    comments (#.), index (position in the file, 0-based).
    The first entry is usually the header (id == '').
    Obsolete entries (#~) and previous-msgid lines (#|) are skipped.
    """
    entries, cur, field = [], {}, None
    with open(path, encoding='utf-8') as f:
        for raw in f:
            line = raw.rstrip('\n')
            if not line.strip():
                if cur:
                    entries.append(cur)
                cur, field = {}, None
                continue
            if line.startswith('#'):
                if line.startswith('#: '):
                    cur.setdefault('ref', line[3:].strip())
                elif line.startswith('#,'):
                    cur['flags'] = line[2:].strip()
                elif line.startswith('#.'):
                    cur.setdefault('comments', []).append(line[2:].strip())
                field = None
                continue
            if line.startswith('msgstr['):
                idx = int(line[7:line.index(']')])
                field = 'str%d' % idx
                cur[field] = _unquote(line)
                continue
            for name, prefix in _FIELDS:
                if line.startswith(prefix):
                    cur[name] = _unquote(line)
                    field = name
                    break
            else:
                if line.startswith('"') and field:
                    cur[field] += _unquote(line)
    if cur:
        entries.append(cur)
    for n, e in enumerate(entries):
        e['index'] = n
    return entries


def units(path):
    """Only the real translation units, without the header."""
    return [e for e in parse(path) if e.get('id')]


def header(path):
    entries = parse(path)
    return entries[0] if entries and not entries[0].get('id') else {}


def header_fields(entry):
    """Header msgstr ('Language: de\\nPlural-Forms: ...') as a dict."""
    text = entry.get('str', '') if entry else ''
    return dict(line.split(': ', 1) for line in text.split('\n') if ': ' in line)


def nplurals(plural_forms):
    """Number of plural forms from a Plural-Forms line. Missing: 2."""
    m = re.search(r'nplurals\s*=\s*(\d+)', plural_forms or '')
    return int(m.group(1)) if m else 2


def _plural_keys(e):
    return sorted((k for k in e if re.match(r'str\d+$', k)), key=lambda k: int(k[3:]))


def is_translated(e):
    if e.get('id_plural'):
        return any(e[k] for k in _plural_keys(e))
    return bool(e.get('str'))


def translation(e):
    """The translation of a unit: a string, or the list of plural forms."""
    if e.get('id_plural'):
        return [e[k] for k in _plural_keys(e)]
    return e.get('str', '')


def key(e):
    """The unit's identity, as gettext defines it: msgctxt and msgid together.

    Works for any PO. context() alone is only unique where every unit has a
    msgctxt of its own, as in Mahara.
    """
    return (e.get('ctxt') or '', e['id'])


def context(e):
    """Where a unit lives, for display and grouping: msgctxt, else the #: line."""
    return e.get('ctxt') or e.get('ref') or ''


def format_flags(flags):
    """The format flags of a '#,' line (php-format, no-c-format, ...), without fuzzy.

    They tell msgfmt --check which placeholders to compare. fuzzy must not travel:
    a suggestion is not a fuzzy translation.
    """
    kept = [f.strip() for f in (flags or '').split(',') if f.strip().endswith('-format')]
    return ', '.join(kept)


def split_context(ctxt):
    """'artefact/blog/lang/en.utf8/artefact.blog.php addpost' -> (file, key)."""
    path, _, key = ctxt.rpartition(' ')
    return (path, key) if path else ('', ctxt)


def _line(field, value):
    return '%s "%s"\n' % (field, encode(value))


def write(path, header_text, entries, preamble=''):
    """Write a PO file.

    header_text  the header's msgstr, line by line, without trailing \\n
    entries      dicts with ctxt/id/id_plural/ref/flags/comments and the
                 translation under 'target' (string or list of plural forms)
    preamble     comment block before the header, e.g. a disclosure
    """
    out = []
    if preamble:
        out.append(preamble if preamble.endswith('\n') else preamble + '\n')
    out.append('msgid ""\nmsgstr ""\n')
    for line in header_text.rstrip('\n').split('\n'):
        out.append('"%s\\n"\n' % encode(line))

    for e in entries:
        out.append('\n')
        for line in e.get('comments', []):
            out.append('#. %s\n' % line)
        if e.get('ref'):
            out.append('#: %s\n' % e['ref'])
        if e.get('flags'):
            out.append('#, %s\n' % e['flags'])
        if e.get('ctxt'):
            out.append(_line('msgctxt', e['ctxt']))
        out.append(_line('msgid', e['id']))
        value = e['target']
        if e.get('id_plural'):
            forms = value if isinstance(value, list) else [value]
            out.append(_line('msgid_plural', e['id_plural']))
            for i, form in enumerate(forms):
                out.append(_line('msgstr[%d]' % i, form))
        else:
            if isinstance(value, list):
                raise ValueError('plural forms given for a singular unit: %s'
                                 % context(e))
            out.append(_line('msgstr', value))

    with open(path, 'w', encoding='utf-8') as f:
        f.write(''.join(out))
    return len(entries)


HEADER_ORDER = ['Project-Id-Version', 'Report-Msgid-Bugs-To', 'POT-Creation-Date',
                'PO-Revision-Date', 'Last-Translator', 'Language-Team', 'Language',
                'MIME-Version', 'Content-Type', 'Content-Transfer-Encoding',
                'Plural-Forms']


def build_header(source_fields, language, plural_forms=None, extra=None):
    """Build a PO header from the export's header fields.

    POT-Creation-Date and PO-Revision-Date are kept so that the platform can place
    the file in time. Language and Plural-Forms come from the profile.
    """
    fields = dict(source_fields)
    fields['Language'] = language
    if plural_forms:
        fields['Plural-Forms'] = plural_forms
    fields.setdefault('MIME-Version', '1.0')
    fields.setdefault('Content-Type', 'text/plain; charset=utf-8')
    fields.setdefault('Content-Transfer-Encoding', '8bit')
    # X-Generator names the platform that produced the export; this file isn't from there.
    fields.pop('X-Generator', None)
    if extra:
        fields.update(extra)
    lines = [k + ': ' + fields[k] for k in HEADER_ORDER if k in fields]
    lines += [k + ': ' + v for k, v in fields.items() if k not in HEADER_ORDER]
    return '\n'.join(lines)


def match_edges(source, target):
    """Copy leading and trailing whitespace from the source.

    Applications need these characters at runtime ('DRY RUN: ' with a trailing
    space). They get lost regularly during translation, so they are restored
    rather than reported.
    """
    lead = source[:len(source) - len(source.lstrip())]
    trail = source[len(source.rstrip()):]
    return lead + target.strip() + trail
