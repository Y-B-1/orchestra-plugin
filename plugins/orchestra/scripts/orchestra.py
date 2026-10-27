#!/usr/bin/env python3
"""Portable Orchestra CLI. Each command prints a JSON receipt."""
import os
import subprocess
import sys

if os.name == 'nt' and not sys.flags.utf8_mode:
    # Windows opens text files in the locale encoding unless Python runs in UTF-8 mode: run again in it.
    raise SystemExit(subprocess.call([sys.executable, '-X', 'utf8', *sys.argv]))
import argparse
import contextlib
import io
import functools
import json
import os
from pathlib import Path
import shlex
import math
import subprocess
import sys
import uuid

from orchestra_core import briefs, cli_support, delta, ledger, now, portable
from orchestra_core.engine import ACTIVE_MISMATCH, ASKS_ERROR, SIZES, Engine, EngineError
from orchestra_core.guards import classify_command
from orchestra_core.paths import atomic, load_policy, main_checkout, repository, state_location

ROOT = Path(__file__).resolve().parents[1]
# Commands that add one `board` line to their JSON when a card changed state.
BOARD_COMMANDS = {'add','dispatch','inline','wave','report','accept','criterion','review','park','cancel','unpark','hold','replace','resume'}
# No parser takes an abbreviated option: `--leas` must not parse as `--lease`, which the refusal log strips.
STRICT_PARSER = functools.partial(argparse.ArgumentParser, allow_abbrev=False)


def read_text(path):
    """A file's text; a missing or unreadable file is an engine error that names the path."""
    try:
        return Path(path).read_text()
    except FileNotFoundError:
        raise EngineError('File not found: ' + str(path)) from None
    except OSError as exc:
        raise EngineError('Cannot read %s: %s' % (path, exc.strerror or exc)) from None


def read_json(path):
    return json.loads(read_text(path))


