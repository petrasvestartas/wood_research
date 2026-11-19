# pics.py <run dir> [--max 40] [--cases <file>] [--ops <tier.tsv>] [--out <dir>]: pictures of the cases in
# <run dir>/changed.tsv (judge.py --prev) or of --cases (suite, case, note, optional file prefix): ours (this run's
# build and entry, driver relinked for coarse picture meshes) on top, OCCT below; columns operands, ∩, ∪, A−B, B−A, ⊕,
# or with --ops only the operations that tier lists for the case. Counts and volumes under each, differences in red.
# In red: on our row the faces our mesher gives no triangles (their boundary) or wrong ones (the triangles and the
# boundary; wrong at the picture's coarser quality is twice geo.py's bounds), at the picture's quality or the viewer's, and our edges and vertices without a counterpart in OCCT's result; on OCCT's row
# its edges and vertices without a counterpart in ours (geo.py against the stored shape, where there is one).
# Writes <out>/<prefix><case>.png (out defaults to <run dir>/pics) and, with --ops, <out>/index.txt.
import html, json, os, re, resource, shutil, subprocess, sys
run = sys.argv[1]
opt = dict(zip(sys.argv[2::2], sys.argv[3::2]))
HERE = os.path.dirname(os.path.abspath(__file__))
S = '/tmp/claude-0/-home-user-wood-research/8b288b7c-72c4-56e2-9565-a39939e050f9/scratchpad'
PY = '/tmp/claude-0/-home-user/8b288b7c-72c4-56e2-9565-a39939e050f9/scratchpad/ocp/venv/bin/python'
D = os.environ.get('SCORE_DATA', S + '/score')
OPS = ['intersection', 'union', 'a-b', 'b-a', 'xor']
EMPTY = {'pos': [], 'idx': [], 'edges': [], 'verts': [], 'counts': [0, 0, 0]}
pics = opt.get('--out', run + '/pics')
work = pics + '/work'
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
NAMES = dict(zip(OPS, ['A ∩ B', 'A ∪ B', 'A − B', 'B − A', 'A ⊕ B']))
only = {}
for l in open(opt['--ops']) if '--ops' in opt else []:
    if not l.startswith('#'):
        only.setdefault(tuple(l.split('\t')[:2]), []).append(l.rstrip('\n').split('\t')[2])
todo = [l.rstrip('\n').split('\t') for l in open(opt.get('--cases', run + '/changed.tsv')) if l.strip()][:int(opt.get('--max', 40))]


def cap():
    resource.setrlimit(resource.RLIMIT_AS, (4 << 30, 4 << 30))


def drv(args, wire=[]):
    for nomesh in ('', '1'):
        try:
            return subprocess.run([DRV] + args, capture_output=True, text=True, timeout=60, preexec_fn=cap,
                                  env=dict(os.environ, **({'SCORE_NOMESH': '1'} if nomesh else {})))
        except subprocess.TimeoutExpired:
            wire.append(1)
    raise subprocess.TimeoutExpired(args, 60)


