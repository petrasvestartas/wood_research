"""One row per case where ours did not return valid results: which ops failed, the stage (source file of the message) and the first message."""
import os, sys
C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = [('Native BRep Booleans require closed oriented', 'input check (brep_boolean.cpp): operand not a closed oriented solid as read'),
         ('Split curve/trim correspondence', 'split (split.h): original edge/pcurve not same-parameter'),
         ('Required edge event lacks', 'split (split.cpp)'), ('Cannot keep an adjacent trim', 'split (split.cpp)'),
         ('Native Boolean face classification is unresolved', 'classification (split.cpp)'),
         ('Analytic pullback', 'section: SSI pullback (intersection.cpp)'), ('Native SSI', 'section: SSI (intersection.cpp)'),
         ('Empty support inventory', 'section: SSI (intersection.cpp)'), ('Analytic section pcurve', 'section: SSI (intersection.cpp)'),
         ('Interference lacks', 'section: interferences (brep_section.cpp)'), ('Boundary event has invalid', 'section: boundary events (brep_section.cpp)'),
         ('On-surface overlap', 'section: curve/surface (curve_surface_intersection.cpp)'),
         ('pcurve reparameterization', 'assembly (brep_assemble.cpp)'), ('edge and pcurve disagree', 'assembly (brep_assemble.cpp)'),
         ('stoul', 'load: STEP reader returned no BRep for this file')]
def stage(m):
    return next((s for k, s in STAGE if m.startswith(k)), 'other: ' + m[:60])
raw = sys.argv[1]
rows = {}
for l in open(f'{C}/run/{raw}'):
    p = l.split()
    if p[1] != 'OP' or p[3] in ('ok', 'SLOW'):
        continue
    msg = l.split(' volume nan ', 1)[1].strip() if ' volume nan ' in l else ''
    rows.setdefault(p[0], []).append((p[2], p[3], msg))
import collections
if len(sys.argv) > 2:
    cnt = collections.Counter(stage(m) for r in rows.values() for _, _, m in r)
    print('| booleans | stage |')
    print('|---|---|')
    for k, v in cnt.most_common():
        print(f'| {v} | {k} |')
    sys.exit()
print('| case | ops not returned | stage | first message |')
print('|---|---|---|---|')
for n, r in rows.items():
    print(f"| {n} | {' '.join(o for o, _, _ in r)} | {stage(r[0][2])} | {r[0][1]}: {r[0][2][:150].replace('|', '/')} |")
