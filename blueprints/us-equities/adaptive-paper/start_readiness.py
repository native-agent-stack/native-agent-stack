"""Opt-in, exact registered extended-hours PAPER startup envelope.

This is an observation/readiness window, never an order-pricing permission.
"""
REGISTERED = {'window_seconds': 30, 'benchmark_quote_timeout_seconds': 5}


def validate_start_readiness(config):
    if 'extended_hours_start_readiness' not in config:
        return {}
    block = config['extended_hours_start_readiness']
    if (type(block) is not dict or set(block) != set(REGISTERED)
            or any(type(block[k]) is not int or block[k] != v for k, v in REGISTERED.items())):
        raise ValueError('invalid_extended_hours_start_readiness')
    if (config.get('regular_session_only') is not False
            or config.get('extended_hours_enabled') is not True
            or config.get('sessions', {}).get('extended_hours') is not True):
        raise ValueError('extended_hours_start_readiness_requires_extended_hours')
    return dict(block)


def start_readiness_settings(config, command, session):
    block = validate_start_readiness(config)
    return block if command == 'paper' and session in ('PRE', 'POST') else {}
