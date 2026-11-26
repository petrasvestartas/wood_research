# run.py <driver> <cases.tsv> <run dir> [--subset subset.tsv] [--jobs 2] [--timeout 60]
# One process per boolean, appended to <run dir>/results.tsv as it finishes (a rerun resumes):
#   suite case op status wall bool_s faces edges vertices valid solid volume message [closure]
# The first boolean of each case also measures our operands: <run dir>/operands.tsv  suite case volA validA volB validB [closureA closureB]
# closure: how far the volume can move as the solid's faces do not close, where the driver prints it (CLOSURE)
# Each result's geometry goes to <run dir>/geo/<suite>__<case>__<op>.json for geo.py (SCORE_GEO): the timeout is on the
# boolean as before (its BOOL line), the measuring and the viewer's mesh after it have GEO_LIMIT seconds of their own
# (<...>.json.mesh says so when the mesher is not back by then).
import os, re, sys, time, random, resource, subprocess, concurrent.futures as cf
drv, cases_f, out = sys.argv[1:4]
opt = dict(zip(sys.argv[4::2], sys.argv[5::2]))
jobs, limit = int(opt.get('--jobs', 2)), float(opt.get('--timeout', 60))
OPS = ['intersection', 'union', 'a-b', 'b-a', 'xor']
GEO_LIMIT = 60
os.makedirs(out + '/geo', exist_ok=True)
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
    geo = '%s/geo/%s__%s__%s.json' % (out, suite, re.sub(r'[^A-Za-z0-9_.-]', '_', case), op)
    env['SCORE_GEO'] = geo
    t0 = time.time()
    p = subprocess.Popen([drv, 'bool', w[4], w[5], op, w[3]], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, preexec_fn=cap)
    try:
        try:
            so, se = p.communicate(timeout=limit)
        except subprocess.TimeoutExpired as e:
            part = e.stdout or ''
            if not re.search(r'^BOOL .*\n', part.decode(errors='replace') if isinstance(part, bytes) else part, re.M):
                raise
            try:
                so, se = p.communicate(timeout=GEO_LIMIT)
            except subprocess.TimeoutExpired:
                p.kill()
                so, se = p.communicate()
        if 'GEO ok' not in so and os.path.exists(geo):
            os.remove(geo)
        if 'MESH ok' not in so:
            open(geo + '.mesh', 'w').write('{"failed": "%s"}' % ('face_meshes() not back in %d s' % GEO_LIMIT if p.returncode == -9 else 'the process ended in face_meshes(): status %d' % p.returncode))
        lines = so.splitlines()
        o = next((l.split()[1:] for l in lines if l.startswith('OPS ')), None)
        b = next((l.split(None, 10) for l in lines if l.startswith('BOOL ')), None)
        if b:
            rec = [b[2], b[3]] + b[4:10] + [' '.join(b[10:])] + [l.split()[1] for l in lines if l.startswith('CLOSURE ')][:1]
        else:
            why = 'signal %d' % -p.returncode if p.returncode < 0 else 'exit %d' % p.returncode
            rec = ['CRASH', '0', '0', '0', '0', '0', '0', 'nan', why + ' ' + (se.strip().splitlines() or [''])[-1][:200]]
    except subprocess.TimeoutExpired as e:
        p.kill()
        p.communicate()
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
