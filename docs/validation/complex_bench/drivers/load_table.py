"""Load table (markdown) from run/load_occt.txt (OCCT STEP reader via OCP 8.0.1), run/solids_occt.txt and run/load_ours.txt."""
import os
from collections import defaultdict

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
occt = {}
for line in open(f'{C}/run/load_occt.txt'):
    p = line.split()
    d = dict(status=p[2], read_s=float(p[4]))
    if p[2] == 'ok':
        d.update(solids=int(p[8]), faces=int(p[12]), kinds=p[13][6:], valid=p[15], volume=float(p[17]))
    occt[p[1]] = d
ours, breps = {}, defaultdict(list)
for line in open(f'{C}/run/load_ours.txt'):
    p = line.split()
    name = os.path.basename(p[1])
    if p[0] == 'LOAD':
        ours[name] = dict(status=p[2], read_s=float(p[4]), n=int(p[6]), msg=' '.join(p[7:]))
    elif p[0] == 'BREP':
        vol = p[p.index('volume') + 1]
        breps[name].append(dict(faces=int(p[3]), shells=int(p[6]), solids=int(p[7]), valid=p[8] == '1', solid=p[9] == '1',
                                kinds=[int(x) for x in p[10][6:].split(',')], volume=float(vol.replace('(mesh)', '')), mesh='(mesh)' in vol))

print('| file | OCCT read | OCCT solids | OCCT faces | OCCT kinds plane/cyl/cone/sphere/torus/bspline/other | OCCT valid | OCCT volume | ours read | ours breps | ours faces | ours kinds plane/cyl/cone/sphere/torus/free (recognised) | ours valid & solid | ours volume (sum) | rel diff |')
print('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
for name, o in occt.items():
    u = ours.get(name, dict(status='not run', read_s=0, n=0, msg=''))
    bs = breps.get(name, [])
    k = [0] * 6
    for b in bs:
        for i, v in enumerate(b['kinds']):
            k[i] += v
    # ours kinds come as plane,sphere,cylinder,cone,torus,free; print in OCCT's order plane,cyl,cone,sphere,torus,free
    kind = f'{k[0]},{k[2]},{k[3]},{k[1]},{k[4]},{k[5]}'
    vol = sum(abs(b['volume']) for b in bs)
    good = sum(1 for b in bs if b['valid'] and b['solid'])
    rel = abs(vol - o['volume']) / o['volume'] if o.get('volume') else float('nan')
    neg = sum(1 for b in bs if b['volume'] < 0)
    print(f"| {name} | {o['status']} {o['read_s']:.3f} s | {o.get('solids', '-')} | {o.get('faces', '-')} | {o.get('kinds', '-')} | {o.get('valid', '-')} | {o.get('volume', float('nan')):.10g} | "
          f"{u['status']} {u['read_s']:.3f} s{(' ' + u['msg'][:80]) if u['msg'] else ''} | {u['n']} | {sum(b['faces'] for b in bs)} | {kind} | {good} of {len(bs)}{f' ({neg} negative volume)' if neg else ''} | "
          f"{vol:.10g}{' (mesh)' if any(b['mesh'] for b in bs) else ''} | {rel:.2g} |")
