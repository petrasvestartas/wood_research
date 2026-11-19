# SMLib (NVIDIA usd-brep kernel) as the second oracle, fed the operands OCCT built: no USD, OCCT -> text -> SmBrepConstructor.
#   smlib_ref.py bool <specA> <specB>            five lines as occt_ref.py bool: <op> <status> <faces> <edges> <vertices> <valid> <volume> - - [msg]
#   smlib_ref.py ref <cases.tsv> <out.tsv> [subset.tsv] [--jobs 2] [--timeout 60]
#     suite case op status faces edges vertices valid volume volA volB [msg]   (appended as they finish; a rerun resumes)
# An operand is exported after BRepBuilderAPI_NurbsConvert: vertices, edges (3D B-spline, range, end vertices) and
# faces (B-spline surface, sense, loops of edge uses with their pcurves where those lie on the edge), in OCCT's own topology. smlib_drv rebuilds it
# with SmBrepConstructor and runs SmApiBoolean. volA/volB are SMLib's volumes of the converted operands, to be held
# against OCCT's before a result is believed.
import os, sys, tempfile, subprocess, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__))
DRV = os.environ.get('SMLIB_DRV', '/tmp/claude-0/-home-user/8b288b7c-72c4-56e2-9565-a39939e050f9/scratchpad/smlib/build/smlib_drv')
OPS = ['intersection', 'union', 'a-b', 'b-a', 'xor']


def nums(v):
    return ' '.join('%.17g' % x for x in v)


def curve_text(c, dim):
    knots = [c.Knot(i) for i in range(1, c.NbKnots() + 1)]
    mults = [c.Multiplicity(i) for i in range(1, c.NbKnots() + 1)]
    poles = []
    for i in range(1, c.NbPoles() + 1):
        p = c.Pole(i)
        poles += [p.X(), p.Y()] + ([p.Z()] if dim == 3 else []) + [c.Weight(i)]
    return '%d %d %d\n%s\n%s\n%s\n' % (c.Degree(), c.NbPoles(), len(knots), nums(knots), ' '.join(map(str, mults)), nums(poles))


def bspline(convert, trimmed, curve, first, last):
    # the B-spline of the curve over [first, last]; a periodic B-spline is cut there, also across its origin
    if curve.IsPeriodic() and 'BSpline' in type(curve).__name__:
        c = convert(curve)
        try:
            c.Segment(first, last)
        except Exception:
            pass
    else:
        try:
            c = convert(trimmed(curve, first, last))
        except Exception:
            c = convert(curve)
    if c.IsPeriodic():
        c.SetNotPeriodic()
    return c


