"""NOW.md: one short file with the present state of a run, rewritten from the board view."""
import os
import tempfile

from .delta import next_command

MAX_CARDS = 50
MAX_FILES = 3
HEADER = ['# Orchestra now', 'Rewritten by the engine; do not edit.']


def _line(card):
    who = [card['worker']] if card.get('worker') else []
    if card.get('inline'):
        who.append('inline')
    files = list(card.get('files') or [])
    shown = ', '.join(files[:MAX_FILES])+(' +%d' % (len(files)-MAX_FILES) if len(files) > MAX_FILES else '')
    text = '- %s %s/%s %s%s files: %s' % (card['id'], card['role'], card['mode'], card['state'],
                                          ' (%s)' % ', '.join(who) if who else '', shown)
    return text+('; waits on: '+', '.join(card['deps_open']) if card.get('deps_open') else '')


def render(view):
    """Markdown of at most 60 lines for an `Engine.view()` dict."""
    view = view if isinstance(view, dict) else {}
    cards = view.get('cards') or []
    if not (view.get('session') or {}).get('active') or not cards:
        return '\n'.join(HEADER+['No active run.'])+'\n'
    run = view['session']
    opened = sorted((c for c in cards if c.get('state') != 'accepted'), key=lambda c: c.get('seq') or 0)
    lines = HEADER+['Run: active, size %s, autonomy %s' % (run.get('size'), 'armed' if (view.get('autonomy') or {}).get('active') else 'off')]
    lines += [_line(c) for c in opened[:MAX_CARDS]]
    if len(opened) > MAX_CARDS:
        lines.append('+%d more' % (len(opened)-MAX_CARDS))
    lines.append('Next: '+(next_command(view) or 'none'))
    lines.append('Accepted: %d cards' % (len(cards)-len(opened)))
    return '\n'.join(lines)+'\n'


def refresh(engine):
    """Write `NOW.md` in the engine state directory atomically; True on success, False on any failure."""
    try:
        text = render(engine.view())
        fd, name = tempfile.mkstemp(dir=engine.state_dir, prefix='.now-')
        try:
            with os.fdopen(fd, 'w') as handle:
                handle.write(text)
            os.replace(name, engine.state_dir / 'NOW.md')
        except BaseException:
            try:
                os.unlink(name)
            except OSError:
                pass
            raise
        return True
    except Exception:
        return False
