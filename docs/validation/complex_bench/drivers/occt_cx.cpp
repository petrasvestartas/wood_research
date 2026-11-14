// OCCT side of the complex-model boolean bench (docs/validation/complex_bench); OCCT is the oracle only.
//   occt_cx operands <specA> <specB> <dump.json>
//   occt_cx op <specA> <specB> <op> [dump.json]
//     OP <op> <status> bool_s <s> counts <f> <e> <v> shells <n> solids <n> valid <0|1> solid <0|1> vol_s <s> volume <v> [error]
//   op: intersection union a-b b-a (one BRepAlgoAPI call each, own PaveFiller),
//       xor3 (Fuse(Cut(a,b), Cut(b,a)): three booleans, as in the earlier drivers),
//       xorcells (one BOPAlgo_CellsBuilder general fuse of a and b, cells in exactly one argument kept)
// A spec is `brep=<path>` (an OCCT .brep written from OCCT's STEP reader), `box=sx,sy,sz` (centred) or `cyl=r,h`
// (+Z from z=0), followed by `|m=<a11..a14,a21..a24,a31..a34>` rigid moves applied in order (same matrices as ours).
#include <BOPAlgo_CellsBuilder.hxx>
#include <BRepAdaptor_Curve.hxx>
#include <BRepAlgoAPI_Common.hxx>
#include <BRepAlgoAPI_Cut.hxx>
#include <BRepAlgoAPI_Fuse.hxx>
#include <BRepBuilderAPI_Transform.hxx>
#include <BRepCheck_Analyzer.hxx>
#include <BRepGProp.hxx>
#include <BRepMesh_IncrementalMesh.hxx>
#include <BRepPrimAPI_MakeBox.hxx>
#include <BRepPrimAPI_MakeCylinder.hxx>
#include <BRepTools.hxx>
#include <BRep_Builder.hxx>
#include <BRep_Tool.hxx>
#include <Bnd_Box.hxx>
#include <BRepBndLib.hxx>
#include <GProp_GProps.hxx>
#include <NCollection_IndexedMap.hxx>
#include <NCollection_List.hxx>
#include <Poly_Triangulation.hxx>
#include <Standard_Failure.hxx>
#include <TopExp.hxx>
#include <TopExp_Explorer.hxx>
#include <TopTools_ShapeMapHasher.hxx>
#include <TopoDS.hxx>
#include <TopoDS_Shape.hxx>
#include <gp_Trsf.hxx>

#include <chrono>
#include <cmath>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

static double since(std::chrono::steady_clock::time_point t0) {
    return std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
}

static std::vector<std::string> split(const std::string& s, char c) {
    std::vector<std::string> v;
    std::stringstream in(s);
    std::string item;
    while (std::getline(in, item, c)) v.push_back(item);
    return v;
}

static std::vector<double> numbers(const std::string& s) {
    std::vector<double> v;
    for (const std::string& x : split(s, ',')) v.push_back(std::stod(x));
    return v;
}

static TopoDS_Shape build(const std::string& spec) {
    const std::vector<std::string> parts = split(spec, '|');
    const size_t eq = parts[0].find('=');
    const std::string kind = parts[0].substr(0, eq), arg = parts[0].substr(eq + 1);
    TopoDS_Shape s;
    if (kind == "brep") {
        BRep_Builder builder;
        if (!BRepTools::Read(s, arg.c_str(), builder)) throw std::runtime_error("cannot read " + arg);
    } else if (kind == "box") {
        const auto q = numbers(arg);
        s = BRepPrimAPI_MakeBox(gp_Pnt(-q[0] / 2, -q[1] / 2, -q[2] / 2), q[0], q[1], q[2]).Shape();
    } else if (kind == "cyl") {
        const auto q = numbers(arg);
        s = BRepPrimAPI_MakeCylinder(q[0], q[1]).Shape();
    } else {
        throw std::runtime_error("unknown spec " + kind);
    }
    for (size_t i = 1; i < parts.size(); ++i) {
        const auto q = numbers(parts[i].substr(2));
        gp_Trsf t;
        t.SetValues(q[0], q[1], q[2], q[3], q[4], q[5], q[6], q[7], q[8], q[9], q[10], q[11]);
        s = BRepBuilderAPI_Transform(s, t, true).Shape();
    }
    return s;
}

