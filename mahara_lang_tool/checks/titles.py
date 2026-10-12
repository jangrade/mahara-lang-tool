"""Does a help text carry the same title as the field it belongs to?

A help key is named like its field plus a suffix ("_help" in Mahara), and the help
text repeats the field label as <h1>. Both strings sit side by side in the same
file but were translated at different times: the label is in the corpus, the help
text is new. If they differ, the help window carries a different name than the
field in front of it.

Two classes:

  cosmetic  same words, different spelling — hyphen, an ending, a bracket.
  material  different words.

Only where the English help title is the English field label: "Section title" as
help for a field labelled "Overview" is a different name on purpose.

Material does not mean wrong. A corpus grown over years contains typos, old
spelling and terms the glossary has since replaced. The list is for deciding, not
for copying over.
"""
import re

from .structure import Finding, NOTE

HEADING = re.compile(r'<h[12][^>]*>(.*?)</h[12]>', re.S | re.I)


def _plain(s):
    return re.sub(r'<[^>]+>', '', s).replace('&amp;', '&').strip()


def _norm(s, patterns):
    """Drop cosmetics: bracketed additions, whatever the profile names, hyphens, spaces."""
    s = re.sub(r'\([^)]*\)', '', s.lower())
    for p in patterns:
        s = re.sub(p, '', s)
    return re.sub(r'[-\s.]', '', s)


def _heading(text):
    m = HEADING.search(text or '')
    return _plain(m.group(1)) if m else ''


def check_unit(target, label, profile, source=None, label_source=None):
    """label: the translated field label from the corpus, or None.

    source, label_source: the English help text and field label. If both are given
    and the English title is not the English label, there is nothing to match.
    """
    if not label:
        return []
    if source is not None and label_source is not None:
        if _norm(_heading(source).rstrip(':'), []) != _norm(_plain(label_source).rstrip(':'), []):
            return []
    text = target[0] if isinstance(target, list) else target
    m = HEADING.search(text or '')
    if not m:
        return []
    title = _plain(m.group(1))
    if not title:
        return []
    field = _plain(label)
    if title == field:
        return []
    same = _norm(title, profile.title_normalize) == _norm(field, profile.title_normalize)
    kind = 'title_cosmetic' if same else 'title_material'
    return [Finding(kind, NOTE, 'help title "%s" vs. field label "%s"' % (title, field))]
