// session_cpp side of the complex-model boolean bench (docs/validation/complex_bench).
//   ours_cx load <file.step>
//     LOAD <file> <status> read_s <s> breps <n> [error]
//     BREP <file> <i> faces edges vertices shells solids valid solid kinds=plane,sphere,cylinder,cone,torus,free volume bbox x0,y0,z0,x1,y1,z1
//   ours_cx operands <specA> <specB> <dump.json>         picture data of the two operands
//   ours_cx op <specA> <specB> <op> <tol> [dump.json]     one boolean, one line:
//     OP <op> <status> bool_s <s> counts <f> <e> <v> shells <n> solids <n> valid <0|1> solid <0|1> vol_s <s> volume <v> [error]
// A spec is `step=<path>#<shell index>`, `box=sx,sy,sz` (centred at the origin) or `cyl=r,h` (+Z from z=0), followed by
// `|m=<a11..a14,a21..a24,a31..a34>` rigid moves (row-major 3x4) applied in order. op: intersection union a-b b-a xor.
// OURS_REPAIR=1: a STEP BRep that is not is_solid() as read gets the driver-side orientation repair below (not kernel code).
#include "brep.h"
#include "curve_surface_intersection.h"
#include "file_step.h"
#include "nurbs_implicit.h"
#include "xform.h"
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

using namespace session_cpp;

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

// Driver-side topology repair (NOT kernel code), only with OURS_REPAIR=1, and only on a STEP BRep whose is_solid() is false as read: reverse the edge order of a wire that is open as
// read but closes when walked backwards, then flip shell face uses so every edge is used once each way (keeping the majority of each connected piece as read), then flip the
// whole shell when the volume comes out negative. Separates the reader's orientation handling from the booleans.
static bool wire_closed(const BRep& b, const std::vector<BRepRef>& edges) {
    int start = -1, previous = -1;
    for (const BRepRef& r : edges) {
        if (r.orientation == BRepOrientation::Internal || r.orientation == BRepOrientation::External) continue;
        const BRepEdge& e = b.m_edges[r.index];
        const int first = r.orientation == BRepOrientation::Reversed ? e.end_vertex : e.start_vertex;
        const int last = r.orientation == BRepOrientation::Reversed ? e.start_vertex : e.end_vertex;
        if (previous >= 0 && previous != first) return false;
        if (start < 0) start = first;
        previous = last;
    }
    return start < 0 || previous == start;
}

static BRepOrientation flip(BRepOrientation o) {
    return o == BRepOrientation::Forward ? BRepOrientation::Reversed : o == BRepOrientation::Reversed ? BRepOrientation::Forward : o;
}

static std::string repair(BRep& b) {
    int wires = 0, faces = 0, shells = 0;
    for (BRepWire& w : b.m_wires)
        if (!wire_closed(b, w.edges)) {
            std::vector<BRepRef> c(w.edges.rbegin(), w.edges.rend());
            if (wire_closed(b, c)) { w.edges = c; ++wires; }
        }
    for (BRepShell& sh : b.m_shells) {
        const int n = (int)sh.faces.size();
        std::vector<std::vector<std::pair<int, int>>> uses(b.m_edges.size());  // (face slot, sign)
        for (int k = 0; k < n; ++k)
            for (const BRepRef& wr : b.m_faces[sh.faces[k].index].wires)
                for (const BRepRef& er : b.wire_edges(wr)) {
                    if (b.m_edges[er.index].degenerated) continue;
                    const BRepOrientation o = brep_compose(sh.faces[k].orientation, er.orientation);
                    if (o == BRepOrientation::Forward) uses[er.index].push_back({k, 1});
                    else if (o == BRepOrientation::Reversed) uses[er.index].push_back({k, -1});
                }
        std::vector<std::vector<std::pair<int, int>>> adj(n);  // (other slot, 1 when signs are equal)
        for (const auto& u : uses)
            if (u.size() == 2 && u[0].first != u[1].first) {
                const int same = u[0].second == u[1].second;
                adj[u[0].first].push_back({u[1].first, same});
                adj[u[1].first].push_back({u[0].first, same});
            }
        std::vector<int> state(n, -1);
        for (int s0 = 0; s0 < n; ++s0) {
            if (state[s0] >= 0) continue;
            state[s0] = 0;
            std::vector<int> stack{s0}, component{s0};
            while (!stack.empty()) {
                const int f = stack.back();
                stack.pop_back();
                for (const auto& [g, same] : adj[f])
                    if (state[g] < 0) { state[g] = state[f] ^ same; stack.push_back(g); component.push_back(g); }
            }
            // keep the majority of each connected piece as read (the reader gets only some faces wrong)
            int flipped = 0;
            for (int f : component) flipped += state[f];
            if (2 * flipped > (int)component.size())
                for (int f : component) state[f] ^= 1;
        }
        for (int k = 0; k < n; ++k)
            if (state[k] == 1) { sh.faces[k].orientation = flip(sh.faces[k].orientation); ++faces; }
    }
    double v = 0.0;
    try { v = b.volume_exact(); } catch (...) { try { v = b.volume(); } catch (...) {} }
    if (v < 0)
        for (BRepShell& sh : b.m_shells) { for (BRepRef& r : sh.faces) r.orientation = flip(r.orientation); ++shells; }
    std::ostringstream o;
    o << "wires_reordered=" << wires << " faces_flipped=" << faces << " shells_flipped=" << shells;
    return o.str();
}