def export(shape, path):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX, TopAbs_WIRE, TopAbs_SHELL, TopAbs_FORWARD, TopAbs_REVERSED
    from OCP.TopoDS import TopoDS
    from OCP.TopExp import TopExp
    from OCP.BRep import BRep_Tool
    from OCP.BRepTools import BRepTools, BRepTools_WireExplorer
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Curve2d, BRepAdaptor_Surface
    from OCP.GeomConvert import GeomConvert
    from OCP.Geom2dConvert import Geom2dConvert
    from OCP.Geom import Geom_TrimmedCurve
    from OCP.Geom2d import Geom2d_TrimmedCurve
    from occt_ref import items, ShapeMap
    if len(items(shape, TopAbs_SHELL)) != 1:
        raise RuntimeError('operand has %d shells (one supported)' % len(items(shape, TopAbs_SHELL)))
    s = BRepBuilderAPI_NurbsConvert(shape, True).Shape()
    vm, em = ShapeMap(), ShapeMap()
    TopExp.MapShapes_s(s, TopAbs_VERTEX, vm)
    TopExp.MapShapes_s(s, TopAbs_EDGE, em)
    out = ['V %d\n' % vm.Extent()]
    for i in range(1, vm.Extent() + 1):
        p = BRep_Tool.Pnt_s(TopoDS.Vertex(vm.FindKey(i)))
        out.append(nums([p.X(), p.Y(), p.Z()]) + '\n')
    out.append('E %d\n' % em.Extent())
    for i in range(1, em.Extent() + 1):
        e = TopoDS.Edge(em.FindKey(i).Oriented(TopAbs_FORWARD))
        if BRep_Tool.Degenerated_s(e):
            out.append('0\n')
            continue
        a = BRepAdaptor_Curve(e)
        f, l = a.FirstParameter(), a.LastParameter()
        c = bspline(GeomConvert.CurveToBSplineCurve_s, Geom_TrimmedCurve, a.Curve().Curve(), f, l)
        c.Transform(a.Trsf())
        v0, v1 = TopExp.FirstVertex_s(e, True), TopExp.LastVertex_s(e, True)
        out.append('1 %s %d %d\n' % (nums([f, l]), vm.FindIndex(v0) - 1, vm.FindIndex(v1) - 1) + curve_text(c, 3))
    faces = items(s, TopAbs_FACE)
    out.append('F %d\n' % len(faces))
    for face in faces:
        face = TopoDS.Face(face)
        ff = TopoDS.Face(face.Oriented(TopAbs_FORWARD))
        g = GeomConvert.SurfaceToBSplineSurface_s(BRep_Tool.Surface_s(ff))
        sa = BRepAdaptor_Surface(ff)
        wires = items(ff, TopAbs_WIRE)
        outer = BRepTools.OuterWire_s(ff)
        wires.sort(key=lambda w: not w.IsSame(outer))
        loops, us, vs = [], [], []
        for w in wires:
            uses, ex = [], BRepTools_WireExplorer(TopoDS.Wire(w), ff)
            while ex.More():
                e = ex.Current()
                if not BRep_Tool.Degenerated_s(e):
                    a, a3 = BRepAdaptor_Curve2d(e, ff), BRepAdaptor_Curve(e)
                    f, l = a.FirstParameter(), a.LastParameter()
                    pts = [a.Value(f + (l - f) * k / 16.0) for k in range(17)]
                    gap = max(sa.Value(p.X(), p.Y()).Distance(a3.Value(f + (l - f) * k / 16.0)) for k, p in enumerate(pts))
                    # NurbsConvert (OCCT 8.0.1) leaves some pcurves of closed edges on periodic faces off their edge: those are
                    # not passed on, SMLib projects the 3D curve instead
                    if gap <= 10 * max(BRep_Tool.Tolerance_s(e), 1e-7):
                        c = bspline(Geom2dConvert.CurveToBSplineCurve_s, Geom2d_TrimmedCurve, a.Curve(), f, l)
                        us += [p.X() for p in pts]
                        vs += [p.Y() for p in pts]
                        uses.append('%d %d 1\n' % (em.FindIndex(e) - 1, e.Orientation() != TopAbs_REVERSED) + curve_text(c, 2))
                    else:
                        uses.append('%d %d 0\n' % (em.FindIndex(e) - 1, e.Orientation() != TopAbs_REVERSED))
                ex.Next()
            loops.append('%d\n' % len(uses) + ''.join(uses))
        # the face's domain is the surface's (NurbsConvert cut it to the face); across a seam the patch under the pcurves is cut out
        lo = g.Bounds()
        eps = 1e-9 * max(lo[1] - lo[0], lo[3] - lo[2])
        u0, u1, v0, v1 = lo
        if g.IsUPeriodic() and us and (min(us) < lo[0] - eps or max(us) > lo[1] + eps):
            u0, u1 = min(us), min(max(us), min(us) + lo[1] - lo[0])
        if g.IsVPeriodic() and vs and (min(vs) < lo[2] - eps or max(vs) > lo[3] + eps):
            v0, v1 = min(vs), min(max(vs), min(vs) + lo[3] - lo[2])
        if (u0, u1, v0, v1) != lo:
            try:
                g.Segment(u0, u1, v0, v1)
            except Exception:
                u0, u1, v0, v1 = lo
        if g.IsUPeriodic():
            g.SetUNotPeriodic()
        if g.IsVPeriodic():
            g.SetVNotPeriodic()
        uk = [g.UKnot(i) for i in range(1, g.NbUKnots() + 1)]
        vk = [g.VKnot(i) for i in range(1, g.NbVKnots() + 1)]
        poles = []
        for i in range(1, g.NbUPoles() + 1):
            for j in range(1, g.NbVPoles() + 1):
                p = g.Pole(i, j)
                poles += [p.X(), p.Y(), p.Z(), g.Weight(i, j)]
        out.append('%d %d %d %d %d %d %d\n%s\n%s\n%s\n%s\n%s\n%s\n%d\n' % (
            face.Orientation() != TopAbs_REVERSED, g.UDegree(), g.VDegree(), g.NbUPoles(), g.NbVPoles(), len(uk), len(vk), nums(uk),
            ' '.join(str(g.UMultiplicity(i)) for i in range(1, len(uk) + 1)), nums(vk),
            ' '.join(str(g.VMultiplicity(i)) for i in range(1, len(vk) + 1)), nums(poles), nums([u0, u1, v0, v1]), len(loops)) + ''.join(loops))
    open(path, 'w').write(''.join(out))


