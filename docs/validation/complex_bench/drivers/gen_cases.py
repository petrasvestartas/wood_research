"""Case list of the complex-model bench: run/cases.tsv, one case per line:
   name  title  tol  oursA  oursB  occtA  occtB
Operands are the units of tools/map_units.py (run/units.txt): one BRep of our STEP reader with its OCCT solid(s), so both
volume and bounding-box centre. Every move is one rigid 3x4 matrix, given identically to both kernels."""
import math, os, random, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = '/home/user/wood_research/session/session_cpp/tests/fixtures'
ELEM = '/home/user/session_data/elements'
SOURCES = {'solidbrep': f'{FIX}/solidbrep.stp',
           'InputTwisted-object-0': f'{FIX}/rhino_booleans/inputs/InputTwisted-object-0.step',
           'InputTwisted-object-1': f'{FIX}/rhino_booleans/inputs/InputTwisted-object-1.step'}
for f in os.listdir(ELEM):
    if f.endswith('.step') or f.endswith('.stp'):
        SOURCES[os.path.splitext(f)[0]] = f'{ELEM}/{f}'

occt = {}  # (file, unit) -> dict; a unit is one BRep of our reader with its OCCT solid(s) (tools/map_units.py)
for line in open(f'{C}/run/units.txt'):
    p = line.split()
    if p[0] != 'UNIT':
        continue
    occt[(p[1], int(p[2]))] = dict(brep=f'{C}/brep/{p[1]}.u{p[2]}.brep', ours=None if p[3] == '-' else int(p[3]), faces=int(p[6]),
                                   vol=float(p[8]), bbox=[float(x) for x in p[10].split(',')])


def centre(b):
    return [(b[i] + b[i + 3]) / 2 for i in range(3)]


def matmul(a, b):  # 3x4 rigid (row-major) composition a*b
    r = []
    for i in range(3):
        row = []
        for j in range(4):
            v = sum(a[i * 4 + k] * b[k * 4 + j] for k in range(3)) + (a[i * 4 + 3] if j == 3 else 0.0)
            row.append(v)
        r += row
    return r


def translation(t):
    return [1, 0, 0, t[0], 0, 1, 0, t[1], 0, 0, 1, t[2]]


def rotation(axis, deg, about=(0, 0, 0)):
    n = math.sqrt(sum(x * x for x in axis))
    x, y, z = (v / n for v in axis)
    a = math.radians(deg)
    c, s, t = math.cos(a), math.sin(a), 1 - math.cos(a)
    r = [t * x * x + c, t * x * y - s * z, t * x * z + s * y, 0,
         t * x * y + s * z, t * y * y + c, t * y * z - s * x, 0,
         t * x * z - s * y, t * y * z + s * x, t * z * z + c, 0]
    return matmul(translation(about), matmul(r, translation([-v for v in about])))


def mtext(m):
    return '|m=' + ','.join(repr(float(v)) for v in m)


def random_axis(rng):  # unit vector
    while True:
        v = [rng.uniform(-1, 1) for _ in range(3)]
        n = math.sqrt(sum(x * x for x in v))
        if 0.3 < n <= 1:
            return [x / n for x in v]


def solid(stem, k, move=None):
    """(ours spec, occt spec) of OCCT solid k of a file, optionally moved"""
    oi = occt[(stem, k)]['ours']
    tail = mtext(move) if move else ''
    ours_spec = f'step={SOURCES[stem]}#{oi}{tail}' if oi is not None else f'step={SOURCES[stem]}#missing'
    return ours_spec, f'brep={occt[(stem, k)]["brep"]}{tail}'


cases = []


def add(name, title, tol, a, b):
    cases.append((name, title, tol, a[0], b[0], a[1], b[1]))


# (a) chairs
chair_a, chair_b = ('solidbrep', 0), ('solidbrep', 1)
cb = centre(occt[chair_b]['bbox'])
add('chair_pose0', 'chairs as stored (solidbrep.stp)', '1e-6', solid(*chair_a), solid(*chair_b))
for seed in range(1, 11):
    rng = random.Random(1000 + seed)
    axis, angle = random_axis(rng), rng.uniform(-90, 90)
    shift = [rng.uniform(-1, 1) for _ in range(3)]
    m = matmul(translation(shift), rotation(axis, angle, cb))
    add(f'chair_pose{seed}', f'chairs, chair B rotated {angle:.1f}° about ({axis[0]:.2f},{axis[1]:.2f},{axis[2]:.2f}) through its centre, shift ({shift[0]:.2f},{shift[1]:.2f},{shift[2]:.2f})',
        '1e-6', solid(*chair_a), solid(*chair_b, m))
rng = random.Random(2000)
axis = random_axis(rng)
ca = centre(occt[chair_a]['bbox'])
add('chair_self', f'chair A against itself rotated 25° about ({axis[0]:.2f},{axis[1]:.2f},{axis[2]:.2f}) through its centre', '1e-6',
    solid(*chair_a), solid(*chair_a, rotation(axis, 25, ca)))