static BRep build(const std::string& spec) {
    const std::vector<std::string> parts = split(spec, '|');
    const size_t eq = parts[0].find('=');
    const std::string kind = parts[0].substr(0, eq), arg = parts[0].substr(eq + 1);
    BRep b;
    if (kind == "step") {
        const size_t hash = arg.rfind('#');
        const std::vector<BRep> breps = file_step::read_file_step_breps(arg.substr(0, hash));
        const size_t index = std::stoul(arg.substr(hash + 1));
        if (index >= breps.size()) throw std::runtime_error("STEP file holds fewer shells than the index");
        b = breps[index];
        if (std::getenv("OURS_REPAIR") && !b.is_solid()) std::cerr << "repaired: " << repair(b) << "\n";
    } else if (kind == "box") {
        const auto s = numbers(arg);
        b = BRep::create_box(s[0], s[1], s[2]);
    } else if (kind == "cyl") {
        const auto s = numbers(arg);
        b = BRep::create_cylinder(s[0], s[1]);
    } else {
        throw std::runtime_error("unknown spec " + kind);
    }
    for (size_t i = 1; i < parts.size(); ++i) {
        const auto q = numbers(parts[i].substr(2));
        Xform x = Xform::identity();
        for (int r = 0; r < 3; ++r)
            for (int c = 0; c < 4; ++c) x(r, c) = q[r * 4 + c];
        b.transform(x);
    }
    return b;
}

static std::string kinds(const BRep& b) {
    std::array<int, 6> n{};
    for (const BRepFace& f : b.m_faces) {
        if (f.surface_index < 0) continue;
        int k = 0;
        try { k = nurbs_implicit::recognize(b.m_surfaces[f.surface_index], 1e-6).kind; } catch (...) { k = 0; }
        ++n[k == 0 ? 5 : k - 1];
    }
    std::ostringstream o;
    o << n[0] << "," << n[1] << "," << n[2] << "," << n[3] << "," << n[4] << "," << n[5];
    return o.str();
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
    o << "],\"idx\":[" << idx.str() << "],\"edges\":[";
    first = true;
    for (const BRepEdge& e : r.m_edges) {
        if (e.degenerated || e.curve_3d_index < 0) continue;
        const NurbsCurve& c = r.m_curves_3d[e.curve_3d_index];
        const auto [t0, t1] = c.domain();
        o << (first ? "" : ",") << "[";
        first = false;
        for (int i = 0; i <= 48; ++i) { const Point p = c.point_at(t0 + (t1 - t0) * i / 48.0); o << (i ? "," : "") << p[0] << "," << p[1] << "," << p[2]; }
        o << "]";
    }
    o << "],\"verts\":[";
    for (size_t i = 0; i < r.m_vertices.size(); ++i) { const Point& p = r.m_vertices[i].point; o << (i ? "," : "") << p[0] << "," << p[1] << "," << p[2]; }
    o << "],\"counts\":[" << r.face_count() << "," << r.edge_count() << "," << r.vertex_count() << "]}";
    return o.str();
}

static std::string volume_text(const BRep& r) {
    const auto t0 = std::chrono::steady_clock::now();
    std::ostringstream o;
    o.precision(15);
    if (r.face_count() == 0) { o << "vol_s 0 volume 0"; return o.str(); }
    double v = std::nan("");
    std::string note;
    try { v = r.volume_exact(); } catch (const std::exception&) {
        try { v = r.volume(); note = "(mesh)"; } catch (...) {}
    }
    o << "vol_s " << since(t0) << " volume " << v << note;
    return o.str();
}

static std::string clean(std::string m) {
    for (char& c : m) if (c == '\n' || c == '\r' || c == '\t') c = ' ';
    return m.substr(0, 400);
}

