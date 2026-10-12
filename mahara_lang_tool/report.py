"""The quality report of a round.

The numbers come from the run itself: the checks are executed again, and if the
suggestion PO already exists, it is held against export and batches once more
(round trip, overlap, msgfmt). What the report says is therefore the state of the
files at the moment of writing — not the state at the last build.

What the report cannot do, it says itself: order of identical placeholders,
spelling, review, interface. That is always in it, even when all numbers are zero —
especially then.
"""
import datetime
import os

from . import build as build_module
from . import po
from . import rounds
from .checks import run as check_run
from .checks import structure
from .errors import Error
from .messages import text, kind_label


# Per kind at most this many places in the report; findings.json has all.
PLACES = 40
# Listed as a count only: identical placeholders are counted under "not checked",
# whitespace at the edges is restored by the build anyway.
COUNT_ONLY = (('placeholder', structure.NOTE), ('edges', structure.NOTE))


def _cell(s):
    return s.replace('|', '\\|').replace('\n', ' ')


def excerpt(text, needle=None, width=140):
    """A one-line piece of text, around needle if it occurs."""
    text = ' '.join(text) if isinstance(text, list) else text
    text = ' '.join(text.split())
    if len(text) <= width:
        return text
    at = text.find(needle) if needle else -1
    start = max(0, min(at - width // 3, len(text) - width)) if at > 0 else 0
    return ('…' if start else '') + text[start:start + width] + '…'


def places(findings, by_nr, translations, lang):
    """The findings worth reading one by one, grouped by kind."""
    def t(key, **kw):
        return text(lang, key, **kw)

    groups = {}
    for f in findings:
        if f['nr'] is None or (f['kind'], f['severity']) in COUNT_ONLY:
            continue
        groups.setdefault(f['kind'], []).append(f)
    out = []
    for kind in sorted(groups, key=lambda k: -len(groups[k])):
        entries = groups[kind]
        out += ['### %s — %d' % (kind_label(lang, kind), len(entries)), '']
        for f in entries[:PLACES]:
            row = by_nr.get(f['nr'], {})
            path, key = po.split_context(row.get('context', '?'))
            needle = f['text'].rsplit(': ', 1)[-1] if kind == 'form' else None
            error = '**%s** ' % t('error') if f['severity'] == structure.ERROR else ''
            out.append('- **#%d** `%s` · `%s` — %s%s'
                       % (f['nr'], os.path.basename(path), key, error, f['text']))
            out.append('  - %s: %s' % (t('english'), excerpt(row.get('source', ''))))
            out.append('  - %s: %s' % (t('translation'),
                                       excerpt(translations.get(f['nr'], ''), needle)))
        if len(entries) > PLACES:
            out.append('- ' + t('and_more_findings', n=len(entries) - PLACES))
        out.append('')
    return out


def check_file(r, path):
    """Hold a built suggestion PO against export and batches.

    Returns a dict of numbers, or {'stale': reason} if the batches can no longer
    be built cleanly (e.g. because something has been translated in the export).
    """
    try:
        entries = build_module.collect(r)
    except Error as e:
        return {'stale': str(e)}

    written = po.units(path)
    in_file = set(po.key(e) for e in written)
    expected = set(po.key(e) for e in entries)
    translated = set(po.key(e) for e in r.units() if po.is_translated(e))
    code, out = build_module.msgfmt(path)
    return {
        'entries': len(entries),
        'in_file': len(in_file),
        'plural': sum(1 for e in entries if e.get('id_plural')),
        'edges': sum(1 for e in entries if e['id'] != e['id'].strip()),
        'round_trip': len(build_module.round_trip(written, entries)),
        'overlap': len(translated & in_file),
        'only_file': len(in_file - expected),
        'only_batches': len(expected - in_file),
        'msgfmt_code': code,
        'msgfmt': out.replace('\n', ' ').rstrip('.'),
    }


def render(r, lang='en', today=None):
    """The report as Markdown, plus a dict of key figures."""
    def t(key, **kw):
        return text(lang, key, **kw)

    findings, coll, counts, missing, messages = check_run.collect(r)
    translations, notes, _, _ = r.batches()
    po_path = r.suggestions_path()
    built = check_file(r, po_path) if os.path.exists(po_path) else None

    header = r.header_fields()
    today = today or datetime.date.today().isoformat()
    out = [t('report_title', file=os.path.basename(po_path)), '']
    out.append(t('report_basis', today=today, export=os.path.basename(r.export),
                 exported=datetime.date.fromtimestamp(
                     os.path.getmtime(r.export)).isoformat(),
                 revision=header.get('PO-Revision-Date', '?')[:10],
                 profile=os.path.basename(r.config.get('profile') or '-')))
    out += ['', t('report_contents'), '']
    plural = sum(1 for nr in translations
                 if nr in r.by_nr and r.by_nr[nr].get('source_plural'))
    out.append(t('report_contents_text', translated=counts['translated'],
                 units=counts['units'], plural=plural))
    if missing:
        out += ['', t('report_missing', n=len(missing),
                      first=', '.join(str(n) for n in missing[:12]))]
    out += ['', t('report_origin'), '']

    out += [t('report_formal'), '']
    if built is None:
        out.append(t('report_not_built'))
    elif 'stale' in built:
        out.append(t('report_stale', reason=built['stale']))
    else:
        if built['msgfmt_code'] is None:
            msgfmt = t('report_no_msgfmt')
        else:
            msgfmt = '%s, %s' % (built['msgfmt'], t('exit_code', code=built['msgfmt_code']))
        out.append('| | |')
        out.append('|---|---|')
        out.append('| `msgfmt --check --statistics` | %s |' % _cell(msgfmt))
        out.append('| %s | %s |' % (t('row_round_trip'), t('mismatches', n=built['round_trip'])))
        out.append('| %s | %d |' % (t('row_overlap'), built['overlap']))
        out.append('| %s | %d / %d |' % (t('row_coverage'), built['in_file'], built['entries']))
        out.append('| %s | %d |' % (t('row_edges'), built['edges']))
    out.append('')

    out += [t('report_content'), '', t('error_vs_note') + ' ' + t('report_where'), '']
    per_kind = {}
    for f in findings:
        e, h = per_kind.get(f['kind'], (0, 0))
        per_kind[f['kind']] = (e + 1, h) if f['severity'] == structure.ERROR else (e, h + 1)
    if per_kind:
        out.append(t('report_table_head'))
        out.append('|---|---:|---:|')
        for kind in sorted(per_kind, key=lambda k: (-per_kind[k][0], -per_kind[k][1])):
            e, h = per_kind[kind]
            out.append('| %s | %d | %d |' % (kind_label(lang, kind), e, h))
    else:
        out.append(t('report_no_findings'))
    out.append('')

    listed = places(findings, r.by_nr, translations, lang)
    if listed:
        out += [t('report_places'), '', t('report_places_text'), ''] + listed

    if coll:
        out += [t('report_collisions'), '', t('report_collisions_text'), '']
        for c in coll:
            out.append('- %s' % c['text'])
            for name, nrs in sorted(c['places'].items()):
                out.append('  - %s: %s' % (name, ', '.join(str(n) for n in nrs)))
        out.append('')

    if messages:
        out += [t('report_corrections'), '']
        out += ['- %s' % m for m in messages]
        out.append('')

    if notes:
        out += [t('report_notes'), '', t('report_notes_text'), '']
        out.append(t('report_notes_head'))
        out.append('|---:|---|---|')
        for nr in sorted(notes):
            row = r.by_nr.get(nr, {})
            path, key = po.split_context(row.get('context', '?'))
            out.append('| %s | `%s` · `%s` | %s |'
                       % (nr, os.path.basename(path), key, _cell(notes[nr])))
        out.append('')

    identical = sum(1 for f in findings
                    if f['kind'] == 'placeholder' and f['severity'] == structure.NOTE)
    out += [t('report_limits'), '']
    for key in ('limit_placeholders', 'limit_spelling', 'limit_review', 'limit_interface'):
        out += [t(key, n=identical), '']
    out += [t('report_current'), '', t('report_current_text')]

    figures = {'counts': counts, 'built': built, 'collisions': len(coll)}
    return '\n'.join(out) + '\n', figures


def write(folder, lang=None):
    r = rounds.load(folder)
    lang = lang or r.lang
    body, k = render(r, lang)
    path = r.report_path(lang)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(body)

    z, built = k['counts'], k['built']
    print('%s' % path)
    print('  %d of %d units, %d errors, %d notes, %d collisions'
          % (z['translated'], z['units'], z['errors'], z['hints'], k['collisions']))
    if built is None:
        print('  suggestion PO not built yet')
    elif 'stale' in built:
        print('  suggestion PO is stale: %s' % built['stale'])
    else:
        print('  PO: round trip %d, overlap %d, msgfmt %s'
              % (built['round_trip'], built['overlap'], built['msgfmt']))

    broken = built is not None and (
        'stale' in built or built['round_trip'] or built['overlap']
        or built['msgfmt_code'] or built['only_file'] or built['only_batches'])
    return 1 if (z['errors'] or broken) else 0
