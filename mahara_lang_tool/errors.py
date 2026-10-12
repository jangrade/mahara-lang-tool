"""Errors the user has to fix.

The modules raise these; only the command line turns them into a message and an
exit code. That keeps the modules usable as a library and in tests.
"""


class Error(Exception):
    """Something in the round needs attention, e.g. a build that would be unsafe."""
    code = 1


class UsageError(Error):
    """A wrong call: missing round folder, export not found, broken profile."""
    code = 2
