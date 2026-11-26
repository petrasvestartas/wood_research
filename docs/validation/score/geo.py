# geo.py: the geometry of our boolean results against OCCT's, with OCCT's own tools (run with the OCP venv python).
#   geo.py cmp <ours.json> <occt.brep> <out.json>   one boolean: ours (score_drv, SCORE_GEO) against
#     the shape occt_ref.py geo stored; prints the row of geo.tsv, writes the detail (per vertex, edge and face)
#   geo.py run <run dir> <data dir> [--jobs 2]   every ok boolean of <run dir>/results.tsv -> <run dir>/geo.tsv, detail in
#     <run dir>/geo/<name>.cmp.json; rows already there are kept
# Measures. A bound is the larger of the two shapes' own tolerances there (what the operands' tolerances became in the
# results) and FLOOR = 1e-6 of the result's diagonal, the relative bound of the volume rule:
#   vertices  each vertex to the nearest of the other side; bound max(both vertex tolerances, FLOOR)
#   edges     33 points of each edge over its range to the other side's edges (nearest stored point, then Newton on the
#             exact curve within its range; ours are transferred as their NURBS, checked against our own points); bound
#             max(both edge tolerances, FLOOR); an edge with a point outside it has no counterpart; lengths by OCCT
#   faces     ours: area and centroid integrated by the driver; OCCT: BRepGProp (eps 1e-9). Paired one to one by
#             centroid distance / diagonal + relative area difference; a pair matches when the areas agree within
#             perimeter * max(both faces' tolerances, FLOOR) + 1e-6 area + both integration errors (a face's tolerance:
#             the largest of the face, its edges and their vertices: its boundary may lie that far off) and the centroids within
#             that area bound / area * perimeter / 2 + the tolerance; a pair further apart than half its size or 50 % in
#             area is two faces without counterpart
#   mesh      of ours (face_meshes(), the viewer's: 20 degrees, chord 0.005 of the diagonal): a face without triangles is
#             undrawn; one whose triangles' area is off its area by more than MESH_REL (what an inscribed mesh at 20
#             degrees can lose) + MESH_EDGE * perimeter * chord, or whose triangles' centroid is further from the face's
#             than chord + MESH_SAG * perimeter (the sagitta such a mesh can have), is wrongly drawn
#   *_over    the worst distance (area difference) as a multiple of its own bound: above 1 is a difference
#   bbox      largest difference of a box coordinate (ours from what is drawn, OCCT's exact)
import concurrent.futures as cf, json, math, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
COLS = ['suite', 'case', 'op', 'status', 'vertices', 'edges', 'faces', 'draws', 'v_worst', 'v_bound', 'v_ours', 'v_occt', 'e_worst_ours', 'e_worst_occt', 'e_bound',
        'e_ours', 'e_occt', 'len_ours', 'len_occt', 'f_worst', 'f_differ', 'f_ours', 'f_occt', 'area_ours', 'area_occt', 'n_faces', 'undrawn', 'wrong',
        'mesh_s', 'tol_ours', 'tol_occt', 'v_over', 'e_over', 'f_over', 'bbox', 'note']
MESH_REL, MESH_EDGE, MESH_SAG = 0.03, 0.1, 0.015


def geo_name(suite, case, op):
    return '%s__%s__%s' % (suite, re.sub(r'[^A-Za-z0-9_.-]', '_', case), op)


