"""Adapt retained SYN sources in memory for NEW r3 packets only.

Source: published seq2-replay test_wiring.Wiring.keyed/lifecycle and
test_unit_contracts.Units at a59e2fd2; CPython3.12.3 unittest loader/patch.
Neither archived tests nor the native launcher are rewritten by this adapter.
"""


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('unexpected_r3_replay_source_shape')
    return text.replace(old, new, 1)


def adapt_r3_replay(name, text):
    if name == 'test_wiring':
        text = replace_once(text, '        return 0\n\n    def token(',
            """        elif '--output' in argv:
            output=Path(argv[argv.index('--output')+1])
            output.write_text(json.dumps({'status':'passed'}))
        elif environment is not None and 'OUT_DIR' in environment:
            output=Path(environment['OUT_DIR'])/'paper-output.json'
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_text(json.dumps({'status':'passed'}))
        return 0

    def token(""")
    elif name == 'test_unit_contracts':
        text = replace_once(text, "('4500s' if stage=='pre' else '1200s')",
                            "('5150s' if stage=='pre' else '1850s')")
        text = replace_once(text, "'TimeoutStopSec=900s'", "'TimeoutStopSec=2140s'")
    if name in ('test_wiring', 'test_sequencing'):
        text = replace_once(text, "self.assertIn('scheduled_trial.sh',",
                            "self.assertIn('scheduled_trial_r3.sh',")
    return text


def driver(text):
    """Keep the reviewed driver/tripwires; insert only the SYN r3 adapter."""
    text = replace_once(text, '\ndef replay(bundle, launch, pointer_calls, attempts):',
                        '\nfrom replay_adapter import adapt_r3_replay\n\ndef replay(bundle, launch, pointer_calls, attempts):')
    return replace_once(text, '        text = path.read_text()\n',
                        '        text = adapt_r3_replay(name, path.read_text())\n'
                        '        if name in ("test_wiring", "test_sequencing", "test_unit_contracts"):\n'
                        '            adaptations.append(name + ": r3 paper output, scheduler and envelopes")\n')
