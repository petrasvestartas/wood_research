// Scoreboard driver: one real boolean per call, through brep_boolean::apply or (built with -DSCORE_BOP) bop::apply.
//   score_drv bool <specA> <specB> <op> <tol> [dump.json]
//     OPS <volA> <validA> <volB> <validB>                       only with SCORE_OPS=1, before the boolean
//     BOOL <op> <status> <bool_s> <faces> <edges> <vertices> <valid> <solid> <volume> [message]
//       message: the exception of a FAIL; for an ok bop result, what bop::Report noted (distinct notes, "; "-joined);
//       a bop result whose Report::failure is set is a FAIL with that reason
//   score_drv operands <specA> <specB> <dump.json>
// Picture dumps mesh the faces coarsely (edges and vertices only where meshing throws, or with SCORE_NOMESH=1).
// A spec is step=<path> (the shell of largest volume) or step=<path>#<i>, box=sx,sy,sz (centred), cyl=r,h, cone=r,h
// or sph=r, then |-separated moves in order: t=x,y,z, r=ax,ay,az,deg,cx,cy,cz or m=<3x4 row-major>. op: intersection
// union a-b b-a xor.
#include "brep.h"
#include "brep_boolean.h"
#include "file_step.h"
#include "xform.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#ifdef SCORE_BOP
#include "bop.h"
#endif
#ifndef SCORE_OP
#define SCORE_OP session_cpp::brep_boolean::Operation
#endif

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

static std::string clean(std::string m) {
    for (char& c : m) if (c == '\n' || c == '\r' || c == '\t') c = ' ';
    return m.substr(0, 300);
}

static BRep largest(const std::vector<BRep>& breps) {
    if (breps.empty()) throw std::runtime_error("STEP file holds no BRep");
    if (breps.size() == 1) return breps[0];
    size_t best = 0;
    double best_volume = -1.0;
    for (size_t i = 0; i < breps.size(); ++i) {
        double v = std::nan("");
        try { v = std::abs(breps[i].volume()); } catch (...) {}
        if (!std::isfinite(v)) {
            double lo[3] = {1e300, 1e300, 1e300}, hi[3] = {-1e300, -1e300, -1e300};
            for (const BRepVertex& p : breps[i].m_vertices)
                for (int k = 0; k < 3; ++k) { lo[k] = std::min(lo[k], p.point[k]); hi[k] = std::max(hi[k], p.point[k]); }
            v = breps[i].m_vertices.empty() ? 0.0 : (hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2]);
        }
        if (v > best_volume) { best_volume = v; best = i; }
    }
    return breps[best];
}

static BRep build(const std::string& spec) {
    const std::vector<std::string> parts = split(spec, '|');
    const size_t eq = parts[0].find('=');
    const std::string kind = parts[0].substr(0, eq), arg = parts[0].substr(eq + 1);
    BRep b;
    if (kind == "step") {
        const size_t hash = arg.rfind('#');
        const std::vector<BRep> breps = file_step::read_file_step_breps(arg.substr(0, hash));
        if (hash == std::string::npos) b = largest(breps);
        else {
            const size_t index = std::stoul(arg.substr(hash + 1));
            if (index >= breps.size()) throw std::runtime_error("STEP file holds fewer shells than the index");
            b = breps[index];
        }
    } else if (kind == "box") {
        const auto s = numbers(arg);
        b = BRep::create_box(s[0], s[1], s[2]);
    } else if (kind == "cyl") {
        const auto s = numbers(arg);
        b = BRep::create_cylinder(s[0], s[1]);
    } else if (kind == "cone") {
        const auto s = numbers(arg);
        b = BRep::create_cone(s[0], s[1]);
    } else if (kind == "sph") {
        b = BRep::create_sphere(numbers(arg)[0]);
    } else {
        throw std::runtime_error("unknown spec " + kind);
    }
    for (size_t i = 1; i < parts.size(); ++i) {
        const char k = parts[i][0];
        const auto s = numbers(parts[i].substr(2));
        Xform x = Xform::identity();
        if (k == 't') x = Xform::translation(s[0], s[1], s[2]);
        else if (k == 'r')
            x = Xform::translation(s[4], s[5], s[6]) * Xform::rotation(Vector(s[0], s[1], s[2]), s[3], true) * Xform::translation(-s[4], -s[5], -s[6]);
        else
            for (int r = 0; r < 3; ++r)
                for (int c = 0; c < 4; ++c) x(r, c) = s[r * 4 + c];
        b.transform(x);
    }
    return b;
}

