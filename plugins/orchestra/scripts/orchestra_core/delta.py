"""The one-line board delta: what moved between two `Engine.view` boards."""
import hashlib
import json


def _states(view):
    return {c['id']: c['state'] for c in (view or {}).get('cards', [])}


def signature(view):
    """A short digest of every card's id and state; it changes exactly when a card moves."""
    pairs = sorted(_states(view).items())
    return hashlib.sha256(json.dumps(pairs).encode()).hexdigest()[:16]


def delta(before_view, after_view):
    """`ID old>new, ...; state N, ...` for the cards that changed state, or None when none did. A new card moves from `-`."""
    if before_view is None or after_view is None:
        return None
    before, after = _states(before_view), _states(after_view)
    moves = ['%s %s>%s' % (i, before.get(i, '-'), s) for i, s in after.items() if before.get(i) != s]
    if not moves:
        return None
    counts = ', '.join('%s %d' % (s, n) for s, n in (after_view.get('counts') or {}).items() if n)
    return ', '.join(moves)+('; '+counts if counts else '')
