#!/usr/bin/env python3
"""A small export for trying out an agent: all translated units, few untranslated ones.

    sample_export.py EXPORT.po [-n 40] [-o OUT.po]

What costs tokens in a round is translating. The setup needs the existing translations
in full (they are what the analysis counts), but not 2,000 open units. This keeps every
translated unit and N untranslated ones, spread evenly over the export so that labels,
help texts, messages and units with placeholders all occur, plus every untranslated
plural unit. The new terms of the analysis stay findable as long as N is not tiny.

The result is a valid export like Weblate's, in PO order. Its file name says it is a
sample (default: EXPORT-sample40.po in the current folder, never beside the export:
a second .po in a round's input/ would break the round).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mahara_lang_tool import po  # noqa: E402


def sample(entries, n):
    units = [e for e in entries if e.get('id')]
    todo = [i for i, e in enumerate(units) if not po.is_translated(e)]
    keep = set(i for i in todo if units[i].get('id_plural'))
    rest = [i for i in todo if i not in keep]
    want = max(0, n - len(keep))
    if want and rest:
        step = len(rest) / float(min(want, len(rest)))
        keep.update(rest[int(k * step)] for k in range(min(want, len(rest))))
    return [e for i, e in enumerate(units) if po.is_translated(e) or i in keep]


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('export')
    a.add_argument('-n', type=int, default=40, help='untranslated units to keep (default: 40)')
    a.add_argument('-o', '--out', help='target file (default: EXPORT-sampleN.po here)')
    args = a.parse_args(argv)

    entries = po.parse(args.export)
    header = entries[0] if entries and not entries[0].get('id') else {}
    kept = sample(entries, args.n)
    out = args.out or '%s-sample%d.po' % (
        os.path.splitext(os.path.basename(args.export))[0], args.n)
    for e in kept:
        e['target'] = po.translation(e)
    po.write(out, header.get('str', ''), kept)
    open_units = sum(1 for e in kept if not po.is_translated(e))
    print('%s: %d translated, %d untranslated (of %d)'
          % (out, len(kept) - open_units, open_units,
             sum(1 for e in entries if e.get('id') and not po.is_translated(e))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
