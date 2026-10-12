"""Run all checks of a round.

Order: count what is there, then structure, language and titles per unit, finally
collisions (across all drafts together, not per unit).

Exit code 1 as soon as there is an error. Notes do not stop anything — they are for
looking through, not for working off.
"""
import json
import os

from .. import batches as batch_module
from .. import corpus as corpus_module
from .. import rounds
from . import language, structure, titles

LIMIT = 12


def collect(r):
    """Run the checks. Returns (findings, collisions, counts, missing, messages)."""
    translations, notes, messages, problems = r.batches()
    corpus = corpus_module.Corpus(r.units())
    house = corpus.house_terms(r.profile)
    nplurals = r.profile.nplurals

    findings = [{'nr': None, 'context': '', 'kind': 'batch',
                 'severity': structure.ERROR, 'text': p} for p in problems]
    pairs = []
    for nr in sorted(translations):
        row = r.by_nr.get(nr)
        if row is None:
            findings.append({'nr': nr, 'context': '?', 'kind': 'unknown',
                             'severity': structure.ERROR,
                             'text': 'number is not in the scaffold'})
            continue
        target = translations[nr]
        pairs.append((nr, row['source'], target))

        found = structure.check_unit(
            row['source'], target, r.profile, is_html=row['html'],
            source_plural=row['source_plural'] or None, nplurals=nplurals)
        if not r.profile.skipped(row['context']):
            found += language.check_unit(row['source'], target, r.profile, house)
            found += titles.check_unit(target, row['label'], r.profile, row['source'],
                                       row.get('label_source'))
        for f in found:
            severity = f.severity
            if (f.blocking or f.kind in r.profile.blocking) and nr not in notes:
                severity = structure.ERROR
            findings.append({'nr': nr, 'context': row['context'], 'kind': f.kind,
                             'severity': severity, 'text': f.text})

    coll = [{'kind': f.kind, 'severity': f.severity, 'text': f.text, 'places': places}
            for f, places in language.collisions(pairs, r.profile)]

    missing = sorted(set(row['nr'] for row in r.scaffold) - set(translations))
    counts = {
        'units': len(r.scaffold),
        'translated': len(set(translations) & set(r.by_nr)),
        'missing': len(missing),
        'notes': len(notes),
        'errors': sum(1 for f in findings if f['severity'] == structure.ERROR),
        'hints': sum(1 for f in findings if f['severity'] == structure.NOTE),
    }
    return findings, coll, counts, missing, messages


def check(folder, errors_only=False):
    r = rounds.load(folder)
    findings, coll, counts, missing, messages = collect(r)

    print('%s' % folder)
    rounds.print_drift(r)
    print('  %d of %d units translated, %d notes'
          % (counts['translated'], counts['units'], counts['notes']))
    print('  %d errors, %d notes' % (counts['errors'], counts['hints']))
    for m in messages:
        print('  %s' % m)
    print()

    by_kind = {}
    for f in findings:
        if errors_only and f['severity'] != structure.ERROR:
            continue
        by_kind.setdefault((f['severity'], f['kind']), []).append(f)

    for severity in (structure.ERROR, structure.NOTE):
        groups = [(k, v) for (s, k), v in by_kind.items() if s == severity]
        if not groups:
            continue
        print('ERRORS' if severity == structure.ERROR else 'Notes')
        for kind, entries in sorted(groups, key=lambda g: -len(g[1])):
            print('  %-20s %d' % (kind, len(entries)))
            for f in entries[:LIMIT]:
                print('      %5s %s' % (f['nr'] if f['nr'] is not None else '', f['text']))
                if f['context']:
                    print('            %s' % f['context'])
            if len(entries) > LIMIT:
                print('      … and %d more' % (len(entries) - LIMIT))
        print()

    if coll and not errors_only:
        print('Collisions')
        for c in coll:
            print('  %s' % c['text'])
            for name, nrs in sorted(c['places'].items()):
                print('      %-14s %s' % (name, nrs))
        print()

    if missing:
        print('%d numbers still missing, first: %s' % (len(missing), missing[:12]))
        print()

    with open(r.path('findings.json'), 'w', encoding='utf-8') as f:
        json.dump({'counts': counts, 'findings': findings, 'collisions': coll,
                   'missing': missing, 'messages': messages},
                  f, ensure_ascii=False, indent=1, sort_keys=True)
    print('%s' % r.path('findings.json'))
    print()
    print('NEXT: %s' % next_step(r, folder, counts, missing))
    return 1 if counts['errors'] else 0


def next_step(r, folder, counts, missing):
    """One line that tells a person or an agent what to do now."""
    if counts['errors']:
        text = 'fix the %d errors above, then run %s again.' % (
            counts['errors'], rounds.command('check', folder))
        if r.profile.blocks():
            text += (' Errors of kind %s come from blocking rules of the profile: fix '
                     'them, or explain in the unit\'s "note" why the translation is right.'
                     % '/'.join(sorted(set(k for k, _ in r.profile.blocks()))))
        return text
    if missing:
        for name, numbers, filled in batch_module.per_file(r.work):
            if numbers - filled:
                path = os.path.normpath(os.path.join(folder, rounds.WORK, 'batches', name))
                return 'translate %s (%d units open), then run %s.' % (
                    path, len(numbers - filled), rounds.command('check', folder))
        return '%d units are still missing.' % len(missing)
    return ('all units translated, no errors. Look through the notes above, then run '
            '%s and %s; the results go to output/.'
            % (rounds.command('build', folder), rounds.command('report', folder)))
