# OCCT (OCP 8.0.1) STEP reader -> native OCCT .brep text files (exact), plus a load line per file.
#   LOADOCCT <name> <status> read_s <s> roots <n> solids <n> shells <n> faces <n> kinds=plane,cyl,cone,sphere,torus,bspline,other valid <0|1> volume <v> bbox x0,y0,z0,x1,y1,z1
import sys, time, os
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepTools import BRepTools
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID, TopAbs_SHELL, TopAbs_FACE
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone, GeomAbs_Sphere, GeomAbs_Torus, GeomAbs_BSplineSurface
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.TopoDS import TopoDS

out = sys.argv[1]
for path in sys.argv[2:]:
    name = os.path.basename(path)
    t0 = time.perf_counter()
    r = STEPControl_Reader()
    st = r.ReadFile(path)
    if st != IFSelect_RetDone:
        print(f"LOADOCCT {name} FAIL read_s {time.perf_counter()-t0:.4f} status {st}"); continue
    n = r.TransferRoots()
    shape = r.OneShape()
    dt = time.perf_counter() - t0
    def count(kind):
        e = TopExp_Explorer(shape, kind); c = 0
        while e.More(): c += 1; e.Next()
        return c
    kinds = [0]*7
    e = TopExp_Explorer(shape, TopAbs_FACE)
    while e.More():
        t = BRepAdaptor_Surface(TopoDS.Face(e.Current())).GetType()
        k = {GeomAbs_Plane:0, GeomAbs_Cylinder:1, GeomAbs_Cone:2, GeomAbs_Sphere:3, GeomAbs_Torus:4, GeomAbs_BSplineSurface:5}.get(t, 6)
        kinds[k] += 1; e.Next()
    valid = BRepCheck_Analyzer(shape).IsValid()
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(shape, g)
    b = Bnd_Box(); BRepBndLib.Add_s(shape, b); bb = [b.CornerMin().X(), b.CornerMin().Y(), b.CornerMin().Z(), b.CornerMax().X(), b.CornerMax().Y(), b.CornerMax().Z()]
    base = os.path.splitext(name)[0]
    BRepTools.Write_s(shape, os.path.join(out, base + ".brep"))
    # one file per solid as well
    e = TopExp_Explorer(shape, TopAbs_SOLID); i = 0
    while e.More():
        BRepTools.Write_s(e.Current(), os.path.join(out, f"{base}.s{i}.brep")); i += 1; e.Next()
    print(f"LOADOCCT {name} ok read_s {dt:.4f} roots {n} solids {count(TopAbs_SOLID)} shells {count(TopAbs_SHELL)} faces {count(TopAbs_FACE)} kinds={','.join(map(str,kinds))} valid {int(valid)} volume {g.Mass():.10g} bbox {','.join(f'{x:.4f}' for x in bb)}", flush=True)
