# viewer_pics.py <run dir> [--cases <file>] [--ops <tier.tsv>] [--max 40] [--out <dir>]: the pictures of pics.py, drawn by
# session_viewer (wasm, WebGPU) instead of three.js. pics.py computes the panels (ours on top, OCCT below; operands, then
# one column per operation; red marks) into <out>/threejs; each case becomes one viewer scene, <out>/scene/pb/<name>.pb
# (meshes, edge polylines, vertex points) and <out>/scene/scenes/<name>.yaml (placement, texts, front view), shot with
# Playwright at deviceScaleFactor 2 into <out>/<name>.png. VIEWER_DIST is the built viewer (trunk build), PANEL_PB the
# writer of the .pb (panel_pb, a small crate over session_rust). The scenes open in a local `trunk serve` too: see
# viewer_open.sh.
import json, math, os, re, subprocess, sys
run = sys.argv[1]
opt = dict(zip(sys.argv[2::2], sys.argv[3::2]))
HERE = os.path.dirname(os.path.abspath(__file__))
S = '/tmp/claude-0/-home-user-wood-research/8b288b7c-72c4-56e2-9565-a39939e050f9/scratchpad'
DIST = os.environ.get('VIEWER_DIST', S + '/viewer/dist')
PB = os.environ.get('PANEL_PB', S + '/viewer/target_native/release/panel_pb')
out = opt.get('--out', run + '/viewer_pics')
three = out + '/threejs'
scene = out + '/scene'
for d in (scene + '/pb', scene + '/scenes', out + '/json'):
    os.makedirs(d, exist_ok=True)
todo = [l.rstrip('\n').split('\t') for l in open(opt.get('--cases', run + '/changed.tsv')) if l.strip()][:int(opt.get('--max', 40))]
names = [(w[3] if len(w) > 3 else '') + re.sub(r'[^A-Za-z0-9_.-]', '_', w[1]) for w in todo]
if not all(os.path.exists('%s/work/%s_%s.json' % (three, s, n)) for n in names for s in ('ours', 'occt')):
    args = ['python3', HERE + '/pics.py', run, '--out', three] + sum([[k, v] for k, v in opt.items() if k != '--out'], [])
    subprocess.run(args, check=True)

GREY, TAN, BLACK, RED = [0.79, 0.83, 0.87], [0.91, 0.79, 0.66], [0.07, 0.07, 0.07], [0.88, 0.06, 0.12]
COL = ['operands A, B', 'A ∩ B', 'A ∪ B', 'A − B', 'B − A', 'A ⊕ B']


def frame(panels):
    # the three.js camera: every panel seen from (1, -1.25, 0.9) about the common centre, z up; returned as the map into
    # the viewer's front view (screen right = +x, screen up = +z, towards the eye = -y)
    lo, hi = [1e300] * 3, [-1e300] * 3
    for s in panels:
        for i in range(0, len(s['pos']), 3):
            for k in range(3):
                lo[k], hi[k] = min(lo[k], s['pos'][i + k]), max(hi[k], s['pos'][i + k])
    if lo[0] > hi[0]:
        lo, hi = [0] * 3, [1] * 3
    c = [(a + b) / 2 for a, b in zip(lo, hi)]
    rad = max(math.dist(lo, hi) / 2, 1e-9)
    n = lambda v: [x / math.sqrt(sum(y * y for y in v)) for x in v]
    f = n([1.0, -1.25, 0.9])
    x = n([-f[1], f[0], 0.0])  # z × f
    y = [f[1] * x[2] - f[2] * x[1], f[2] * x[0] - f[0] * x[2], f[0] * x[1] - f[1] * x[0]]
    dot = lambda a, b: sum(p * q for p, q in zip(a, b))
    return rad, lambda p, o: [dot([p[0] - c[0], p[1] - c[1], p[2] - c[2]], x) + o[0], -dot([p[0] - c[0], p[1] - c[1], p[2] - c[2]], f), dot([p[0] - c[0], p[1] - c[1], p[2] - c[2]], y) + o[1]]