def compare(ours_f, brep_f, out_f):
    import numpy as np
    from OCP.TopoDS import TopoDS, TopoDS_Shape
    from OCP.TopExp import TopExp, TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.BRep import BRep_Builder, BRep_Tool
    from OCP.BRepTools import BRepTools
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAdaptor import GeomAdaptor_Curve
    from OCP.Geom import Geom_BSplineCurve
    from OCP.GCPnts import GCPnts_AbscissaPoint
    from OCP.GProp import GProp_GProps
    from OCP.BRepGProp import BRepGProp
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.collections import Array1_gp_Pnt, Array1_double, Array1_int
    from OCP.gp import gp_Pnt, gp_Vec

    P, V1, V2 = gp_Pnt(), gp_Vec(), gp_Vec()

    class Crv:
        def __init__(self, ad, tol, seam):
            self.ad, self.tol, self.seam = ad, tol, seam
            self.t0, self.t1 = ad.FirstParameter(), ad.LastParameter()
            self.ts = np.linspace(self.t0, self.t1, 33)
            self.pts = np.array([(lambda p: (p.X(), p.Y(), p.Z()))(ad.Value(t)) for t in self.ts])
            self.length = GCPnts_AbscissaPoint.Length_s(ad)

        def near(self, q, k):
            # distance from q to the curve within its range: Newton from stored point k, never worse than that point
            t, lo, hi = self.ts[k], self.t0, self.t1
            best = math.dist(q, self.pts[k])
            for _ in range(12):
                self.ad.D2(t, P, V1, V2)
                d = (P.X() - q[0], P.Y() - q[1], P.Z() - q[2])
                best = min(best, math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]))
                f = d[0] * V1.X() + d[1] * V1.Y() + d[2] * V1.Z()
                g = V1.SquareMagnitude() + d[0] * V2.X() + d[1] * V2.Y() + d[2] * V2.Z()
                step = -f / g if g > 0 else -math.copysign((hi - lo) / 64, f)
                step = max(-(hi - lo) / 16, min((hi - lo) / 16, step))
                new = max(lo, min(hi, t + step))
                if abs(new - t) <= 1e-15 * max(1.0, abs(t)):
                    break
                t = new
            self.ad.D0(t, P)
            return min(best, math.dist(q, (P.X(), P.Y(), P.Z())))

    def to_set(points, curves):
        # per point: distance to the nearest of the curves, and that curve
        if not curves or not len(points):
            return np.full(len(points), np.inf), np.full(len(points), -1)
        target = np.vstack([c.pts for c in curves])
        owner = np.repeat(np.arange(len(curves)), 33)
        dist, which = np.empty(len(points)), np.empty(len(points), int)
        rows = max(1, int(2e7 // len(target)))
        for a in range(0, len(points), rows):
            q = points[a:a + rows]
            d2 = (q * q).sum(1)[:, None] + (target * target).sum(1)[None, :] - 2.0 * q @ target.T
            near = np.argpartition(d2, min(3, d2.shape[1] - 1), axis=1)[:, :4] if d2.shape[1] > 4 else np.argsort(d2, axis=1)
            for i in range(len(q)):
                best, at, seen = float('inf'), -1, set()
                for j in sorted(near[i], key=lambda j: d2[i, j]):
                    if owner[j] in seen:
                        continue
                    seen.add(owner[j])
                    d = curves[owner[j]].near(q[i], j % 33)
                    if d < best:
                        best, at = d, owner[j]
                    if best < 0.01 * floor:
                        break
                dist[a + i], which[a + i] = best, at
        return dist, which

    ours = json.load(open(ours_f))
    try:
        mesh = json.load(open(ours_f + '.mesh'))
    except (OSError, ValueError):
        mesh = {'failed': 'face_meshes() not back'}
    drawn_box = mesh.get('bbox', ours['bbox'])
    shape = TopoDS_Shape()
    BRepTools.Read_s(shape, brep_f, BRep_Builder())

    def mapped(kind):
        m = ShapeMap()
        TopExp.MapShapes_s(shape, kind, m)
        return m

    # OCCT's side
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    occt_box = None if box.IsVoid() else [box.CornerMin().X(), box.CornerMin().Y(), box.CornerMin().Z(), box.CornerMax().X(), box.CornerMax().Y(), box.CornerMax().Z()]
    diag = math.dist(occt_box[:3], occt_box[3:]) if occt_box else math.dist(ours['bbox'][:3], ours['bbox'][3:]) if ours['verts'] else 1.0
    floor = 1e-6 * diag
    vm, em, fm = mapped(TopAbs_VERTEX), mapped(TopAbs_EDGE), mapped(TopAbs_FACE)
    ov = np.array([(lambda p: (p.X(), p.Y(), p.Z()))(BRep_Tool.Pnt_s(TopoDS.Vertex(vm.FindKey(i)))) for i in range(1, vm.Extent() + 1)]).reshape(-1, 3)
    ov_tol = np.array([BRep_Tool.Tolerance_s(TopoDS.Vertex(vm.FindKey(i))) for i in range(1, vm.Extent() + 1)])
    seams, face_edges, face_tol = set(), [], []
    for i in range(1, fm.Extent() + 1):
        f, e, v, mine, tol = TopoDS.Face(fm.FindKey(i)), TopExp_Explorer(fm.FindKey(i), TopAbs_EDGE), TopExp_Explorer(fm.FindKey(i), TopAbs_VERTEX), set(), 0.0
        while e.More():
            mine.add(em.FindIndex(e.Current()))
            tol = max(tol, BRep_Tool.Tolerance_s(TopoDS.Edge(e.Current())))
            if BRep_Tool.IsClosed_s(TopoDS.Edge(e.Current()), f):
                seams.add(em.FindIndex(e.Current()))
            e.Next()
        while v.More():
            tol = max(tol, BRep_Tool.Tolerance_s(TopoDS.Vertex(v.Current())))
            v.Next()
        face_edges.append(mine)
        face_tol.append(max(tol, BRep_Tool.Tolerance_s(f)))
    oe, oe_index = [], {}
    for i in range(1, em.Extent() + 1):
        e = TopoDS.Edge(em.FindKey(i))
        if not BRep_Tool.Degenerated_s(e):
            oe_index[i] = len(oe)
            oe.append(Crv(BRepAdaptor_Curve(e), BRep_Tool.Tolerance_s(e), i in seams))
    of = []
    for i in range(1, fm.Extent() + 1):
        g = GProp_GProps()
        err = BRepGProp.SurfaceProperties_s(fm.FindKey(i), g, 1e-9)
        c = g.CentreOfMass()
        of.append({'area': g.Mass(), 'acc': abs(err) * abs(g.Mass()), 'c': [c.X(), c.Y(), c.Z()], 'tol': face_tol[i - 1],
                   'perimeter': sum(oe[oe_index[k]].length for k in face_edges[i - 1] if k in oe_index)})

    # ours: vertices as they are, edges as OCCT curves of their NURBS
    uv = np.array([v[:3] for v in ours['verts']]).reshape(-1, 3)
    uv_tol = np.array([v[3] for v in ours['verts']])
    ue, transfer, notes = [], 0.0, []
    for e in ours['edges']:
        pts = np.array(e['pts']).reshape(-1, 3)
        try:
            k, cv, deg = e['knots'], np.array(e['cvs']).reshape(-1, 4), e['degree']
            full = [k[0]] + k + [k[-1]]
            knots = sorted(set(full))
            poles, weights = Array1_gp_Pnt(1, len(cv)), Array1_double(1, len(cv))
            ks, ms = Array1_double(1, len(knots)), Array1_int(1, len(knots))
            for i, c in enumerate(cv):
                poles.SetValue(i + 1, gp_Pnt(*c[:3]))
                weights.SetValue(i + 1, c[3])
            for i, x in enumerate(knots):
                ks.SetValue(i + 1, x)
                ms.SetValue(i + 1, full.count(x))
            crv = Crv(GeomAdaptor_Curve(Geom_BSplineCurve(poles, weights, ks, ms, deg)), e['tol'], bool(e['seam']))
            transfer = max(transfer, max(crv.near(q, min(range(33), key=lambda j: math.dist(q, crv.pts[j]))) for q in pts))
            crv.at = len(ue)
        except Exception as x:
            notes.append('edge %d not transferred: %s' % (e['i'], str(x).split('\n')[0][:60]))
            continue
        ue.append(crv)
    if transfer > 0.01 * floor:
        notes.append('our NURBS edges are %.2g off our curves' % transfer)

    # (a) vertices
    def nearest(a, b):
        if not len(a) or not len(b):
            return np.full(len(a), np.inf), np.zeros(len(a), int)
        d = np.sqrt(((a[:, None, :] - b[None, :, :]) ** 2).sum(2))
        return d.min(1), d.argmin(1)

    d_uo, j_uo = nearest(uv, ov)
    d_ou, j_ou = nearest(ov, uv)
    b_uo = np.maximum(np.maximum(uv_tol, ov_tol[j_uo] if len(ov) else 0), floor)
    b_ou = np.maximum(np.maximum(ov_tol, uv_tol[j_ou] if len(uv) else 0), floor)
    v_ours, v_occt = [int(i) for i in np.nonzero(d_uo > b_uo)[0]], [int(i) for i in np.nonzero(d_ou > b_ou)[0]]

    # (b) edges
    def edges_against(src, dst):
        if not src:
            return [], [], []
        d, w = to_set(np.vstack([c.pts for c in src]), dst)
        worst, lost, over = [], [], []
        for i, c in enumerate(src):
            di, wi = d[33 * i:33 * i + 33], w[33 * i:33 * i + 33]
            bound = np.array([max(c.tol, dst[k].tol if k >= 0 else 0.0, floor) for k in wi])
            worst.append(float(di.max()))
            over.append(float((di / bound).max()))
            if (di > bound).any():
                lost.append(i)
        return worst, lost, over

    w_uo, e_ours, x_uo = edges_against(ue, oe)
    w_ou, e_occt, x_ou = edges_against(oe, ue)
    e_bound = max([c.tol for c in ue + oe] + [floor])

    # (c) faces
    uf = ours['faces']
    pairs = sorted((math.dist(a['c'], b['c']) / diag + abs(a['area'] - b['area']) / max(a['area'], b['area'], 1e-300), i, j)
                   for i, a in enumerate(uf) for j, b in enumerate(of))
    got_u, got_o, f_rows, f_ours, f_occt, f_differ, f_worst, f_over = set(), set(), [], [], [], [], 0.0, 0.0
    for cost, i, j in pairs:
        if i in got_u or j in got_o:
            continue
        a, b = uf[i], of[j]
        size, big = max(a['perimeter'], b['perimeter']), max(a['area'], b['area'], 1e-300)
        dc, da = math.dist(a['c'], b['c']), abs(a['area'] - b['area'])
        if dc > 0.25 * size or da > 0.5 * big:
            continue
        got_u.add(i)
        got_o.add(j)
        tol = max(a['tol'], b['tol'], floor)
        bound = size * tol + 1e-6 * big + a['acc'] + b['acc']
        ok = da <= bound and dc <= bound / big * size / 2 + tol and not a['note']
        f_worst, f_over = max(f_worst, da / big), max(f_over, da / bound, dc / (bound / big * size / 2 + tol))
        if not ok:
            f_differ.append(i)
        f_rows.append({'ours': i, 'occt': j, 'area_ours': a['area'], 'area_occt': b['area'], 'centroids_apart': dc, 'area_bound': bound, 'ok': ok})
    f_ours, f_occt = [i for i in range(len(uf)) if i not in got_u], [j for j in range(len(of)) if j not in got_o]

    # (d) the viewer's mesh of ours
    our_diag = math.dist(ours['bbox'][:3], ours['bbox'][3:]) if uf else 0.0
    undrawn, wrong, mesh_rows, allowed = [], [], [], [MESH_REL * f['area'] + MESH_EDGE * f['perimeter'] * 0.005 * our_diag for f in uf]
    apart = [0.005 * our_diag + MESH_SAG * f['perimeter'] for f in uf]
    for i, f in enumerate(uf):
        t = mesh['faces'][i] if 'faces' in mesh else {'tris': 0, 'why': mesh['failed']}
        if not t['tris']:
            undrawn.append(i)
            mesh_rows.append({'face': i, 'what': 'undrawn', 'area': f['area'], 'why': t['why']})
        elif not f['note'] and (abs(t['mesh_area'] - f['area']) > allowed[i] or math.dist(t['c'], f['c']) > apart[i]):
            wrong.append(i)
            mesh_rows.append({'face': i, 'what': 'wrong', 'area': f['area'], 'mesh_area': t['mesh_area'], 'allowed': allowed[i], 'triangles': t['tris'],
                              'why': 'triangles %.3g from the face (allowed %.3g), area %+.1f %%' % (math.dist(t['c'], f['c']), apart[i], 100 * (t['mesh_area'] - f['area']) / f['area'])})
    notes += ['area of face %d: %s' % (i, f['note']) for i, f in enumerate(uf) if f['note']][:3]

    box_diff = max(abs(a - b) for a, b in zip(drawn_box, occt_box)) if occt_box and uf else 0.0 if not occt_box and not uf else float('inf')
    flat = lambda a: [round(float(x), 6) for x in np.asarray(a).ravel()]
    row = {'vertices': int(not v_ours and not v_occt), 'edges': int(not e_ours and not e_occt and len(ue) == len(ours['edges'])),
           'faces': int(not f_differ and not f_ours and not f_occt), 'draws': int(not undrawn and not wrong),
           'v_worst': max([0.0] + list(d_uo) + list(d_ou)), 'v_bound': max([floor] + list(b_uo) + list(b_ou)), 'v_ours': len(v_ours), 'v_occt': len(v_occt),
           'e_worst_ours': max([0.0] + w_uo), 'e_worst_occt': max([0.0] + w_ou), 'e_bound': e_bound, 'e_ours': len(e_ours), 'e_occt': len(e_occt),
           'len_ours': sum(c.length for c in ue), 'len_occt': sum(c.length for c in oe), 'f_worst': f_worst, 'f_differ': len(f_differ), 'f_ours': len(f_ours),
           'f_occt': len(f_occt), 'area_ours': sum(f['area'] for f in uf), 'area_occt': sum(f['area'] for f in of), 'n_faces': len(uf), 'undrawn': len(undrawn),
           'wrong': len(wrong), 'mesh_s': mesh.get('seconds', -1.0), 'tol_ours': max([0.0] + list(uv_tol) + [c.tol for c in ue]),
           'tol_occt': max([0.0] + list(ov_tol) + [c.tol for c in oe]), 'v_over': float(max([0.0] + list(d_uo / b_uo) + list(d_ou / b_ou))),
           'e_over': max([0.0] + x_uo + x_ou), 'f_over': float('inf') if f_ours or f_occt else f_over, 'bbox': box_diff, 'note': '; '.join(notes)}
    detail = dict(row, floor=floor, diagonal=diag, transfer=transfer,
                  vertices_ours=[{'vertex': i, 'distance': float(d_uo[i]), 'bound': float(b_uo[i]), 'p': flat(uv[i])} for i in v_ours],
                  vertices_occt=[{'vertex': i, 'distance': float(d_ou[i]), 'bound': float(b_ou[i]), 'p': flat(ov[i])} for i in v_occt],
                  edges_ours=[{'edge': i, 'distance': w_uo[i], 'over': x_uo[i], 'length': ue[i].length, 'seam': ue[i].seam, 'pts': flat(ue[i].pts)} for i in e_ours],
                  edges_occt=[{'edge': i, 'distance': w_ou[i], 'over': x_ou[i], 'length': oe[i].length, 'seam': oe[i].seam, 'pts': flat(oe[i].pts)} for i in e_occt],
                  face_pairs=[r for r in f_rows if not r['ok']], faces_ours=[{'face': i, 'area': uf[i]['area']} for i in f_ours],
                  faces_occt=[{'face': j, 'area': of[j]['area']} for j in f_occt], mesh=mesh_rows,
                  face_area=[f['area'] for f in uf], face_allowed=allowed, face_centroid=[f['c'] for f in uf], face_apart=apart)
    json.dump(detail, open(out_f, 'w'))
    print(json.dumps(row))


def run(run_dir, data, jobs):
    tsv = lambda f: [l.rstrip('\n').split('\t') for l in open(f) if l.strip() and not l.startswith('#')] if os.path.exists(f) else []
    done = {tuple(w[:3]) for w in tsv(run_dir + '/geo.tsv')}
    todo = [tuple(w[:3]) for w in tsv(run_dir + '/results.tsv') if w[3] == 'ok' and tuple(w[:3]) not in done]

    def one(key):
        n = geo_name(*key)
        mine, ref, out = '%s/geo/%s.json' % (run_dir, n), '%s/geo/%s.brep' % (data, n), '%s/geo/%s.cmp.json' % (run_dir, n)
        if not os.path.exists(mine) or not os.path.getsize(mine):
            return key, {'status': 'ours not measured'}
        if not os.path.exists(ref):
            return key, {'status': 'no OCCT shape'}
        try:
            p = subprocess.run([sys.executable, '-I', os.path.abspath(__file__), 'cmp', mine, ref, out], capture_output=True, text=True, timeout=600)
            return key, dict(json.loads(p.stdout.splitlines()[-1]), status='ok')
        except Exception as e:
            return key, {'status': 'not compared: ' + (('timeout' if isinstance(e, subprocess.TimeoutExpired) else (p.stderr.strip().splitlines() or ['?'])[-1][:150]))}

    new = not os.path.exists(run_dir + '/geo.tsv')
    with open(run_dir + '/geo.tsv', 'a') as f, cf.ThreadPoolExecutor(max_workers=jobs) as ex:
        if new:
            f.write('#' + '\t'.join(COLS) + '\n')
        for r in cf.as_completed([ex.submit(one, k) for k in todo]):
            key, row = r.result()
            f.write('\t'.join(list(key) + [('%.6g' % row[c] if isinstance(row[c], float) else str(row[c])) if c in row else '-' for c in COLS[3:]]) + '\n')
            f.flush()


if __name__ == '__main__':
    if sys.argv[1] == 'cmp':
        compare(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        opt = dict(zip(sys.argv[4::2], sys.argv[5::2]))
        run(sys.argv[2], sys.argv[3], int(opt.get('--jobs', 2)))
