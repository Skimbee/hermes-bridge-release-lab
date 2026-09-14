"""Bounded, allowlisted diagnostics for disposable-lab update receipts only."""
import json
import re
import sys


SENSITIVE = re.compile(r'token|password|secret|api.?key|authorization|github_pat_|gh[pousr]_', re.I)


def text(value):
    if not isinstance(value, str):
        return None
    if SENSITIVE.search(value):
        return '[REDACTED]'
    return value[:1200]


def rows(value, keys):
    if not isinstance(value, list):
        return []
    return [{key: (entry.get(key) if type(entry.get(key)) is bool else None)
             if key == 'ok' else text(entry.get(key)) for key in keys}
            for entry in value[:80] if isinstance(entry, dict)]


def diagnostic(data):
    if not isinstance(data, dict):
        data = {}
    receipt = data.get('receipt', {})
    if not isinstance(receipt, dict):
        receipt = {}
    restart = receipt.get('gateway_restart') or {}
    if not isinstance(restart, dict):
        restart = {}
    fleet = receipt.get('fleet') or []
    if not isinstance(fleet, list):
        fleet = []
    action = data.get('action_status') or {}
    if not isinstance(action, dict):
        action = {}
    lines = action.get('lines') or []
    if isinstance(lines, str):
        lines = lines.splitlines()
    if not isinstance(lines, list):
        lines = []
    states = [text(row.get('state')) for row in fleet[:80] if isinstance(row, dict)]
    return {'outcome': text(receipt.get('outcome')),
            'exit_code': receipt.get('exit_code') if type(receipt.get('exit_code')) is int else None,
            'stop_reason': text(receipt.get('stop_reason')),
            'steps': rows(receipt.get('steps'), ('name', 'ok', 'detail')),
            'skips': rows(receipt.get('skips'), ('name', 'reason')),
            'gateway_restart': {
                'incomplete': restart.get('incomplete') if type(restart.get('incomplete')) is bool else None,
                'phase_error': text(restart.get('phase_error'))},
            'fleet_states': sorted({state for state in states if isinstance(state, str)}),
            'action_log_tail': [text(line) for line in lines[-60:]],
            'action_status_read_error': text(data.get('action_status_read_error'))}


if __name__ == '__main__':
    raw = sys.stdin.buffer.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise SystemExit('Diagnostic input exceeds bound')
    print(json.dumps(diagnostic(json.loads(raw))))
