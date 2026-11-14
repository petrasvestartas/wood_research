// The pairs of session_cpp/examples/native_boolean_bench.cpp through OCCT, one line per operation:
//   label op status bool_s faces edges vertices vol_s volume
// and per pair the time of the intersection part alone (BOPAlgo_PaveFiller) and of the four builds on it.
#include <BOPAlgo_PaveFiller.hxx>
#include <BRepMesh_IncrementalMesh.hxx>
#include <BRepAdaptor_Curve.hxx>
#include <BRep_Tool.hxx>
#include <Poly_Triangulation.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <fstream>
#include <sstream>
#include <BRepAlgoAPI_Common.hxx>
#include <BRepAlgoAPI_Cut.hxx>
#include <BRepAlgoAPI_Fuse.hxx>
#include <BRepBuilderAPI_MakePolygon.hxx>
#include <BRepBuilderAPI_MakeVertex.hxx>
#include <BRepBuilderAPI_Transform.hxx>
#include <BRepCheck_Analyzer.hxx>
#include <BRepGProp.hxx>
#include <BRepOffsetAPI_ThruSections.hxx>
#include <BRepPrimAPI_MakeBox.hxx>
#include <BRepPrimAPI_MakeCone.hxx>
#include <BRepPrimAPI_MakeCylinder.hxx>
#include <BRepPrimAPI_MakeSphere.hxx>
#include <BRepPrimAPI_MakeTorus.hxx>
#include <GProp_GProps.hxx>
#include <TopExp.hxx>
#include <NCollection_IndexedMap.hxx>
#include <NCollection_List.hxx>
#include <TopTools_ShapeMapHasher.hxx>
#include <TopoDS_Shape.hxx>
#include <gp_Ax1.hxx>
#include <gp_Ax2.hxx>
#include <gp_Trsf.hxx>

#include <array>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <random>
#include <string>

static TopoDS_Shape box(double sx, double sy, double sz) {
    return BRepPrimAPI_MakeBox(gp_Pnt(-sx / 2, -sy / 2, -sz / 2), sx, sy, sz).Shape();
}

static TopoDS_Shape primitive(int kind, const std::array<double, 3>& s) {
    switch (kind) {
        case 0: return box(s[0], s[1], s[2]);
        case 1: return BRepPrimAPI_MakeCylinder(0.5 * s[0], s[1]).Shape();
        case 2: return BRepPrimAPI_MakeSphere(0.6 * s[0]).Shape();
        case 3: return BRepPrimAPI_MakeCone(0.6 * s[0], 0.0, s[1]).Shape();
        case 4: {
            const double h = s[0] / 2;
            BRepBuilderAPI_MakePolygon base(gp_Pnt(-h, -h, 0), gp_Pnt(h, -h, 0), gp_Pnt(h, h, 0), gp_Pnt(-h, h, 0), true);
            BRepOffsetAPI_ThruSections loft(true, true);
            loft.AddWire(base.Wire());
            loft.AddVertex(BRepBuilderAPI_MakeVertex(gp_Pnt(0, 0, s[1])).Vertex());
            loft.Build();
            return loft.Shape();
        }
        case 5: return BRepPrimAPI_MakeTorus(0.8 * s[0], 0.25 * s[1]).Shape();
        default: {
            const TopoDS_Shape hole = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, -s[2]), gp_Dir(0, 0, 1)), 0.3, 2 * s[2]).Shape();
            return BRepAlgoAPI_Cut(box(1.2 * s[0], 1.2 * s[1], s[2]), hole).Shape();
        }
    }
}