def build(n, title):
    ours = json.load(open('%s/work/ours_%s.json' % (three, n)))
    occt = json.load(open('%s/work/occt_%s.json' % (three, n)))
    rad, to = frame(ours + occt)
    cw, ch = 2.5 * rad, 2.9 * rad
    geo = {'name': n, 'meshes': [], 'lines': [], 'points': []}
    texts = []
    H = lambda h: round(h * rad, 6)

    def text(t, at, h, color=None):
        t = t.replace('−', '-')  # the viewer's font has no U+2212
        texts.append(dict(text=t, at=[round(v, 6) for v in at], right=[1, 0, 0], up=[0, 0, 1], height=H(h), plate=False, **({'color': color} if color else {})))

    def flat(a, o):
        return [round(v, 9) for i in range(0, len(a) - 2, 3) for v in to(a[i:i + 3], o)]

    def panel(s, o, color, tag):
        if s['idx']:
            geo['meshes'].append(dict(name=tag + ' faces', pos=flat(s['pos'], o), idx=s['idx'], color=color))
        if s.get('red_idx'):
            geo['meshes'].append(dict(name=tag + ' wrongly meshed', pos=flat(s['pos'], o), idx=s['red_idx'], color=RED))
        for e in s['edges']:
            geo['lines'].append(dict(name=tag + ' edge', pts=flat(e, o), color=BLACK, width=1.5))
        for e in s.get('red_edges', []):
            geo['lines'].append(dict(name=tag + ' red edge', pts=flat(e, o), color=RED, width=4))
        for i in range(0, len(s['verts']) - 2, 3):
            geo['points'].append(dict(name=tag + ' vertex', p=to(s['verts'][i:i + 3], o), color=RED, width=6))
        for i in range(0, len(s.get('red_verts', [])) - 2, 3):
            geo['points'].append(dict(name=tag + ' red vertex', p=to(s['red_verts'][i:i + 3], o), color=RED, width=14))

    cols = len(ours) - 1
    text(title, [-0.9 * rad, 0, 1.45 * rad], 0.13)
    for row, (set_, other) in enumerate(((ours, occt), (occt, ours))):
        oz = -row * ch
        text('OCCT' if row else 'session_cpp', [-1.9 * rad, 0, oz], 0.14)
        for col in range(cols):
            o = (col * cw, oz)
            s = set_[col + 1] if col else set_[0]
            tag = ('occt ' if row else 'ours ') + (s.get('name') or COL[col])
            panel(s, o, GREY, tag)
            if not col:
                panel(set_[1], o, TAN, tag + ' B')
            y = oz - 0.8 * rad
            text(s.get('name') or COL[col], [o[0] - 0.9 * rad, 0, y], 0.1)
            lines = []
            if s.get('error') or (not col and (set_[0].get('error') or set_[1].get('error'))):
                lines.append(((s.get('error') or set_[0].get('error') or set_[1].get('error'))[:60], True))
            elif col:
                a, b = s['counts'], other[col + 1]['counts']
                lines.append(('faces %d · edges %d · vertices %d' % tuple(a), a != b))
                va, vb = s.get('volume'), other[col + 1].get('volume')
                if va is not None:
                    lines.append(('volume %.10g' % va, vb is None or not abs(va - vb) <= 1e-6 * abs(vb)))
            if s.get('marks'):
                lines.append((s['marks'][:70], True))
            for k, (t, bad) in enumerate(lines):
                text(t, [o[0] - 0.9 * rad, 0, y - (k + 1) * 0.15 * rad], 0.08, [224, 16, 31, 255] if bad else [60, 60, 60, 255])
    j = '%s/json/%s.json' % (out, n)
    json.dump(geo, open(j, 'w'))
    subprocess.run([PB, j, '%s/pb/%s.pb' % (scene, n)], check=True)
    y = ['name: %s' % json.dumps(n), 'grid: false', 'view: front', 'items:', '  - file: "pb/%s.pb"' % n, '    name: %s' % json.dumps(n), '    at: [0, 0, 0]', 'texts:']
    y += ['  - ' + json.dumps(t, ensure_ascii=False) for t in texts]
    open('%s/scenes/%s.yaml' % (scene, n), 'w').write('\n'.join(y) + '\n')
    return cols


D = os.environ.get('SCORE_DATA', S + '/score')
family = {(w[0], w[1]): w[2] for w in (l.split('\t') for l in open(D + '/cases.tsv') if not l.startswith('#'))}
jobs = []
for w, n in zip(todo, names):
    cols = build(n, '%s (%s): %s' % (w[1], family.get((w[0], w[1]), '?'), w[2] if len(w) > 2 else ''))
    jobs.append([n, 330 * cols + 60, 700])
p = subprocess.run(['timeout', '900', 'node', HERE + '/viewer_shoot.cjs', DIST, scene, out, json.dumps(jobs)], capture_output=True, text=True,
                   env=dict(os.environ, NODE_PATH='/opt/node-tools/node_modules'))
sys.stderr.write(p.stdout[-3000:] + p.stderr[-3000:])
for n, _, _ in jobs:
    print(('picture %s/%s.png' % (out, n)) if os.path.exists('%s/%s.png' % (out, n)) else 'MISSING ' + n)
