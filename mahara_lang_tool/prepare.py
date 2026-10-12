"""Prepare a round: scaffold, batch files, brief.

The core is the order: the untranslated units are numbered in PO order, which is
exactly the order in which Weblate shows them under the filter `state:empty`.
Whoever puts batches and Weblate side by side can follow along — and notices at
once when they have slipped, instead of a hundred entries later.

For each unit, everything that helps with translating is collected:
  - the earlier translation from a previous export, by the same context (the
    project reworded the source text)
  - the translated field label, if it is a help text
  - glossary hits
  - example pairs from the same file, as a tone sample
"""
import datetime
import json
import os
import shutil

from . import __version__
from . import batches as batch_module
from . import corpus as corpus_module
from . import po
from . import rounds
from .errors import UsageError
from .messages import kind_label, text


def _previous_memory(path):
    """Translated units of an earlier export by context: where the project only
    reworded a source text, the old translation is a model for the new one."""
    if not path:
        return {}
    return {po.context(e): e for e in po.units(path) if po.is_translated(e)}


def _duplicates(units):
    """Units that share msgctxt and msgid. gettext forbids them; the build could not
    tell them apart."""
    seen, dup = set(), []
    for e in units:
        k = po.key(e)
        if k in seen:
            dup.append(po.context(e) or e['id'])
        seen.add(k)
    return dup


def build_scaffold(export, profile, previous=None):
    units = po.units(export)
    dup = _duplicates(units)
    if dup:
        raise UsageError('%s has %d duplicate units (same msgctxt and msgid), e.g. %s'
                         % (export, len(dup), dup[0]))
    corpus = corpus_module.Corpus(units)
    old_context = _previous_memory(previous)
    example_cache = {}

    rows = []
    todo = [e for e in units if not po.is_translated(e)]
    for nr, e in enumerate(todo, 1):
        ctxt = po.context(e)
        path, key = po.split_context(ctxt)
        source = e['id']

        model = old_context.get(ctxt)
        origin = 'same context, source reworded' if model else None

        label = corpus.label_for(ctxt, profile.help_suffix)
        if path not in example_cache:
            example_cache[path] = corpus.examples(path)

        rows.append({
            'nr': nr,
            'ctxt': e.get('ctxt') or '',
            'context': ctxt,
            'ref': e.get('ref', ''),
            'file': path,
            'key': key,
            'source': source,
            'source_plural': e.get('id_plural', ''),
            'html': '<' in source,
            'placeholders': profile.placeholder.findall(source),
            'edges': [source[:len(source) - len(source.lstrip())],
                      source[len(source.rstrip()):]],
            'previous': po.translation(model) if model else None,
            'previous_source': model['id'] if model else None,
            'previous_origin': origin,
            'label': label['str'] if label else None,
            'label_source': label['id'] if label else None,
            'glossary': [{'source': g['source'], 'target': g['target']}
                         for g in profile.glossary_hits(source)],
            'examples': example_cache[path],
        })
    return rows


def write_batches(rows, folder, profile, size, lang):
    os.makedirs(folder, exist_ok=True)
    parts = [rows[i:i + size] for i in range(0, len(rows), size)]
    width = max(2, len(str(len(parts))))
    written = 0
    for n, part in enumerate(parts, 1):
        path = os.path.join(folder, 'b%0*d.json' % (width, n))
        if os.path.exists(path):
            continue  # never overwrite work in progress
        files = sorted(set(r['file'] for r in part))
        about = text(lang, 'batch_about', n=n, total=len(parts), first=part[0]['nr'],
                     last=part[-1]['nr'], nplurals=profile.nplurals,
                     files=', '.join(files[:8]) + (' …' if len(files) > 8 else ''))
        batch_module.write_empty(path, part, profile.nplurals, about)
        written += 1
    return len(parts), written