def parser():
    p = STRICT_PARSER(description=__doc__)
    p.add_argument('--repo', default=os.getcwd())
    p.add_argument('--state', help='External run directory; defaults to user state for this repository')
    p.add_argument('--actor', default='main', help='Workflow identity, not an authenticated principal')
    p.add_argument('--lease', help='Coordinator lease returned by start')
    sub = p.add_subparsers(dest='command', required=True, parser_class=STRICT_PARSER)
    start = sub.add_parser('start')
    start.add_argument('--policy', help='Explicit JSON policy; copied outside the application')
    start.add_argument('--harness-session', help='Harness session id (from the SessionStart context); ending that session releases the run')
    start.add_argument('--size', choices=list(SIZES), help='Size of the largest ask in the request (required when '
                       'this opens a new run): tiny up to 50 changed lines, medium up to 400; large only with --owner-request')
    start.add_argument('--asks', help='Number of separately stated asks (default 1); the size-check budget is the tier guide times it')
    start.add_argument('--owner-request', action='store_true', help='The owner asked for a map: allows a large start and plan cards')
    start.add_argument('--items', type=int, help='The 2.4 flag; refused, start with --size')
    start.add_argument('--recover', action='store_true', help='Take back the lease of the run this harness session already owns '
                       '(needs --harness-session); running cards keep their assignments')
    start.add_argument('--take-over', action='store_true', help='With --recover: move an ended or interrupted run owned by another '
                       'session to this one (logged in progress.md; arms nothing)')
    start.add_argument('--new-run', action='store_true', help='Archive a previously inactive run before starting')
    sub.add_parser('where', help='Print the repository, state directory and whether standing-orders.md exists')
    for name in ['ready','interrupt','scan']:
        sub.add_parser(name)
    finish = sub.add_parser('finish', help='Check and close the run')
    finish.add_argument('--accept-reported', action='store_true',
                        help='First accept every reported card whose accept passes; the rest stay reported')
    do = sub.add_parser('do', help='Run several coordinator commands in one call, in order, with this call\'s --lease; '
                        'stops at the first refusal and keeps the earlier steps. Each step is one quoted command, e.g. '
                        'do "accept B1" "wave --inline B3 B4"')
    do.add_argument('steps', nargs='+')
    status = sub.add_parser('status', help='Print the run state; review receipts leave out their per-file entries')
    status.add_argument('--brief', action='store_true', help='Print a compact summary instead (counts, running, reported, lease, autonomy, versions); no lease, read-only')
    status.add_argument('--full', action='store_true', help='Keep the per-file entries of review receipts')
    board = sub.add_parser('board', help='Print card ids by role and state; --view prints the cheap lease-free board the Kanban mod reads')
    board.add_argument('--view', action='store_true')
    board.add_argument('--session', help='With --view: the harness session id; `bound` says whether it owns the run (the id is never printed)')
    sub.add_parser('waves', help='Print overlaps, unmet prerequisites, ordered waves and the cards that can start now; no lease, read-only')
    sub.add_parser('worktrees', help='Print leftover worktrees under .claude/worktrees (branch, card, landed, clean) and the removal commands for landed clean ones; no lease, read-only')
    sub.add_parser('brief', help='Print the newest run brief; no lease, read-only')
    refusals = sub.add_parser('refusals', help='Print the newest refused commands (exit 2) from the refusal log; no lease, read-only')
    refusals.add_argument('--last', type=int, default=10, help='How many entries (default 10)')
    art = sub.add_parser('artifact', help='Print the whole-repo artifact, or with --tasks the artifact scoped to those cards\' reserved files')
    art.add_argument('--tasks', help='Comma-separated task IDs')
    sub.add_parser('prepr', help='Print the pre-PR size check and reviewer choice; no lease, read-only')
    route = sub.add_parser('route', help='Change the size tier (--size, optionally --asks), or on a 2.4 run the item count '
                                         '(--items; 1 to 5 inline, 6 or more workflow), and log the reason')
    route.add_argument('--size', choices=list(SIZES))
    route.add_argument('--asks', help='With --size: the new count of separately stated asks; default keeps the current count')
    route.add_argument('--items', type=int, help='2.4 runs only')
    route.add_argument('--reason', required=True)
    add = sub.add_parser('add', help='Add a card from a task JSON file. Inline route: no designer-planner plan card. '
                                     'Order cards with dependencies')
    add.add_argument('task', help='Task JSON path')
    replace = sub.add_parser('replace', help='Add a card from a task JSON file in place of a queued, reported or parked card: '
                             'dependencies and review targets move to the new card and the old one is cancelled, in one step')
    replace.add_argument('old', metavar='OLD', help='Card to replace')
    replace.add_argument('task', help='Task JSON path of the new card')
    dispatch = sub.add_parser('dispatch')
    dispatch.add_argument('task_id')
    dispatch.add_argument('worker', nargs='?', help='Worker name; default orchestra-TASK_ID')
    dispatch.add_argument('--serial', metavar='REASON', help='Start this card alone although others could start beside it; the reason is logged')
    dispatch.add_argument('--helper', metavar='REASON', help='Why a helper does this builder card instead of the main session: '
                          'required for a tiny unit on a size run, and for a 2.4 inline route. 2.4 workflow route: a builder '
                          'card needs an accepted designer-planner plan card first')
    inline = sub.add_parser('inline', help='Reserve a card for execution by the main coordinator')
    inline.add_argument('task_id')
    inline.add_argument('--report', metavar='FILE', help='Also record this result file as the report, in the same step; a refused report reserves nothing')
    inline.add_argument('--accept', action='store_true', help='With --report: also accept the card in the same step')
    inline.add_argument('--serial', metavar='REASON', help='Start this card alone although others could start beside it; the reason is logged')
    wave = sub.add_parser('wave', help='Start every named card in one step, all or none; at most one is --inline')
    wave.add_argument('task_ids', nargs='+', metavar='ID')
    wave.add_argument('--inline', metavar='ID', help='The card the main session runs')
    wave.add_argument('--helper', metavar='REASON', help='Why helpers do builder cards on a size run or inline route')
    wave.add_argument('--serial', metavar='REASON', help='Start a single card alone although others could start beside it; the reason is logged')
    wave.add_argument('--emit', action='store_true', help='After the start, print per card the agent type, brief path, prompt and agent() call')
    card = sub.add_parser('card', help='Print the brief skeleton for a card; no lease, read-only')
    card.add_argument('task_id')
    card.add_argument('--out', metavar='FILE', help='Write the brief to FILE')
    ledger_ = sub.add_parser('ledger', help='Print BUILD-LEDGER rows for accepted cards from engine facts; no lease, read-only')
    ledger_.add_argument('--cards', help='Comma-separated task IDs (default: every accepted card)')
    package = sub.add_parser('package', help='Write brief, report, self-review and diff stat for a card under <state>/packages/TASK; no lease')
    package.add_argument('task_id')
    report = sub.add_parser('report')
    report.add_argument('worker')
    report.add_argument('token')
    report.add_argument('report', help='Nonempty result file')
    report.add_argument('--accept', action='store_true', help='Inline cards only: record the report and accept the card in one call; needs --lease')
    report.add_argument('--lease', default=argparse.SUPPRESS, help='Coordinator lease, for --accept')
    criterion = sub.add_parser('criterion', help='Record coordinator evidence on one unmet self-review criterion of a reported worker card')
    criterion.add_argument('task_id')
    criterion.add_argument('criterion', help='The criterion text, as the report repeats it')
    criterion.add_argument('--evidence', required=True, metavar='TEXT', help='What you checked, at most 1000 characters')
    accept = sub.add_parser('accept')
    accept.add_argument('task_id')
    accept.add_argument('--ruling', metavar='TEXT', help='Accept a worker card whose only gaps are unmet criteria or failing checks the text '
                        'names (its command or test), with the coordinator reason')
    review = sub.add_parser('review')
    review.add_argument('report', nargs='?', help='Structured review JSON path; with --token and no path, the report '
                        'captured for the token')
    review.add_argument('--token', help='Assignment token of the final review card: report it, record the receipt and '
                        'accept the card in one step (a final receipt, a critic receipt or a fix re-review)')
    review.add_argument('--defer-out-of-scope', metavar='REASON', help='With --token: record each out-of-scope item as '
                        'deferred to a brief, with REASON')
    gate = sub.add_parser('gate')
    gate.add_argument('name')
    gate.add_argument('--again', action='store_true', help='Rerun a gate that already passed on this artifact')
    gate.add_argument('--timeout', type=float, help='Seconds for this run; overrides gate_timeout_seconds')
    gate.add_argument('argv', nargs=argparse.REMAINDER)
    finding = sub.add_parser('finding', help='Record or list dispositions of review findings')
    findings = finding.add_subparsers(dest='finding_command', required=True, parser_class=STRICT_PARSER)
    fadd = findings.add_parser('add')
    fadd.add_argument('--review', required=True)
    fadd.add_argument('--kind', required=True, choices=['finding', 'out_of_scope'])
    fadd.add_argument('--index', required=True, type=int)
    fadd.add_argument('--disposition', required=True)
    fadd.add_argument('--reason', required=True)
    fadd.add_argument('--card')
    flist = findings.add_parser('list')
    flist.add_argument('--for-brief', action='store_true')
    for name in ['permit','release']:
        action = sub.add_parser(name)
        action.add_argument('remote')
        action.add_argument('target')
    autonomy = sub.add_parser('autonomy', help='Arm, disarm or inspect the autonomous loop; takes no lease')
    autonomy.add_argument('action', choices=['arm','disarm','status'])
    park = sub.add_parser('park', help='Set a card aside at an approval boundary')
    park.add_argument('task_id')
    park.add_argument('--reason', required=True)
    cancel = sub.add_parser('cancel', help='Drop a queued or parked card that should never run')
    cancel.add_argument('task_id')
    cancel.add_argument('--reason', required=True)
    own = sub.add_parser('own', help='Add one owned path to a running or reported builder card when no other card holds it')
    own.add_argument('action', choices=['add'])
    own.add_argument('task_id')
    own.add_argument('path')
    unpark = sub.add_parser('unpark', help='Return a parked card to the queue')
    unpark.add_argument('task_id')
    resume = sub.add_parser('resume', help='Send a reported card back to its worker: running again, same token; its report is kept as history')
    resume.add_argument('task_id')
    hold = sub.add_parser('hold', help='End the repair ladder: move a blocked repair chain to held and log the finding')
    hold.add_argument('task_id')
    hold.add_argument('--finding', required=True)
    pr = sub.add_parser('pr', help='Record a pull request the run opened; the run brief lists it for the owner')
    pr.add_argument('url')
    pr.add_argument('--task', action='append', help='A card this pull request carries; repeat for more than one')
    base = sub.add_parser('base', help='Print the branch a card\'s pull request is based on; no lease, read-only')
    base.add_argument('task_id')
    classify = sub.add_parser('classify')
    classify.add_argument('shell_command')
    return p


