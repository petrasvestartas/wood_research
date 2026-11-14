"""Tables for RESULTS.md from run/raw_{ours,occt}.txt and run/cases.tsv (markdown on stdout).
A boolean counts as a success when it returns and its result is valid (ours: is_valid() and is_solid(), or empty with
0 faces; OCCT: BRepCheck_Analyzer). Volumes agree when |ours - OCCT| <= 1e-6 * max(|OCCT|, scale), where scale is
1e-3 of the OCCT union volume of the case (so empty results compare against the operands' size)."""
import math, os, sys
from collections import defaultdict

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPS = ['intersection', 'union', 'a-b', 'b-a', 'xor']


REPAIR = len(sys.argv) > 1 and sys.argv[1] == 'repair'  # ours from run/raw_ours_repair.txt (driver-side orientation repair)


def load(side):
    r = {}
    for line in open(f'{C}/run/raw_{side}.txt'):
        p = line.split()
        if len(p) < 3 or p[1] != 'OP':
            continue
        q = p[2:]
        d = {'status': q[1], 's': float(q[3])}
        try:
            d['faces'], d['edges'], d['verts'] = int(q[5]), int(q[6]), int(q[7])
            d['solids'] = int(q[11])
            d['valid'] = d['faces'] == 0 or (q[13] == '1' and (side == 'occt' or q[15] == '1'))
            v = q[q.index('volume') + 1] if 'volume' in q else 'nan'
            d['mesh_volume'] = '(mesh)' in v
            d['volume'] = float(v.replace('(mesh)', ''))
            d['msg'] = ' '.join(q[q.index('volume') + 2:]) if 'volume' in q else ''
        except (ValueError, IndexError):
            d.update(faces=0, edges=0, verts=0, solids=0, valid=False, volume=float('nan'), msg='', mesh_volume=False)
        if d['status'] not in ('ok', 'SLOW'):
            d['valid'] = False
        r[(p[0], q[0])] = d
    return r


ours, occt = load('ours_repair' if REPAIR else 'ours'), load('occt')
cases = [l.rstrip('\n').split('\t') for l in open(f'{C}/run/cases.tsv')]


def group(name):
    return 'chairs' if name.startswith('chair') else 'twisted' if name.startswith('twisted') else \
        'joints as stored' if name.startswith('joint') and not name.endswith('_rot') else 'joints rotated' if name.startswith('joint') else \
        'element vs rotated self' if name.endswith('_self') else 'element vs box' if name.endswith('_box') else 'element vs cylinder'


def gmean(xs):
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else float('nan')


rows, agg = [], defaultdict(lambda: defaultdict(list))
failures = []
for name, title, *_ in cases:
    if (name, 'intersection') not in ours:
        continue
    g = group(name)
    scale = 1e-3 * abs(occt.get((name, 'union'), {}).get('volume', float('nan')))
    per = {'ok_o': 0, 'ok_c': 0, 'inv_o': 0, 'inv_c': 0, 'fail_o': 0, 'fail_c': 0, 'agree': 0, 'cmp': 0, 'maxrel': 0.0,
           't_o': 0.0, 't_c': 0.0, 'tx_o': float('nan'), 'tx_c': float('nan'), 'tx3_c': float('nan'), 'ratios': []}
    for op in OPS:
        o = ours.get((name, op))
        c = occt.get((name, 'xorcells' if op == 'xor' else op))
        c3 = occt.get((name, 'xor3')) if op == 'xor' else None
        if o is None or c is None:
            continue
        for d, k in ((o, 'o'), (c, 'c')):
            if d['status'] not in ('ok', 'SLOW'):
                per['fail_' + k] += 1
            elif not d['valid']:
                per['inv_' + k] += 1
            else:
                per['ok_' + k] += 1
        both = o['status'] in ('ok', 'SLOW') and c['status'] == 'ok'
        rel = float('nan')
        if both and not math.isnan(o['volume']) and not math.isnan(c['volume']):
            rel = abs(o['volume'] - c['volume']) / max(abs(c['volume']), scale if scale == scale else 1e-30, 1e-300)
            per['cmp'] += 1
            per['maxrel'] = max(per['maxrel'], rel)
            if rel <= 1e-6:
                per['agree'] += 1
        agg[g]['rel'].append(rel)
        if both:
            r = max(o['s'], 1e-6) / max(c['s'], 1e-6)
            if op == 'xor':
                per['tx_o'], per['tx_c'] = o['s'], c['s']
                per['tx3_c'] = c3['s'] if c3 and c3['status'] == 'ok' else float('nan')
                agg[g]['xratio'].append(r)
                agg['ALL']['xratio'].append(r)
                agg[g]['tx_o'].append(o['s']); agg[g]['tx_c'].append(c['s'])
                agg['ALL']['tx_o'].append(o['s']); agg['ALL']['tx_c'].append(c['s'])
                if c3 and c3['status'] == 'ok':
                    agg[g]['x3ratio'].append(max(o['s'], 1e-6) / max(c3['s'], 1e-6))
                    agg['ALL']['x3ratio'].append(max(o['s'], 1e-6) / max(c3['s'], 1e-6))
                    agg[g]['tx3_c'].append(c3['s']); agg['ALL']['tx3_c'].append(c3['s'])
            else:
                per['t_o'] += o['s']
                per['t_c'] += c['s']
                per['ratios'].append(r)
                agg[g]['ratio'].append(r)
                agg['ALL']['ratio'].append(r)
                agg[g]['t_o'].append(o['s']); agg[g]['t_c'].append(c['s'])
                agg['ALL']['t_o'].append(o['s']); agg['ALL']['t_c'].append(c['s'])
        bad_o = o['status'] not in ('ok', 'SLOW') or not o['valid'] or (both and rel > 1e-6)
        if bad_o or o['status'] == 'SLOW' or o['s'] > 10:
            why = o['status'] if o['status'] not in ('ok',) else ('INVALID' if not o['valid'] else ('VOLUME' if rel > 1e-6 else 'SLOW'))
            failures.append((name, op, why, o, c, rel))
        for k, d in (('o', o), ('c', c)):
            agg[g]['n_' + k].append(d['status'] in ('ok', 'SLOW') and d['valid'])
    for k in ('ok_o', 'ok_c', 'inv_o', 'inv_c', 'fail_o', 'fail_c', 'agree', 'cmp'):
        agg[g][k].append(per[k])
        agg['ALL'][k].append(per[k])
    rows.append((name, g, per))


