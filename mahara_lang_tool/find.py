"""`find`: look at units of an export by pattern.

For an agent that wants to see what the existing translations do before it writes a
rule: which units match, with key, source and translation, and how many there are.
The same matching as in the profile, so a number seen here is the number the analysis
will count: --source is searched without regard to case (like "terms"), --target with
regard to it (like "forms") unless --ignore-case is given. Like the analysis, --target
looks at singular units only: a plural unit has several translations of one text.
"""
import re

from . import po
from .errors import UsageError


def _short(text, pattern, width):
    text = ' '.join(text.split())
    if len(text) <= width:
        return text
    m = pattern.search(text) if pattern else None
    start = max(0, m.start() - width // 3) if m else 0
    return ('…' if start else '') + text[start:start + width] + '…'


def run(export, source=None, target=None, state='all', limit=10, ignore_case=False,
        width=160):
    try:
        src = re.compile(source, re.I) if source else None
        tgt = re.compile(target, re.I if ignore_case else 0) if target else None
    except re.error as e:
        raise UsageError('unusable regular expression: %s' % e)
    hits, occurrences = [], 0
    for e in po.units(export):
        done = po.is_translated(e)
        if (state == 'translated' and not done) or (state == 'untranslated' and done):
            continue
        text = ' | '.join(po.translation(e)) if e.get('id_plural') else e.get('str', '')
        english = e['id'] + (' | ' + e['id_plural'] if e.get('id_plural') else '')
        if src and not src.search(english):
            continue
        if tgt:
            if e.get('id_plural'):
                continue
            found = tgt.findall(text)
            if not found:
                continue
            occurrences += len(found)
        hits.append((po.context(e), english, text, done))

    translated = sum(1 for h in hits if h[3])
    print('%d units match (%d translated, %d untranslated)%s'
          % (len(hits), translated, len(hits) - translated,
             ', %d occurrences of the target pattern' % occurrences if tgt else ''))
    for key, english, text, _ in hits[:limit]:
        print()
        print('  %s' % key)
        print('    source: %s' % _short(english, src, width))
        print('    target: %s' % (_short(text, tgt, width) or '(not translated)'))
    if len(hits) > limit:
        print()
        print('  … and %d more (--limit N shows more)' % (len(hits) - limit))
    return 0
