"""The one-line board delta: what moved between two `Engine.view` boards."""
import hashlib
import json
from pathlib import Path


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


PREFIX = 'Orchestra board: '


def ids(view, state):
    return [c['id'] for c in (view or {}).get('cards', []) if c.get('state') == state]


def next_command(view):
    """The command the board waits on: accept the first acceptable card (the reported ones for a view without
    `acceptable_now`), else record a reported code review card's receipt (F109), else wave the startable ones; None when none."""
    cards = (view or {}).get('cards', [])
    reviews = [c['id'] for c in cards if c.get('state') == 'reported' and c.get('role') == 'code-reviewer']
    reported = [i for i in ids(view, 'reported') if i not in reviews] if 'acceptable_now' not in (view or {}) \
        else list(view['acceptable_now'])
    if reported:
        return 'orchestra.py accept '+reported[0]
    if reviews:  # F109: a code review card is accepted by recording its receipt, never by `accept`
        return 'orchestra.py review --token TOKEN for %s (its receipt accepts it)' % reviews[0]
    startable = list((view or {}).get('startable_now') or [])
    return 'orchestra.py wave '+' '.join(startable) if startable else None


def live(view):
    """True for a board of an active run that has cards."""
    return isinstance(view, dict) and bool((view.get('session') or {}).get('active')) and bool(view.get('cards'))


def read(directory, name):
    """The JSON object stored under `directory/name`, or {} when it is missing or unreadable."""
    try:
        found = json.loads((Path(directory)/name).read_text())
        return found if isinstance(found, dict) else {}
    except (OSError, ValueError):
        return {}


def record(view):
    """The board-seen record both writers store: the signature and each card's state."""
    return {'signature': signature(view), 'cards': _states(view)}


def store(directory, name, view):
    """Record the board signature and each card's state under `directory/name`; a failed write is ignored."""
    try:
        from .paths import atomic
        atomic(Path(directory)/name, json.dumps(record(view)).encode())
    except Exception:
        pass


NO_FIT = 'no card fits the session model; you coordinate, accept and review'
WAIT = 'nothing can start now; accept and review the running work'


def track_text(view):
    """`Track: you run E2; side: H, M` for the first track step of the board, or the plain no-fit text when no card fits the
    session model; None when the board has no track."""
    steps = (view or {}).get('track') or []
    if not steps:
        return None
    first = steps[0]
    side = first.get('side') or []
    main = ('you run '+first['card'] if first.get('card') else 'you are running '+first['busy'] if first.get('busy')
            else WAIT if first.get('wait') else NO_FIT)
    return 'Track: '+main+('; side: '+', '.join(side) if side else '')


def line(view, seen):
    """`Orchestra board: ...` naming the moved cards (or, with no card states stored, the waiting ones) and the next
    command, or None when the board is not live or its signature equals the stored one."""
    if not live(view) or seen.get('signature') == signature(view):
        return None
    before = seen.get('cards')
    moved = delta({'cards': [{'id': i, 'state': s} for i, s in before.items()]}, view) if isinstance(before, dict) else None
    if moved is None:
        waits = [w+' '+', '.join(found) for w, found in (('reported', ids(view, 'reported')),
                                                         ('startable', list(view.get('startable_now') or []))) if found]
        moved = '; '.join(waits) or ', '.join('%s %d' % (s, n) for s, n in (view.get('counts') or {}).items() if n)
    command = next_command(view)
    track = track_text(view)
    return PREFIX+moved+('. Next: '+command if command else '')+('. '+track if track else '')
