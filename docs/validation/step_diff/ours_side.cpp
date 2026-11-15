// ours_side <file> [dump.json]: session_cpp reader, the lines of occt_side.py for our side:
//   UENT <type> <count>; EDGE brep #edge_curve length x0 y0 z0 x1 y1 z1; WIRE brep #face wire #edge_curve per edge (0 made by the reader, -id a piece of a split edge);
//   USE brep #face #edge_curve deviation; FACE <file> brep face area cx cy cz z-flux wires edges-per-wire (non-degenerated);
//   SOLID <file> brep faces valid solid volume max-edge-tolerance; dump = meshes of every BRep
#include "brep.h"
#include "file_step.h"
#include <array>
#include <cmath>
#include <fstream>
#include <iostream>
#include <sstream>
using namespace session_cpp;
static const double X[10] = {-0.9739065285171717, -0.8650633666889845, -0.6794095682990244, -0.4333953941292472, -0.1488743389816312,
    0.1488743389816312, 0.4333953941292472, 0.6794095682990244, 0.8650633666889845, 0.9739065285171717};
static const double W[10] = {0.0666713443086881, 0.1494513491505806, 0.2190863625159820, 0.2692667193099963, 0.2955242247147529,
    0.2955242247147529, 0.2692667193099963, 0.2190863625159820, 0.1494513491505806, 0.0666713443086881};
