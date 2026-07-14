"""Errors raised while parsing a user-supplied FOLD file. Kept distinct from
generic exceptions so main.py can map exactly this class to a 422 response
with a human-readable message, instead of a 500 crash."""


class FoldValidationError(Exception):
    pass