def without_entries(receipt):
    """A review receipt as printed: its per-file `entries` digests stay in state.json only."""
    receipt.pop('entries',None)
    return receipt


def parse_asks(text):
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        raise EngineError(ASKS_ERROR) from None


def archive_inactive(state,engine):
    with (state/'state.lock').open('a') as stream:
        portable.lock(stream)
        source = state/'state.json'
        if not source.exists():
            return
        try:
            old = read_json(source)
            if not isinstance(old,dict):
                raise ValueError('not a JSON object')
        except ValueError:  # A truncated, garbled or non-object file: keep it for inspection and let a new run start
            kept = state/'history'/('unreadable-'+uuid.uuid4().hex+'.json')
            kept.parent.mkdir(parents=True,exist_ok=True)
            source.replace(kept)
            return
        if (old.get('session') or {}).get('active'):
            if old.get('repo') != str(engine.repo) or not engine.binds(old):
                raise EngineError(ACTIVE_MISMATCH)  # O35: same recovery as the engine gives
            raise EngineError('Stop or finish the active run before starting another')
        auto = old.get('autonomy')
        approval = old.get('approval')
        if (isinstance(auto,dict) and 'report' in auto and old.get('run_id') is not None
                and not (isinstance(approval,dict) and approval.get('run') == old['run_id'])):
            raise EngineError('New run refused: autonomy kept a report for run %s and the owner has not approved it; type approved '
                              "in the owner's session, or run orchestra.py autonomy disarm in a terminal" % old['run_id'])
        archive = {'state':old,'policy':load_policy(state)}
        atomic(state/'history'/('run-'+uuid.uuid4().hex+'.json'),json.dumps(archive,indent=2).encode())
        source.unlink()  # Receipts and logs remain at their existing immutable paths.


