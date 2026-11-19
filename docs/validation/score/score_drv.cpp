// Scoreboard driver: one real boolean per call, through brep_boolean::apply or (built with -DSCORE_BOP) bop::apply.
//   score_drv bool <specA> <specB> <op> <tol> [dump.json]
//     OPS <volA> <validA> <volB> <validB>                       only with SCORE_OPS=1, before the boolean
//     BOOL <op> <status> <bool_s> <faces> <edges> <vertices> <valid> <solid> <volume> [message]
//       message: the exception of a FAIL; for an ok bop result, what bop::Report noted (distinct notes, "; "-joined);
//       a bop result whose Report::failure is set is a FAIL with that reason
//   score_drv operands <specA> <specB> <dump.json>
//     GEO ok | GEO FAIL <message>                              only with SCORE_GEO=<file>, after BOOL: the result's geometry
//       for geo.py, written to <file>: vertices with tolerance; every edge over its range (33 points of its curve, its NURBS,
//       tolerance, seam or not); every face's area and centroid integrated from its own trimmed surface (Green's theorem
//       along its pcurves, Gauss 8, twice: "acc" is the change on doubling the panels), perimeter and tolerance (the largest
//       of the face, its edges and their vertices)
//     MESH ok <seconds>                                         then <file>.mesh: what face_meshes() (the viewer's mesh) gives
//       for each face: triangles, their area and centroid, and why there are none (the exception, and what the face does meshed alone)
// Picture dumps mesh the faces coarsely (edges and vertices only where meshing throws, or with SCORE_NOMESH=1); "ftri" is
// the number of triangles per face, "farea" their area, "fcen" their centroid and "fedge" the drawn edges of each face, for pics.py to mark the
// faces without a mesh or with a wrong one.
// A spec is step=<path> (the shell of largest volume) or step=<path>#<i>, box=sx,sy,sz (centred), cyl=r,h, cone=r,h
// or sph=r, then |-separated moves in order: t=x,y,z, r=ax,ay,az,deg,cx,cy,cz or m=<3x4 row-major>. op: intersection
// union a-b b-a xor.
#include "brep.h"
#include "brep_boolean.h"
#include "file_step.h"
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

// position of every edge among the drawn ones (not degenerated, with a 3D curve), -1 for the rest
static std::vector<int> drawn_edges(const BRep& r) {
    std::vector<int> at(r.m_edges.size(), -1);
    int n = 0;
    for (size_t i = 0; i < r.m_edges.size(); ++i)
        if (!r.m_edges[i].degenerated && r.m_edges[i].curve_3d_index >= 0) at[i] = n++;
    return at;
}

static std::string quoted(std::string m) {
    for (char& c : m) if (c == '"' || c == '\\' || (unsigned char)c < 32) c = ' ';
    return "\"" + m.substr(0, 200) + "\"";
}

struct FaceMeasure { double area = 0.0, c[3] = {0.0, 0.0, 0.0}, gap = 0.0; std::string note; };

