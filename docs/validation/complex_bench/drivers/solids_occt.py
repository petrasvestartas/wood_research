# per-solid OCCT facts for every <file>.s<i>.brep: SOLID <brep> faces volume bbox kinds valid
import glob, sys, os
from OCP.BRepTools import BRepTools
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Shape, TopoDS
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone, GeomAbs_Sphere, GeomAbs_Torus, GeomAbs_BSplineSurface
for f in sorted(glob.glob(os.path.join(sys.argv[1], '*.s*.brep'))):
    s = TopoDS_Shape(); BRepTools.Read_s(s, f, BRep_Builder())
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(s, g, 1e-9)
    b = Bnd_Box(); BRepBndLib.Add_s(s, b, False); lo = b.CornerMin(); hi = b.CornerMax()
    k = [0]*7; e = TopExp_Explorer(s, TopAbs_FACE)
    while e.More():
        t = BRepAdaptor_Surface(TopoDS.Face(e.Current())).GetType()
        k[{GeomAbs_Plane:0, GeomAbs_Sphere:1, GeomAbs_Cylinder:2, GeomAbs_Cone:3, GeomAbs_Torus:4, GeomAbs_BSplineSurface:5}.get(t, 6)] += 1; e.Next()
    print('SOLID', os.path.basename(f), sum(k), repr(g.Mass()), ','.join('%.6f' % x for x in (lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z())), 'kinds=' + ','.join(map(str, k)), int(BRepCheck_Analyzer(s).IsValid()))
