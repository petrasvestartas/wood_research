# run.py <driver> <cases.tsv> <run dir> [--subset subset.tsv] [--jobs 2] [--timeout 60]
# One process per boolean, appended to <run dir>/results.tsv as it finishes (a rerun resumes):
#   suite case op status wall bool_s faces edges vertices valid solid volume message
# The first boolean of each case also measures our operands: <run dir>/operands.tsv  suite case volA validA volB validB
import os, sys, time, random, resource, subprocess, concurrent.futures as cf
drv, cases_f, out = sys.argv[1:4]
opt = dict(zip(sys.argv[4::2], sys.argv[5::2]))
jobs, limit = int(opt.get('--jobs', 2)), float(opt.get('--timeout', 60))
OPS = ['intersection', 'union', 'a-b', 'b-a', 'xor']
cases = {}
for l in open(cases_f):
    if not l.startswith('#'):
        w = l.rstrip('\n').split('\t')
        cases[(w[0], w[1])] = w
if '--subset' in opt:
    todo = [tuple(l.split('\t')[:3]) for l in open(opt['--subset']) if not l.startswith('#')]
else:
    todo = [(s, c, op) for (s, c) in cases for op in OPS]
    random.Random(7).shuffle(todo)
res, ops = out + '/results.tsv', out + '/operands.tsv'
done = {tuple(l.split('\t')[:3]) for l in open(res)} if os.path.exists(res) else set()
measured = {tuple(l.split('\t')[:2]) for l in open(ops)} if os.path.exists(ops) else set()
todo = [k for k in todo if k not in done]
first = {}
for k in todo:
    first.setdefault(k[:2], k)


def cap():
    resource.setrlimit(resource.RLIMIT_AS, (4 << 30, 4 << 30))
    os.nice(5)


def one(key):
    suite, case, op = key
    w = cases[(suite, case)]
    env = dict(os.environ)
    if first[(suite, case)] == key and (suite, case) not in measured:
        env['SCORE_OPS'] = '1'
    t0 = time.time()
    try:
        p = subprocess.run([drv, 'bool', w[4], w[5], op, w[3]], capture_output=True, text=True, timeout=limit, env=env, preexec_fn=cap)
        lines = p.stdout.splitlines()
        o = next((l.split()[1:] for l in lines if l.startswith('OPS ')), None)
        b = next((l.split(None, 10) for l in lines if l.startswith('BOOL ')), None)
        if b:
            rec = [b[2], b[3]] + b[4:10] + [' '.join(b[10:])]
        else:
            why = 'signal %d' % -p.returncode if p.returncode < 0 else 'exit %d' % p.returncode
            rec = ['CRASH', '0', '0', '0', '0', '0', '0', 'nan', why + ' ' + (p.stderr.strip().splitlines() or [''])[-1][:200]]
    except subprocess.TimeoutExpired as e:
        s = e.stdout or ''
        s = s.decode(errors='replace') if isinstance(s, bytes) else s
        o = next((l.split()[1:] for l in s.splitlines() if l.startswith('OPS ')), None)
        rec = ['TIMEOUT', '%g' % limit, '0', '0', '0', '0', '0', 'nan', 'timeout %gs' % limit]
    return key, time.time() - t0, rec, o


with open(res, 'a') as fr, open(ops, 'a') as fo, cf.ThreadPoolExecutor(max_workers=jobs) as ex:
    for f in cf.as_completed([ex.submit(one, k) for k in todo]):
        key, wall, rec, o = f.result()
        fr.write('\t'.join(list(key) + [rec[0], '%.3f' % wall] + rec[1:]) + '\n')
        fr.flush()
        if o:
            fo.write('\t'.join(list(key[:2]) + o) + '\n')
            fo.flush()