// Area and centroid of a face from its own surface and pcurves: with F(u, v) the integral of |Su x Sv| from u0 to u,
// the area is the integral of F dv along the wires (Green). Outer: every edge use cut at its pcurve's knots and where it
// crosses a knot line of the surface, 2 * level panels of Gauss 8 on each piece; inner: the surface's u spans (NURBS),
// one panel (plane) or 4 * level panels, Gauss 8 each.
static FaceMeasure face_measure(const BRep& r, int fi, int level) {
    static const double X[4] = {0.1834346424956498, 0.5255324099163290, 0.7966664774136267, 0.9602898564975363};
    static const double W[4] = {0.3626837833783620, 0.3137066458778873, 0.2223810344533745, 0.1012285362903763};
    FaceMeasure m;
    const BRepFace& face = r.m_faces[fi];
    const Surface& s = r.m_surfaces[face.surface_index];
    const Surface::Kind kind = s.kind();
    std::vector<double> knots;
    if (kind == Surface::Kind::Nurbs) knots = s.nurbs().m_nurbsknot[0];
    bool have = false;
    double u0 = 0.0, sum = 0.0, mom[3] = {0.0, 0.0, 0.0};
    for (const BRepRef& wire : face.wires) {
        const std::vector<BRepRef> uses = r.wire_edges(wire);
        std::vector<std::array<double, 4>> ends;
        for (const BRepRef& er : uses) {
            const BRepCurveOnSurface* use = nullptr;
            for (const BRepCurveOnSurface& pc : r.m_edges[er.index].pcurves)
                if (pc.surface_index == face.surface_index) { use = &pc; break; }
            if (!use) { m.note = "edge " + std::to_string(er.index) + " has no pcurve on the face"; return m; }
            const bool rev = er.orientation == BRepOrientation::Reversed;
            const Curve2d c = r.pcurve(*use, rev && use->curve_2d_index_2 >= 0);
            const auto [t0, t1] = c.domain();
            const Point a = c.point_at(rev ? t1 : t0), b = c.point_at(rev ? t0 : t1);
            ends.push_back({a[0], a[1], b[0], b[1]});
            if (!have) { u0 = a[0]; have = true; }
            // the integrand is smooth between the pcurve's own knots and its crossings of the surface's knot lines
            std::vector<double> at = {t0, t1};
            if (c.kind() == Curve::Kind::Nurbs)
                for (double k : c.nurbs().m_nurbsknot) if (k > t0 && k < t1) at.push_back(k);
            if (kind == Surface::Kind::Nurbs)
                for (int d = 0; d < 2; ++d) {
                    double before = c.point_at(t0)[d];
                    for (int i = 1; i <= 32; ++i) {
                        const double ta = t0 + (t1 - t0) * (i - 1) / 32.0, tb = t0 + (t1 - t0) * i / 32.0, after = c.point_at(tb)[d];
                        for (double k : s.nurbs().m_nurbsknot[d]) {
                            if ((before - k) * (after - k) >= 0.0) continue;
                            double lo = ta, hi = tb;
                            for (int it = 0; it < 50; ++it) { const double mid = 0.5 * (lo + hi); ((c.point_at(mid)[d] - k) * (before - k) > 0.0 ? lo : hi) = mid; }
                            at.push_back(0.5 * (lo + hi));
                        }
                        before = after;
                    }
                }
            std::sort(at.begin(), at.end());
            at.erase(std::unique(at.begin(), at.end()), at.end());
            const int panels = 2 * level * int(at.size() - 1);
            for (int p = 0; p < panels; ++p)
                for (int g = 0; g < 8; ++g) {
                    const double ta = at[p / (2 * level)], h = (at[p / (2 * level) + 1] - ta) / (2 * level);
                    const double t = ta + h * (p % (2 * level) + 0.5 + (g < 4 ? -0.5 * X[3 - g] : 0.5 * X[g - 4]));
                    const std::vector<Vector> cv = c.evaluate(t, 1);
                    const double u = cv[0][0], v = cv[0][1], dv = cv[1][1] * 0.5 * h * W[g < 4 ? 3 - g : g - 4] * (rev ? -1.0 : 1.0);
                    if (dv == 0.0) continue;
                    std::vector<double> cut = {u0};
                    if (kind == Surface::Kind::Nurbs) {
                        for (double k : knots) if (k > std::min(u0, u) && k < std::max(u0, u) && k != cut.back()) cut.push_back(k);
                        if (u < u0) std::reverse(cut.begin() + 1, cut.end());
                    } else if (kind != Surface::Kind::Plane)
                        for (int k = 1; k < 4 * level; ++k) cut.push_back(u0 + (u - u0) * k / (4.0 * level));
                    cut.push_back(u);
                    double f = 0.0, q[3] = {0.0, 0.0, 0.0};
                    for (size_t k = 0; k + 1 < cut.size(); ++k)
                        for (int j = 0; j < 8; ++j) {
                            const double hu = cut[k + 1] - cut[k], uu = cut[k] + hu * (0.5 + (j < 4 ? -0.5 * X[3 - j] : 0.5 * X[j - 4]));
                            const std::vector<Vector> e = s.evaluate(uu, v, 1);
                            const double nx = e[2][1] * e[1][2] - e[2][2] * e[1][1], ny = e[2][2] * e[1][0] - e[2][0] * e[1][2], nz = e[2][0] * e[1][1] - e[2][1] * e[1][0];
                            const double w = std::sqrt(nx * nx + ny * ny + nz * nz) * 0.5 * hu * W[j < 4 ? 3 - j : j - 4];
                            f += w;
                            for (int d = 0; d < 3; ++d) q[d] += w * e[0][d];
                        }
                    sum += f * dv;
                    for (int d = 0; d < 3; ++d) mom[d] += q[d] * dv;
                }
        }
        for (size_t k = 0; k < ends.size(); ++k) {
            const std::array<double, 4>& a = ends[k], & b = ends[(k + 1) % ends.size()];
            m.gap = std::max(m.gap, std::hypot(a[2] - b[0], a[3] - b[1]));
        }
    }
    m.area = std::abs(sum);
    for (int d = 0; d < 3; ++d) m.c[d] = sum != 0.0 ? mom[d] / sum : 0.0;
    return m;
}

