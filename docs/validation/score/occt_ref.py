# OCCT side of the scoreboard, through the cadquery-ocp wheel (OCCT 8.0.1). Specs as score_drv.cpp plus brep=<path>.
#   occt_ref.py bool <specA> <specB> [dump.json]   five lines: <op> <status> <faces> <edges> <vertices> <valid> <volume> [msg]
#   occt_ref.py operands <cases.tsv> <out.tsv> [regex]   per operand: suite case side volume area tolband maxtol valid
# tolband = sum over faces of area * face tolerance: how far the volume may move within the operand's own tolerance.
import sys, re, math, json, time
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.TopoDS import TopoDS, TopoDS_Shape
from OCP.TopExp import TopExp_Explorer, TopExp
from OCP.TopAbs import TopAbs_SOLID, TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX, TopAbs_REVERSED
from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Fuse, BRepAlgoAPI_Cut
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
from OCP.BRepTools import BRepTools
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopLoc import TopLoc_Location
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.gp import gp_Pnt, gp_Trsf, gp_Vec, gp_Ax1, gp_Dir

OPS = ['intersection', 'union', 'a-b', 'b-a', 'xor']


def items(s, t):
    out, e = [], TopExp_Explorer(s, t)
    while e.More():
        out.append(e.Current())
        e.Next()
    return out


def count(s, t):
    m = ShapeMap()
    TopExp.MapShapes_s(s, t, m)
    return m.Extent()


def volume(s):
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(s, g)
    return g.Mass()


def area(s):
    g = GProp_GProps()
    BRepGProp.SurfaceProperties_s(s, g)
    return g.Mass()


def file_unit_mm(path):
    t = open(path, errors='replace').read().upper()
    m = re.search(r"CONVERSION_BASED_UNIT\s*\(\s*'(INCH|FOOT|IN|FT)'", t)
    if m:
        return 25.4 if m.group(1) in ('INCH', 'IN') else 304.8
    m = re.search(r"LENGTH_UNIT\s*\(\s*\)\s*NAMED_UNIT\s*\(\s*\*\s*\)\s*SI_UNIT\s*\(\s*([.A-Z$]+)\s*,\s*\.METRE\.", t) or \
        re.search(r"SI_UNIT\s*\(\s*([.A-Z$]+)\s*,\s*\.METRE\.", t)
    if m:
        return {'.MILLI.': 1.0, '.CENTI.': 10.0, '.DECI.': 100.0, '$': 1000.0, '.KILO.': 1e6, '.MICRO.': 1e-3}.get(m.group(1), 1.0)
    return 1.0


def transformed(s, t):
    return BRepBuilderAPI_Transform(s, t, True).Shape()


def read_step(path):
    r = STEPControl_Reader()
    if r.ReadFile(path) != IFSelect_RetDone:
        raise RuntimeError('ReadFile failed')
    r.TransferRoots()
    s, f = r.OneShape(), file_unit_mm(path)
    if f != 1.0:
        t = gp_Trsf()
        t.SetScale(gp_Pnt(0, 0, 0), 1.0 / f)
        s = transformed(s, t)
    return s


def build(spec):
    parts = spec.split('|')
    kind, arg = parts[0].split('=', 1)
    if kind == 'step':
        sol = items(read_step(arg), TopAbs_SOLID)
        if not sol:
            raise RuntimeError('no solid in file')
        s = max(sol, key=lambda x: abs(volume(x)))
    elif kind == 'brep':
        s = TopoDS_Shape()
        BRepTools.Read_s(s, arg, BRep_Builder())
    else:
        v = [float(x) for x in arg.split(',')]
        if kind == 'box':
            s = BRepPrimAPI_MakeBox(gp_Pnt(-v[0] / 2, -v[1] / 2, -v[2] / 2), v[0], v[1], v[2]).Shape()
        elif kind == 'cyl':
            s = BRepPrimAPI_MakeCylinder(v[0], v[1]).Shape()
        elif kind == 'cone':
            s = BRepPrimAPI_MakeCone(v[0], 0.0, v[1]).Shape()
        elif kind == 'sph':
            s = BRepPrimAPI_MakeSphere(v[0]).Shape()
        else:
            raise RuntimeError('unknown spec ' + kind)
    for p in parts[1:]:
        v = [float(x) for x in p[2:].split(',')]
        t = gp_Trsf()
        if p[0] == 't':
            t.SetTranslation(gp_Vec(v[0], v[1], v[2]))
        elif p[0] == 'r':
            t.SetRotation(gp_Ax1(gp_Pnt(v[4], v[5], v[6]), gp_Dir(v[0], v[1], v[2])), math.radians(v[3]))
        else:
            t.SetValues(*v)
        s = transformed(s, t)
    return s