def fmt(x, n=3):
    return '–' if x != x else f'{x:.{n}g}'


print('## Summary by group\n')
print('| group | cases | booleans | ours ok / invalid / failed | OCCT ok / invalid / failed | volumes agree (1e-6) | ours s (4 single ops) | OCCT s | total ratio | geo-mean ratio | xor: ours s / OCCT cells s / OCCT 3-bool s | xor geo-mean ratio vs cells / vs 3-bool |')
print('|---|---|---|---|---|---|---|---|---|---|---|---|')
for g in ['chairs', 'twisted', 'joints as stored', 'joints rotated', 'element vs rotated self', 'element vs box', 'element vs cylinder', 'ALL']:
    a = agg[g]
    if not a['ok_o']:
        continue
    n = len(a['ok_o']) if g != 'ALL' else len(rows)
    nb = sum(a['ok_o']) + sum(a['inv_o']) + sum(a['fail_o'])
    print(f"| {g} | {n} | {nb} | {sum(a['ok_o'])} / {sum(a['inv_o'])} / {sum(a['fail_o'])} | {sum(a['ok_c'])} / {sum(a['inv_c'])} / {sum(a['fail_c'])} | "
          f"{sum(a['agree'])} of {sum(a['cmp'])} | {sum(a['t_o']):.2f} | {sum(a['t_c']):.2f} | {fmt(sum(a['t_o']) / sum(a['t_c']) if a['t_c'] else float('nan'))} | "
          f"{fmt(gmean(a['ratio']))} | {sum(a['tx_o']):.2f} / {sum(a['tx_c']):.2f} / {sum(a['tx3_c']):.2f} | {fmt(gmean(a['xratio']))} / {fmt(gmean(a['x3ratio']))} |")

print('\n## Per case\n')
print('Times are the sum of the four single booleans (∩ ∪ A−B B−A) where both kernels returned; xor separately (OCCT: CellsBuilder, one general fuse). '
      'ratio = ours / OCCT. "agree" counts booleans whose volumes agree to 1e-6 relative.\n')
print('| case | ours ok/inv/fail | OCCT ok/inv/fail | agree | max rel vol diff | ours s | OCCT s | ratio | geo-mean | xor ours s | xor OCCT cells s | xor OCCT 3-bool s | picture |')
print('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
for name, g, p in rows:
    print(f"| {name} | {p['ok_o']}/{p['inv_o']}/{p['fail_o']} | {p['ok_c']}/{p['inv_c']}/{p['fail_c']} | {p['agree']}/{p['cmp']} | {fmt(p['maxrel'], 2)} | "
          f"{p['t_o']:.3f} | {p['t_c']:.3f} | {fmt(p['t_o'] / p['t_c'] if p['t_c'] else float('nan'))} | {fmt(gmean(p['ratios']))} | "
          f"{fmt(p['tx_o'], 3)} | {fmt(p['tx_c'], 3)} | {fmt(p['tx3_c'], 3)} | [png](images/cmp_{name}.png) |")

print('\n## Booleans of ours that failed, were invalid, disagree in volume, or took over 10 s\n')
print('| case | op | what | ours s | ours faces/edges/vertices | OCCT s | OCCT faces/edges/vertices | ours volume | OCCT volume | rel diff | ours message |')
print('|---|---|---|---|---|---|---|---|---|---|---|')
for name, op, why, o, c, rel in failures:
    print(f"| {name} | {op} | {why} | {o['s']:.2f} | {o['faces']}/{o['edges']}/{o['verts']} | {c['s']:.3f} | {c['faces']}/{c['edges']}/{c['verts']} | "
          f"{o['volume']:.10g}{' (mesh)' if o.get('mesh_volume') else ''} | {c['volume']:.10g} | {fmt(rel, 2)} | {o['msg'][:160].replace('|', '/')} |")

occt_bad = [(k, d) for k, d in occt.items() if d['status'] != 'ok' or not d['valid']]
print('\n## OCCT booleans that failed or were invalid\n')
if not occt_bad:
    print('None.')
else:
    print('| case | op | status | valid | s | message |')
    print('|---|---|---|---|---|---|')
    for (name, op), d in occt_bad:
        print(f"| {name} | {op} | {d['status']} | {int(d['valid'])} | {d['s']:.3f} | {d['msg'][:160].replace('|', '/')} |")