struct Triangles { size_t n = 0; double area = 0.0, c[3] = {0.0, 0.0, 0.0}; };

// number, area and centroid of a face mesh's triangles
static Triangles triangles(const Mesh& mesh) {
    const auto [vs, fs] = mesh.to_vertices_and_faces();
    Triangles t;
    for (const auto& f : fs)
        for (size_t k = 1; k + 1 < f.size(); ++k) {
            const Point& a = vs[f[0]], & b = vs[f[k]], & c = vs[f[k + 1]];
            const double x[3] = {b[0] - a[0], b[1] - a[1], b[2] - a[2]}, y[3] = {c[0] - a[0], c[1] - a[1], c[2] - a[2]};
            const double area = 0.5 * std::sqrt(std::pow(x[1] * y[2] - x[2] * y[1], 2) + std::pow(x[2] * y[0] - x[0] * y[2], 2) + std::pow(x[0] * y[1] - x[1] * y[0], 2));
            for (int d = 0; d < 3; ++d) t.c[d] += area * (a[d] + b[d] + c[d]) / 3.0;
            t.area += area;
            ++t.n;
        }
    for (int d = 0; d < 3; ++d) t.c[d] = t.area > 0.0 ? t.c[d] / t.area : 0.0;
    return t;
}

// why face_meshes() gives a face no triangles: the exception of the whole call, else what the face does meshed alone
static std::string unmeshed(const BRep& nurbs, int fi, const std::string& whole, const std::string& measured) {
    std::string why = whole.empty() ? "no triangles and no exception" : "face_meshes throws: " + whole;
    BRep one = nurbs;
    one.m_faces = {nurbs.m_faces[fi]};
    one.m_shells.clear();
    one.m_solids.clear();
    try {
        const std::vector<Mesh> alone = one.face_meshes();
        why += alone.empty() || triangles(alone[0]).n == 0 ? "; alone: no triangles and no exception" : "; alone it meshes";
    } catch (const std::exception& e) { why += std::string("; alone throws: ") + e.what(); }
    return measured.empty() ? why : why + "; " + measured;
}

