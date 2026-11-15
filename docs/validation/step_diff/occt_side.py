# occt_side.py <file.step>: OCCT 8.0.1 as the oracle (file units)
#   UNIT <file length unit in mm>; ENT <type> <count>                                                  entity types of the StepData model (stage 1)
#   OEDGE <solid> <#edge_curve> <length> <x0 y0 z0> <x1 y1 z1>           edges paired by entity id (stage 2)
#   OWIRE <solid> <#face> <wire> <#edge_curve per edge, 0 for an edge the healing made>   (stage 3)
#   OUSE <solid> <#face> <#edge_curve> <deviation of the pcurve from the edge curve>        (stage 4)
#   OFACE <file> <solid> <face> <area> <cx> <cy> <cz> <wires> <edges per wire, non-degenerated>   faces in shell order (stages 3, 5)
#   OSOLID <file> <solid> <faces> <valid> <volume> <max edge tolerance>                             (stage 5)
# Shapes are paired with entities through XSControl_TransferReader::EntityFromShapeResult (the TransientProcess bindings);
# the entity's file id is its position in the model, read from the file's DATA order since OCP's Interface_InterfaceModel::Number does not resolve.
import sys, re, collections
sys.path.insert(0, '/home/user/session_data/brep_boolean_bench/tools')
from occt_step_bench import file_unit_mm, items
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_FACE, TopAbs_WIRE, TopAbs_EDGE, TopAbs_SOLID
from OCP.TopoDS import TopoDS
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Curve2d, BRepAdaptor_Surface
from OCP.GCPnts import GCPnts_AbscissaPoint
path = sys.argv[1]
def unit_mm(path):  # OCCT reads in millimetres; a conversion-based length unit of any name (fork.stp: 'SAT', 25.4 mm) is resolved through its measure
    t = re.sub(r'\s+', '', open(path, errors='replace').read().upper())
    ents = dict(re.findall(r'#(\d+)=([^;]*);', t))
    for body in ents.values():
        m = re.search(r"CONVERSION_BASED_UNIT\('[^']*',#(\d+)\)", body)
        if m and 'LENGTH_UNIT' in body:
            v = re.search(r'LENGTH_MEASURE\(([-+.0-9E]+)\),#(\d+)', ents.get(m.group(1), ''))
            if v:
                p = re.search(r'SI_UNIT\(([.A-Z$]+),\.METRE\.', ents.get(v.group(2), ''))
                return float(v.group(1)) * {'.MILLI.': 1.0, '.CENTI.': 10.0, '.DECI.': 100.0, '$': 1000.0, '.KILO.': 1e6, '.MICRO.': 1e-3}.get(p.group(1) if p else '.MILLI.', 1.0)
    return file_unit_mm(path)
k = unit_mm(path)
print('UNIT', k)
r = STEPControl_Reader()
if r.ReadFile(path) != 1: print('OFAIL', path); sys.exit(0)
model = r.StepModel()
keep = [model.Value(i) for i in range(1, model.NbEntities() + 1)]
text = open(path, errors='replace').read()
data = re.sub(r"'(?:[^']|'')*'", "''", text[text.find('DATA;'):])
labels = [int(x) for x in re.findall(r'(?:^|;)\s*#(\d+)\s*=', data)]
label = {id(x): labels[i] if len(labels) == len(keep) else i + 1 for i, x in enumerate(keep)}
r.TransferRoots()
tr = r.WS().TransferReader()
def ident(shape):
    e = tr.EntityFromShapeResult(shape, -1)
    return 0 if e is None else label.get(id(e), 0)
types = collections.Counter(x.DynamicType().Name() for x in keep)
for t, n in sorted(types.items()): print('ENT', t, n)
for i, s in enumerate(items(r.OneShape(), TopAbs_SOLID)):
    for e in items(s, TopAbs_EDGE):
        ed = TopoDS.Edge(e)
        if BRep_Tool.Degenerated_s(ed): continue
        c = BRepAdaptor_Curve(ed); a, b = c.Value(c.FirstParameter()), c.Value(c.LastParameter())
        print('OEDGE', i, ident(ed), GCPnts_AbscissaPoint.Length_s(c) / k, a.X() / k, a.Y() / k, a.Z() / k, b.X() / k, b.Y() / k, b.Z() / k)
    for j, f in enumerate(items(s, TopAbs_FACE)):
        fa = TopoDS.Face(f); fid = ident(fa); srf = BRepAdaptor_Surface(fa)
        g = GProp_GProps(); BRepGProp.SurfaceProperties_s(f, g, 1e-10); c = g.CentreOfMass()
        ws = items(f, TopAbs_WIRE)
        for wi, w in enumerate(ws):
            print('OWIRE', i, fid, wi, ','.join(str(ident(e)) for e in items(w, TopAbs_EDGE) if not BRep_Tool.Degenerated_s(TopoDS.Edge(e))))
        for e in items(f, TopAbs_EDGE):
            ed = TopoDS.Edge(e)
            if BRep_Tool.Degenerated_s(ed): continue
            c3 = BRepAdaptor_Curve(ed); c2 = BRepAdaptor_Curve2d(ed, fa); dev = 0.0
            for q in range(17):
                t = c3.FirstParameter() + (c3.LastParameter() - c3.FirstParameter()) * q / 16
                uv = c2.Value(t); dev = max(dev, srf.Value(uv.X(), uv.Y()).Distance(c3.Value(t)))
            print('OUSE', i, fid, ident(ed), dev / k)
        print('OFACE', path, i, j, repr(g.Mass() / k / k), c.X() / k, c.Y() / k, c.Z() / k, len(ws),
              ','.join(str(sum(1 for e in items(w, TopAbs_EDGE) if not BRep_Tool.Degenerated_s(TopoDS.Edge(e)))) for w in ws))
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(s, g, 1e-11)
    tol = max([BRep_Tool.Tolerance_s(TopoDS.Edge(e)) for e in items(s, TopAbs_EDGE)] or [0])
    print('OSOLID', path, i, len(items(s, TopAbs_FACE)), int(BRepCheck_Analyzer(s).IsValid()), repr(g.Mass() / k ** 3), tol / k)
