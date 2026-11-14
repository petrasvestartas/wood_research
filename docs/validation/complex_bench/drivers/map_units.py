"""Operands ("units") of the bench: one per BRep our STEP reader returns, paired with the OCCT solid(s) of the same file
that make up the same geometry (OCCT's STEP reader splits a shell with several disjoint pieces into several solids, ours
keeps one BRep). Pairing: equal total face count, then nearest bounding-box centre. A file our reader returns nothing
for keeps OCCT's solids as units (our side then fails to load those operands).
Writes brep/<stem>.u<k>.brep (a compound when several OCCT solids) and prints
   UNIT <stem> <k> <ours index or -> <occt solid indices> faces <n> volume <occt volume> bbox <occt bbox>"""
import itertools, math, os, sys
from OCP.BRepTools import BRepTools
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Shape, TopoDS_Compound
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
occt = {}
for line in open(f'{C}/run/solids_occt.txt'):
    _, brep, faces, vol, bbox, kinds, valid = line.split()
    stem, idx = brep[:-5].rsplit('.s', 1)
    occt.setdefault(stem, {})[int(idx)] = dict(faces=int(faces), vol=float(vol), bbox=[float(x) for x in bbox.split(',')])
ours = {}
for line in open(f'{C}/run/load_ours.txt'):
    p = line.split()
    stem = os.path.splitext(os.path.basename(p[1]))[0]
    if p[0] == 'LOAD':
        ours.setdefault(stem, [])
    elif p[0] == 'BREP':
        ours[stem].append(dict(i=int(p[2]), faces=int(p[3]), bbox=[float(x) for x in p[p.index('bbox') + 1].split(',')]))


def centre(b):
    return [(b[i] + b[i + 3]) / 2 for i in range(3)]


def merged(boxes):
    return [min(b[i] for b in boxes) for i in range(3)] + [max(b[i + 3] for b in boxes) for i in range(3)]


def write(stem, k, idx):
    b = BRep_Builder()
    if len(idx) == 1:
        s = TopoDS_Shape(); BRepTools.Read_s(s, f'{C}/brep/{stem}.s{idx[0]}.brep', b)
    else:
        s = TopoDS_Compound(); b.MakeCompound(s)
        for i in idx:
            t = TopoDS_Shape(); BRepTools.Read_s(t, f'{C}/brep/{stem}.s{i}.brep', b); b.Add(s, t)
    BRepTools.Write_s(s, f'{C}/brep/{stem}.u{k}.brep')
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(s, g, 1e-9)
    box = Bnd_Box(); BRepBndLib.Add_s(s, box, False); lo, hi = box.CornerMin(), box.CornerMax()
    return g.Mass(), [lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()]


for stem in sorted(occt):
    solids = occt[stem]
    mine = ours.get(stem, [])
    units = []
    if not mine:
        units = [(None, [i]) for i in sorted(solids)]
    else:
        free = set(solids)
        for u in mine:
            best = None
            for n in (1, 2, 3):
                for combo in itertools.combinations(sorted(free), n):
                    if sum(solids[i]['faces'] for i in combo) != u['faces']:
                        continue
                    d = math.dist(centre(merged([solids[i]['bbox'] for i in combo])), centre(u['bbox']))
                    if best is None or d < best[0]:
                        best = (d, combo)
                if best:
                    break
            if best is None:  # no face-count match (e.g. one BRep for the whole file): take all remaining solids
                best = (0, tuple(sorted(free))) if len(mine) == 1 else None
            if best is None:
                print(f'# no OCCT match for {stem} ours {u["i"]}', file=sys.stderr)
                continue
            free -= set(best[1])
            units.append((u['i'], list(best[1])))
        if free:
            print(f'# OCCT solids of {stem} left unmatched: {sorted(free)}', file=sys.stderr)
    for k, (oi, idx) in enumerate(units):
        vol, bb = write(stem, k, idx)
        print(f"UNIT {stem} {k} {'-' if oi is None else oi} {','.join(map(str, idx))} faces {sum(solids[i]['faces'] for i in idx)} volume {vol!r} bbox {','.join('%.9g' % x for x in bb)}")
