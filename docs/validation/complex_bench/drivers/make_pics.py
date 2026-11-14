"""Picture data for page.html from run/dumps + run/raw_*.txt: shots/data/{ours,occt}_<case>.json = [A, B, ∩, ∪, A−B, B−A, ⊕],
then shoot.cjs renders images/cmp_<case>.png.   python3 -I make_pics.py <out images dir> [name-regex]"""
import json, os, re, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = f'{C}/run/dumps'
OUT = f'{C}/shots/data'
os.makedirs(OUT, exist_ok=True)
images = sys.argv[1]
os.makedirs(images, exist_ok=True)
pattern = re.compile(sys.argv[2]) if len(sys.argv) > 2 else None
OPS = ['intersection', 'union', 'a-b', 'b-a', 'xor']


def raw(side):
    r = {}
    if not os.path.exists(f'{C}/run/raw_{side}.txt'):
        return r
    for line in open(f'{C}/run/raw_{side}.txt'):
        p = line.split(maxsplit=2)
        if p[1] == 'OP':
            q = p[2].split()
            r[(p[0], q[0])] = p[2]
        elif p[1] == 'OPERAND':
            r[(p[0], 'operand' + p[2].split()[0])] = p[2]
    return r


def parse(line):
    q = line.split()
    d = {'op': q[0], 'status': q[1], 'bool_s': float(q[3])}
    try:
        d['valid'] = q[q.index('valid') + 1] == '1'
        d['volume'] = q[q.index('volume') + 1] if 'volume' in q else 'nan'
        d['message'] = ' '.join(q[q.index('volume') + 2:]) if 'volume' in q else ''
    except ValueError:
        d['valid'], d['volume'], d['message'] = False, 'nan', ''
    return d


def empty(error):
    return {'pos': [], 'idx': [], 'edges': [], 'verts': [], 'counts': [0, 0, 0], 'error': error}


R = {'ours': raw('ours'), 'occt': raw('occt'), 'oursrep': raw('ours_repair')}
# cases whose operands our kernel refused as read ("require closed oriented solid operands") are pictured with the
# driver-side orientation repair (OURS_REPAIR=1) in the top row; the as-read refusal is stated in the title.
repaired = {k[0] for k in R['oursrep']}
jobs = []
for name, title, *_ in (l.rstrip('\n').split('\t') for l in open(f'{C}/run/cases.tsv')):
    if pattern and not pattern.search(name):
        continue
    for out_side in ('ours', 'occt'):
        side = 'oursrep' if out_side == 'ours' and name in repaired else out_side
        panels = []
        f = f'{D}/{side}_{name}_operands.json'
        ops = json.load(open(f)) if os.path.exists(f) else [None, None]
        for k, tag in ((0, 'operandA'), (1, 'operandB')):
            if ops[k] is None:
                msg = R[side].get((name, tag), 'load failed')
                ops[k] = empty('load failed: ' + msg.replace('A FAIL', '').replace('B FAIL', '').strip()[:200])
        panels += ops
        for op in OPS:
            key = 'xorcells' if side == 'occt' and op == 'xor' else op
            line = R[side].get((name, key))
            f = f'{D}/{side}_{name}_{op}.json'
            if line is None:
                panels.append(empty('not run'))
                continue
            d = parse(line)
            if d['status'] not in ('ok', 'SLOW') or not os.path.exists(f) or os.path.getsize(f) == 0:
                panels.append(empty(f"{d['status']} after {d['bool_s']:.1f} s: {d['message'][:220]}"))
                continue
            p = json.load(open(f))
            try:
                vol = f"{float(d['volume'].replace('(mesh)', '')):.6g}"
            except ValueError:
                vol = d['volume']
            p['note'] = f"vol {vol} · {d['bool_s']:.2f} s · " + ('valid' if d['valid'] else '<span class="bad">INVALID</span>')
            panels.append(p)
        json.dump(panels, open(f'{OUT}/{out_side}_{name}.json', 'w'), separators=(',', ':'))
    note = ' (session_cpp row: STEP face orientation repaired in the driver; as read the kernel refused the operands)' if name in repaired else ''
    jobs.append([name, f'{name}: {title}{note}', name.startswith('joint')])

for f in ('page.html',):
    src, dst = f'{C}/shots/{f}', f'{OUT}/{f}'
    if not os.path.exists(dst):
        os.symlink(src, dst)
if not os.path.exists(f'{OUT}/node_modules'):
    os.symlink(f'{C}/shots/node_modules', f'{OUT}/node_modules')
json.dump(jobs, open(f'{OUT}/jobs.json', 'w'))
subprocess.run(['node', f'{C}/shots/shoot.cjs', OUT, f'{OUT}/jobs.json', images], check=True)