static std::string dump(const TopoDS_Shape& s) {
    BRepMesh_IncrementalMesh(s, 0.002, false, 0.2);
    std::ostringstream o, idx;
    o.precision(7);
    o << "{\"pos\":[";
    size_t base = 0;
    bool first = true;
    for (TopExp_Explorer f(s, TopAbs_FACE); f.More(); f.Next()) {
        TopLoc_Location loc;
        const TopoDS_Face face = TopoDS::Face(f.Current());
        const Handle(Poly_Triangulation) t = BRep_Tool::Triangulation(face, loc);
        if (t.IsNull()) continue;
        for (int i = 1; i <= t->NbNodes(); ++i) { const gp_Pnt p = t->Node(i).Transformed(loc.Transformation()); o << (base + i - 1 ? "," : "") << p.X() << "," << p.Y() << "," << p.Z(); }
        const bool rev = face.Orientation() == TopAbs_REVERSED;
        for (int i = 1; i <= t->NbTriangles(); ++i) {
            int a, b, c;
            t->Triangle(i).Get(a, b, c);
            if (rev) std::swap(b, c);
            idx << (first ? "" : ",") << base + a - 1 << "," << base + b - 1 << "," << base + c - 1;
            first = false;
        }
        base += t->NbNodes();
    }
    o << "],\"idx\":[" << idx.str() << "],\"edges\":[";
    NCollection_IndexedMap<TopoDS_Shape, TopTools_ShapeMapHasher> edges, verts;
    TopExp::MapShapes(s, TopAbs_EDGE, edges);
    TopExp::MapShapes(s, TopAbs_VERTEX, verts);
    first = true;
    for (int i = 1; i <= edges.Extent(); ++i) {
        const TopoDS_Edge e = TopoDS::Edge(edges(i));
        if (BRep_Tool::Degenerated(e)) continue;
        BRepAdaptor_Curve c(e);
        o << (first ? "" : ",") << "[";
        first = false;
        for (int k = 0; k <= 96; ++k) { const gp_Pnt p = c.Value(c.FirstParameter() + (c.LastParameter() - c.FirstParameter()) * k / 96.0); o << (k ? "," : "") << p.X() << "," << p.Y() << "," << p.Z(); }
        o << "]";
    }
    o << "],\"verts\":[";
    for (int i = 1; i <= verts.Extent(); ++i) { const gp_Pnt p = BRep_Tool::Pnt(TopoDS::Vertex(verts(i))); o << (i > 1 ? "," : "") << p.X() << "," << p.Y() << "," << p.Z(); }
    NCollection_IndexedMap<TopoDS_Shape, TopTools_ShapeMapHasher> faces;
    TopExp::MapShapes(s, TopAbs_FACE, faces);
    o << "],\"counts\":[" << faces.Extent() << "," << edges.Extent() << "," << verts.Extent() << "]}";
    return o.str();
}

int main(int argc, char** argv) {
    const int ka = std::stoi(argv[1]), kb = std::stoi(argv[2]), seed = std::stoi(argv[3]), mode = std::stoi(argv[4]);
    std::mt19937 engine(seed * 7919 + ka * 31 + kb);
    const auto unit = [&engine] { return engine() / 4294967296.0; };
    const auto size = [&unit] { return 0.6 + unit(); };
    const auto signed_unit = [&unit] { return 2.0 * unit() - 1.0; };
    std::array<double, 3> sa, sb, shift, axis;
    for (double& v : sa) v = size();
    for (double& v : sb) v = size();
    for (double& v : shift) v = 0.45 * signed_unit();
    for (double& v : axis) v = signed_unit();
    const double angle = 3.0 * signed_unit();
    const TopoDS_Shape a = primitive(ka, sa);
    gp_Trsf placed;
    placed.SetTranslation(gp_Vec(shift[0], shift[1], shift[2]));
    if (mode == 0) { gp_Trsf turned; turned.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(axis[0], axis[1], axis[2])), angle); placed.Multiply(turned); }
    const TopoDS_Shape b = BRepBuilderAPI_Transform(primitive(kb, sb), placed, true).Shape();
    std::ofstream out(argv[5]);
    out << "[" << dump(a) << "," << dump(b);
    for (int op = 0; op < 5; ++op) {
        TopoDS_Shape r;
        switch (op) {
            case 0: r = BRepAlgoAPI_Common(a, b).Shape(); break;
            case 1: r = BRepAlgoAPI_Fuse(a, b).Shape(); break;
            case 2: r = BRepAlgoAPI_Cut(a, b).Shape(); break;
            case 3: r = BRepAlgoAPI_Cut(b, a).Shape(); break;
            default: r = BRepAlgoAPI_Fuse(BRepAlgoAPI_Cut(a, b).Shape(), BRepAlgoAPI_Cut(b, a).Shape()).Shape();
        }
        out << "," << dump(r);
    }
    out << "]";
}
