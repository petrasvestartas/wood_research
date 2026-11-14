// The pairs of session_cpp/examples/native_boolean_bench.cpp through OCCT, one line per operation:
//   label op status bool_s faces edges vertices vol_s volume
// and per pair the time of the intersection part alone (BOPAlgo_PaveFiller) and of the four builds on it.
#include <BOPAlgo_PaveFiller.hxx>
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

static double seconds_since(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
}

static int count(const TopoDS_Shape& shape, TopAbs_ShapeEnum kind) {
    NCollection_IndexedMap<TopoDS_Shape, TopTools_ShapeMapHasher> map;
    TopExp::MapShapes(shape, kind, map);
    return map.Extent();
}

int main(int argc, char** argv) {
    const std::array<std::array<int, 4>, 15> cases = {{
        {6, 5, 3, 0}, {6, 5, 3, 1}, {5, 0, 1, 0}, {5, 4, 1, 0}, {5, 0, 1, 1}, {5, 6, 2, 1}, {6, 2, 2, 0}, {5, 3, 2, 0},
        {5, 2, 1, 0}, {0, 0, 1, 0}, {0, 1, 1, 0}, {1, 2, 1, 0}, {3, 4, 1, 0}, {4, 2, 1, 0}, {2, 2, 1, 0},
    }};
    const std::array<const char*, 5> names = {"intersection", "union", "a-b", "b-a", "xor"};
    const std::string filter = argc > 1 ? argv[1] : "";
    const int repeat = argc > 2 ? std::stoi(argv[2]) : 1;
    double grand = 0.0, grand_filler = 0.0, grand_build = 0.0;
    std::cout << std::setprecision(13) << "# label op status bool_s faces edges vertices vol_s volume\n";
    for (const auto& [ka, kb, seed, mode] : cases) {
        const std::string label = std::to_string(ka) + " " + std::to_string(kb) + " " + std::to_string(seed) + " " + std::to_string(mode);
        if (label.find(filter) == std::string::npos)
            continue;
        std::mt19937 engine(seed * 7919 + ka * 31 + kb);
        const auto unit = [&engine] { return engine() / 4294967296.0; };
        const auto size = [&unit] { return 0.6 + unit(); };
        const auto signed_unit = [&unit] { return 2.0 * unit() - 1.0; };
        std::array<double, 3> sa, sb, shift, axis;
        for (double& value : sa) value = size();
        for (double& value : sb) value = size();
        for (double& value : shift) value = 0.45 * signed_unit();
        for (double& value : axis) value = signed_unit();
        const double angle = 3.0 * signed_unit();
        const TopoDS_Shape a = primitive(ka, sa);
        gp_Trsf placed;
        placed.SetTranslation(gp_Vec(shift[0], shift[1], shift[2]));
        if (mode == 0) {
            gp_Trsf turned;
            turned.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(axis[0], axis[1], axis[2])), angle);
            placed.Multiply(turned);
        }
        const TopoDS_Shape b = BRepBuilderAPI_Transform(primitive(kb, sb), placed, true).Shape();

        double case_seconds = 0.0;
        for (int op = 0; op < 5; ++op) {
            TopoDS_Shape result;
            double seconds = 0.0;
            for (int run = 0; run < repeat; ++run) {
                const auto start = std::chrono::steady_clock::now();
                switch (op) {
                    case 0: result = BRepAlgoAPI_Common(a, b).Shape(); break;
                    case 1: result = BRepAlgoAPI_Fuse(a, b).Shape(); break;
                    case 2: result = BRepAlgoAPI_Cut(a, b).Shape(); break;
                    case 3: result = BRepAlgoAPI_Cut(b, a).Shape(); break;
                    default: result = BRepAlgoAPI_Fuse(BRepAlgoAPI_Cut(a, b).Shape(), BRepAlgoAPI_Cut(b, a).Shape()).Shape();
                }
                const double once = seconds_since(start);
                seconds = run == 0 ? once : std::min(seconds, once);
            }
            case_seconds += seconds;
            const auto measured = std::chrono::steady_clock::now();
            GProp_GProps props;
            BRepGProp::VolumeProperties(result, props, 1e-10);
            std::cout << '"' << label << "\" " << names[op] << (BRepCheck_Analyzer(result).IsValid() ? " ok " : " invalid ") << seconds << ' '
                      << count(result, TopAbs_FACE) << ' ' << count(result, TopAbs_EDGE) << ' ' << count(result, TopAbs_VERTEX) << ' '
                      << seconds_since(measured) << ' ' << props.Mass() << '\n' << std::flush;
        }
        // The intersection part once, and the four builds that share it.
        NCollection_List<TopoDS_Shape> both;
        both.Append(a);
        both.Append(b);
        auto start = std::chrono::steady_clock::now();
        BOPAlgo_PaveFiller filler;
        filler.SetArguments(both);
        filler.Perform();
        const double filling = seconds_since(start);
        start = std::chrono::steady_clock::now();
        BRepAlgoAPI_Common(a, b, filler).Shape();
        BRepAlgoAPI_Fuse(a, b, filler).Shape();
        BRepAlgoAPI_Cut(a, b, filler).Shape();
        BRepAlgoAPI_Cut(a, b, filler, false).Shape();
        const double building = seconds_since(start);
        grand += case_seconds;
        grand_filler += filling;
        grand_build += building;
        std::cout << "SUMMARY \"" << label << "\" bool_s " << case_seconds << " pave_filler_s " << filling << " four_builds_s " << building << '\n' << std::flush;
    }
    std::cout << "TOTAL bool_s " << grand << " pave_filler_s " << grand_filler << " four_builds_s " << grand_build << '\n';
}
