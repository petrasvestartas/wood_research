# pics.py <run dir> [--max 40] [--cases <file>]: pictures of the cases in <run dir>/changed.tsv (judge.py --prev),
# ours (this run's build and entry, driver relinked for coarse picture meshes) on top, OCCT below; columns operands, ∩, ∪, A−B, B−A, ⊕. Writes <run dir>/pics/<case>.png.
import html, json, os, re, resource, shutil, subprocess, sys
run = sys.argv[1]
opt = dict(zip(sys.argv[2::2], sys.argv[3::2]))
HERE = os.path.dirname(os.path.abspath(__file__))
S = '/tmp/claude-0/-home-user-wood-research/8b288b7c-72c4-56e2-9565-a39939e050f9/scratchpad'
PY = '/tmp/claude-0/-home-user/8b288b7c-72c4-56e2-9565-a39939e050f9/scratchpad/ocp/venv/bin/python'
D = os.environ.get('SCORE_DATA', S + '/score')
OPS = ['intersection', 'union', 'a-b', 'b-a', 'xor']
EMPTY = {'pos': [], 'idx': [], 'edges': [], 'verts': [], 'counts': [0, 0, 0]}
work, pics = run + '/pics/work', run + '/pics'
os.makedirs(work, exist_ok=True)
for f in ('page.html', 'shoot.cjs'):
    shutil.copy(os.path.join(HERE, f), work)
if not os.path.exists(work + '/node_modules'):
    os.symlink(S + '/shots/node_modules', work + '/node_modules')
DRV = pics + '/drv'
if not os.path.exists(DRV):
    build, entry = open(run + '/run.info').read().split()[:2]
    subprocess.run(['timeout', '600', 'bash', HERE + '/link.sh', build, DRV, entry], check=True)
cases = {(w[0], w[1]): w for w in (l.rstrip('\n').split('\t') for l in open(D + '/cases.tsv') if not l.startswith('#'))}
todo = [l.rstrip('\n').split('\t') for l in open(opt.get('--cases', run + '/changed.tsv')) if l.strip()][:int(opt.get('--max', 40))]


def cap():
    resource.setrlimit(resource.RLIMIT_AS, (4 << 30, 4 << 30))


def ours(c, n):
    f = '%s/ours_ops_%s.json' % (work, n)
    try:
        subprocess.run([DRV, 'operands', c[4], c[5], f], capture_output=True, timeout=120, preexec_fn=cap)
        panels = [p or dict(EMPTY, error='operand fails to load') for p in json.load(open(f))]
    except Exception:
        panels = [dict(EMPTY, error='operands fail to load'), dict(EMPTY)]
    for op in OPS:
        f = '%s/ours_%s_%s.json' % (work, n, op)
        try:
            p = subprocess.run([DRV, 'bool', c[4], c[5], op, c[3], f], capture_output=True, text=True, timeout=120, preexec_fn=cap)
            line = next((l for l in p.stdout.splitlines() if l.startswith('BOOL')), 'BOOL %s CRASH' % op).split(None, 10)
            panels.append(json.load(open(f)) if line[2] == 'ok' else dict(EMPTY, error=' '.join([line[2]] + line[10:])))
        except Exception as e:
            panels.append(dict(EMPTY, error='TIMEOUT' if isinstance(e, subprocess.TimeoutExpired) else 'no result'))
    return panels


def occt(c, n):
    f = '%s/occt_%s_raw.json' % (work, n)
    try:
        subprocess.run(['timeout', '900', PY, '-I', HERE + '/occt_ref.py', 'bool', c[6], c[7], f], capture_output=True)
        return json.load(open(f))
    except Exception:
        return [dict(EMPTY, error='OCCT did not run'), dict(EMPTY)] + [dict(EMPTY) for _ in OPS]


jobs = []
for w in todo:
    c = cases[(w[0], w[1])]
    n = re.sub(r'[^A-Za-z0-9_.-]', '_', w[1])
    json.dump(ours(c, n), open('%s/ours_%s.json' % (work, n), 'w'))
    json.dump(occt(c, n), open('%s/occt_%s.json' % (work, n), 'w'))
    jobs.append([n, html.escape('%s (%s): %s' % (w[1], c[2], w[2] if len(w) > 2 else ''))])
for k in range(0, len(jobs), 8):
    batch = jobs[k:k + 8]
    subprocess.run(['timeout', '1800', 'node', work + '/shoot.cjs', work, json.dumps(batch)], cwd=work,
                   env=dict(os.environ, NODE_PATH='/opt/node-tools/node_modules'), capture_output=True)
    for n, _ in batch:
        src = '%s/cmp_%s.png' % (work, n)
        print(('picture ' + pics + '/' + n + '.png') if os.path.exists(src) else 'MISSING ' + n)
        if os.path.exists(src):
            os.replace(src, '%s/%s.png' % (pics, n))
