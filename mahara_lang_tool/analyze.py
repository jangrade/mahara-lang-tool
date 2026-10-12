"""Corpus analysis — the first step for every language.

Before a single line is translated, measure what is already there: where the pack
translates the same source term differently, where it translates different terms
the same way, where placeholders and markup don't fit the source, and which
linguistic forms occur at all.

The report is a basis for decisions, not a list of errors. It counts and cites
places; what gets changed is up to the people who maintain the pack.

The profile follows from the report: copy the house terms and unwanted forms from
it instead of inventing them.
"""
import collections
import json
import os
import re

from . import corpus as corpus_module
from . import po
from .checks import structure
from .messages import text, kind_label

SAMPLES = 15

# New terms: words of the source that are frequent in the untranslated units and
# rare in the translated ones, like "section" after Mahara renamed "block". Rates
# are per word, not per unit, because untranslated units are often long help texts.
NEW_TERMS = 10
NEW_MIN_UNITS = 3
NEW_RATIO = 10
WORD = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")
MARKUP = re.compile(r'<[^>]+>|https?://\S+|\S+\.(?:php|html|js|css)\b')


def _words(text, profile):
    text = profile.placeholder.sub(' ', MARKUP.sub(' ', text))
    return [w.lower().strip("'-") for w in WORD.findall(text)]


def new_terms(units, profile, limit=NEW_TERMS):
    """Source words the existing translations have hardly ever seen.

    A word counts when it occurs in at least NEW_MIN_UNITS untranslated units, its
    share of all untranslated words is NEW_RATIO times its share among the
    translated ones, and it occurs in few translated units. A plural "s" is folded
    into the singular where both exist.
    """
    def count(es):
        occ, df = collections.Counter(), collections.Counter()
        for e in es:
            words = _words(e['id'] + ' ' + (e.get('id_plural') or ''), profile)
            occ.update(words)
            df.update(set(words))
        return occ, df

    units = [e for e in units if not profile.skipped(po.context(e))]
    todo = [e for e in units if not po.is_translated(e)]
    done = [e for e in units if po.is_translated(e)]
    (occ_u, df_u), (occ_t, df_t) = count(todo), count(done)
    vocabulary = set(occ_u) | set(occ_t)

    def fold(counter):
        out = collections.Counter()
        for w, n in counter.items():
            out[w[:-1] if w.endswith('s') and w[:-1] in vocabulary else w] += n
        return out

    occ_u, df_u, occ_t, df_t = fold(occ_u), fold(df_u), fold(occ_t), fold(df_t)
    total_u, total_t = sum(occ_u.values()) or 1, sum(occ_t.values()) or 1
    rare = max(3, len(done) * 0.002)
    found = []
    for w, n in df_u.items():
        ratio = (occ_u[w] / total_u) / max(occ_t[w] / total_t, 1.0 / total_t)
        if n >= NEW_MIN_UNITS and ratio >= NEW_RATIO and df_t[w] <= rare:
            found.append((n, w))
    found.sort(key=lambda x: (-x[0], x[1]))
    out = []
    for n, w in found[:limit]:
        pattern = re.compile(r'\b%ss?\b' % re.escape(w), re.I)
        examples = []
        for e in todo:
            plain = ' '.join(MARKUP.sub(' ', e['id']).split())
            m = pattern.search(plain)
            if m:
                start = max(0, m.start() - 30)
                examples.append(('…' if start else '') + plain[start:m.end() + 40]
                                + ('…' if m.end() + 40 < len(plain) else ''))
            if len(examples) == 3:
                break
        translations = [(e['id'], e['str'] if 'str' in e else ' | '.join(po.translation(e)))
                        for e in done if pattern.search(e['id'])][:4]
        out.append({'term': w, 'untranslated': n, 'translated': df_t[w],
                    'examples': examples, 'translations': translations})
    return out


def _ids(d):
    """Evidence ids: T1… for terms, F1… for forms, N1… for new terms. decisions.md
    cites them, so a counted question always points to numbers the tool made."""
    for prefix, key in (('T', 'house_terms'), ('F', 'forms'), ('N', 'new_terms')):
        for i, item in enumerate(d.get(key) or [], 1):
            item['id'] = '%s%d' % (prefix, i)
    return d