def dump(s):
    b = Bnd_Box()
    BRepBndLib.Add_s(s, b)
    diag = 1.0 if b.IsVoid() else b.CornerMin().Distance(b.CornerMax())
    BRepMesh_IncrementalMesh(s, 0.002 * diag, False, 0.2)
    pos, idx, edges, verts, base = [], [], [], [], 0
    for f in items(s, TopAbs_FACE):
        face, loc = TopoDS.Face(f), TopLoc_Location()
        t = BRep_Tool.Triangulation_s(face, loc)
        if t is None:
            continue
        tr = loc.Transformation()
        for i in range(1, t.NbNodes() + 1):
            p = t.Node(i).Transformed(tr)
            pos += [p.X(), p.Y(), p.Z()]
        rev = face.Orientation() == TopAbs_REVERSED
        for i in range(1, t.NbTriangles() + 1):
            a, b2, c = t.Triangle(i).Get()
            idx += [base + a - 1] + ([base + c - 1, base + b2 - 1] if rev else [base + b2 - 1, base + c - 1])
        base += t.NbNodes()
    m = ShapeMap()
    TopExp.MapShapes_s(s, TopAbs_EDGE, m)
    for i in range(1, m.Extent() + 1):
        e = TopoDS.Edge(m.FindKey(i))
        if BRep_Tool.Degenerated_s(e):
            continue
        c = BRepAdaptor_Curve(e)
        a, b2 = c.FirstParameter(), c.LastParameter()
        line = []
        for k in range(49):
            p = c.Value(a + (b2 - a) * k / 48.0)
            line += [p.X(), p.Y(), p.Z()]
        edges.append(line)
    m = ShapeMap()
    TopExp.MapShapes_s(s, TopAbs_VERTEX, m)
    for i in range(1, m.Extent() + 1):
        p = BRep_Tool.Pnt_s(TopoDS.Vertex(m.FindKey(i)))
        verts += [p.X(), p.Y(), p.Z()]
    r = lambda v: [round(x, 6) for x in v]
    return {'pos': r(pos), 'idx': idx, 'edges': [r(e) for e in edges], 'verts': r(verts),
            'counts': [count(s, TopAbs_FACE), count(s, TopAbs_EDGE), count(s, TopAbs_VERTEX)]}


EMPTY = {'pos': [], 'idx': [], 'edges': [], 'verts': [], 'counts': [0, 0, 0]}


def booleans(sa, sb, out):
    try:
        a, b = build(sa), build(sb)
    except Exception as e:
        for op in OPS:
            print(op, 'LOADFAIL 0 0 0 0 nan', str(e)[:200], flush=True)
        return
    panels = [dump(a), dump(b)] if out else None
    for op in OPS:
        try:
            if op == 'xor':
                algo = BRepAlgoAPI_Fuse(BRepAlgoAPI_Cut(a, b).Shape(), BRepAlgoAPI_Cut(b, a).Shape())
            else:
                algo = {'intersection': BRepAlgoAPI_Common, 'union': BRepAlgoAPI_Fuse, 'a-b': BRepAlgoAPI_Cut}.get(op, BRepAlgoAPI_Cut)(
                    *((b, a) if op == 'b-a' else (a, b)))
            r = algo.Shape()
            if not algo.IsDone():
                raise RuntimeError('NotDone')
        except Exception as e:
            print(op, 'FAIL 0 0 0 0 nan', str(e)[:200], flush=True)
            if panels is not None:
                panels.append(dict(EMPTY, error='OCCT FAIL'))
            continue
        nf = count(r, TopAbs_FACE)
        valid = int(nf == 0 or BRepCheck_Analyzer(r).IsValid())
        print(op, 'ok', nf, count(r, TopAbs_EDGE), count(r, TopAbs_VERTEX), valid, '%.15g' % volume(r), flush=True)
        if panels is not None:
            panels.append(dump(r))
    if out:
        json.dump(panels, open(out, 'w'))


def operands(cases, out, rx):
    done = set()
    try:
        done = {tuple(l.split('\t')[:2]) for l in open(out)}
    except FileNotFoundError:
        pass
    with open(out, 'a') as f:
        for l in open(cases):
            w = l.rstrip('\n').split('\t')
            if l.startswith('#') or (w[0], w[1]) in done or (rx and not re.search(rx, w[1])):
                continue
            for side, spec in (('A', w[6]), ('B', w[7])):
                try:
                    s = build(spec)
                    band = sum(area(x) * BRep_Tool.Tolerance_s(TopoDS.Face(x)) for x in items(s, TopAbs_FACE))
                    tol = max([BRep_Tool.Tolerance_s(TopoDS.Vertex(x)) for x in items(s, TopAbs_VERTEX)] +
                              [BRep_Tool.Tolerance_s(TopoDS.Edge(x)) for x in items(s, TopAbs_EDGE)] + [0.0])
                    rec = '%.15g\t%.9g\t%.6g\t%.6g\t%d' % (volume(s), area(s), band, tol, BRepCheck_Analyzer(s).IsValid())
                except Exception as e:
                    rec = 'nan\tnan\tnan\tnan\t0\t' + str(e)[:100]
                f.write('%s\t%s\t%s\t%s\n' % (w[0], w[1], side, rec))
            f.flush()


if __name__ == '__main__':
    if sys.argv[1] == 'bool':
        booleans(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    else:
        operands(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
