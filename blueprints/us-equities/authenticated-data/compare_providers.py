#!/usr/bin/env python3
"""Supported entry point for the retained provider-neutral comparison recipe.

The September 23 receipt measured this exact implementation against the frozen
25-session AAPL control and retained IBM/SPY data. This entry point promotes
that measured recipe without changing the hash-bound original comparator.
"""
import importlib.util
from pathlib import Path


IMPLEMENTATION = (Path(__file__).resolve().parents[3] /
                  "blueprints/gap-wave2-20260923/us-equities__market-data-reference/compare_multi.py")


def load_comparator():
    spec = importlib.util.spec_from_file_location("market_data_comparator", IMPLEMENTATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    load_comparator().main()


if __name__ == "__main__":
    main()