static int count(const TopoDS_Shape& shape, TopAbs_ShapeEnum kind) {
    NCollection_IndexedMap<TopoDS_Shape, TopTools_ShapeMapHasher> map;
    TopExp::MapShapes(shape, kind, map);
    return map.Extent();
}

static std::string dump(const TopoDS_Shape& s0) {
    TopoDS_Shape s = s0;
    Bnd_Box box;
    BRepBndLib::Add(s, box);
    const double diag = box.IsVoid() ? 1.0 : std::sqrt(box.SquareExtent());
    BRepMesh_IncrementalMesh(s, 0.0005 * diag, false, 0.2);
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
    NCollection_IndexedMap<TopoDS_Shape, TopTools_ShapeMapHasher> edges, verts, faces;
    TopExp::MapShapes(s, TopAbs_EDGE, edges);
    TopExp::MapShapes(s, TopAbs_VERTEX, verts);
    TopExp::MapShapes(s, TopAbs_FACE, faces);
    first = true;
    for (int i = 1; i <= edges.Extent(); ++i) {
        const TopoDS_Edge e = TopoDS::Edge(edges(i));
        if (BRep_Tool::Degenerated(e)) continue;
        BRepAdaptor_Curve c(e);
        o << (first ? "" : ",") << "[";
        first = false;
        for (int k = 0; k <= 48; ++k) { const gp_Pnt p = c.Value(c.FirstParameter() + (c.LastParameter() - c.FirstParameter()) * k / 48.0); o << (k ? "," : "") << p.X() << "," << p.Y() << "," << p.Z(); }
        o << "]";
    }
    o << "],\"verts\":[";
    for (int i = 1; i <= verts.Extent(); ++i) { const gp_Pnt p = BRep_Tool::Pnt(TopoDS::Vertex(verts(i))); o << (i > 1 ? "," : "") << p.X() << "," << p.Y() << "," << p.Z(); }
    o << "],\"counts\":[" << faces.Extent() << "," << edges.Extent() << "," << verts.Extent() << "]}";
    return o.str();
}

static std::string clean(std::string m) {
    for (char& c : m) if (c == '\n' || c == '\r' || c == '\t') c = ' ';
    return m.substr(0, 400);
}

static TopoDS_Shape run(const std::string& op, const TopoDS_Shape& a, const TopoDS_Shape& b, std::string& error) {
    auto check = [&error](BRepAlgoAPI_BooleanOperation& algo) {
        if (algo.HasErrors()) {
            std::ostringstream o;
            algo.DumpErrors(o);
            error = clean(o.str());
        }
        return algo.Shape();
    };
    if (op == "intersection") { BRepAlgoAPI_Common x(a, b); return check(x); }
    if (op == "union") { BRepAlgoAPI_Fuse x(a, b); return check(x); }
    if (op == "a-b") { BRepAlgoAPI_Cut x(a, b); return check(x); }
    if (op == "b-a") { BRepAlgoAPI_Cut x(b, a); return check(x); }
    if (op == "xor3") {
        BRepAlgoAPI_Cut x(a, b), y(b, a);
        const TopoDS_Shape p = check(x), q = check(y);
        if (!error.empty()) return TopoDS_Shape();
        BRepAlgoAPI_Fuse z(p, q);
        return check(z);
    }
    if (op == "xorcells") {
        NCollection_List<TopoDS_Shape> both, la, lb;
        both.Append(a);
        both.Append(b);
        la.Append(a);
        lb.Append(b);
        BOPAlgo_CellsBuilder cells;
        cells.SetArguments(both);
        cells.Perform();
        if (cells.HasErrors()) {
            std::ostringstream o;
            cells.DumpErrors(o);
            error = clean(o.str());
            return TopoDS_Shape();
        }
        cells.AddToResult(la, lb, 1);
        cells.AddToResult(lb, la, 1);
        cells.RemoveInternalBoundaries();
        return cells.Shape();
    }
    throw std::runtime_error("unknown op " + op);
}