def booleans(sa, sb, limit=60.0, ops=OPS):
    sys.path.insert(0, HERE)
    from occt_ref import build
    with tempfile.TemporaryDirectory() as d:
        try:
            export(build(sa), d + '/a.txt')
            export(build(sb), d + '/b.txt')
        except Exception as e:
            return {op: [op, 'LOADFAIL', '0', '0', '0', '0', 'nan', '-', '-', 'export: ' + str(e)[:200]] for op in ops}
        out = {}
        for op in ops:
            try:
                p = subprocess.run([DRV, d + '/a.txt', d + '/b.txt', op], capture_output=True, text=True, timeout=limit)
                line = next((l.split(None, 9) for l in p.stdout.splitlines() if l.startswith(op + ' ')), None)
                out[op] = line or [op, 'CRASH', '0', '0', '0', '0', 'nan', '-', '-', 'signal %d' % -p.returncode if p.returncode < 0 else 'exit %d' % p.returncode]
            except subprocess.TimeoutExpired:
                out[op] = [op, 'TIMEOUT', '0', '0', '0', '0', 'nan', '-', '-', 'timeout %gs' % limit]
        return out


def one(job):
    w, ops, limit = job
    p = subprocess.run([sys.executable, '-I', os.path.abspath(__file__), 'bool', w[6], w[7], str(limit)] + ops, capture_output=True, text=True)
    got = {l.split()[0]: l.rstrip('\n').split(None, 9) for l in p.stdout.splitlines() if l.split() and l.split()[0] in OPS}
    return w, [got.get(op, [op, 'CRASH', '0', '0', '0', '0', 'nan', '-', '-', (p.stderr.strip().splitlines() or ['no output'])[-1][:200]]) for op in ops]


def reference(cases, out, subset, jobs, limit):
    want = {}
    if subset:
        for l in open(subset):
            if not l.startswith('#'):
                w = l.split('\t')
                want.setdefault((w[0], w[1]), []).append(w[2])
    done = {tuple(l.split('\t')[:3]) for l in open(out)} if os.path.exists(out) else set()
    todo = []
    for l in open(cases):
        w = l.rstrip('\n').split('\t')
        ops = [op for op in want.get((w[0], w[1]), [] if subset else OPS) if (w[0], w[1], op) not in done]
        if not l.startswith('#') and ops:
            todo.append((w, ops, limit))
    with open(out, 'a') as f, cf.ThreadPoolExecutor(max_workers=jobs) as ex:
        for r in cf.as_completed([ex.submit(one, j) for j in todo]):
            w, rows = r.result()
            for g in rows:
                f.write('\t'.join([w[0], w[1]] + g[:9] + [g[9] if len(g) > 9 else '']) + '\n')
            f.flush()


if __name__ == '__main__':
    if sys.argv[1] == 'bool':
        limit = float(sys.argv[4]) if len(sys.argv) > 4 else 60.0
        for g in booleans(sys.argv[2], sys.argv[3], limit, sys.argv[5:] or OPS).values():
            print(' '.join(g), flush=True)
    else:
        rest = sys.argv[4:]
        subset = rest.pop(0) if rest and not rest[0].startswith('--') else None
        opt = dict(zip(rest[::2], rest[1::2]))
        reference(sys.argv[2], sys.argv[3], subset, int(opt.get('--jobs', 2)), float(opt.get('--timeout', 60)))