# (c-models) the Rhino twisted pair (not a primitive: 6 B-spline faces)
ta, tb = ('InputTwisted-object-0', 0), ('InputTwisted-object-1', 0)
add('twisted_pose0', 'Rhino twisted solids as stored (rhino_booleans/InputTwisted)', '1e-7', solid(*ta), solid(*tb))
rng = random.Random(3000)
axis = random_axis(rng)
add('twisted_rot', 'Rhino twisted solids, B rotated 7° about a random axis through its centre', '1e-7', solid(*ta),
    solid(*tb, rotation(axis, 7, centre(occt[tb]['bbox']))))

# (b) timber elements: distinct solids, and the pairs of one assembly whose boxes touch or overlap
elements = [k for k in sorted(occt) if k[0].startswith('schoring')]


def key(k):
    o = occt[k]
    return (o['faces'], round(o['vol'], 9), tuple(round(v, 4) for v in o['bbox']))


distinct, seen = [], set()
for k in elements:
    if key(k) not in seen:
        seen.add(key(k))
        distinct.append(k)

assemblies = [['schoring_body_start_0', 'schoring_foot_0'], ['schoring_body_end_0', 'schoring_head_0'],
              ['schoring_body_start_1', 'schoring_foot_1'], ['schoring_body_end_1', 'schoring_head_1'],
              ['schoring_body_start_2'], ['schoring_body_start_3']]


def overlap(p, q, gap=1e-5):
    a, b = occt[p]['bbox'], occt[q]['bbox']
    return all(a[i] <= b[i + 3] + gap and b[i] <= a[i + 3] + gap for i in range(3))


pairs, seen_pairs = [], set()
for files in assemblies:
    members = [k for k in elements if k[0] in files]
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            p, q = members[i], members[j]
            if overlap(p, q) and (key(p), key(q)) not in seen_pairs:
                seen_pairs.add((key(p), key(q)))
                pairs.append((p, q))


def short(k):
    return k[0].replace('schoring_', '') + f'.u{k[1]}'


for n, (p, q) in enumerate(pairs):
    add(f'joint{n:02d}', f'joint as stored: {short(p)} with {short(q)}', '1e-7', solid(*p), solid(*q))
    rng = random.Random(4000 + n)
    axis, angle = random_axis(rng), rng.uniform(2, 6) * rng.choice([-1, 1])
    add(f'joint{n:02d}_rot', f'joint {short(p)} with {short(q)} rotated {angle:.1f}° about a random axis through its centre', '1e-7',
        solid(*p), solid(*q, rotation(axis, angle, centre(occt[q]['bbox']))))

for n, k in enumerate(distinct):
    o = occt[k]
    c = centre(o['bbox'])
    ext = [o['bbox'][i + 3] - o['bbox'][i] for i in range(3)]
    order = sorted(range(3), key=lambda i: ext[i])  # smallest .. largest extent
    rng = random.Random(5000 + n)
    axis = random_axis(rng)
    add(f'elem{n:02d}_self', f'{short(k)} against itself rotated 15° about ({axis[0]:.2f},{axis[1]:.2f},{axis[2]:.2f}) through its centre', '1e-7',
        solid(*k), solid(*k, rotation(axis, 15, c)))
    # box cutter: a slab across the longest axis, 0.3 of it thick, through everything else, tilted 6°, off centre
    big = order[2]
    size = [1.6 * e for e in ext]
    size[big] = 0.3 * ext[big]
    at = list(c)
    at[big] += 0.07 * ext[big]
    tilt_axis = [0, 0, 0]
    tilt_axis[order[1]] = 1
    m = matmul(translation(at), rotation(tilt_axis, 6))
    add(f'elem{n:02d}_box', f'{short(k)} cut by a box slab across its longest axis, tilted 6°', '1e-7',
        solid(*k), (f'box={size[0]!r},{size[1]!r},{size[2]!r}{mtext(m)}', f'box={size[0]!r},{size[1]!r},{size[2]!r}{mtext(m)}'))
    # cylinder cutter: a drilled hole along the smallest extent, radius 0.25 of the next one, off centre
    small = order[0]
    r = 0.25 * ext[order[1]]
    h = 1.6 * ext[small]
    z = [0, 0, 0]
    z[small] = 1
    to_axis = {0: rotation([0, 1, 0], 90), 1: rotation([1, 0, 0], -90), 2: translation([0, 0, 0])}[small]  # +Z -> axis
    base = list(c)
    base[small] -= 0.8 * ext[small]
    base[order[1]] += 0.11 * ext[order[1]]
    base[order[2]] += 0.09 * ext[order[2]]
    m = matmul(translation(base), to_axis)
    add(f'elem{n:02d}_cyl', f'{short(k)} drilled by a cylinder (r {r:.4g}) along its thinnest axis', '1e-7',
        solid(*k), (f'cyl={r!r},{h!r}{mtext(m)}', f'cyl={r!r},{h!r}{mtext(m)}'))

with open(f'{C}/run/cases.tsv', 'w') as out:
    for c in cases:
        out.write('\t'.join(c) + '\n')
print(len(cases), 'cases;', len(pairs), 'joint pairs;', len(distinct), 'distinct elements', file=sys.stderr)