def marks(c, n, op, panel, wire):
    # what geo.py finds for this boolean: red marks for our panel, and those for OCCT's
    g = '%s/geo_%s_%s.json' % (work, n, op)
    ref = '%s/geo/%s__%s__%s.brep' % (D, c[0], re.sub(r'[^A-Za-z0-9_.-]', '_', c[1]), op)
    cmp = {}
    try:
        subprocess.run([DRV, 'bool', c[4], c[5], op, c[3]], capture_output=True, timeout=90, preexec_fn=cap, env=dict(os.environ, SCORE_GEO=g))
    except subprocess.TimeoutExpired:
        pass
    if os.path.exists(g) and os.path.exists(ref):
        subprocess.run(['timeout', '300', PY, '-I', HERE + '/geo.py', 'cmp', g, ref, g + '.cmp'], capture_output=True)
        cmp = json.load(open(g + '.cmp')) if os.path.exists(g + '.cmp') else {}
    area, allowed, cen, apart = (cmp.get(k, []) for k in ('face_area', 'face_allowed', 'face_centroid', 'face_apart'))
    off = lambda i: i < len(area) and (abs(panel['farea'][i] - area[i]) > 2 * allowed[i] or sum((a - b) ** 2 for a, b in zip(panel['fcen'][i], cen[i])) ** 0.5 > 2 * apart[i])
    viewer = {m['face']: m['what'] for m in cmp.get('mesh', [])}
    undrawn = [i for i, k in enumerate(panel.get('ftri', [])) if (not k and not wire) or viewer.get(i) == 'undrawn']
    wrong = [i for i, k in enumerate(panel.get('ftri', [])) if k and (viewer.get(i) == 'wrong' or off(i))]
    start = [0]
    for k in panel.get('ftri', []):
        start.append(start[-1] + 3 * k)
    panel['red_idx'] = [x for i in wrong for x in panel['idx'][start[i]:start[i + 1]]]
    panel['red_edges'] = [panel['edges'][e] for i in undrawn + wrong for e in panel['fedge'][i]] + [e['pts'] for e in cmp.get('edges_ours', [])]
    panel['red_verts'] = [x for v in cmp.get('vertices_ours', []) for x in v['p']]
    said = [('%d faces undrawn' % len(undrawn)) if undrawn else '', ('%d wrongly drawn' % len(wrong)) if wrong else '',
            ('%d edges, %d vertices not in OCCT' % (len(cmp.get('edges_ours', [])), len(cmp.get('vertices_ours', [])))) if cmp.get('edges_ours') or cmp.get('vertices_ours') else '',
            'faces differ' if cmp and not cmp['faces'] else '']
    panel['marks'] = ' · '.join(x for x in said if x)
    other = {'red_edges': [e['pts'] for e in cmp.get('edges_occt', [])], 'red_verts': [x for v in cmp.get('vertices_occt', []) for x in v['p']]}
    other['marks'] = '%d edges, %d vertices not in ours' % (len(other['red_edges']), len(other['red_verts']) // 3) if other['red_edges'] or other['red_verts'] else ''
    return other


def ours(c, n, wire, ops):
    f = '%s/ours_ops_%s.json' % (work, n)
    try:
        drv(['operands', c[4], c[5], f], wire)
        panels = [p or dict(EMPTY, error='operand fails to load') for p in json.load(open(f))]
    except Exception:
        panels = [dict(EMPTY, error='operands fail to load'), dict(EMPTY)]
    for op in ops:
        f = '%s/ours_%s_%s.json' % (work, n, op)
        try:
            p = drv(['bool', c[4], c[5], op, c[3], f], wire)
            line = next((l for l in p.stdout.splitlines() if l.startswith('BOOL')), 'BOOL %s CRASH' % op).split(None, 10)
            panels.append(dict(json.load(open(f)), volume=float(line[9].replace('(mesh)', ''))) if line[2] == 'ok' else dict(EMPTY, error=' '.join([line[2]] + line[10:])))
        except Exception as e:
            panels.append(dict(EMPTY, error='TIMEOUT' if isinstance(e, subprocess.TimeoutExpired) else 'no result'))
        panels[-1]['name'] = NAMES[op]
        red[op] = marks(c, n, op, panels[-1], wire) if 'error' not in panels[-1] else {}
    return panels


def occt(c, n, ops):
    f = '%s/occt_%s_raw.json' % (work, n)
    try:
        p = subprocess.run(['timeout', '900', PY, '-I', HERE + '/occt_ref.py', 'bool', c[6], c[7], f], capture_output=True, text=True, env=dict(os.environ, GEO_OPS=','.join(ops)))
        volume = {l.split()[0]: float(l.split()[6]) for l in p.stdout.splitlines() if l.split()[1:2] == ['ok']}
        panels = json.load(open(f))
        return panels[:2] + [dict(panels[2 + ops.index(op)], name=NAMES[op], **red.get(op, {}), **({'volume': volume[op]} if op in volume else {})) for op in ops]
    except Exception:
        return [dict(EMPTY, error='OCCT did not run'), dict(EMPTY)] + [dict(EMPTY, name=NAMES[op]) for op in ops]


jobs, index, red = [], [], {}
for w in todo:
    c = cases[(w[0], w[1])]
    ops = only.get((w[0], w[1]), OPS)
    n = (w[3] if len(w) > 3 else '') + re.sub(r'[^A-Za-z0-9_.-]', '_', w[1])
    wire = []
    a, b = ours(c, n, wire, ops), occt(c, n, ops)
    json.dump(a, open('%s/ours_%s.json' % (work, n), 'w'))
    json.dump(b, open('%s/occt_%s.json' % (work, n), 'w'))
    note = '  (ours drawn as edges where meshing took over 60 s)' if wire else ''
    jobs.append([n, html.escape('%s (%s): %s%s' % (w[1], c[2], w[2] if len(w) > 2 else '', note))])
    for op, x, y in zip(ops, a[2:], b[2:]):
        vx, vy = x.get('volume'), y.get('volume')
        differs = [name for name, i in (('faces', 0), ('edges', 1), ('vertices', 2)) if x['counts'][i] != y['counts'][i]]
        if vx is None or vy is None or abs(vx - vy) > 1e-6 * abs(vy):
            differs.append('volume' + (' (%+.3g relative)' % ((vx - vy) / vy) if vx is not None and vy else ''))
        differs += [m for m in (x.get('marks'), y.get('marks')) if m]
        index.append('\t'.join([n + '.png', w[1], op, 'ours ' + (x.get('error') or '%d/%d/%d volume %.12g' % (*x['counts'], vx)),
                                'OCCT ' + (y.get('error') or '%d/%d/%d volume %.12g' % (*y['counts'], vy if vy is not None else float('nan'))),
                                'differs: ' + (', '.join(differs) or 'nothing')]))
if only or '--cases' in opt:
    open(pics + '/index.txt', 'w').write('#picture\tcase\top\tours faces/edges/vertices volume\tOCCT faces/edges/vertices volume\twhat differs\n' + '\n'.join(index) + '\n')
for k in range(0, len(jobs), 8):
    batch = jobs[k:k + 8]
    subprocess.run(['timeout', '1800', 'node', work + '/shoot.cjs', work, json.dumps(batch)], cwd=work,
                   env=dict(os.environ, NODE_PATH='/opt/node-tools/node_modules'), capture_output=True)
    for n, _ in batch:
        src = '%s/cmp_%s.png' % (work, n)
        print(('picture ' + pics + '/' + n + '.png') if os.path.exists(src) else 'MISSING ' + n)
        if os.path.exists(src):
            os.replace(src, '%s/%s.png' % (pics, n))
