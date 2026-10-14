"""Extend the landed native retirement checker locally to the installed flat generation.

The shared seq3 inventory file is deliberately left for its separate PR.
"""
from types import FunctionType
from seq2_retirement import STAGES, assert_retired as original_retired

PATHS = tuple('paper-ready-' + stage + '-8c95a50d-seq2-flat.path' for stage in STAGES)


def assert_retired():
    original = original_retired()
    # Execute the exact landed checker with a private globals dictionary, so
    # its original PATHS and any concurrent reader are never changed.
    flat_check = FunctionType(original_retired.__code__,
                              {**original_retired.__globals__, 'PATHS': PATHS})
    return original + flat_check()