def execute(args):
    if args.command == 'classify':
        return classify_command(args.shell_command).__dict__,0
    repo = repository(args.repo)
    state = Path(args.state).expanduser().resolve() if args.state else state_location(repo)
    if args.command=='where':
        try:
            mode = (load_policy(state) or {}).get('guard_mode','minimal')
        except ValueError:
            mode = 'minimal'
        return {'repo':str(repo),'state':str(state),'standing_orders':(state/'standing-orders.md').is_file(),'guard_mode':mode},0
    if not args.state:  # F7: a linked worktree has no run of its own while the main checkout has one
        main = main_checkout(repo)
        if main and not (state/'state.json').exists() and (state_location(main)/'state.json').exists():
            raise EngineError('This is a linked worktree with no run of its own; the run lives in the main checkout %s: '
                              'run the command with --repo %s' % (main,shlex.quote(str(main))))
    if args.command=='refusals':  # lease-free and read-only; reads the log and nothing else
        return {'refusals':cli_support.read_refusals(state,args.last)},0
    if args.command=='start' and args.policy:
        policy = read_json(args.policy)
        if not isinstance(policy,dict) or policy.get('schema_version') != 1:  # the rule load_policy applies later
            raise EngineError('Invalid project policy: --policy needs a JSON object with schema_version 1')
    else:
        policy = load_policy(state)
    engine = Engine(state,repo,policy)
    args.state_dir, args.board_before = state, None
    if args.command in BOARD_COMMANDS:
        try:
            args.board_before = engine.view(args.actor)
        except Exception:  # no readable board: the command reports its own error
            pass
    args.engine = engine
    if args.command=='start':
        if args.items is not None:
            raise EngineError('--items is the 2.4 flag; start with --size')
        if args.take_over and not args.recover:
            raise EngineError('--take-over needs --recover')
        if args.recover:
            if args.new_run or args.size or args.asks or args.owner_request:
                raise EngineError('--recover takes only --harness-session')
            return {'lease':engine.recover_lease(args.actor,args.harness_session,take_over=args.take_over),'state':str(state),'repo':str(repo)},0
        asks = parse_asks(args.asks)
        if args.new_run:  # refuse before archiving, so the ended run stays in place
            engine._check_start(args.size,asks,args.owner_request)
            engine._check_identity(args.actor,args.harness_session)
            archive_inactive(state,engine)
        try:
            lease = engine.open_session(args.actor,args.harness_session,
                                        size=args.size,asks=asks,owner_request=args.owner_request,require_size=True)
        except EngineError as exc:
            if str(exc).startswith('Malformed run state'):
                raise EngineError(str(exc)+'. Start over with `start --new-run ...`; the unreadable file is kept in '+str(state/'history'))
            raise
        if args.policy:
            atomic(state/'policy.json',(json.dumps(policy,indent=2)+'\n').encode())
        return {'lease':lease,'state':str(state),'repo':str(repo),'requeued':engine.requeued,'resume':engine.resume},0
    if args.command=='status' and args.brief:  # lease-free and read-only
        return engine.status_brief(),0
    if args.command=='status':
        result = engine.status(lenses=True)
        if not args.full:
            for receipt in result['reviews']:
                without_entries(receipt)
        return result,0
    if args.command=='prepr':  # lease-free and read-only, like status
        result=engine.prepr()
        if result['warning']:
            print(result['warning'],file=sys.stderr)
        return result,0
    if args.command=='brief':  # lease-free and read-only, like status
        text=engine.brief()
        return ({'brief':text} if text else {'brief':None,'message':'No run brief yet'}),0
    if args.command=='base':  # lease-free and read-only; one plain line, exit 2 when the card must wait
        print(engine.base(args.task_id))
        return None,0
    if args.command=='autonomy':  # O8: no lease, so the ledger is armed from outside the run
        if args.action=='arm':
            return engine.arm_autonomy(),0
        return {'disarm':engine.disarm_autonomy,'status':engine.autonomy_status}[args.action](),0
    if args.command=='artifact':
        ids=[i for i in (args.tasks or '').split(',') if i]
        if args.tasks is not None and not ids:
            raise EngineError('--tasks needs at least one task id')
        return engine.artifact(engine.scope_for(ids) if ids else None),0
    if args.command=='inline' and args.accept and not args.report:
        raise EngineError('inline --accept needs --report FILE')
    if args.command=='inline' and args.report:
        if not args.lease:
            raise EngineError('Supply the coordinator lease from start for coordinator actions')
        result = engine.start_inline_report(args.actor,args.lease,args.task_id,read_text(args.report),accept=args.accept,serial=args.serial)
        return dict(result,executor=args.actor,inline=True),0
    if args.command=='inline':
        return {'token':engine.start_inline(args.actor,args.lease,args.task_id,serial=args.serial), 'executor':args.actor, 'inline':True},0
    if args.command=='finding' and args.finding_command=='list':  # lease-free, like status
        result = engine.list_findings(args.for_brief)
        return ({'findings':result} if isinstance(result,str) else result),0
    if args.command=='card':  # lease-free and read-only; --out writes only the file it names
        text=briefs.card(engine,args.task_id)
        if args.out:
            atomic(Path(args.out).expanduser().resolve(),text.encode())
            return {'path':str(Path(args.out).expanduser().resolve())},0
        return {'brief':text},0
    if args.command=='ledger':  # lease-free and read-only
        return {'ledger':ledger.rows(engine,[i for i in (args.cards or '').split(',') if i] or None)},0
    if args.command=='package':  # lease-free; writes only under <state>/packages
        return {'package':str(ledger.package(engine,args.task_id))},0
    if args.command=='worktrees':  # lease-free and read-only; prints the removal commands, never runs them
        return engine.worktrees(),0
    if args.command=='waves':  # lease-free and read-only, like status
        return engine.waves(args.actor),0
    if args.command=='board' and args.view:  # lease-free; from an allowlist, no lenses or hashing
        return engine.view(args.actor,args.session),0
    if args.command=='board':
        cards = engine.status()['tasks'].values()
        board = {}
        for card in cards:
            board.setdefault(card['role'],{}).setdefault(card['state'],[]).append(card['id'])
        leftover = engine.worktrees()['leftover']
        if leftover:
            board['leftover_worktrees'] = leftover
        return board,0
    if args.command=='report' and args.accept:
        if not args.lease:
            raise EngineError('report --accept needs --lease from start')
        return engine.report_accept(args.actor,args.lease,args.worker,args.token,read_text(args.report)),0
    if args.command=='report':
        engine.report(args.worker,args.token,read_text(args.report))
        return {'reported':args.token},0
    if not args.lease:
        raise EngineError('Supply --lease from start for coordinator actions')
    if args.command=='ready':
        return {'ready':engine.ready(args.actor,args.lease)},0
    if args.command in ['interrupt','finish']:
        if args.command=='finish':
            engine.close_session(args.actor,args.lease,accept_reported=args.accept_reported)
        else:
            engine.interrupt(args.actor,args.lease)
        return {'session':args.command,'state':str(state)},0
    if args.command=='add':
        warned=engine.add_task(args.actor,args.lease,read_json(args.task)) or {}
        return {'added':read_json(args.task)['id'],**warned},0
    if args.command=='replace':
        task = read_json(args.task)
        warned=engine.replace_task(args.actor,args.lease,args.old,task) or {}
        return {'replaced':args.old,'by':task['id'],**warned},0
    if args.command=='resume':
        engine.resume_card(args.actor,args.lease,args.task_id)
        return {'resumed':args.task_id},0
    if args.command=='dispatch':
        worker = args.worker if args.worker is not None else 'orchestra-'+args.task_id
        token = engine.dispatch(args.actor,args.lease,args.task_id,worker,helper=args.helper,serial=args.serial)
        return {'assignment':token,'task':args.task_id,'worker':worker},0
    if args.command=='wave':
        prepared = briefs.prepare(engine,args.task_ids,args.inline) if args.emit else None  # refuses before any card starts
        result = engine.wave(args.actor,args.lease,args.task_ids,inline=args.inline,helper=args.helper,serial=args.serial)
        if prepared is not None:
            engine.record_bases(args.actor,args.lease,args.task_ids if args.inline is None or args.inline in args.task_ids else [args.inline,*args.task_ids],prepared['base'])
            result['emit'] = briefs.emit(engine,prepared,result)
        return result,0
    if args.command=='accept':
        engine.accept(args.actor,args.lease,args.task_id,ruling=args.ruling)
        return {'accepted':args.task_id},0
    if args.command=='criterion':
        engine.record_criterion(args.actor,args.lease,args.task_id,args.criterion,args.evidence)
        return {'criterion':args.task_id},0
    if args.command=='review':
        if args.report is None:
            if not args.token:
                raise EngineError('review needs a report path or --token')
            result = engine.review_with_token(args.actor,args.lease,args.token,None,args.defer_out_of_scope)
            without_entries(result['receipt'])
            return result,0
        review = read_json(args.report)
        if not isinstance(review,dict):
            raise EngineError('Review report must be a JSON object')
        missing = [k for k in ('reviewer','categories','tasks','final','findings') if k not in review]
        if missing:
            raise EngineError('Review report is missing: '+', '.join(missing))
        if args.defer_out_of_scope is not None and not args.token:
            raise EngineError('--defer-out-of-scope needs --token')
        if args.token:
            result = engine.review_with_token(args.actor,args.lease,args.token,args.report,args.defer_out_of_scope)
            without_entries(result['receipt'])
            return result,0
        result = engine.record_review(args.actor,args.lease,review['reviewer'],args.report,
                                     review['categories'],review['tasks'],review['final'],review['findings'])
        return without_entries(result),0
    if args.command=='gate':
        argv, again, timeout = args.argv, args.again, args.timeout
        while argv[:1] in (['--again'], ['--timeout']):  # REMAINDER swallows flags written after NAME
            if argv[0]=='--again':
                argv, again = argv[1:], True
            else:
                try:
                    argv, timeout = argv[2:], float(argv[1])
                except (IndexError, ValueError):
                    raise EngineError('Gate timeout must be positive and finite') from None
        argv = argv[1:] if argv[:1]==['--'] else argv
        result = engine.run_gate(args.actor,args.lease,args.name,argv,again=again,timeout=timeout)
        return result,0 if result['passed'] else 1
    if args.command=='finding':
        return engine.add_finding(args.actor,args.lease,args.review,args.kind,args.index,args.disposition,args.reason,args.card),0
    if args.command=='scan':
        result=engine.run_secret_scan(args.actor,args.lease)
        return result,0 if result.get('passed') or result.get('unavailable') else 1
    if args.command=='permit':
        return engine.release_permit(args.actor,args.lease,args.remote,args.target),0
    if args.command=='release':
        engine.validate_lease(args.actor,args.lease)
        argv = engine.policy['release']['argv']
        engine.check_release(args.remote,args.target,argv=argv)
        # Reject destructive forms even when an operator accidentally configures one.
        if classify_command(shlex.join(argv)).action=='deny':
            raise EngineError('Configured release command violates the shared guard')
        timeout=engine.policy.get('release_timeout_seconds',600)
        if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not math.isfinite(timeout) or timeout<=0:
            raise EngineError('Release timeout must be positive and finite')
        before=engine.artifact()
        log=state/('release-'+uuid.uuid4().hex+'.log')
        with log.open('xb') as stream:
            try:
                engine.validate_lease(args.actor,args.lease)
                engine.check_release(args.remote,args.target,argv=argv)
                process=subprocess.Popen(argv,cwd=repo,stdout=stream,stderr=subprocess.STDOUT,
                                         **portable.group_kwargs())
                try:
                    code=process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    try:
                        portable.kill_group(process)
                    except OSError:
                        pass
                    process.wait()
                    raise
            except subprocess.TimeoutExpired:
                code=124
                stream.write(b'Release timed out; inspect remote state before any retry.\n')
            except OSError as exc:
                code=127
                stream.write(str(exc).encode())
            stream.flush()
            os.fsync(stream.fileno())
        import hashlib
        receipt={'action':'release','argv':argv,'exit_code':code,'artifact':before,
                 'after':engine.artifact(),'log':str(log),'sha256':hashlib.sha256(log.read_bytes()).hexdigest(),
                 'remote':args.remote,'target':args.target}
        atomic(state/('release-receipt-'+uuid.uuid4().hex+'.json'),json.dumps(receipt,indent=2).encode())
        return receipt,0 if code==0 else 1
    if args.command=='park':
        engine.park(args.actor,args.lease,args.task_id,args.reason)
        return {'parked':args.task_id},0
    if args.command=='cancel':
        engine.cancel(args.actor,args.lease,args.task_id,args.reason)
        return {'cancelled':args.task_id},0
    if args.command=='own':
        engine.own_add(args.actor,args.lease,args.task_id,args.path)
        return {'owned':args.path,'task':args.task_id},0
    if args.command=='unpark':
        engine.unpark(args.actor,args.lease,args.task_id)
        return {'unparked':args.task_id},0
    if args.command=='pr':
        return {'pull_requests':engine.record_pr(args.actor,args.lease,args.url,tasks=args.task)},0
    if args.command=='hold':
        return engine.hold(args.actor,args.lease,args.task_id,args.finding),0
    if args.command=='route':
        return engine.set_route(args.actor,args.lease,args.items,args.reason,size=args.size,asks=parse_asks(args.asks)),0
    raise EngineError('Unsupported command')