int main(int argc, char** argv) {
    std::cout.precision(15);
    if (argc < 3) return 2;
    const std::string mode = argv[1];
    if (mode == "load") {
        const std::string path = argv[2];
        const auto t0 = std::chrono::steady_clock::now();
        std::vector<BRep> breps;
        try {
            breps = file_step::read_file_step_breps(path);
        } catch (const std::exception& e) {
            std::cout << "LOAD " << path << " FAIL read_s " << since(t0) << " breps 0 " << clean(e.what()) << "\n";
            return 0;
        }
        std::cout << "LOAD " << path << " ok read_s " << since(t0) << " breps " << breps.size() << "\n" << std::flush;
        for (size_t i = 0; i < breps.size(); ++i) {
            if (std::getenv("OURS_REPAIR") && !breps[i].is_solid()) std::cout << "REPAIRED " << path << " " << i << " " << repair(breps[i]) << "\n";
            const BRep& b = breps[i];
            bool valid = false, solid = false;
            try { valid = b.is_valid(); } catch (...) {}
            try { solid = b.is_solid(); } catch (...) {}
            std::array<double, 3> lo{1e300, 1e300, 1e300}, hi{-1e300, -1e300, -1e300};
            for (const BRepVertex& p : b.m_vertices)
                for (int k = 0; k < 3; ++k) { lo[k] = std::min(lo[k], p.point[k]); hi[k] = std::max(hi[k], p.point[k]); }
            std::cout << "BREP " << path << " " << i << " " << b.face_count() << " " << b.edge_count() << " " << b.vertex_count() << " "
                      << b.shell_count() << " " << b.solid_count() << " " << valid << " " << solid << " kinds=" << kinds(b) << " "
                      << volume_text(b) << " bbox " << lo[0] << "," << lo[1] << "," << lo[2] << "," << hi[0] << "," << hi[1] << "," << hi[2] << "\n" << std::flush;
        }
        return 0;
    }
    if (mode == "pcheck") {
        // pcheck <file.step> [tol]: certified edge/pcurve correspondence of every pcurve of every BRep as read
        //   PCHECK <file> <i> pcurves <n> matched <n> mismatched <n> unresolved <n> mismatched_on=<surface kinds>
        const double tol = argc > 3 ? std::stod(argv[3]) : 1e-7;
        const std::vector<BRep> breps = file_step::read_file_step_breps(argv[2]);
        for (size_t i = 0; i < breps.size(); ++i) {
            const BRep& b = breps[i];
            int n = 0, ok = 0, bad = 0, open = 0;
            std::array<int, 6> on{};
            for (const BRepEdge& e : b.m_edges) {
                if (e.degenerated || e.curve_3d_index < 0) continue;
                for (const BRepCurveOnSurface& r : e.pcurves)
                    for (const int index : {r.curve_2d_index, r.curve_2d_index_2}) {
                        if (index < 0) continue;
                        ++n;
                        curve_surface_intersection::ParameterMatch m = curve_surface_intersection::ParameterMatch::Unresolved;
                        try { m = curve_surface_intersection::same_parameter(b.m_curves_3d[e.curve_3d_index], b.m_curves_2d[index], b.m_surfaces[r.surface_index], tol); } catch (...) {}
                        if (m == curve_surface_intersection::ParameterMatch::Matched) ++ok;
                        else {
                            m == curve_surface_intersection::ParameterMatch::Mismatched ? ++bad : ++open;
                            int k = 0;
                            try { k = nurbs_implicit::recognize(b.m_surfaces[r.surface_index], 1e-6).kind; } catch (...) {}
                            ++on[k == 0 ? 5 : k - 1];
                        }
                    }
            }
            std::cout << "PCHECK " << argv[2] << " " << i << " pcurves " << n << " matched " << ok << " mismatched " << bad << " unresolved " << open
                      << " not_matched_on(plane,sphere,cylinder,cone,torus,free)=" << on[0] << "," << on[1] << "," << on[2] << "," << on[3] << "," << on[4] << "," << on[5] << "\n";
        }
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
        const double tol = std::stod(argv[5]);
        BRep a, b;
        try {
            a = build(argv[2]);
            b = build(argv[3]);
        } catch (const std::exception& e) {
            std::cout << "OP " << op << " LOADFAIL bool_s 0 counts 0 0 0 shells 0 solids 0 valid 0 solid 0 vol_s 0 volume nan " << clean(e.what()) << "\n";
            return 0;
        }
        BRep r;
        const auto t0 = std::chrono::steady_clock::now();
        try {
            r = op == "intersection" ? a.boolean_intersection(b, tol) : op == "union" ? a.boolean_union(b, tol)
                : op == "a-b" ? a.boolean_difference(b, tol) : op == "b-a" ? b.boolean_difference(a, tol) : a.boolean_xor(b, tol);
        } catch (const std::exception& e) {
            std::cout << "OP " << op << " FAIL bool_s " << since(t0) << " counts 0 0 0 shells 0 solids 0 valid 0 solid 0 vol_s 0 volume nan " << clean(e.what()) << "\n";
            return 0;
        }
        const double seconds = since(t0);
        bool valid = false, solid = false;
        try { valid = r.is_valid(); } catch (...) {}
        try { solid = r.is_solid(); } catch (...) {}
        std::cout << "OP " << op << " ok bool_s " << seconds << " counts " << r.face_count() << " " << r.edge_count() << " " << r.vertex_count()
                  << " shells " << r.shell_count() << " solids " << r.solid_count() << " valid " << valid << " solid " << solid << " " << std::flush;
        std::cout << volume_text(r) << "\n" << std::flush;
        if (argc > 6) {
            std::ofstream out(argv[6]);
            out << dump(r);
        }
        return 0;
    }
    return 2;
}