def build_brief(rows, profile, check, batch_count, lang):
    def t(key, **kw):
        return text(lang, key, **kw)

    help_count = sum(1 for r in rows if r['key'].endswith(profile.help_suffix or '\0'))
    plural = sum(1 for r in rows if r['source_plural'])
    with_previous = sum(1 for r in rows if r['previous'])

    out = [t('brief_title', project=profile.project or 'Project',
             language=profile.language_name), '']
    out.append(t('brief_summary', units=len(rows), batches=batch_count,
                 help=help_count, plural=plural))
    if with_previous:
        out.append(t('brief_previous', n=with_previous))
    out += ['', t('brief_how_heading'), '']
    out.append(t('brief_how', nplurals=profile.nplurals, check=check))
    out.append('')
    if plural and profile.nplurals == 1:
        out += [t('brief_one_form'), '']

    if profile.guidelines:
        out += [t('brief_guidelines'), '']
        out += ['- %s' % g for g in profile.guidelines]
        out.append('')
    if profile.agent_notes:
        out += [t('brief_working'), '']
        out += ['- %s' % g for g in profile.agent_notes]
        out.append('')
    if profile.glossary:
        out += [t('brief_glossary'), '']
        out.append('| %s | %s | |' % (t('english'), profile.language_name))
        out.append('|---|---|---|')
        for g in profile.glossary:
            out.append('| %s | %s | %s |' % (g['source'], g['target'], g.get('note', '')))
        out.append('')
    out += [t('brief_checks_heading'), '', t('brief_checks'), '']
    if profile.blocks():
        out += [t('brief_blocking', kinds=', '.join(
            '%s "%s"' % (kind_label(lang, k), name) if name else kind_label(lang, k)
            for k, name in profile.blocks())), '']
    return '\n'.join(out) + '\n'


def _into_input(export, round_dir):
    """The export for this round: the one in input/, or a given one copied there."""
    if export is None:
        return rounds.find_export(round_dir)
    if not os.path.exists(export):
        raise UsageError('export not found: %s' % export)
    where = os.path.join(round_dir, rounds.INPUT)
    target = os.path.join(where, os.path.basename(export))
    if os.path.abspath(export) == os.path.abspath(target):
        return target
    os.makedirs(where, exist_ok=True)
    other = [n for n in os.listdir(where) if n.endswith('.po') and n != os.path.basename(export)]
    if other:
        raise UsageError('%s already holds %s — one export per round folder'
                         % (where, other[0]))
    shutil.copyfile(export, target)
    return target


def prepare(export, profile, round_dir, previous=None, batch_size=None, lang='en'):
    """export: a PO file to copy into input/, or None to take the one already there."""
    os.makedirs(round_dir, exist_ok=True)
    work = os.path.join(round_dir, rounds.WORK)
    if os.path.exists(os.path.join(work, rounds.SCAFFOLD)):
        existing = rounds.load(round_dir)
        given = export or rounds.find_export(round_dir)
        if rounds.checksum(given) != existing.config.get('export_sha256'):
            raise UsageError('%s already belongs to %s — use a new round folder for '
                             'another export' % (round_dir, existing.export))
    export = _into_input(export, round_dir)
    os.makedirs(work, exist_ok=True)
    os.makedirs(os.path.join(round_dir, rounds.OUTPUT), exist_ok=True)

    header = po.header_fields(po.header(export))
    profile.adopt(header)
    if not header.get('Language') and 'language' not in profile.data:
        raise UsageError('language unknown: neither %s nor the export header names it '
                         '— set "language" in the profile' % (profile.path or 'the profile'))
    size = batch_size or profile.batch_size

    rows = build_scaffold(export, profile, previous)
    if not rows:
        print('No untranslated units in %s' % export)
        return 1

    with open(os.path.join(work, rounds.SCAFFOLD), 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1, sort_keys=True)

    count, written = write_batches(rows, os.path.join(work, 'batches'), profile, size, lang)
    os.makedirs(os.path.join(work, 'corrections'), exist_ok=True)

    with open(os.path.join(work, 'brief.md'), 'w', encoding='utf-8') as f:
        f.write(build_brief(rows, profile, rounds.command('check', round_dir), count, lang))

    with open(os.path.join(work, rounds.CONFIG), 'w', encoding='utf-8') as f:
        json.dump({
            'export': rounds.relative(export, work),
            'export_sha256': rounds.checksum(export),
            'profile': rounds.relative(profile.path, work),
            'profile_sha256': rounds.checksum(profile.path),
            'previous': rounds.relative(previous, work),
            'batch_size': size,
            'units': len(rows),
            'lang': lang,
            'created': datetime.date.today().isoformat(),
            'tool_version': __version__,
        }, f, ensure_ascii=False, indent=1, sort_keys=True)

    print('%s' % round_dir)
    print('  input/          %s' % os.path.basename(export))
    print('  work/           %d untranslated units in %d batches of %d (%d new),'
          % (len(rows), count, size, written))
    print('                  brief.md with the instructions for the translator')
    print('  output/         suggestion PO and quality report, after build and report')
    return 0
