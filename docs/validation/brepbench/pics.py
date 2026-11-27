"""pics.py <repo copy> <results.tsv> <out dir> case...: a shaded picture of our STEP result for each case.

Run with the OCP venv's python (-I): Open CASCADE reads and meshes the STEP the harness graded, matplotlib draws it,
two views side by side; the title gives our measured and the expected volume and area from results.tsv."""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402
from OCP.BRep import BRep_Tool  # noqa: E402
from OCP.BRepMesh import BRepMesh_IncrementalMesh  # noqa: E402
from OCP.IFSelect import IFSelect_RetDone  # noqa: E402
from OCP.STEPControl import STEPControl_Reader  # noqa: E402
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED  # noqa: E402
from OCP.TopExp import TopExp_Explorer  # noqa: E402
from OCP.TopLoc import TopLoc_Location  # noqa: E402
from OCP.TopoDS import TopoDS  # noqa: E402

repo, tsv, out = sys.argv[1:4]
rows = {}
with open(tsv) as f:
    head = f.readline().rstrip("\n").split("\t")
    for line in f:
        r = dict(zip(head, line.rstrip("\n").split("\t")))
        rows[r["case"]] = r
os.makedirs(out, exist_ok=True)
for case in sys.argv[4:]:
    path = os.path.join(repo, "results", "meshes", "session_cpp", case + ".step")
    rd = STEPControl_Reader()
    if rd.ReadFile(path) != IFSelect_RetDone:
        print("cannot read", path)
        continue
    rd.TransferRoots()
    shape = rd.OneShape()
    BRepMesh_IncrementalMesh(shape, 0.02, True, 0.2, True)
    tris, n_faces, bare = [], 0, 0
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        face = TopoDS.Face(ex.Current())
        n_faces += 1
        loc = TopLoc_Location()
        t = BRep_Tool.Triangulation_s(face, loc)
        if t is None:
            bare += 1
        else:
            tr = loc.Transformation()
            pts = [t.Node(i).Transformed(tr) for i in range(1, t.NbNodes() + 1)]
            for i in range(1, t.NbTriangles() + 1):
                a, b, c = t.Triangle(i).Get()
                if face.Orientation() == TopAbs_REVERSED:
                    b, c = c, b
                tris.append([(pts[k - 1].X(), pts[k - 1].Y(), pts[k - 1].Z()) for k in (a, b, c)])
        ex.Next()
    r = rows.get(case, {})
    fig = plt.figure(figsize=(9, 4.6))
    for j, (elev, azim) in enumerate([(25, -60), (-30, 120)]):
        ax = fig.add_subplot(1, 2, j + 1, projection="3d")
        ax.add_collection3d(Poly3DCollection(tris, facecolor="#9db4d0", edgecolor="#33333322", linewidth=0.1))
        xs = [p[0] for t in tris for p in t] or [0]
        ys = [p[1] for t in tris for p in t] or [0]
        zs = [p[2] for t in tris for p in t] or [0]
        c = [(min(v) + max(v)) / 2 for v in (xs, ys, zs)]
        h = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) / 2 or 1
        ax.set_xlim(c[0] - h, c[0] + h), ax.set_ylim(c[1] - h, c[1] + h), ax.set_zlim(c[2] - h, c[2] + h)
        ax.view_init(elev, azim)
        ax.set_box_aspect((1, 1, 1))
    fig.suptitle(f"{case}: {r.get('ours', '?')}, {n_faces} faces ({bare} unmeshed)\n"
                 f"volume {r.get('vol') or 'n/a'} vs {r.get('vol_exp')}, area {r.get('area') or 'n/a'} vs {r.get('area_exp')}",
                 fontsize=9)
    name = os.path.join(out, case.replace("/", "__") + ".png")
    fig.savefig(name, dpi=80)
    plt.close(fig)
    print("wrote", name)
