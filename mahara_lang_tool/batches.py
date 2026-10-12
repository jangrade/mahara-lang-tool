"""Batch files: where the translations of a round are written.

A batch is a JSON file, not code — loading it never executes anything, so batches
from any agent or person can be handled safely. Each unit carries its source text:

    {
      "units": {
        "17": {"source": "Delete page", "target": "Seite löschen"},
        "18": {"source": "%d file", "source_plural": "%d files",
               "target": ["%d Datei", "%d Dateien"], "note": "..."}
      }
    }

The copied source is the guard against the most expensive mistake of a round:
numbers that have slipped by one. If "source" does not match the scaffold, the
unit is rejected.

Two folders, two rules:

  batches/      the regular work. Two files must not fill the same number; if it
                happens anyway, it is a mistake and is reported.
  corrections/  may overwrite. Terminology fixes and title alignments go here
                after a check has found something — the original entry stays in
                place and remains traceable.

An empty target ("" or a list of empty strings) means: not done yet.
"""
import collections
import glob
import json
import os

FOLDERS = (('batches', False), ('corrections', True))


def _empty(target):
    if isinstance(target, list):
        return not any(target)
    return not target


def read_file(path):
    """Returns (units, problems). units: {nr: dict}; problems: list of texts."""
    name = os.path.join(os.path.basename(os.path.dirname(path)), os.path.basename(path))
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except ValueError as e:
        return {}, ['%s: not valid JSON — %s' % (name, e)]
    if not isinstance(data, dict) or not isinstance(data.get('units'), dict):
        return {}, ['%s: expected an object with "units"' % name]

    units, problems = {}, []
    for key, unit in data['units'].items():
        where = '%s #%s' % (name, key)
        if not key.isdigit():
            problems.append('%s: key must be a unit number' % where)
            continue
        if not isinstance(unit, dict) or 'target' not in unit:
            problems.append('%s: expected an object with "target"' % where)
            continue
        target = unit['target']
        if not (isinstance(target, str) or
                (isinstance(target, list) and all(isinstance(t, str) for t in target))):
            problems.append('%s: "target" must be a string or a list of strings' % where)
            continue
        if 'note' in unit and not isinstance(unit['note'], str):
            problems.append('%s: "note" must be a string' % where)
            continue
        units[int(key)] = unit
    return units, problems


def load(work, scaffold=None):
    """Load all batches and corrections of a round (work: the round's work/ folder).

    scaffold: {nr: row} to verify the copied source texts, or None.
    Returns (translations, notes, messages, problems):

      translations  nr -> string or list of plural forms (only non-empty ones)
      notes         nr -> explanation
      messages      informational: which correction file overwrote what
      problems      errors: broken files, duplicate numbers, shifted sources
    """
    translations, notes, messages, problems = {}, {}, [], []
    origin = {}
    overwritten = collections.OrderedDict()

    for folder, may_overwrite in FOLDERS:
        for path in sorted(glob.glob(os.path.join(work, folder, '*.json'))):
            name = os.path.join(folder, os.path.basename(path))
            units, file_problems = read_file(path)
            problems.extend(file_problems)
            for nr, unit in sorted(units.items()):
                if scaffold is not None and 'source' in unit:
                    row = scaffold.get(nr)
                    if row is not None and unit['source'] != row['source']:
                        problems.append('%s #%d: source text does not match the '
                                        'scaffold — numbers shifted?' % (name, nr))
                        continue
                if unit.get('note'):
                    notes[nr] = unit['note']
                if _empty(unit['target']):
                    continue
                if nr in translations:
                    if may_overwrite:
                        overwritten.setdefault(name, []).append(nr)
                    else:
                        problems.append('#%d filled twice: %s and %s'
                                        % (nr, origin[nr], name))
                origin[nr] = name
                translations[nr] = unit['target']

    for name, nrs in overwritten.items():
        messages.append('%s overwrites %d entries (%s%s)'
                        % (name, len(nrs), ', '.join(str(n) for n in sorted(nrs)[:6]),
                           ' …' if len(nrs) > 6 else ''))
    return translations, notes, messages, problems


def per_file(work, folder='batches'):
    """Which numbers each file fills — for the progress display."""
    out = []
    for path in sorted(glob.glob(os.path.join(work, folder, '*.json'))):
        units, _ = read_file(path)
        filled = set(nr for nr, u in units.items() if not _empty(u['target']))
        out.append((os.path.basename(path), set(units), filled))
    return out


def write_empty(path, rows, nplurals, about):
    """A batch with every unit prefilled: source copied, target empty."""
    units = collections.OrderedDict()
    for r in rows:
        u = collections.OrderedDict()
        u['context'] = r['context']
        u['source'] = r['source']
        if r['source_plural']:
            u['source_plural'] = r['source_plural']
            u['target'] = [''] * nplurals
        else:
            u['target'] = ''
        units[str(r['nr'])] = u
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(collections.OrderedDict([('_about', about), ('units', units)]),
                  f, ensure_ascii=False, indent=1)
        f.write('\n')
