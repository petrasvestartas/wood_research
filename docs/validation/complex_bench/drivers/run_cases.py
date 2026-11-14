"""Runs run/cases.tsv through both drivers, one process per boolean, ours then OCCT back to back (same machine load).
   python3 -I run_cases.py [name-regex]
Appends `<case> <OP line>` to run/raw_ours.txt / run/raw_occt.txt (skips case/op pairs already there) and writes picture
data to run/dumps/. A boolean of ours not finished within LIMIT seconds is TIMEOUT; a dead process is CRASH."""
import os, re, resource, subprocess, sys, time

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = f'{C}/tools'
D = f'{C}/run/dumps'
os.makedirs(D, exist_ok=True)
LIMIT = 120
MEM = 6 << 30
args = [a for a in sys.argv[1:] if not a.startswith('--')]
pattern = re.compile(args[0]) if args else None
# --repair: ours only, with OURS_REPAIR=1 (driver-side orientation repair of STEP BReps that are not is_solid() as read),
# for the cases whose ours booleans were refused as read; lines to run/raw_ours_repair.txt, dumps as oursrep_*.
REPAIR = '--repair' in sys.argv
ENV = dict(os.environ, OURS_REPAIR='1') if REPAIR else None


def cap():
    resource.setrlimit(resource.RLIMIT_AS, (MEM, MEM))


def done(path):
    s = set()
    if os.path.exists(path):
        for line in open(path):
            p = line.split()
            if len(p) > 2 and p[1] == 'OP':
                s.add((p[0], p[2]))
    return s


def call(argv, limit):
    t0 = time.time()
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=limit, preexec_fn=cap, env=ENV if argv[0].endswith('ours_cx') else None)
        out, err, rc = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or '')
        err, rc = 'timeout', 'timeout'
    return out, err, rc, time.time() - t0


def one(side, case, a, b, op, tol, dump):
    exe = f'{T}/ours_cx' if side == 'ours' else f'{T}/occt_cx'
    argv = [exe, 'op', a, b, op] + ([tol] if side == 'ours' else []) + ([dump] if dump else [])
    out, err, rc, wall = call(argv, LIMIT + 60)
    line = next((l for l in out.splitlines() if l.startswith('OP ')), None)
    if line is None:
        tail = ' '.join(err.strip().splitlines()[-2:])[:300]
        status = 'TIMEOUT' if rc == 'timeout' else 'CRASH'
        line = f'OP {op} {status} bool_s {wall:.3f} counts 0 0 0 shells 0 solids 0 valid 0 solid 0 vol_s 0 volume nan rc={rc} {tail}'
    elif rc == 'timeout':
        line += ' (killed after the boolean: volume or picture data unfinished)'
    elif rc not in (0,):
        line += f' (process rc={rc} after the boolean)'
    if ' ok ' in line and float(line.split()[4]) > LIMIT:
        line = line.replace(' ok ', ' SLOW ', 1)
    return line


cases = [l.rstrip('\n').split('\t') for l in open(f'{C}/run/cases.tsv')]
OURS = 'raw_ours_repair.txt' if REPAIR else 'raw_ours.txt'
have = {'ours': done(f'{C}/run/{OURS}'), 'occt': done(f'{C}/run/raw_occt.txt')}
logs = {'ours': open(f'{C}/run/{OURS}', 'a'), 'occt': open(f'{C}/run/raw_occt.txt', 'a')}
refused = {l.split()[0] for l in open(f'{C}/run/raw_ours.txt') if 'require closed oriented solid' in l} if REPAIR else set()
for name, title, tol, oa, ob, ca, cb in cases:
    if pattern and not pattern.search(name):
        continue
    if REPAIR and name not in refused:
        continue
    sides = (('ours', oa, ob),) if REPAIR else (('ours', oa, ob), ('occt', ca, cb))
    for side, a, b in sides:
        f = f'{D}/{"oursrep" if REPAIR else side}_{name}_operands.json'
        if not os.path.exists(f):
            exe = f'{T}/ours_cx' if side == 'ours' else f'{T}/occt_cx'
            out, err, rc, _ = call([exe, 'operands', a, b, f], 300)
            for l in out.splitlines():
                if l.startswith('OPERAND'):
                    logs[side].write(f'{name} {l}\n')
    for op in ('intersection', 'union', 'a-b', 'b-a', 'xor'):
        for side, a, b in sides:
            ops = [op] if side == 'ours' or op != 'xor' else ['xorcells', 'xor3']
            for o in ops:
                if (name, o) in have[side]:
                    continue
                dump = None if o == 'xor3' else f'{D}/{"oursrep" if REPAIR else side}_{name}_{op}.json'
                line = one(side, name, a, b, o, tol, dump)
                logs[side].write(f'{name} {line}\n')
                logs[side].flush()
                print(side, name, line[:150], flush=True)
