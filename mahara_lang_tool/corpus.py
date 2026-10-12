"""The existing translations as a source of knowledge.

What a term is called in a language pack is not written in a glossary but in the
units that are already translated in the same export. The corpus is the glossary —
it only has to be counted.

Three things follow from it:
  - the analysis (which terms are translated inconsistently?)
  - the house terms that new drafts are checked against
  - the examples that show an agent the tone of a file
"""
import collections
import re

from . import po

# Labels are short. For long texts a different wording is normal and says nothing
# about terminology.
SHORT = 40


class Corpus:

    def __init__(self, units):
        # Only translated singular units: plural forms would skew the counts,
        # because one msgid then has several target versions.
        self.units = [e for e in units if e.get('str') and not e.get('id_plural')]
        self.by_context = {po.context(e): e for e in self.units}

    def __len__(self):
        return len(self.units)

    # -- counting ------------------------------------------------------------

    def memory(self):
        """Source text -> counter over its target versions."""
        m = collections.defaultdict(collections.Counter)
        for e in self.units:
            m[e['id']][e['str']] += 1
        return m

    def inconsistent(self, short=SHORT):
        """Same source text, several target versions.

        Returns triples (source, counter, sample contexts), long texts last: on a
        label inconsistency shows on screen, in a paragraph it doesn't.
        """
        places = collections.defaultdict(list)
        for e in self.units:
            places[e['id']].append(po.context(e))
        hits = [(src, c, places[src]) for src, c in self.memory().items() if len(c) > 1]
        hits.sort(key=lambda h: (len(h[0]) > short, -len(h[1]), h[0].lower()))
        return hits

    def collisions(self, short=SHORT):
        """Same target text for several source terms.

        The sharpest of the counts: a distinction the source makes disappears.
        Short texts only, otherwise it is noise.
        """
        m = collections.defaultdict(collections.Counter)
        for e in self.units:
            if len(e['str']) <= short:
                m[e['str']][e['id']] += 1
        hits = [(target, c) for target, c in m.items() if len(c) > 1]
        hits.sort(key=lambda h: (-len(h[1]), h[0].lower()))
        return hits

    # -- information for checks and the brief --------------------------------

    def house_terms(self, profile):
        """Per term in the profile: which variant prevails in the corpus.

        Returns dicts with name, source, variants (count per variant), house (the
        most frequent), samples, and "other": units whose source has the term but
        whose translation matches none of the variants. That count keeps a variant
        nobody thought of from disappearing.
        """
        out = []
        for t in profile.terms:
            source = re.compile(t['source'], re.I)
            counts = collections.Counter()
            samples = collections.defaultdict(list)
            other, other_samples = 0, []
            for e in self.units:
                if not source.search(e['id']):
                    continue
                hit = False
                for v in t['variants']:
                    if re.search(v, e['str'], re.I):
                        hit = True
                        counts[v] += 1
                        if len(samples[v]) < 3:
                            samples[v].append((e['id'], e['str']))
                if not hit:
                    other += 1
                    if len(other_samples) < 3:
                        other_samples.append((e['id'], e['str']))
            house = counts.most_common(1)[0][0] if counts else None
            out.append({'name': t['name'], 'source': t['source'],
                        'blocking': bool(t.get('blocking')),
                        'variants': dict(counts), 'house': house,
                        'samples': dict(samples), 'other': other,
                        'other_samples': other_samples})
        return out

    def examples(self, path, n=4):
        """Translated pairs from the same file — a tone sample for the brief.

        Prefers medium-length sentences: one-word labels show no tone, long help
        texts blow up the brief.
        """
        candidates = []
        for e in self.units:
            if po.split_context(po.context(e))[0] != path:
                continue
            if '<' in e['id'] or len(e['id']) > 160:
                continue
            candidates.append((abs(len(e['id']) - 60), e['id'], e['str']))
        candidates.sort()
        return [(src, tgt) for _, src, tgt in candidates[:n]]

    def label_for(self, ctxt, suffix='_help'):
        """For 'file.php field_help' the translated unit 'file.php field', or None.

        Help texts repeat the field label as their heading. If the label is
        already translated, the new help title has to match it — otherwise the
        help window carries a different name than the field in front of it.
        """
        path, key = po.split_context(ctxt)
        if not suffix or not key.endswith(suffix):
            return None
        return self.by_context.get('%s %s' % (path, key[:-len(suffix)]))

    def forms(self, profile, samples=3):
        """Count the profile's forms in the corpus.

        Raw counts that need curating: a pattern for one form can also hit
        the same word in another meaning.
        """
        out = []
        for f in profile.forms:
            pattern = re.compile(f['pattern'])
            hits = [e for e in self.units if pattern.search(e['str'])]
            out.append({'name': f['name'],
                        'pattern': f['pattern'],
                        'wanted': f.get('wanted', True),
                        'units': len(hits),
                        'occurrences': sum(len(pattern.findall(e['str'])) for e in hits),
                        'samples': [(po.context(e), e['str']) for e in hits[:samples]]})
        return out
