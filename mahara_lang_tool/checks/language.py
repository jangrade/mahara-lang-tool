"""Language checks — everything the profile prescribes.

structure.py asks: does the translation fit the source? The question here is
different: does it fit the rest of the language pack? Four checks, none of which
knows a particular language — they work through the profile's lists.

  1. House terms  The corpus decides what a term is called. If a draft deviates
                  from the prevailing version, that is a note.
  2. Collisions   One target word for several source terms — a distinction the
                  source makes disappears.
  3. Forms        What the profile marks as unwanted.
  4. Craft        Doubled words, unbalanced brackets and quotes, double spaces.
                  Runs without any profile entry.

Without a profile only 4 remains — a new language works right away, just checked
less strictly.
"""
import re

from .structure import Finding, NOTE

REPEATED_WORD = re.compile(r'\b(\w{2,})\s+\1\b', re.I)
DOUBLE_SPACE = re.compile(r'\S  +\S')


def _text(target):
    return ' '.join(target) if isinstance(target, list) else target


def craft(target, profile=None):
    """Small things one overlooks while writing. Checkable without the language."""
    f = []
    text = _text(target)
    bare = re.sub(r'<[^>]+>', ' ', text)
    allowed = profile.repeated_word_ok if profile else set()

    for m in REPEATED_WORD.finditer(bare):
        if m.group(1).lower() in allowed:
            continue
        f.append(Finding('craft', NOTE, 'repeated word: "%s %s"'
                         % (m.group(1), m.group(1))))
    if text.count('"') % 2:
        f.append(Finding('craft', NOTE, 'odd number of double quotes'))
    if text.count('(') != text.count(')'):
        f.append(Finding('craft', NOTE, 'unbalanced brackets (%d open, %d close)'
                         % (text.count('('), text.count(')'))))
    if DOUBLE_SPACE.search(text):
        f.append(Finding('craft', NOTE, 'double space inside the text'))
    return f


def forms(target, profile):
    f = []
    text = _text(target)
    for form in profile.forms:
        if form.get('wanted', True):
            continue
        m = re.search(form['pattern'], text)
        if m:
            f.append(Finding('form', NOTE,
                             'unwanted form "%s": %s' % (form['name'], m.group(0)),
                             blocking=bool(form.get('blocking'))))
    return f


def house_terms(source, target, house):
    """house: result of Corpus.house_terms(profile), computed once."""
    f = []
    text = _text(target)
    for h in house:
        if not h['house'] or not re.search(h['source'], source, re.I):
            continue
        hit = [v for v in [h['house']] + [x for x in h['variants'] if x != h['house']]
               if re.search(v, text, re.I)]
        if hit and h['house'] not in hit:
            f.append(Finding('term', NOTE,
                             '"%s" appears as `%s`; the corpus prefers `%s` (%d times)'
                             % (h['name'], hit[0], h['house'],
                                h['variants'].get(h['house'], 0)),
                             blocking=bool(h.get('blocking'))))
    return f


def collisions(pairs, profile):
    """Across all drafts, not per unit.

    pairs: list of (nr, source, target). Returns (finding, {term: [nr, ...]}).
    """
    out = []
    for c in profile.collisions:
        pattern = re.compile(c['pattern'])
        hits = {}
        for nr, source, target in pairs:
            if not pattern.search(_text(target)):
                continue
            for s in c['sources']:
                if re.search(s['source'], source, re.I):
                    hits.setdefault(s['name'], []).append(nr)
        if len(hits) > 1:
            listing = ', '.join('%s (%dx)' % (name, len(nrs))
                                for name, nrs in sorted(hits.items()))
            out.append((Finding('collision', NOTE,
                                '"%s" stands for: %s' % (c['target'], listing)),
                        {name: nrs[:10] for name, nrs in hits.items()}))
    return out


def check_unit(source, target, profile, house=None):
    f = []
    if house:
        f += house_terms(source, target, house)
    f += forms(target, profile)
    f += craft(target, profile)
    return f
