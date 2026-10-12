"""Build the suggestion PO.

Four guarantees make the file trustworthy:

  1. Check gate       The build refuses while `check` reports errors. --force builds
                      anyway, for errors a person has looked at and accepted.
  2. Overwrite guard  Only units that were empty in the export go in, and only if
                      their source text is still the one the translation was made
                      for. That the file cannot overwrite existing work is not a
                      matter of care when uploading; the construction rules it out.
  3. Round trip       The written file is read back and compared character by
                      character. This is the real test of the escaping.
  4. msgfmt           The outside cross-check, with somebody else's parser. The
                      format flags (php-format, ...) are copied from the export so
                      that msgfmt compares the placeholders too.

Units are matched by msgctxt and msgid, the identity gettext uses. msgctxt, msgid
and the #: line are copied exactly from the export, so that the platform can match
the units. Output is single-line — the lossless form.
"""
import datetime
import os
import subprocess

from . import po
from . import rounds
from .checks import run as check_run
from .errors import Error
from .messages import text


def collect(r):
    """The entries of the suggestion PO, in PO order.

    Raises Error as soon as building on would be dangerous: a broken batch, a unit
    already translated in the export, a source text that changed since prepare, or
    plural forms that do not fit the export.
    """
    translations, _, _, problems = r.batches()
    if problems:
        raise Error('ABORT: %d problems in the batches, first: %s '
                    '(run "status" or "check")' % (len(problems), problems[0]))
    units = r.units()
    source = {po.key(e): e for e in units}
    by_context = {po.context(e): e for e in units}
    nplurals = r.profile.nplurals

    entries, missing, changed = [], [], []
    for row in r.scaffold:
        nr = row['nr']
        if nr not in translations:
            continue
        s = source.get(rounds.key(row))
        if s is None:
            (changed if row['context'] in by_context else missing).append(row['context'])
            continue
        if po.is_translated(s):
            raise Error('ABORT: %s is already translated in the export' % row['context'])

        value = translations[nr]
        if s.get('id_plural'):
            if not isinstance(value, list) or len(value) != nplurals:
                raise Error('ABORT: #%d needs a list of %d plural forms (%s)'
                            % (nr, nplurals, row['context']))
            target = [po.match_edges(s['id'] if i == 0 else s['id_plural'], f)
                      for i, f in enumerate(value)]
        else:
            if isinstance(value, list):
                raise Error('ABORT: #%d has plural forms, the export unit %s has none'
                            % (nr, row['context']))
            target = po.match_edges(s['id'], value)

        entries.append({'ctxt': s.get('ctxt'), 'id': s['id'],
                        'id_plural': s.get('id_plural'), 'ref': s.get('ref'),
                        'flags': po.format_flags(s.get('flags')), 'target': target})
    if changed:
        raise Error('ABORT: %d source texts changed in the export since prepare, e.g. %s — '
                    'the translations were made for the old text; prepare a new round'
                    % (len(changed), changed[0]))
    if missing:
        raise Error('ABORT: %d units are missing from the export, e.g. %s'
                    % (len(missing), missing[0]))
    return entries


def round_trip(written, entries):
    """written: the units read back. Every msgstr must be identical, every msgid present."""
    back = {po.key(e): e for e in written}
    mismatches = []
    for e in entries:
        read = back.get(po.key(e))
        if read is None:
            mismatches.append((po.context(e), 'missing when read back'))
        elif po.translation(read) != e['target']:
            mismatches.append((po.context(e), 'msgstr differs'))
    return mismatches


def msgfmt(path):
    """Cross-check with an independent parser. If msgfmt is missing, say so."""
    try:
        p = subprocess.Popen(['msgfmt', '--check', '--statistics', '-o', os.devnull,
                              path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = p.communicate()[0].decode('utf-8', 'replace').strip()
        return p.returncode, out
    except OSError:
        return None, 'msgfmt not found — this cross-check was skipped'


def build(folder, disclosure=True, target=None, force=False):
    r = rounds.load(folder)
    entries = collect(r)
    if not entries:
        print('No translations in the batches — nothing to build.')
        return 1

    errors = check_run.collect(r)[2]['errors']
    if errors and not force:
        raise Error('ABORT: "check" reports %d errors — fix them, or build with --force '
                    'if you have looked at them and they are fine' % errors)

    source_header = r.header_fields()
    header = po.build_header(source_header, r.profile.language, r.profile.plural_forms,
                             extra={'Last-Translator': ''})

    preamble = ''
    if disclosure:
        preamble = text(r.lang, 'disclosure',
                        exported=datetime.date.fromtimestamp(
                            os.path.getmtime(r.export)).isoformat(),
                        revision=source_header.get('PO-Revision-Date', '')[:10])
        preamble = ''.join('# %s\n' % line if line else '#\n'
                           for line in preamble.split('\n'))

    path = target or r.suggestions_path()
    po.write(path, header, entries, preamble)

    plural = sum(1 for e in entries if e.get('id_plural'))
    print('%s' % path)
    rounds.print_drift(r)
    if errors:
        print('  WARNING: built with --force despite %d check errors' % errors)
    print('  %d units, %d with plural forms' % (len(entries), plural))
    print('  disclosure in header: %s' % ('yes' if disclosure else 'no'))

    written = po.units(path)
    mismatches = round_trip(written, entries)
    print('  round trip: %d mismatches' % len(mismatches))
    for key, what in mismatches[:5]:
        print('    %s — %s' % (key, what))

    translated = set(po.key(e) for e in r.units() if po.is_translated(e))
    overlap = translated & set(po.key(e) for e in written)
    print('  overlap with already translated units: %d' % len(overlap))

    code, out = msgfmt(path)
    print('  msgfmt: %s' % out.replace('\n', ' '))

    return 1 if (mismatches or overlap or code) else 0
