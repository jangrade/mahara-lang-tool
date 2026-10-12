"""Command line.

    mahara-lang-tool next    [--round NAME]
    mahara-lang-tool find    [--source RE] [--target RE] [--export EXPORT.po] [--limit N]
    mahara-lang-tool analyze --export EXPORT.po [--profile P.json] [--out R.md] [--json R.json]
    mahara-lang-tool prepare --profile P.json [--export EXPORT.po] [--round DIR] [--previous OLD.po]
    mahara-lang-tool status  [--round DIR]
    mahara-lang-tool check   [--round DIR] [--errors-only]
    mahara-lang-tool build   [--round DIR] [--no-disclosure] [--out FILE.po] [--force]
    mahara-lang-tool report  [--round DIR] [--lang de]

The round folder (default: the current one) holds input/ with the export, work/ with
everything the translator needs, and output/ with the results.

Exit codes: 0 fine, 1 findings or problems that need attention, 2 usage error.
"""
import argparse
import sys

from . import __version__
from .errors import Error
from .messages import LANGUAGES


def _profile(path):
    from . import profile
    return profile.load(path)


def cmd_analyze(a):
    from . import analyze
    from .checks import structure
    p = _profile(a.profile)
    d, body = analyze.run(a.export, p, a.out, a.json, a.lang)
    if not a.out:
        sys.stdout.write(body)
        return 0
    z = d['counts']
    print('%s' % a.out)
    print('  %d units, %d translated, %d untranslated'
          % (z['units'], z['translated'], z['untranslated']))
    print('  %d source texts translated inconsistently' % len(d['inconsistent']))
    print('  %d collisions' % len(d['collisions']))
    for kind in sorted(d['defects']):
        entries = d['defects'][kind]
        errors = sum(1 for m in entries if m['severity'] == structure.ERROR)
        print('  %s: %d errors, %d notes' % (kind, errors, len(entries) - errors))
    if a.json:
        print('%s' % a.json)
    return 0


def _the_export():
    """The newest export under input/ of this folder or its rounds."""
    import glob
    import os
    found = glob.glob('input/*.po') + glob.glob('*/input/*.po')
    if not found:
        from .errors import UsageError
        raise UsageError('no export under input/ here: name it with --export')
    newest = max(found, key=os.path.getmtime)
    if len(found) > 1:
        print('(searching %s, the newest export; --export names another)' % newest)
    return newest


def cmd_find(a):
    from . import find
    state = 'translated' if a.translated else 'untranslated' if a.untranslated else 'all'
    return find.run(a.export or _the_export(), a.source, a.target, state, a.limit,
                    a.ignore_case)


def cmd_prepare(a):
    from . import prepare
    return prepare.prepare(a.export, _profile(a.profile), a.round, a.previous,
                           a.batch_size, a.lang)


def cmd_status(a):
    from . import rounds
    return rounds.status(a.round)


def cmd_check(a):
    from .checks import run
    return run.check(a.round, errors_only=a.errors_only)


def cmd_build(a):
    from . import build
    return build.build(a.round, disclosure=not a.no_disclosure, target=a.out,
                       force=a.force)


def cmd_report(a):
    from . import report
    return report.write(a.round, lang=a.lang)


def cmd_next(a):
    from . import guide
    return guide.run('.', a.round)


def parser():
    p = argparse.ArgumentParser(
        prog="mahara-lang-tool",
        description='Prepare, check and build translation rounds for gettext PO files.')
    p.add_argument('--version', action='version', version='mahara-lang-tool ' + __version__)
    sub = p.add_subparsers(dest='command')

    a = sub.add_parser('next', help='say what to do now (run it in the language folder)')
    a.add_argument('--round', help='the round to work on, if several are unfinished')
    a.set_defaults(fn=cmd_next)

    a = sub.add_parser('analyze', help='count and assess the existing translations of an export')
    a.add_argument('--export', required=True, help='PO file exported from the platform')
    a.add_argument('--profile', help='language profile (JSON); without it, structure only')
    a.add_argument('--out', help='write the report as Markdown; otherwise to stdout')
    a.add_argument('--json', help='also write the raw data as JSON')
    a.add_argument('--lang', choices=LANGUAGES, default='en', help='report language')
    a.set_defaults(fn=cmd_analyze)

    a = sub.add_parser('find', help='show and count units of an export by pattern')
    a.add_argument('--source', help='regular expression for the English text (any case)')
    a.add_argument('--target', help='regular expression for the translation')
    a.add_argument('--ignore-case', action='store_true', help='for --target')
    a.add_argument('--translated', action='store_true', help='only translated units')
    a.add_argument('--untranslated', action='store_true', help='only untranslated units')
    a.add_argument('--export', help='PO file (default: the one export under input/)')
    a.add_argument('--limit', type=int, default=10, help='units to show (default: 10)')
    a.set_defaults(fn=cmd_find)

    a = sub.add_parser('prepare', help='create scaffold, batches and brief for a round')
    a.add_argument('--profile', required=True, help='language profile (JSON)')
    a.add_argument('--export', help='PO file exported from the platform; copied into '
                                    'input/ (default: the one already in input/)')
    a.add_argument('--round', default='.',
                   help='round folder, created if missing (default: current folder)')
    a.add_argument('--previous', help='export of an earlier version, used as memory')
    a.add_argument('--batch-size', type=int, help='units per batch (default: from profile, 80)')
    a.add_argument('--lang', choices=LANGUAGES, default='en',
                   help='language of brief and reports for this round')
    a.set_defaults(fn=cmd_prepare)

    a = sub.add_parser('status', help='progress per batch')
    a.add_argument('--round', default='.', help='round folder (default: current folder)')
    a.set_defaults(fn=cmd_status)

    a = sub.add_parser('check', help='check the drafts against the source')
    a.add_argument('--round', default='.', help='round folder (default: current folder)')
    a.add_argument('--errors-only', action='store_true')
    a.set_defaults(fn=cmd_check)

    a = sub.add_parser('build', help='write the suggestion PO')
    a.add_argument('--round', default='.', help='round folder (default: current folder)')
    a.add_argument('--no-disclosure', action='store_true',
                   help='leave out the comment on origin (language model) in the header')
    a.add_argument('--out', help='target file (default: output/suggestions-LANG.po)')
    a.add_argument('--force', action='store_true',
                   help='build even though "check" reports errors')
    a.set_defaults(fn=cmd_build)

    a = sub.add_parser('report', help='write the quality report')
    a.add_argument('--round', default='.', help='round folder (default: current folder)')
    a.add_argument('--lang', choices=LANGUAGES, help='default: the round\'s language')
    a.set_defaults(fn=cmd_report)
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    if not args.command:
        p.print_help()
        return 2
    try:
        return args.fn(args) or 0
    except Error as e:
        sys.stdout.flush()
        print(str(e), file=sys.stderr)
        return e.code
