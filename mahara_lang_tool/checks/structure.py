"""Structural checks — everything that works without knowing the target language.

These checks run in two places with the same code: on the new drafts of a round
(command `check`) and on the existing translations of an export (command `analyze`).
So nothing here knows about rounds or files, only the question: does this
translation fit this source structurally?
"""
import re

TAG = re.compile(r'</?([a-zA-Z][a-zA-Z0-9]*)\b')
NUMBER = re.compile(r'\d+(?:[.,]\d+)?')
URL = re.compile(r'https?://[^\s"\'<>]+')
CODE = re.compile(r'\$cfg->\w+|\$\w+|[\w./-]+\.(?:php|html|js|css|json)\b')
# Latin full stop, ! and ? end a sentence before a space; the sentence marks of other
# scripts need none: 。！？ (Chinese, Japanese), ؟ (Arabic script), । (Devanagari),
# ။ (Myanmar), ። (Ethiopic).
SENTENCE_END = re.compile(r'[.!?](?:\s|$)|[。！？؟।။።]+')

ERROR = 'error'
NOTE = 'note'


class Finding:
    __slots__ = ('kind', 'severity', 'text', 'blocking')

    def __init__(self, kind, severity, text, blocking=False):
        self.kind = kind
        self.severity = severity
        self.text = text
        # Set by a rule of the profile that carries "blocking": true.
        self.blocking = blocking

    def __repr__(self):
        return '<%s %s: %s>' % (self.severity, self.kind, self.text)

    def as_dict(self):
        return {'kind': self.kind, 'severity': self.severity, 'text': self.text}


def tags(text):
    return [t.lower() for t in TAG.findall(text)]


def _number_norm(s):
    """1,000 and 1.000 to the same form — separators are a locale matter."""
    return s.replace('.', '').replace(',', '')


def _without_markup(text):
    return re.sub(r'<[^>]+>', ' ', text)


def sentences(text):
    return len(SENTENCE_END.findall(_without_markup(text).strip()))


def check_text(source, target, profile, is_html=None):
    """Check a single string against its source. Returns a list of findings.

    The caller decides what to do with notes — errors should stop it.
    """
    f = []
    if not target or not target.strip():
        return [Finding('empty', ERROR, 'no translation')]

    if target == source and len(source) > 25:
        f.append(Finding('unchanged', NOTE, 'identical to the source'))

    # %s / %d are filled in order -> the sequence must match.
    a, z = profile.positional.findall(source), profile.positional.findall(target)
    if a != z:
        f.append(Finding('placeholder', ERROR,
                         'positional placeholders: source %s, translation %s'
                         % (a or '-', z or '-')))
    elif len(a) > 1 and len(set(a)) == 1:
        f.append(Finding('placeholder', NOTE,
                         '%d identical placeholders — argument order can only be '
                         'checked by hand' % len(a)))

    # %1$s and {$a->foo} bind their argument by index or name. The order is
    # free, the set is not.
    for name, pattern in (('indexed placeholders', profile.indexed),
                          ('named placeholders', profile.named)):
        a, z = sorted(pattern.findall(source)), sorted(pattern.findall(target))
        if a != z:
            f.append(Finding('placeholder', ERROR, '%s: source %s, translation %s'
                             % (name, a or '-', z or '-')))

    if is_html is None:
        is_html = '<' in source
    if is_html:
        a, z = tags(source), tags(target)
        if a != z:
            f.append(Finding('html', ERROR,
                             'tag sequence: source %s, translation %s' % (a, z)))

    if source.strip() and (source[:1].isspace() or source[-1:].isspace()):
        lead_a = len(source) - len(source.lstrip())
        lead_z = len(target) - len(target.lstrip())
        trail_a = len(source) - len(source.rstrip())
        trail_z = len(target) - len(target.rstrip())
        if (lead_a, trail_a) != (lead_z, trail_z):
            f.append(Finding('edges', NOTE,
                             'leading/trailing whitespace differs (source %d/%d, '
                             'translation %d/%d) — restored on build'
                             % (lead_a, trail_a, lead_z, trail_z)))

    # Numbers only after removing placeholders, otherwise the 1 in %1$s counts.
    bare_a = profile.placeholder.sub(' ', source)
    bare_z = set(_number_norm(n) for n in NUMBER.findall(profile.placeholder.sub(' ', target)))
    missing = sorted(set(n for n in NUMBER.findall(bare_a) if _number_norm(n) not in bare_z))
    if missing:
        f.append(Finding('numbers', ERROR,
                         'numbers missing in the translation: %s' % ', '.join(missing)))

    for name, pattern in (('URL', URL), ('code identifier', CODE)):
        missing = [s for s in set(pattern.findall(source)) if s not in target]
        if missing:
            f.append(Finding('literal', ERROR, '%s changed or lost: %s'
                             % (name, ', '.join(sorted(missing)))))

    sa, sz = sentences(source), sentences(target)
    if sa >= 3 and sz < sa:
        f.append(Finding('sentences', NOTE,
                         'source has %d sentences, translation %d' % (sa, sz)))
    return f


def check_unit(source, target, profile, is_html=None, source_plural=None, nplurals=None):
    """Check a unit, singular or plural. target is a string or a list of forms."""
    if source_plural:
        if not isinstance(target, list):
            return [Finding('plural', ERROR,
                            'source has plural forms, the translation does not')]
        want = nplurals if nplurals is not None else profile.nplurals
        if len(target) != want:
            return [Finding('plural', ERROR,
                            '%d plural forms instead of %d' % (len(target), want))]
        f = []
        # Which numbers each form is shown for, from the Plural-Forms expression. A
        # form for 1 alone is checked against the singular source, every other form
        # against the plural: Japanese has one form for all numbers, Russian uses its
        # first form for 1, 21, 31 … and needs the %d there. A form for a single number
        # (Arabic has forms for 0, 1 and 2) may write the number as a word: there the
        # %d may be left out, and a lost number is only a note. Every other
        # placeholder still has to be there.
        numbers = profile.plural_numbers()
        if not numbers or len(numbers) != len(target):
            numbers = [{1}] + [set(range(2, 1000))] * (len(target) - 1) if len(target) > 1 \
                else [set(range(1000))]
        for i, form in enumerate(target):
            model = source if numbers[i] == {1} else source_plural
            single = len(numbers[i]) == 1
            if single and '%d' not in form:
                model = re.sub(r'%d\s?', '', model)
            for x in check_text(model, form, profile, is_html):
                severity = NOTE if single and x.kind == 'numbers' else x.severity
                f.append(Finding(x.kind, severity, 'form %d: %s' % (i, x.text)))
        return f

    if isinstance(target, list):
        return [Finding('plural', ERROR, 'plural forms given, the source has none')]
    return check_text(source, target, profile, is_html)
