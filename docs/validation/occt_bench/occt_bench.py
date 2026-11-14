import time, math
from OCP.gp import gp_Pnt, gp_Trsf, gp_Ax1, gp_Dir, gp_Vec, gp_Ax2
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere, BRepPrimAPI_MakeCone, BRepPrimAPI_MakeTorus
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform, BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeVertex
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Fuse, BRepAlgoAPI_Cut
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.BRepCheck import BRepCheck_Analyzer

class MT:
    def __init__(s, seed):
        s.mt = [0] * 624; s.i = 624; s.mt[0] = seed & 0xffffffff
        for i in range(1, 624):
            s.mt[i] = (1812433253 * (s.mt[i-1] ^ (s.mt[i-1] >> 30)) + i) & 0xffffffff
    def __call__(s):
        if s.i >= 624:
            for k in range(624):
                y = (s.mt[k] & 0x80000000) | (s.mt[(k+1) % 624] & 0x7fffffff)
                s.mt[k] = s.mt[(k+397) % 624] ^ (y >> 1) ^ (0x9908b0df if y & 1 else 0)
            s.i = 0
        y = s.mt[s.i]; s.i += 1
        y ^= y >> 11; y ^= (y << 7) & 0x9d2c5680; y ^= (y << 15) & 0xefc60000; y ^= y >> 18
        return y & 0xffffffff

def box(sx, sy, sz):
    return BRepPrimAPI_MakeBox(gp_Pnt(-sx/2, -sy/2, -sz/2), sx, sy, sz).Shape()

def primitive(kind, s):
    if kind == 0: return box(*s)
    if kind == 1: return BRepPrimAPI_MakeCylinder(0.5*s[0], s[1]).Shape()
    if kind == 2: return BRepPrimAPI_MakeSphere(0.6*s[0]).Shape()
    if kind == 3: return BRepPrimAPI_MakeCone(0.6*s[0], 0.0, s[1]).Shape()
    if kind == 4:
        h = s[0]/2; poly = BRepBuilderAPI_MakePolygon()
        for x, y in ((-h,-h),(h,-h),(h,h),(-h,h)): poly.Add(gp_Pnt(x, y, 0))
        poly.Close()
        loft = BRepOffsetAPI_ThruSections(True, True)
        loft.AddWire(poly.Wire()); loft.AddVertex(BRepBuilderAPI_MakeVertex(gp_Pnt(0, 0, s[1])).Vertex()); loft.Build()
        return loft.Shape()
    if kind == 5: return BRepPrimAPI_MakeTorus(0.8*s[0], 0.25*s[1]).Shape()
    block = box(1.2*s[0], 1.2*s[1], s[2])
    hole = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, -s[2]), gp_Dir(0, 0, 1)), 0.3, 2*s[2]).Shape()
    return BRepAlgoAPI_Cut(block, hole).Shape()

def volume(shape):
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(shape, g); return g.Mass()

cases = [(6,5,3,0),(6,5,3,1),(5,0,1,0),(5,4,1,0),(5,0,1,1),(5,6,2,1),(6,2,2,0),(5,3,2,0),(5,2,1,0),(0,0,1,0),(0,1,1,0),(1,2,1,0),(3,4,1,0),(4,2,1,0),(2,2,1,0)]
total = 0.0
for ka, kb, seed, mode in cases:
    e = MT(seed*7919 + ka*31 + kb)
    unit = lambda: e() / 4294967296.0
    size = lambda: 0.6 + unit()
    su = lambda: 2.0*unit() - 1.0
    sa = [size() for _ in range(3)]; sb = [size() for _ in range(3)]
    shift = [0.45*su() for _ in range(3)]; axis = [su() for _ in range(3)]; angle = 3.0*su()
    a = primitive(ka, sa); b = primitive(kb, sb)
    t = gp_Trsf()
    if mode == 0: t.SetRotation(gp_Ax1(gp_Pnt(0,0,0), gp_Dir(*axis)), angle)
    tr = gp_Trsf(); tr.SetTranslation(gp_Vec(*shift))
    b = BRepBuilderAPI_Transform(b, tr.Multiplied(t), True).Shape()
    start = time.perf_counter()
    common = BRepAlgoAPI_Common(a, b).Shape(); t1 = time.perf_counter()
    fuse = BRepAlgoAPI_Fuse(a, b).Shape(); t2 = time.perf_counter()
    ab = BRepAlgoAPI_Cut(a, b).Shape(); t3 = time.perf_counter()
    ba = BRepAlgoAPI_Cut(b, a).Shape(); t4 = time.perf_counter()
    xor = BRepAlgoAPI_Fuse(BRepAlgoAPI_Cut(a, b).Shape(), BRepAlgoAPI_Cut(b, a).Shape()).Shape(); t5 = time.perf_counter()
    secs = t5 - start; total += secs
    vols = [volume(s) for s in (common, fuse, ab, ba, xor)]
    ok = all(BRepCheck_Analyzer(s).IsValid() for s in (common, fuse, ab, ba, xor))
    print(f'"{ka} {kb} {seed} {mode}" bool_s {secs:.3f} valid {ok} volumes ' + " ".join(f"{v:.6g}" for v in vols), flush=True)
print(f"TOTAL bool_s {total:.3f}")