static void geo(const BRep& r, const std::string& path) {
    std::ofstream o(path);
    o.precision(17);
    double lo[3] = {1e300, 1e300, 1e300}, hi[3] = {-1e300, -1e300, -1e300};
    const auto grow = [&](const Point& p) { for (int d = 0; d < 3; ++d) { lo[d] = std::min(lo[d], p[d]); hi[d] = std::max(hi[d], p[d]); } };
    o << "{\"verts\":[";
    for (size_t i = 0; i < r.m_vertices.size(); ++i) {
        const BRepVertex& v = r.m_vertices[i];
        grow(v.point);
        o << (i ? "," : "") << "[" << v.point[0] << "," << v.point[1] << "," << v.point[2] << "," << v.tolerance << "]";
    }
    o << "],\"edges\":[";
    std::vector<double> length(r.m_edges.size(), 0.0);
    bool first = true;
    for (size_t ei = 0; ei < r.m_edges.size(); ++ei) {
        const BRepEdge& e = r.m_edges[ei];
        if (e.degenerated || e.curve_3d_index < 0) continue;
        const Curve c = r.edge_curve(int(ei));
        const auto [t0, t1] = c.domain();
        bool seam = false;
        for (const BRepCurveOnSurface& pc : e.pcurves) seam |= pc.curve_2d_index_2 >= 0;
        o << (first ? "" : ",") << "{\"i\":" << ei << ",\"tol\":" << e.tolerance << ",\"seam\":" << seam << ",\"kind\":" << int(c.kind()) << ",\"pts\":[";
        first = false;
        Point last;
        for (int i = 0; i <= 32; ++i) {
            const Point p = c.point_at(t0 + (t1 - t0) * i / 32.0);
            if (i) length[ei] += std::sqrt(std::pow(p[0] - last[0], 2) + std::pow(p[1] - last[1], 2) + std::pow(p[2] - last[2], 2));
            last = p;
            grow(p);
            o << (i ? "," : "") << p[0] << "," << p[1] << "," << p[2];
        }
        o << "]";
        try {
            const NurbsCurve n = r.edge_nurbs(int(ei));
            o << ",\"degree\":" << n.m_order - 1 << ",\"knots\":[";
            for (size_t k = 0; k < n.m_nurbsknot.size(); ++k) o << (k ? "," : "") << n.m_nurbsknot[k];
            o << "],\"cvs\":[";
            for (int k = 0; k < n.m_cv_count; ++k) { const Point p = n.get_cv(k); o << (k ? "," : "") << p[0] << "," << p[1] << "," << p[2] << "," << n.weight(k); }
            o << "]";
        } catch (const std::exception& x) { o << ",\"nurbs_error\":" << quoted(x.what()); }
        o << "}";
    }
    o << "],\"faces\":[";
    std::vector<std::string> notes(r.m_faces.size());
    for (size_t fi = 0; fi < r.m_faces.size(); ++fi) {
        FaceMeasure a, b;
        try {
            a = face_measure(r, int(fi), 1);
            if (a.note.empty()) b = face_measure(r, int(fi), 2);
        } catch (const std::exception& x) { b.note = std::string("area not integrated: ") + x.what(); }
        if (!a.note.empty()) b.note = "area not integrated: " + a.note;
        notes[fi] = b.note;
        double perimeter = 0.0, loosest = r.m_faces[fi].tolerance;
        for (const BRepRef& w : r.m_faces[fi].wires)
            for (const BRepRef& e : r.wire_edges(w)) {
                const BRepEdge& edge = r.m_edges[e.index];
                perimeter += length[e.index];
                loosest = std::max({loosest, edge.tolerance, r.m_vertices[edge.start_vertex].tolerance, r.m_vertices[edge.end_vertex].tolerance});
            }
        o << (fi ? "," : "") << "{\"tol\":" << loosest << ",\"kind\":" << int(r.m_surfaces[r.m_faces[fi].surface_index].kind()) << ",\"area\":" << b.area
          << ",\"acc\":" << std::abs(b.area - a.area) << ",\"c\":[" << b.c[0] << "," << b.c[1] << "," << b.c[2] << "],\"gap\":" << b.gap << ",\"perimeter\":" << perimeter
          << ",\"note\":" << quoted(b.note) << "}";
    }
    o << "],\"bbox\":[" << lo[0] << "," << lo[1] << "," << lo[2] << "," << hi[0] << "," << hi[1] << "," << hi[2] << "]}";
    o.close();
    std::cout << "GEO ok\n" << std::flush;
    // the viewer's mesh, in a file of its own: it can take long or not come back
    const auto t0 = std::chrono::steady_clock::now();
    std::vector<Mesh> meshes;
    std::string whole;
    try { meshes = r.face_meshes(); } catch (const std::exception& x) { whole = x.what(); }
    const double seconds = since(t0);
    BRep nurbs;
    try { nurbs = r.is_nurbs() ? r : r.as_nurbs(); } catch (const std::exception&) {}
    std::ofstream m(path + ".mesh");
    m.precision(17);
    m << "{\"mesh_error\":" << quoted(whole) << ",\"seconds\":" << seconds << ",\"faces\":[";
    for (size_t fi = 0; fi < r.m_faces.size(); ++fi) {
        const Triangles t = fi < meshes.size() ? triangles(meshes[fi]) : Triangles();
        if (fi < meshes.size())
            for (const Point& p : meshes[fi].to_vertices_and_faces().first) grow(p);
        m << (fi ? "," : "") << "{\"tris\":" << t.n << ",\"mesh_area\":" << t.area << ",\"c\":[" << t.c[0] << "," << t.c[1] << "," << t.c[2] << "],\"why\":"
          << quoted(t.n ? "" : nurbs.m_faces.size() == r.m_faces.size() ? unmeshed(nurbs, int(fi), whole, notes[fi]) : "face_meshes throws: " + whole) << "}";
    }
    // the box of what is drawn: vertices, edge points and the mesh (inside the true box by the chord of the mesh)
    m << "],\"bbox\":[" << lo[0] << "," << lo[1] << "," << lo[2] << "," << hi[0] << "," << hi[1] << "," << hi[2] << "]}";
    m.close();
    std::cout << "MESH ok " << seconds << "\n" << std::flush;
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
    std::vector<size_t> ftri(r.m_faces.size(), 0);
    std::vector<Triangles> fmesh(r.m_faces.size());
    for (size_t fi = 0; fi < meshes.size(); ++fi) {
        fmesh[fi] = triangles(meshes[fi]);
        const auto [vs, fs] = meshes[fi].to_vertices_and_faces();
        for (size_t i = 0; i < vs.size(); ++i) o << (base + i ? "," : "") << vs[i][0] << "," << vs[i][1] << "," << vs[i][2];
        for (const auto& f : fs)
            for (size_t k = 1; k + 1 < f.size(); ++k) { idx << (first ? "" : ",") << base + f[0] << "," << base + f[k] << "," << base + f[k + 1]; first = false; ++ftri[fi]; }
        base += vs.size();
    }
    o << "],\"idx\":[" << idx.str() << "],\"ftri\":[";
    for (size_t fi = 0; fi < ftri.size(); ++fi) o << (fi ? "," : "") << ftri[fi];
    o << "],\"farea\":[";
    for (size_t fi = 0; fi < fmesh.size(); ++fi) o << (fi ? "," : "") << fmesh[fi].area;
    o << "],\"fcen\":[";
    for (size_t fi = 0; fi < fmesh.size(); ++fi) o << (fi ? "," : "") << "[" << fmesh[fi].c[0] << "," << fmesh[fi].c[1] << "," << fmesh[fi].c[2] << "]";
    const std::vector<int> drawn = drawn_edges(r);
    o << "],\"fedge\":[";
    for (size_t fi = 0; fi < r.m_faces.size(); ++fi) {
        o << (fi ? "," : "") << "[";
        bool one = true;
        for (const BRepRef& w : r.m_faces[fi].wires)
            for (const BRepRef& e : r.wire_edges(w))
                if (drawn[e.index] >= 0) { o << (one ? "" : ",") << drawn[e.index]; one = false; }
        o << "]";
    }
    o << "],\"edges\":[";
    first = true;
    for (size_t ei = 0; ei < r.m_edges.size(); ++ei) {
        const BRepEdge& e = r.m_edges[ei];
        if (e.degenerated || e.curve_3d_index < 0) continue;
        const NurbsCurve c = r.edge_nurbs(int(ei));
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
    if (const char* path = std::getenv("SCORE_GEO")) {
        try { geo(r, path); } catch (const std::exception& e) { std::cout << "GEO FAIL " << clean(e.what()) << "\n"; }
    }
    return 0;
}