int main(int argc, char** argv) {
    std::cout.precision(15);
    if (argc < 3) return 2;
    const std::string mode = argv[1];
    if (mode == "load") {
        // load <brep>: faces edges vertices shells solids valid volume (OCCT reading its own .brep)
        const TopoDS_Shape s = build(std::string("brep=") + argv[2]);
        GProp_GProps props;
        BRepGProp::VolumeProperties(s, props, 1e-9);
        std::cout << "OLOAD " << argv[2] << " " << count(s, TopAbs_FACE) << " " << count(s, TopAbs_EDGE) << " " << count(s, TopAbs_VERTEX) << " "
                  << count(s, TopAbs_SHELL) << " " << count(s, TopAbs_SOLID) << " " << BRepCheck_Analyzer(s).IsValid() << " " << props.Mass() << "\n";
        return 0;
    }
    if (mode == "operands") {
        std::ofstream out(argv[4]);
        std::string da, db;
        try { da = dump(build(argv[2])); } catch (const std::exception& e) { std::cout << "OPERAND A FAIL " << clean(e.what()) << "\n"; da = "null"; }
        try { db = dump(build(argv[3])); } catch (const std::exception& e) { std::cout << "OPERAND B FAIL " << clean(e.what()) << "\n"; db = "null"; }
        out << "[" << da << "," << db << "]";
        return 0;
    }
    if (mode == "op") {
        const std::string op = argv[4];
        TopoDS_Shape a, b;
        try {
            a = build(argv[2]);
            b = build(argv[3]);
        } catch (const std::exception& e) {
            std::cout << "OP " << op << " LOADFAIL bool_s 0 counts 0 0 0 shells 0 solids 0 valid 0 solid 0 vol_s 0 volume nan " << clean(e.what()) << "\n";
            return 0;
        }
        TopoDS_Shape r;
        std::string error;
        const auto t0 = std::chrono::steady_clock::now();
        try {
            r = run(op, a, b, error);
        } catch (const Standard_Failure& e) {
            error = std::string("Standard_Failure ") + e.what();
        } catch (const std::exception& e) {
            error = e.what();
        }
        const double seconds = since(t0);
        if (!error.empty() || r.IsNull()) {
            std::cout << "OP " << op << " FAIL bool_s " << seconds << " counts 0 0 0 shells 0 solids 0 valid 0 solid 0 vol_s 0 volume nan "
                      << (error.empty() ? std::string("null result") : clean(error)) << "\n";
            return 0;
        }
        const bool valid = BRepCheck_Analyzer(r).IsValid();
        const int solids = count(r, TopAbs_SOLID);
        std::cout << "OP " << op << " ok bool_s " << seconds << " counts " << count(r, TopAbs_FACE) << " " << count(r, TopAbs_EDGE) << " "
                  << count(r, TopAbs_VERTEX) << " shells " << count(r, TopAbs_SHELL) << " solids " << solids << " valid " << valid
                  << " solid " << (solids > 0) << " " << std::flush;
        const auto t1 = std::chrono::steady_clock::now();
        GProp_GProps props;
        BRepGProp::VolumeProperties(r, props, 1e-9);
        std::cout << "vol_s " << since(t1) << " volume " << props.Mass() << "\n" << std::flush;
        if (argc > 5) {
            std::ofstream out(argv[5]);
            out << dump(r);
        }
        return 0;
    }
    return 2;
}
