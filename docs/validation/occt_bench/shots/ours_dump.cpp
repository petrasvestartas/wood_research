#include "brep.h"
#include "xform.h"
#include <array>
#include <fstream>
#include <random>
#include <sstream>
#include <string>

using namespace session_cpp;

static BRep primitive(int kind, const std::array<double, 3>& s) {
    switch (kind) {
        case 0: return BRep::create_box(s[0], s[1], s[2]);
        case 1: return BRep::create_cylinder(0.5 * s[0], s[1]);
        case 2: return BRep::create_sphere(0.6 * s[0]);
        case 3: return BRep::create_cone(0.6 * s[0], s[1]);
        case 4: return BRep::create_pyramid(s[0], s[1]);
        case 5: return BRep::create_torus(0.8 * s[0], 0.25 * s[1]);
        default: return BRep::create_block_with_hole(1.2 * s[0], 1.2 * s[1], s[2], 0.3);
    }
}

static std::string dump(const BRep& r) {
    std::ostringstream o;
    o.precision(7);
    o << "{\"pos\":[";
    std::ostringstream idx;
    size_t base = 0;
    bool first = true;
    for (const Mesh& m : r.face_meshes()) {
        const auto [vs, fs] = m.to_vertices_and_faces();
        for (size_t i = 0; i < vs.size(); ++i) o << (base + i ? "," : "") << vs[i][0] << "," << vs[i][1] << "," << vs[i][2];
        for (const auto& f : fs)
            for (size_t k = 1; k + 1 < f.size(); ++k) { idx << (first ? "" : ",") << base + f[0] << "," << base + f[k] << "," << base + f[k + 1]; first = false; }
        base += vs.size();
    }
    o << "],\"idx\":[" << idx.str();
    o << "],\"edges\":[";
    first = true;
    for (const BRepEdge& e : r.m_edges) {
        if (e.degenerated || e.curve_3d_index < 0) continue;
        const NurbsCurve& c = r.m_curves_3d[e.curve_3d_index];
        const auto [t0, t1] = c.domain();
        o << (first ? "" : ",") << "[";
        first = false;
        for (int i = 0; i <= 96; ++i) { const Point p = c.point_at(t0 + (t1 - t0) * i / 96.0); o << (i ? "," : "") << p[0] << "," << p[1] << "," << p[2]; }
        o << "]";
    }
    o << "],\"verts\":[";
    for (size_t i = 0; i < r.m_vertices.size(); ++i) { const Point& p = r.m_vertices[i].point; o << (i ? "," : "") << p[0] << "," << p[1] << "," << p[2]; }
    o << "],\"counts\":[" << r.face_count() << "," << r.edge_count() << "," << r.vertex_count() << "]}";
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
    const BRep a = primitive(ka, sa);
    BRep b = primitive(kb, sb);
    Xform placed = Xform::translation(shift[0], shift[1], shift[2]);
    if (mode == 0) placed = placed * Xform::rotation(Vector(axis[0], axis[1], axis[2]), angle);
    b.transform(placed);
    std::ofstream out(argv[5]);
    out << "[" << dump(a) << "," << dump(b);
    for (int i = 0; i < 5; ++i) {
        const BRep r = i == 0 ? a.boolean_intersection(b) : i == 1 ? a.boolean_union(b) : i == 2 ? a.boolean_difference(b)
            : i == 3 ? b.boolean_difference(a) : a.boolean_xor(b);
        out << "," << dump(r);
    }
    out << "]";
}
