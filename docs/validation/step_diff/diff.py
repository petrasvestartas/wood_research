# diff.py <out dir>: first stage where session_cpp's STEP reader/writer differs from OCCT 8.0.1, per file.
# Stages, faces and edges paired by entity id: 1 entity types our reader does not translate, or counted differently by the two parsers;
# 2 edge geometry (length 1e-6 relative, end points); 3 topology per face (wires, entity ids of the edges of each wire, a split piece or an
# edge made by the reader or by ShapeFix counted as 0); 4 pcurves (deviation from the edge curve above 1.5 x OCCT's + 1e-7);
# 5 face areas (1e-6 relative), solid validity and volume (1e-9 relative); 6 writer: ours writes -> OCCT reads (valid, faces,
# volume) and ours reads back (faces, volume); OCCT writes -> ours reads (faces, volume).
import sys, os, re, collections
sys.path.insert(0, '/home/user/session_data/brep_boolean_bench/tools')
from occt_step_bench import file_unit_mm
O = sys.argv[1]
SUPPORTED = set('''AdvancedFace FaceSurface FaceBound FaceOuterBound EdgeLoop VertexLoop OrientedEdge EdgeCurve VertexPoint ClosedShell OpenShell
ManifoldSolidBrep BrepWithVoids ShellBasedSurfaceModel OrientedClosedShell Plane CylindricalSurface ConicalSurface SphericalSurface ToroidalSurface
SurfaceOfRevolution BSplineSurfaceWithKnots BSplineSurfaceWithKnotsAndRationalBSplineSurface QuasiUniformSurface QuasiUniformSurfaceAndRationalBSplineSurface
BezierSurface UniformSurface Line Circle Ellipse Hyperbola Polyline BSplineCurveWithKnots BSplineCurveWithKnotsAndRationalBSplineCurve QuasiUniformCurve
QuasiUniformCurveAndRationalBSplineCurve BezierCurve UniformCurve TrimmedCurve SurfaceCurve SeamCurve IntersectionCurve Pcurve CartesianPoint Direction Vector
Axis2Placement3d Axis2Placement2d Axis1Placement'''.split())
GEOM = re.compile(r'Step(Geom|Shape)_')
def load(p, tag):
    out = collections.defaultdict(list)
    if os.path.exists(p):
        for l in open(p, errors='replace'):
            w = l.split()
            if w and w[0] == tag: out[w[0]].append(w)
            elif w and w[0] in ('UNIT', 'ENT', 'UENT', 'OEDGE', 'EDGE', 'OWIRE', 'WIRE', 'OUSE', 'USE', 'OFACE', 'OSOLID', 'FACE', 'SOLID', 'RT', 'RTFAIL', 'FACESFAIL', 'OFAIL'): out[w[0]].append(w)
    return out
def rel(a, b): return abs(a - b) / max(abs(a), abs(b), 1e-300)
def mismatch(occt, ours):
    o = {w[1].split('_', 1)[1]: int(w[2]) for w in occt['ENT'] if '_' in w[1]}
    for w in ours['UENT']:
        name = ''.join(x[:1] + x[1:].lower() for x in w[1].split('_'))
        if '+' not in w[1] and name in SUPPORTED and name in o and o[name] != int(w[2]):
            return 'entity count %s: OCCT %d ours %s' % (w[1], o[name], w[2])
    return ''