// integral over s in [u0, u] of (|N|, S|N|) at v
static std::array<double, 5> inner(const NurbsSurface& s, double u, double v) {
    std::vector<double> cuts{s.domain(0).first};
    for (double k : s.get_span_vector(0)) if (k > cuts.back() && k < u) cuts.push_back(k);
    if (u > cuts.back()) cuts.push_back(u);
    std::array<double, 5> r{0, 0, 0, 0, 0};
    for (size_t i = 1; i < cuts.size(); ++i)
        for (int part = 0; part < 4; ++part) {
            const double a = cuts[i - 1] + (cuts[i] - cuts[i - 1]) * part / 4, b = cuts[i - 1] + (cuts[i] - cuts[i - 1]) * (part + 1) / 4;
            for (int k = 0; k < 10; ++k) {
                const double x = 0.5 * (a + b) + 0.5 * (b - a) * X[k];
                const auto e = s.evaluate(x, v, 1);
                const double n = e[2].cross(e[1]).magnitude() * W[k] * 0.5 * (b - a);
                r[0] += n; r[1] += e[0][0] * n; r[2] += e[0][1] * n; r[3] += e[0][2] * n; r[4] += e[0][2] * e[2].cross(e[1])[2] * W[k] * 0.5 * (b - a);
            }
        }
    return r;
}
static std::string dump(const std::vector<BRep>& bs) {
    std::ostringstream o; o.precision(7);
    o << "{\"pos\":["; std::ostringstream idx, ed; size_t base = 0; bool first = true, fe = true; int nf = 0, ne = 0, nv = 0;
    std::ostringstream vs;
    for (const BRep& r : bs) {
        nf += r.face_count(); ne += r.edge_count(); nv += r.vertex_count();
        std::vector<Mesh> meshes;
        try { meshes = r.face_meshes(); } catch (const std::exception& e) { std::cerr << "MESHFAIL " << e.what() << "\n"; }
        for (const Mesh& m : meshes) {
            const auto [v, f] = m.to_vertices_and_faces();
            for (size_t i = 0; i < v.size(); ++i) o << (base + i ? "," : "") << v[i][0] << "," << v[i][1] << "," << v[i][2];
            for (const auto& t : f) for (size_t k = 1; k + 1 < t.size(); ++k) { idx << (first ? "" : ",") << base + t[0] << "," << base + t[k] << "," << base + t[k + 1]; first = false; }
            base += v.size();
        }
        for (const BRepEdge& e : r.m_edges) {
            if (e.degenerated || e.curve_3d_index < 0) continue;
            const NurbsCurve& c = r.m_curves_3d[e.curve_3d_index];
            ed << (fe ? "" : ",") << "["; fe = false;
            for (int i = 0; i <= 48; ++i) { const Point p = c.point_at(c.domain_start() + (c.domain_end() - c.domain_start()) * i / 48.0); ed << (i ? "," : "") << p[0] << "," << p[1] << "," << p[2]; }
            ed << "]";
        }
        for (const auto& p : r.m_vertices) vs << (vs.tellp() > 0 ? "," : "") << p.point[0] << "," << p.point[1] << "," << p.point[2];
    }
    o << "],\"idx\":[" << idx.str() << "],\"edges\":[" << ed.str() << "],\"verts\":[" << vs.str() << "],\"counts\":[" << nf << "," << ne << "," << nv << "]}";
    return o.str();
}
int main(int argc, char** argv) {
    std::cout.precision(15);
    std::cout << std::unitbuf;
    std::vector<BRep> bs;
    std::vector<file_step::StepIds> ids;
    for (const auto& [type, n] : file_step::read_file_step_entity_counts(argv[1])) std::cout << "UENT " << type << " " << n << "\n";
    try { bs = file_step::read_file_step_breps(argv[1], 1e-7, &ids); } catch (const std::exception& e) {
        std::cout << "FACESFAIL " << argv[1] << " " << e.what() << "\n";
        if (argc > 2) { std::ofstream(argv[2]) << "{\"pos\":[],\"idx\":[],\"edges\":[],\"verts\":[],\"counts\":[0,0,0],\"error\":\"" << std::string(e.what()).substr(0, 80) << "\"}"; }
        return 0;
    }
    for (size_t bi = 0; bi < bs.size(); ++bi) {
        const BRep& b = bs[bi];
        std::vector<bool> used(b.m_edges.size(), false);
        for (const BRepFace& f : b.m_faces) for (const BRepRef& w : f.wires) for (const BRepRef& er : b.wire_edges(w)) used[er.index] = true;
        for (size_t ei = 0; ei < b.m_edges.size(); ++ei) {
            const BRepEdge& e = b.m_edges[ei];
            if (!used[ei] || e.degenerated || e.curve_3d_index < 0) continue;
            const NurbsCurve& c = b.m_curves_3d[e.curve_3d_index];
            const Point p0 = b.m_vertices[e.start_vertex].point, p1 = b.m_vertices[e.end_vertex].point;
            std::cout << "EDGE " << bi << " " << ids[bi].edges[ei] << " " << c.length() << " " << p0[0] << " " << p0[1] << " " << p0[2] << " " << p1[0] << " " << p1[1] << " " << p1[2] << "\n";
        }
        for (int fi = 0; fi < b.face_count(); ++fi) {
            const NurbsSurface& srf = b.m_surfaces[b.m_faces[fi].surface_index];
            for (size_t wi = 0; wi < b.m_faces[fi].wires.size(); ++wi) {
                std::string list;
                for (const BRepRef& er : b.wire_edges(b.m_faces[fi].wires[wi])) {
                    const BRepEdge& e = b.m_edges[er.index];
                    if (e.degenerated) continue;
                    list += (list.empty() ? "" : ",") + std::to_string(ids[bi].edges[er.index]);
                    const int pi = b.pcurve_index(er.index, fi, er.orientation);
                    double dev = INFINITY;
                    if (pi >= 0 && e.curve_3d_index >= 0) {
                        const NurbsCurve& pc = b.m_curves_2d[pi]; const NurbsCurve& w3 = b.m_curves_3d[e.curve_3d_index];
                        dev = 0;
                        for (int q = 0; q <= 16; ++q) {
                            const Point uv = pc.point_at(pc.domain_start() + (pc.domain_end() - pc.domain_start()) * q / 16.0);
                            dev = std::max(dev, Point(srf.point(uv[0], uv[1])).distance(w3.point_at(w3.domain_start() + (w3.domain_end() - w3.domain_start()) * q / 16.0)));
                        }
                    }
                    if (std::getenv("WIREUV") && std::atoi(std::getenv("WIREUV")) == ids[bi].faces[fi] && pi >= 0) {
                        const NurbsCurve& pc = b.m_curves_2d[pi]; const bool rev = er.orientation == BRepOrientation::Reversed;
                        const Point a = rev ? pc.point_at_end() : pc.point_at_start(), c = rev ? pc.point_at_start() : pc.point_at_end(), m = pc.point_at_middle();
                        std::cerr << "  uv edge " << ids[bi].edges[er.index] << " (" << a[0] << ", " << a[1] << ") -> (" << m[0] << ", " << m[1] << ") -> (" << c[0] << ", " << c[1] << ") dom " << srf.domain(0).first << " " << srf.domain(0).second << " " << srf.domain(1).first << " " << srf.domain(1).second << "\n";
                    }
                    std::cout << "USE " << bi << " " << ids[bi].faces[fi] << " " << ids[bi].edges[er.index] << " " << dev << "\n";
                }
                std::cout << "WIRE " << bi << " " << ids[bi].faces[fi] << " " << wi << " " << list << "\n";
            }
        }
        for (int fi = 0; fi < b.face_count(); ++fi) {
            const NurbsSurface& s = b.m_surfaces[b.m_faces[fi].surface_index];
            std::array<double, 5> sum{0, 0, 0, 0, 0};
            for (const BRepRef& w : b.m_faces[fi].wires)
                for (const BRepRef& er : b.wire_edges(w)) {
                    const int pi = b.pcurve_index(er.index, fi, er.orientation);
                    if (pi < 0) continue;
                    const NurbsCurve& pc = b.m_curves_2d[pi];
                    const double sign = er.orientation == BRepOrientation::Reversed ? -1 : 1;
                    const auto spans = pc.get_span_vector();
                    for (size_t i = 1; i < spans.size(); ++i)
                        for (int part = 0; part < 8; ++part) {
                            const double a = spans[i - 1] + (spans[i] - spans[i - 1]) * part / 8, c = spans[i - 1] + (spans[i] - spans[i - 1]) * (part + 1) / 8;
                            for (int k = 0; k < 10; ++k) {
                                const double t = 0.5 * (a + c) + 0.5 * (c - a) * X[k];
                                const auto d = pc.evaluate(t, 1);
                                const auto in = inner(s, d[0][0], d[0][1]);
                                for (int q = 0; q < 5; ++q) sum[q] += sign * in[q] * d[1][1] * W[k] * 0.5 * (c - a);
                            }
                        }
                }
            const double area = std::abs(sum[0]);
            std::string wires;
            for (const BRepRef& w : b.m_faces[fi].wires) {
                int n = 0;
                for (const BRepRef& er : b.wire_edges(w)) n += !b.m_edges[er.index].degenerated;
                wires += (wires.empty() ? "" : ",") + std::to_string(n);
            }
            std::cout << "FACE " << argv[1] << " " << bi << " " << fi << " " << area << " " << sum[1] / sum[0] << " " << sum[2] / sum[0] << " " << sum[3] / sum[0] << " " << (b.face_orientation(fi) == BRepOrientation::Reversed ? -sum[4] : sum[4]) * (sum[0] < 0 ? -1 : 1) << " " << b.m_faces[fi].wires.size() << " " << wires << "\n";
        }
    }
    for (size_t bi = 0; bi < bs.size(); ++bi) {
        double v = NAN, tol = 0;
        try { v = bs[bi].volume_exact(); } catch (...) {}
        for (const auto& e : bs[bi].m_edges) tol = std::max(tol, e.tolerance);
        std::cout << "SOLID " << argv[1] << " " << bi << " " << bs[bi].face_count() << " " << bs[bi].is_valid() << " " << bs[bi].is_solid() << " " << v << " " << tol << "\n";
    }
    if (argc > 2) std::ofstream(argv[2]) << dump(bs);
}