def add_board_line(args,result):
    """Add the one-line `board` delta to a result when a card moved; return the board view to store, or None."""
    if args.command not in BOARD_COMMANDS or not isinstance(result,dict) or args.board_before is None:
        return None
    try:
        after = args.engine.view(args.actor)
    except Exception:
        return None
    line = delta.delta(args.board_before,after)
    if line is None:
        return None
    result['board'] = line
    track = delta.track_text(after)  # the CLI marks the board seen, so a changed track is shown here or not at all
    if track and track != delta.track_text(args.board_before):
        result['track'] = track
    return after


def refused_state(args):
    """The state directory of a refused command, or None when it cannot be told."""
    try:
        return Path(args.state).expanduser().resolve() if args.state else state_location(repository(args.repo))
    except Exception:
        return None


GLOBAL_OPTIONS = ('--repo','--state','--actor','--lease')


class StepRefused(Exception):
    pass


def run_steps(args):
    """`do`: each step is parsed as its own command with this call's global options; the first refusal stops the rest."""
    base = []
    for name in GLOBAL_OPTIONS:
        value = getattr(args,name[2:])
        if value is not None:
            base += [name,value]
    done, refused, engine = [], None, None
    for step in args.steps:
        try:
            tokens = shlex.split(step)
            if not tokens or tokens[0] in ('do','start','autonomy','permit','release'):
                raise StepRefused('A step cannot be `do`, `start`, `autonomy`, `permit` or `release`; run it as its own command')
            if any(tok.split('=')[0] in GLOBAL_OPTIONS for tok in tokens):
                raise StepRefused('A step takes no global option; `do` passes its own')
            caught = io.StringIO()
            try:
                with contextlib.redirect_stderr(caught), contextlib.redirect_stdout(caught):
                    sub = parser().parse_args(base+tokens)
            except SystemExit as stop:
                if stop.code in (0,None):
                    raise StepRefused('help is not a step; run `CMD --help` on its own') from None
                lines = [line for line in caught.getvalue().splitlines() if ': error: ' in line]
                raise StepRefused('Unparsable step: ' + (lines[-1].split(': error: ', 1)[1] if lines else 'see --help')) from None
            result,code = execute(sub)
            engine = getattr(sub,'engine',engine)
            seen = add_board_line(sub,result)
            if seen is not None:
                cli_support.store_seen(sub.state_dir,seen)
            done.append({'step':step,'result':result,'code':code})
        except (StepRefused,EngineError,ValueError,OSError,KeyError,TypeError,AttributeError,subprocess.SubprocessError) as exc:
            refused = {'step':step,'error':str(exc)}
            break
    if engine is not None:
        now.refresh(engine)
    body = {'steps':done}
    if refused:
        body['refused'] = refused
    print(json.dumps(body,indent=2))
    return 2 if refused else 0


def main(argv=None):
    raw = list(sys.argv[1:] if argv is None else argv)
    args=parser().parse_args(raw)
    if args.command=='do':
        if not args.lease:
            print(json.dumps({'steps':[],'refused':{'step':'','error':'Supply --lease from start for coordinator actions'}}))
            return 2
        return run_steps(args)
    state=refused_state(args)
    known=state is not None and state.is_dir()  # a command run before any state exists logs nothing and creates nothing
    try:
        result,code=execute(args)
        seen=add_board_line(args,result)
    except (EngineError,ValueError,OSError,KeyError,TypeError,AttributeError,subprocess.SubprocessError) as exc:
        print(json.dumps({'error':str(exc)}),file=sys.stderr)
        if known:
            cli_support.log_refusal(state,raw,exc)
        return 2
    if result is not None:
        print(json.dumps(result,separators=(',',':')) if args.command=='status' and args.brief else json.dumps(result,indent=2))
    if seen is not None:
        cli_support.store_seen(args.state_dir,seen)
    if (getattr(args,'lease',None) or args.command=='start') and getattr(args,'engine',None) is not None:
        now.refresh(args.engine)  # never raises
    return code


if __name__=='__main__':
    sys.exit(main())