rows = []
for f in [l.strip() for l in open(f'{O}/files.txt')]:
    n = re.sub(r'[^A-Za-z0-9_.-]', '_', f)
    ours, occt, rt, rto, ow = (load(f'{O}/{n}{s}', '') for s in ('.ours', '.occt', '.rt', '.rtocct', '.occtw.ours'))
    stage, what = '-', 'same'
    bad = [w[1] for w in occt['ENT'] if GEOM.match(w[1]) and 'Representation' not in w[1] and 'Context' not in w[1] and 'Style' not in w[1] and w[1].split('_', 1)[1] not in SUPPORTED and re.search(r'Surface|Curve|Line|Circle|Ellipse|Parabola|Hyperbola|Face|Shell|Brep|Loop', w[1])]
    osol = {int(w[2]): w for w in occt['OSOLID']}; usol = {int(w[2]): w for w in ours['SOLID']}
    ofac = collections.defaultdict(list); ufac = collections.defaultdict(list)
    for w in occt['OFACE']: ofac[int(w[2])].append(w + [''] * (10 - len(w)))
    for w in ours['FACE']: ufac[int(w[2])].append(w + [''] * (11 - len(w)))
    def face_ids(lines):  # per solid, face ids in face order, from the wire lines
        out = collections.defaultdict(list)
        for w in lines:
            if not out[int(w[1])] or out[int(w[1])][-1] != int(w[2]) or w[3] == '0': out[int(w[1])].append(int(w[2]))
        return out
    ofid, ufid = face_ids(occt['OWIRE']), face_ids(ours['WIRE'])
    pairs = {}
    for i, w in osol.items():
        cands = [j for j, u in usol.items() if u[3] == w[3]]  # placed instances of one BRep pair with it again
        same = [j for j in cands if ofid.get(i) and sorted(ufid.get(j, [])) == sorted(ofid[i])]
        if cands: pairs[i] = same[0] if same else min(cands, key=lambda j: rel(abs(float(usol[j][6]) if usol[j][6] != 'nan' else 1e300), float(w[5])))
    if bad:
        stage, what = '1', 'entity types not translated: ' + ' '.join(bad)
    elif ours['FACESFAIL'] or not usol:
        stage, what = '1', 'ours did not load: ' + ' '.join(ours['FACESFAIL'][0][2:] if ours['FACESFAIL'] else ['no BRep'])[:100]
    elif mismatch(occt, ours):
        stage, what = '1', mismatch(occt, ours)
    elif len(pairs) < len(osol):
        miss = [i for i in osol if i not in pairs]
        stage, what = '3', 'OCCT solid %d (%s faces) has no BRep of ours with that face count' % (miss[0], osol[miss[0]][3])
    else:
        for i, j in pairs.items():
            oe = collections.defaultdict(list); ue = collections.defaultdict(list)
            for w in occt['OEDGE']:
                if int(w[1]) == i: oe[int(w[2])].append([float(x) for x in w[3:]])
            for w in ours['EDGE']:
                if int(w[1]) == j: ue[int(w[2])].append([float(x) for x in w[3:]])
            for e in sorted(oe):
                if e > 0 and len(oe[e]) == 1 and len(ue.get(e, [])) == 1:
                    a, b = oe[e][0], ue[e][0]
                    ends = min(max(abs(a[1 + q] - b[1 + q]) for q in range(6)), max(abs(a[1 + q] - b[1 + (q + 3) % 6]) for q in range(6)))
                    if rel(a[0], b[0]) > 1e-6 or ends > 1e-6 * max(a[0], 1.0):
                        stage, what = '2', 'solid %d edge #%d: length OCCT %.9g ours %.9g, end points %.2g apart' % (i, e, a[0], b[0], ends); break
            if stage != '-': break
        for i, j in pairs.items():
            if stage != '-': break
            owi = collections.defaultdict(list); uwi = collections.defaultdict(list)
            for w in occt['OWIRE']:
                if int(w[1]) == i: owi[int(w[2])].append(sorted(max(int(x), 0) for x in (w[4] if len(w) > 4 else '').split(',') if x))
            for w in ours['WIRE']:
                if int(w[1]) == j: uwi[int(w[2])].append(sorted(max(int(x), 0) for x in (w[4] if len(w) > 4 else '').split(',') if x))
            for fid in owi:
                if fid > 0 and sorted(owi[fid]) != sorted(uwi.get(fid, [])):
                    show = lambda ws: ' | '.join(','.join(str(x) for x in w) for w in ws)
                    stage, what = '3', 'solid %d face #%d: OCCT wires %s; ours %s' % (i, fid, show(owi[fid])[:120], show(uwi.get(fid, []))[:120]); break
        for i, j in pairs.items():
            if stage != '-': break
            od = collections.defaultdict(float); ud = collections.defaultdict(float)
            for w in occt['OUSE']:
                if int(w[1]) == i: od[(int(w[2]), int(w[3]))] = max(od[(int(w[2]), int(w[3]))], float(w[4]))
            for w in ours['USE']:
                if int(w[1]) == j and int(w[3]) > 0: ud[(int(w[2]), int(w[3]))] = max(ud[(int(w[2]), int(w[3]))], float(w[4]))
            for key in sorted(ud):
                if key in od and key[1] > 0 and ud[key] > 1.5 * od[key] + 1e-7:
                    stage, what = '4', 'solid %d face #%d edge #%d: pcurve deviation OCCT %.2g ours %.2g' % (i, key[0], key[1], od[key], ud[key]); break
        if stage == '-':
            for i, j in pairs.items():
                oa = dict(zip(ofid[i], ofac[i])) if len(ofid[i]) == len(ofac[i]) else dict(enumerate(ofac[i]))
                ua = dict(zip(ufid[j], ufac[j])) if len(ufid[j]) == len(ufac[j]) else dict(enumerate(ufac[j]))
                for k in oa:
                    a, b = oa[k], ua.get(k)
                    if k and b and rel(float(a[4]), float(b[4])) > 1e-6:
                        stage, what = '5', 'solid %d face #%d area OCCT %.9g ours %.9g (rel %.1e)' % (i, k, float(a[4]), float(b[4]), rel(float(a[4]), float(b[4]))); break
                if stage != '-': break
        if stage == '-':
            for i, j in pairs.items():
                u, o = usol[j], osol[i]
                if not (u[4] == '1' and u[5] == '1') or o[4] != '1':
                    stage, what = '5', 'solid %d validity: ours valid %s solid %s, OCCT valid %s' % (i, u[4], u[5], o[4]); break
                if u[6] == 'nan' or rel(abs(float(u[6])), float(o[5])) > 1e-9:
                    stage, what = '5', 'solid %d volume OCCT %.12g ours %s' % (i, float(o[5]), u[6]); break
        if stage == '-' and not os.path.exists(f'{O}/{n}.rt'):
            stage, what = '-', 'same (reader stages)'
        elif stage == '-':
            for w in rt['RT'] + rt['RTFAIL']:
                if w[0] == 'RTFAIL' or 'backfail' in w or w[w.index('back') + 2] != w[3] or (w[5] != 'nan' and w[w.index('back') + 4] != 'nan' and rel(float(w[5]), float(w[w.index('back') + 4])) > 1e-9):
                    stage, what = '6', 'ours write -> ours read: ' + ' '.join(w[2:6] + w[w.index('back'):] if 'back' in w else w[2:])[:140]; break
        if stage == '-' and os.path.exists(f'{O}/{n}.rt'):
            for w in rto['OSOLID']:
                if w[4] != '1':
                    stage, what = '6', 'ours write -> OCCT read: solid not valid (BRepCheck) in ' + os.path.basename(w[1]); break
            if stage == '-' and rto['OFAIL']: stage, what = '6', 'ours write -> OCCT cannot read'
        if stage == '-' and os.path.exists(f'{O}/{n}.rt'):
            k = float(occt['UNIT'][0][1]) if occt['UNIT'] else file_unit_mm(f)
            ov = sorted(float(w[5]) * k ** 3 for w in occt['OSOLID']); uv = sorted(abs(float(w[6])) for w in ow['SOLID'] if w[6] != 'nan')
            if len(ov) != len(uv) or any(rel(a, b) > 1e-9 for a, b in zip(ov, uv)):
                stage, what = '6', 'OCCT write -> ours read: volumes %s vs OCCT %s' % (['%.9g' % x for x in uv[:3]], ['%.9g' % x for x in ov[:3]])
    rows.append((f.replace('/home/user/session_data/brep_boolean_bench/', '').replace('/home/user/', ''), stage, what))
print('| file | first stage differing | what differs |')
print('|---|---|---|')
for r in rows: print('| %s | %s | %s |' % r)
print(collections.Counter(r[1] for r in rows))