def _around(text, pattern, width=90):
    """A one-line excerpt of text around the first match of pattern."""
    text = ' '.join(MARKUP.sub(' ', text).split())
    m = re.search(pattern, text, re.I) if pattern else None
    if not m or len(text) <= width:
        return _short(text, width)
    start = max(0, m.start() - width // 3)
    return ('…' if start else '') + _short(text[start:], width)


def collect(export, profile):
    """Run all counts and return a dict — the basis of report and JSON."""
    entries = po.parse(export)
    profile.adopt(po.header_fields(entries[0] if entries and not entries[0].get('id') else {}))
    units = [e for e in entries if e.get('id')]
    c = corpus_module.Corpus(units)

    defects = collections.defaultdict(list)
    for e in c.units:
        ctxt = po.context(e)
        if profile.skipped(ctxt):
            continue
        for f in structure.check_text(e['id'], e['str'], profile):
            defects[f.kind].append({'context': ctxt, 'severity': f.severity,
                                    'text': f.text, 'source': e['id'], 'target': e['str']})

    return _ids({
        'export': os.path.abspath(export),
        'profile': profile.path,
        'language': profile.language,
        'counts': {
            'units': len(units),
            'translated': sum(1 for e in units if po.is_translated(e)),
            'untranslated': sum(1 for e in units if not po.is_translated(e)),
            'counted': len(c),
        },
        'inconsistent': [{'source': src, 'versions': dict(n), 'places': places[:5]}
                         for src, n, places in c.inconsistent()],
        'collisions': [{'target': tgt, 'sources': dict(n)} for tgt, n in c.collisions()],
        'defects': dict(defects),
        'forms': c.forms(profile),
        'house_terms': c.house_terms(profile),
        'new_terms': new_terms(units, profile),
    })


def _short(s, n=70):
    s = s.replace('\n', '\\n').replace('|', '\\|')
    return s if len(s) <= n else s[:n - 1] + '…'


def _count(entries, severity):
    return sum(1 for m in entries if m['severity'] == severity)


def report(d, lang='en'):
    def t(key, **kw):
        return text(lang, key, **kw)

    z = d['counts']
    out = [t('analysis_title', language=d['language']), '']
    out.append(t('analysis_basis', export=os.path.basename(d['export'])))
    if d['profile']:
        out.append(t('analysis_profile', profile=os.path.basename(d['profile'])))
    out += ['', t('analysis_counts', **z), '']
    out.append(t('analysis_table_head'))
    out.append('|---|---:|---:|')
    out.append('| %s | | %d |' % (t('analysis_row_inconsistent'), len(d['inconsistent'])))
    out.append('| %s | | %d |' % (t('analysis_row_collisions'), len(d['collisions'])))
    order = sorted(d['defects'], key=lambda k: -_count(d['defects'][k], structure.ERROR))
    for kind in order:
        e = _count(d['defects'][kind], structure.ERROR)
        h = _count(d['defects'][kind], structure.NOTE)
        out.append('| %s | %s | %s |' % (kind_label(lang, kind), e or '', h or ''))
    out += ['', t('error_vs_note'), '']

    out += [t('analysis_inconsistent_heading'), '', t('analysis_inconsistent_text'), '']
    if d['inconsistent']:
        out.append(t('analysis_inconsistent_head'))
        out.append('|---|---|')
        for u in d['inconsistent'][:80]:
            versions = sorted(u['versions'].items(), key=lambda x: -x[1])
            out.append('| `%s` | %s |' % (_short(u['source'], 50), ' · '.join(
                '%s (%d)' % (_short(k, 40), n) for k, n in versions)))
        if len(d['inconsistent']) > 80:
            out += ['', t('and_more_json', n=len(d['inconsistent']) - 80)]
    else:
        out.append(t('none'))
    out.append('')

    out += [t('analysis_collisions_heading'), '', t('analysis_collisions_text'), '']
    if d['collisions']:
        out.append(t('analysis_collisions_head'))
        out.append('|---|---|')
        for c in d['collisions'][:60]:
            sources = sorted(c['sources'].items(), key=lambda x: -x[1])
            out.append('| `%s` | %s |' % (_short(c['target'], 40), ' · '.join(
                '%s (%d)' % (_short(s, 30), n) for s, n in sources)))
        if len(d['collisions']) > 60:
            out += ['', t('and_more_json', n=len(d['collisions']) - 60)]
    else:
        out.append(t('none'))
    out.append('')

    out += [t('analysis_defects_heading'), '']
    shown = False
    for kind in order:
        entries = [m for m in d['defects'][kind] if m['severity'] == structure.ERROR]
        if not entries:
            continue
        shown = True
        out += ['', '### %s — %d' % (kind_label(lang, kind), len(entries)), '']
        for m in entries[:SAMPLES]:
            out.append('- `%s`' % m['context'])
            out.append('  %s' % m['text'])
        if len(entries) > SAMPLES:
            out.append('- ' + t('and_more', n=len(entries) - SAMPLES))
    if not shown:
        out.append(t('none'))
    out.append('')

    if d['forms']:
        out += [t('analysis_forms_heading'), '', t('analysis_forms_text'), '']
        out.append(t('analysis_forms_head'))
        out.append('|---|---|---:|---:|---|')
        for f in d['forms']:
            out.append('| **%s** | %s | %d | %d | %s |' % (
                f['id'], f['name'], f['units'], f['occurrences'],
                t('wanted') if f['wanted'] else t('unwanted')))
        out.append('')
        for f in d['forms']:
            if not f['samples']:
                continue
            out.append('**%s** %s:' % (f['id'], f['name']))
            for ctx, sample in f['samples']:
                out.append('- `%s`: %s' % (_short(ctx, 60), _around(sample, f['pattern'])))
            out.append('')

    if d['house_terms']:
        out += [t('analysis_house_heading'), '', t('analysis_house_text'), '']
        for h in d['house_terms']:
            out += ['### %s · %s' % (h['id'], h['name']), '']
            out.append(t('analysis_house_head'))
            out.append('|---|---:|---|')
            rows = sorted(h['variants'].items(), key=lambda x: -x[1])
            for variant, n in rows:
                out.append('| `%s` | %d | %s |' % (variant, n, ' · '.join(
                    '%s → %s' % (_short(s, 40), _around(tr, variant, 50))
                    for s, tr in h['samples'].get(variant, [])[:2])))
            out.append('| %s | %d | %s |' % (t('other_variant'), h.get('other', 0), ' · '.join(
                '%s → %s' % (_short(s, 40), _short(tr, 50))
                for s, tr in h.get('other_samples', [])[:2])))
            out += ['', '%s: %s' % (t('house_form'),
                                    '`%s`' % h['house'] if h['house'] else '—'), '']

    if d.get('new_terms'):
        out += [t('analysis_new_heading'), '', t('analysis_new_text'), '']
        out.append(t('analysis_new_head'))
        out.append('|---|---|---:|---:|---|')
        for n in d['new_terms']:
            out.append('| **%s** | `%s` | %d | %d | %s |' % (
                n['id'], n['term'], n['untranslated'], n['translated'],
                ' · '.join(_short(x, 60) for x in n['examples'])))
        out.append('')
        for n in d['new_terms']:
            if not n.get('translations'):
                continue
            out.append('**%s** %s:' % (n['id'], t('analysis_new_translated', term=n['term'])))
            for s, tr in n['translations']:
                out.append('- %s → %s' % (_around(s, r'\b%s' % re.escape(n['term']), 70),
                                          _short(tr, 90)))
            out.append('')

    return '\n'.join(out) + '\n'


def run(export, profile, report_path=None, json_path=None, lang='en'):
    d = collect(export, profile)
    body = report(d, lang)
    if report_path:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(body)
    if json_path:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=1, sort_keys=True)
    return d, body