static std::string volume_text(const BRep& r) {
    std::ostringstream o;
    o.precision(15);
    if (r.face_count() == 0) return "0";
    try { o << r.volume_exact(); } catch (const std::exception&) {
        double v = std::nan("");
        try { v = r.volume(); } catch (...) {}
        o << v << "(mesh)";
    }
    return o.str();
}

static int valid_solid(const BRep& r) {
    try { return r.is_valid() && r.is_solid(); } catch (...) { return 0; }
}

static std::string dump(const BRep& r) {
    std::ostringstream o;
    o.precision(7);
    o << "{\"pos\":[";
    std::ostringstream idx;
    size_t base = 0;
    bool first = true;
    std::vector<Mesh> meshes;
    if (!std::getenv("SCORE_NOMESH")) try { meshes = r.face_meshes_q(true, 30.0, 0.01); } catch (const std::exception&) {}
    for (const Mesh& m : meshes) {
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

static BRep apply(const BRep& a, const BRep& b, const std::string& op, double tol, std::string& notes) {
    using O = SCORE_OP;
    const O o = op == "intersection" ? O::Intersection : op == "union" ? O::Union : op == "xor" ? O::Xor : O::Difference;
    const BRep& first = op == "b-a" ? b : a;
    const BRep& second = op == "b-a" ? a : b;
#ifdef SCORE_BOP
    bop::Report report;
    const BRep r = bop::apply(first, second, o, tol, &report);
    std::vector<std::string> seen;
    for (const std::string& note : report.log)
        if (std::find(seen.begin(), seen.end(), note) == seen.end()) { seen.push_back(note); notes += (notes.empty() ? "" : "; ") + note; }
    // a result bop itself declares untrustworthy is no result: FAIL with its reason (builds before Report::failure have none)
    if constexpr (requires { report.failure; })
        if (!report.failure.empty()) throw std::runtime_error("bop: " + report.failure + (notes.empty() ? "" : "; " + notes));
    return r;
#else
    return brep_boolean::apply(first, second, o, tol);
#endif
}

int main(int argc, char** argv) {
    std::cout.precision(15);
    if (argc < 5) { std::cerr << "usage: see header\n"; return 2; }
    const std::string mode = argv[1];
    if (mode == "operands") {
        std::ofstream out(argv[4]);
        std::string da = "null", db = "null";
        try { da = dump(build(argv[2])); } catch (const std::exception& e) { std::cout << "OPERAND A FAIL " << clean(e.what()) << "\n"; }
        try { db = dump(build(argv[3])); } catch (const std::exception& e) { std::cout << "OPERAND B FAIL " << clean(e.what()) << "\n"; }
        out << "[" << da << "," << db << "]";
        return 0;
    }
    if (mode != "bool" || argc < 6) return 2;
    const std::string op = argv[4];
    const double tol = std::stod(argv[5]);
    BRep a, b;
    try {
        a = build(argv[2]);
        b = build(argv[3]);
    } catch (const std::exception& e) {
        std::cout << "BOOL " << op << " LOADFAIL 0 0 0 0 0 0 nan " << clean(e.what()) << "\n";
        return 0;
    }
    if (std::getenv("SCORE_OPS"))
        std::cout << "OPS " << volume_text(a) << " " << valid_solid(a) << " " << volume_text(b) << " " << valid_solid(b) << "\n" << std::flush;
    BRep r;
    std::string notes;
    const auto t0 = std::chrono::steady_clock::now();
    try {
        r = apply(a, b, op, tol, notes);
    } catch (const std::exception& e) {
        std::cout << "BOOL " << op << " FAIL " << since(t0) << " 0 0 0 0 0 nan " << clean(e.what()) << "\n";
        return 0;
    }
    const double seconds = since(t0);
    bool valid = false, solid = false;
    try { valid = r.is_valid(); } catch (...) {}
    try { solid = r.is_solid(); } catch (...) {}
    std::cout << "BOOL " << op << " ok " << seconds << " " << r.face_count() << " " << r.edge_count() << " " << r.vertex_count() << " "
              << valid << " " << solid << " " << std::flush << volume_text(r) << " " << clean(notes) << "\n" << std::flush;
    if (argc > 6) {
        std::ofstream out(argv[6]);
        out << dump(r);
    }
    return 0;
}
