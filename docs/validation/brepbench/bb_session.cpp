// brep-bench runner for session_cpp (SPEC.md 1.19, "A runner"): one program holding every case
// implementation, built against an existing session_cpp build by build.sh (nothing rebuilt).
//
//   bb_session --version
//   bb_session CASE OUT.stl [OUT.step]
//
// With OUT.step the solid is written by file_step::write_file_step_brep and the reply is
// {"status": "ok", "seconds": t}; without it (the harness's untimed fallback) the runner gives
// volume_exact, the tessellated area and the triangles in OUT.stl. A case session_cpp cannot build
// is refused with the reason; booleans go through bop::apply, and an empty bop result is the
// kernel declining (refused, with the bop report's failure). Exceptions are not caught: they crash.
#include "bop.h"
#include "brep.h"
#include "brep_measure.h"
#include "file_step.h"
#include "polyline.h"
#include "xform.h"

#include <array>
#include <chrono>
#include <cmath>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

using namespace session_cpp;

static const double PI = 3.14159265358979323846;
static std::string g_failure; // the last bop::Report::failure seen, for a refusal's reason

// ─────────────────────────────── placement ───────────────────────────────

struct V3 {
    double x, y, z;
};

static V3 unit(V3 d) {
    double l = std::sqrt(d.x * d.x + d.y * d.y + d.z * d.z);
    return {d.x / l, d.y / l, d.z / l};
}

// The rotation taking +z to the direction d.
static Xform z_to(V3 d) {
    d = unit(d);
    if (d.z > 1.0 - 1e-15) return Xform::identity();
    if (d.z < -1.0 + 1e-15) return Xform::rotation_x(PI);
    return Xform::rotation(Vector(-d.y, d.x, 0.0), std::acos(d.z));
}

static BRep moved(BRep b, const Xform& x) {
    b.transform(x);
    return b;
}

static BRep at(BRep b, V3 p) {
    b.transform(Xform::translation(p.x, p.y, p.z));
    return b;
}

// ─────────────────────────────── primitives ───────────────────────────────

static BRep box(double x0, double y0, double z0, double x1, double y1, double z1) {
    return at(BRep::create_box(x1 - x0, y1 - y0, z1 - z0), {(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2});
}

// Cylinder of radius r from p along d (d's length is the height).
static BRep cyl(double r, V3 p, V3 d) {
    double h = std::sqrt(d.x * d.x + d.y * d.y + d.z * d.z);
    return at(moved(BRep::create_cylinder(r, h), z_to(d)), p);
}

static BRep cylz(double r, double x, double y, double z0, double z1) { return cyl(r, {x, y, z0}, {0, 0, z1 - z0}); }

// Frustum (a cone where r1 == 0) with its base of radius r0 at p, its top of radius r1 at p + d.
static BRep frustum(double r0, double r1, V3 p, V3 d) {
    double h = std::sqrt(d.x * d.x + d.y * d.y + d.z * d.z);
    BRep b = r1 == 0.0 ? BRep::create_cone(r0, h) : BRep::create_frustum(r0, r1, h);
    return at(moved(b, z_to(d)), p);
}

// Ball of radius r about c, its poles on the line through c along pole (z by default).
static BRep ball(double r, V3 c, V3 pole = {0, 0, 1}) { return at(moved(BRep::create_sphere(r), z_to(pole)), c); }

static BRep torus(double R, double r, V3 c = {0, 0, 0}, V3 axis = {0, 0, 1}) {
    return at(moved(BRep::create_torus(R, r), z_to(axis)), c);
}

// Prism over a polygon in the xy plane from z0 to z1 (BRep::from_polylines closes the faces into a solid).
static BRep prism(const std::vector<std::array<double, 2>>& pts, double z0, double z1) {
    size_t n = pts.size();
    std::vector<Polyline> faces;
    std::vector<Point> bottom, top;
    for (size_t i = 0; i < n; ++i) bottom.push_back(Point(pts[n - 1 - i][0], pts[n - 1 - i][1], z0));
    bottom.push_back(bottom.front());
    for (size_t i = 0; i < n; ++i) top.push_back(Point(pts[i][0], pts[i][1], z1));
    top.push_back(top.front());
    faces.push_back(Polyline(bottom));
    faces.push_back(Polyline(top));
    for (size_t i = 0; i < n; ++i) {
        const auto& a = pts[i];
        const auto& b = pts[(i + 1) % n];
        faces.push_back(Polyline(std::vector<Point>{Point(a[0], a[1], z0), Point(b[0], b[1], z0), Point(b[0], b[1], z1),
                                                    Point(a[0], a[1], z1), Point(a[0], a[1], z0)}));
    }
    return BRep::from_polylines(faces);
}

// A box of side L whose face through p is square to n, lying on the side n points to: a half-space.
static BRep halfspace(V3 p, V3 n, double L) {
    n = unit(n);
    return at(moved(BRep::create_box(L, L, L), z_to(n)), {p.x + n.x * L / 2, p.y + n.y * L / 2, p.z + n.z * L / 2});
}

// ─────────────────────────────── booleans ───────────────────────────────

static BRep op(const BRep& a, const BRep& b, bop::Operation o) {
    bop::Report report;
    BRep r = bop::apply(a, b, o, 0.0, &report);
    if (!report.failure.empty()) g_failure = report.failure;
    return r;
}
static BRep U(const BRep& a, const BRep& b) { return op(a, b, bop::Operation::Union); }
static BRep I(const BRep& a, const BRep& b) { return op(a, b, bop::Operation::Intersection); }
static BRep D(const BRep& a, const BRep& b) { return op(a, b, bop::Operation::Difference); }

// ─────────────────────────────── cases ───────────────────────────────

static std::map<std::string, std::function<BRep()>> CASES;
static std::map<std::string, std::string> WORKAROUND; // case -> what the kernel lacks (workarounds.toml)
static std::map<std::string, std::string> REFUSE;     // case -> why the kernel cannot build it

static void cases_boolean() {
    CASES["boolean/boss-on-a-lobe-of-the-same-radius"] = [] {
        // No extrude of a curved outline: the outline is the polygon through the lobe and blend centres, less the four
        // blend disks, with the two lobe disks, each taken as a prism (the polygon) or a cylinder.
        double a = 30.0 - 2.0 * std::sqrt(39.0);
        BRep plate = prism({{30, 0}, {a, 10}, {a, 4}, {-a, 4}, {-a, 10}, {-30, 0}, {-a, -10}, {-a, -4}, {a, -4}, {a, -10}}, 0, 10);
        for (double sx : {-1.0, 1.0})
            for (double sy : {-1.0, 1.0}) plate = D(plate, cylz(6, sx * a, sy * 10, -1, 11));
        plate = U(plate, cylz(10, -30, 0, 0, 10));
        plate = U(plate, cylz(10, 30, 0, 0, 10));
        return U(plate, cylz(10, 30, 0, 0, 30));
    };
    WORKAROUND["boolean/boss-on-a-lobe-of-the-same-radius"] = "no extrude of a curved outline";
    CASES["boolean/box-minus-through-cylinder"] = [] { return D(box(0, 0, 0, 10, 10, 10), cylz(3, 5, 5, -1, 11)); };
    CASES["boolean/boxes-common"] = [] { return I(box(0, 0, 0, 10, 10, 10), box(5, 5, 0, 15, 15, 10)); };
    CASES["boolean/boxes-cut"] = [] { return D(box(0, 0, 0, 10, 10, 10), box(5, 5, 0, 15, 15, 10)); };
    CASES["boolean/boxes-union"] = [] { return U(box(0, 0, 0, 10, 10, 10), box(5, 5, 0, 15, 15, 10)); };
    CASES["boolean/boxes-sharing-a-face"] = [] { return U(box(0, 0, 0, 10, 10, 10), box(10, 0, 0, 20, 10, 10)); };
    CASES["boolean/boxes-sharing-part-of-a-face"] = [] { return U(box(0, 0, 0, 10, 10, 10), box(5, 0, 10, 15, 10, 20)); };
    auto chain = [] { return U(U(ball(5, {0, 0, 0}), ball(4, {7, 0, 0})), ball(3, {10, 4, 0})); };
    CASES["boolean/chain-of-three-balls"] = chain;
    CASES["boolean/chain-of-three-balls-halved"] = [chain] { return I(chain(), halfspace({0, 0, 0}, {0, 0, 1}, 40)); };
    CASES["boolean/countersink-undercutting-a-counterbore"] = [] {
        BRep s = D(cylz(100, 0, 0, -20, 20), cylz(60, 0, 0, 0, 21));
        s = D(s, cylz(3.5, 59.9, 0, -15, 0));
        return D(s, frustum(4, 0, {59.9, 0, 0}, {0, 0, -4}));
    };
    CASES["boolean/cross-drilled-cube"] = [] {
        BRep s = box(0, 0, 0, 30, 30, 30);
        for (double c : {7.5, 15.0, 22.5}) s = D(s, cyl(2.5, {-1, c, 15}, {32, 0, 0}));
        for (double c : {7.5, 15.0, 22.5}) s = D(s, cyl(2.5, {c, -1, 15}, {0, 32, 0}));
        for (double x : {7.5, 15.0, 22.5})
            for (double y : {7.5, 15.0, 22.5}) s = D(s, cylz(2.5, x, y, -1, 31));
        return s;
    };
    CASES["boolean/drilled-plate"] = [] {
        BRep s = box(0, 0, 0, 100, 20, 10);
        for (int i = 1; i <= 9; ++i) s = D(s, cylz(2, 10.0 * i, 10, -1, 11));
        return s;
    };
    REFUSE["boolean/elbow-tighter-than-its-tube"] =
        "session_cpp has no revolve or sweep of a disk; the turn crosses its axis, so no torus primitive bounds it";
    CASES["boolean/golf-ball"] = [] {
        double f = (1.0 + std::sqrt(5.0)) / 2.0;
        std::vector<V3> v;
        for (double s1 : {-1.0, 1.0})
            for (double s2 : {-1.0, 1.0}) {
                v.push_back({0, s1, s2 * f});
                v.push_back({s1, s2 * f, 0});
                v.push_back({s2 * f, 0, s1});
            }
        auto dist2 = [](V3 a, V3 b) { return (a.x - b.x) * (a.x - b.x) + (a.y - b.y) * (a.y - b.y) + (a.z - b.z) * (a.z - b.z); };
        std::vector<V3> dirs = v;
        for (size_t i = 0; i < 12; ++i)
            for (size_t j = i + 1; j < 12; ++j)
                if (std::abs(dist2(v[i], v[j]) - 4.0) < 1e-9) dirs.push_back({v[i].x + v[j].x, v[i].y + v[j].y, v[i].z + v[j].z});
        for (size_t i = 0; i < 12; ++i)
            for (size_t j = i + 1; j < 12; ++j)
                for (size_t k = j + 1; k < 12; ++k)
                    if (std::abs(dist2(v[i], v[j]) - 4.0) < 1e-9 && std::abs(dist2(v[i], v[k]) - 4.0) < 1e-9 &&
                        std::abs(dist2(v[j], v[k]) - 4.0) < 1e-9)
                        dirs.push_back({v[i].x + v[j].x + v[k].x, v[i].y + v[j].y + v[k].y, v[i].z + v[j].z + v[k].z});
        if (dirs.size() != 62) throw std::runtime_error("icosahedron directions: " + std::to_string(dirs.size()));
        BRep s = ball(10, {0, 0, 0});
        for (V3 d : dirs) {
            d = unit(d);
            s = D(s, ball(1.2, {10.6 * d.x, 10.6 * d.y, 10.6 * d.z}));
        }
        return s;
    };
    CASES["boolean/half-cylinder-boss-tangent"] = [] { return U(box(0, 0, 0, 10, 10, 10), cylz(5, 10, 5, 0, 10)); };
    CASES["boolean/half-torus"] = [] { return D(torus(10, 2), box(-20, -20, -5, 0, 20, 5)); };
    CASES["boolean/hemisphere"] = [] { return D(ball(5, {0, 0, 0}), box(-10, -10, -10, 10, 10, 0)); };
    CASES["boolean/indexed-pattern"] = [] {
        BRep s = cylz(20, 0, 0, -5, 0);
        for (int i = 0; i < 6; ++i) {
            double t = i * PI / 3.0;
            s = D(s, cylz(2, 12 * std::cos(t), 12 * std::sin(t), -6, 1));
        }
        return s;
    };
    CASES["boolean/linked-tori"] = [] { return U(torus(3, 0.5), torus(3, 0.5, {3, 0, 0}, {0, 1, 0})); };
    CASES["boolean/napkin-ring"] = [] { return D(ball(5, {0, 0, 0}), cylz(3, 0, 0, -6, 6)); };
    CASES["boolean/nested-shells"] = [] {
        BRep a = D(ball(10, {0, 0, 0}), ball(8, {1, 0, 0}));
        BRep b = D(ball(6, {1, 1, 0}), ball(4, {1, 1, 1}));
        return U(U(a, b), ball(2, {1, 1.5, 1.5}));
    };
    CASES["boolean/offset-hole-sphere"] = [] { return D(ball(20, {0, 0, 0}), cyl(6, {5, -21, 0}, {0, 42, 0})); };
    CASES["boolean/reuleaux-tetrahedron"] = [] {
        BRep s = I(ball(10, {0, 0, 0}), ball(10, {10, 0, 0}));
        s = I(s, ball(10, {5, 5 * std::sqrt(3.0), 0}));
        return I(s, ball(10, {5, 5 * std::sqrt(3.0) / 3, 10 * std::sqrt(2.0 / 3.0)}));
    };
    CASES["boolean/ring-of-balls"] = [] {
        BRep s = ball(3, {10, 0, 0});
        for (int i = 1; i < 12; ++i) {
            double t = i * PI / 6.0;
            s = U(s, ball(3, {10 * std::cos(t), 10 * std::sin(t), 0}));
        }
        return s;
    };
    CASES["boolean/sphere-lens"] = [] { return I(ball(5, {0, 0, 0}), ball(5, {6, 0, 0})); };
    CASES["boolean/sphere-pocket"] = [] { return D(box(-10, -10, -10, 10, 10, 0), ball(5, {0, 0, 0})); };
    CASES["boolean/spheres-union"] = [] { return U(ball(5, {0, 0, 0}), ball(5, {6, 0, 0})); };
    CASES["boolean/steinmetz-common"] = [] { return I(cyl(5, {-15, 0, 0}, {30, 0, 0}), cyl(5, {0, -15, 0}, {0, 30, 0})); };
    CASES["boolean/steinmetz-union"] = [] { return U(cyl(5, {-15, 0, 0}, {30, 0, 0}), cyl(5, {0, -15, 0}, {0, 30, 0})); };
    CASES["boolean/stepped-shaft"] = [] { return U(cylz(5, 0, 0, 0, 10), cylz(3, 0, 0, 10, 20)); };
    CASES["boolean/tori-common"] = [] { return I(torus(5, 2, {0, 0, -1}), torus(5, 2, {0, 0, 1})); };
    CASES["boolean/tube"] = [] { return D(cylz(5, 0, 0, 0, 10), cylz(3, 0, 0, -1, 11)); };
    CASES["boolean/tube-flush-ends"] = [] { return D(cylz(5, 0, 0, 0, 10), cylz(3, 0, 0, 0, 10)); };
    CASES["boolean/unequal-lens-aslant"] = [] { return I(ball(5.511, {0, 0, 0}), ball(3.317, {4.231, 3.467, 2.653})); };
}

static void cases_primitives() {
    CASES["primitives/box"] = [] { return box(0, 0, 0, 10, 20, 30); };
    CASES["primitives/cone-frustum"] = [] { return BRep::create_frustum(5, 2, 6); };
    CASES["primitives/cylinder"] = [] { return BRep::create_cylinder(5, 10); };
    CASES["primitives/extruded-l"] = [] { return prism({{0, 0}, {20, 0}, {20, 5}, {5, 5}, {5, 15}, {0, 15}}, 0, 8); };
    CASES["primitives/revolved-washer"] = [] { return D(cylz(10, 0, 0, 0, 4), cylz(6, 0, 0, -1, 5)); };
    WORKAROUND["primitives/revolved-washer"] = "no revolve";
    CASES["primitives/revolved-sector"] = [] {
        return I(D(cylz(10, 0, 0, 0, 4), cylz(6, 0, 0, -1, 5)), box(0, 0, -1, 11, 11, 5));
    };
    WORKAROUND["primitives/revolved-sector"] = "no revolve";
    CASES["primitives/sphere"] = [] { return BRep::create_sphere(5); };
    CASES["primitives/torus"] = [] { return BRep::create_torus(10, 2); };
    CASES["geometry/horn-torus"] = [] { return BRep::create_torus(5, 5); };
    CASES["geometry/torus-nearly-horn"] = [] { return BRep::create_torus(5, 4.99); };
    REFUSE["geometry/spindle-torus"] = "create_torus makes the self-crossing spindle surface, not the solid within 5 of the circle; no revolve";
    REFUSE["geometry/lemon"] = "no revolve, and create_torus gives the whole spindle surface, not its inner part";
}

static void cases_tangent() {
    CASES["tangent/ball-in-band"] = [] { return U(ball(5, {0, 0, 0}), cylz(5, 0, 0, -3, 3)); };
    CASES["tangent/bore-a-micron-from-the-wall"] = [] { return D(cylz(5, 0, 0, 0, 10), cylz(4, 0.999999, 0, -1, 11)); };
    CASES["tangent/coaxial-overlap"] = [] {
        return U(cylz(5, 0, 0, 0, 10), moved(cylz(5, 0, 0, 6, 16), Xform::rotation_z(PI / 2)));
    };
    CASES["tangent/cone-hollowed-to-a-thousandth-wall"] = [] {
        return D(BRep::create_cone(5, 10), BRep::create_cone(4.999, 10));
    };
    CASES["tangent/cone-tip-on-face"] = [] { return U(box(-10, -10, 0, 10, 10, 10), frustum(5, 0, {0, 0, 15}, {0, 0, -15})); };
    CASES["tangent/cube-turned-a-hair"] = [] {
        return U(box(-5, -5, 0, 5, 5, 10), moved(box(-5, -5, 0, 5, 5, 10), Xform::rotation_z(0.001, true)));
    };
    CASES["tangent/cylinder-bored-to-a-thousandth-wall"] = [] { return D(cylz(5, 0, 0, 0, 10), cylz(4.999, 0, 0, 0, 10)); };
    CASES["tangent/cylinder-bored-to-a-ten-thousandth-wall"] = [] { return D(cylz(5, 0, 0, 0, 10), cylz(4.9999, 0, 0, 0, 10)); };
    CASES["tangent/cylinder-bored-to-a-thirty-thousandth-wall"] = [] {
        return D(cylz(5, 0, 0, 0, 10), cylz(4.99997, 0, 0, 0, 10));
    };
    CASES["tangent/cylinder-inscribed-through-a-cube"] = [] { return U(box(-5, -5, -5, 5, 5, 5), cyl(5, {-10, 0, 0}, {20, 0, 0})); };
    CASES["tangent/grazing-cylinders"] = [] { return I(cyl(5, {-15, 0, 0}, {30, 0, 0}), cyl(5, {0, -15, 9.99}, {0, 30, 0})); };
    CASES["tangent/hairline-slot"] = [] { return D(box(0, 0, 0, 10, 10, 10), box(5, -1, 5, 5.000001, 11, 11)); };
    CASES["tangent/half-balls-overlapping"] = [] {
        return U(I(ball(5, {0, 0, 0}), box(-6, -6, 0, 6, 6, 6)), I(ball(5, {0, 0, 0}), box(0, -6, -6, 6, 6, 6)));
    };
    CASES["tangent/half-tori-overlapping"] = [] {
        return U(I(torus(10, 3), box(-14, -14, 0, 14, 14, 4)), I(torus(10, 3), box(0, -14, -4, 14, 14, 4)));
    };
    CASES["tangent/ice-cream-cone"] = [] { return U(ball(15, {0, 0, 0}), frustum(12, 0, {0, 0, -9}, {0, 0, -16})); };
    CASES["tangent/inscribed-ball-common"] = [] { return I(box(0, 0, 0, 10, 10, 10), ball(5, {5, 5, 5})); };
    CASES["tangent/inscribed-ball-union"] = [] { return U(box(0, 0, 0, 10, 10, 10), ball(5, {5, 5, 5})); };
    CASES["tangent/knife-edge-dish"] = [] { return D(cylz(5, 0, 0, 0, 10), ball(5, {0, 0, 10})); };
    CASES["tangent/midsphere-common"] = [] { return I(box(-5, -5, -5, 5, 5, 5), ball(5 * std::sqrt(2.0), {0, 0, 0})); };
    CASES["tangent/pole-cap-a-ten-thousandth-high"] = [] { return I(ball(5, {0, 0, 0}), box(-6, -6, 4.9999, 6, 6, 6)); };
    CASES["tangent/small-box-widened-a-hundredth-cut"] = [] {
        double a = 0.001515 / 2, b = 0.0015 / 2;
        return D(box(-a, -a, 0, a, a, 0.0015), box(-b, -b, 0, b, b, 0.0015));
    };
    CASES["tangent/small-cone-widened-a-hundredth-cut"] = [] {
        return D(BRep::create_cone(0.0007575, 0.0015), BRep::create_cone(0.00075, 0.0015));
    };
    double s = 0.0015, h = 0.000015;
    CASES["tangent/small-cube-raised-a-hundredth-common"] = [s, h] { return I(box(0, 0, 0, s, s, s), box(0, 0, h, s, s, s + h)); };
    CASES["tangent/small-cube-raised-a-hundredth-cut"] = [s, h] { return D(box(0, 0, 0, s, s, s), box(0, 0, h, s, s, s + h)); };
    CASES["tangent/small-cube-raised-a-hundredth-united"] = [s, h] { return U(box(0, 0, 0, s, s, s), box(0, 0, h, s, s, s + h)); };
    CASES["tangent/small-cube-turned-about-its-edge-common"] = [] {
        return I(box(0, 0, 0, 0.001, 0.001, 0.001), moved(box(0, 0, 0, 0.001, 0.001, 0.001), Xform::rotation_z(1.2, true)));
    };
    double r = 0.00075;
    CASES["tangent/small-cylinder-raised-a-hundredth-common"] = [r, s, h] { return I(cylz(r, 0, 0, 0, s), cylz(r, 0, 0, h, s + h)); };
    CASES["tangent/small-cylinder-raised-a-hundredth-cut"] = [r, s, h] { return D(cylz(r, 0, 0, 0, s), cylz(r, 0, 0, h, s + h)); };
    CASES["tangent/small-cylinder-raised-a-hundredth-united"] = [r, s, h] { return U(cylz(r, 0, 0, 0, s), cylz(r, 0, 0, h, s + h)); };
    CASES["tangent/small-cylinder-slid-a-fiftieth-common"] = [r, s, h] { return I(cylz(r, 0, 0, 0, s), cylz(r, h, 0, 0, s)); };
    CASES["tangent/small-cylinder-slid-a-fiftieth-cut"] = [r, s, h] { return D(cylz(r, 0, 0, 0, s), cylz(r, h, 0, 0, s)); };
    CASES["tangent/small-cylinder-slid-a-fiftieth-united"] = [r, s, h] { return U(cylz(r, 0, 0, 0, s), cylz(r, h, 0, 0, s)); };
    CASES["tangent/small-cylinder-widened-a-hundredth-cut"] = [r, s] { return D(cylz(0.0007575, 0, 0, 0, s), cylz(r, 0, 0, 0, s)); };
    CASES["tangent/tangent-tee-common"] = [] { return I(cyl(5, {-15, 0, 0}, {30, 0, 0}), cyl(3, {0, -15, 2}, {0, 30, 0})); };
    CASES["tangent/tangent-tee-union"] = [] { return U(cyl(5, {-15, 0, 0}, {30, 0, 0}), cyl(3, {0, -15, 2}, {0, 30, 0})); };
    CASES["tangent/thin-lens"] = [] { return I(ball(5, {0, 0, 0}), ball(5, {9.999999, 0, 0})); };
    CASES["tangent/torus-in-drum"] = [] { return U(torus(10, 3), cylz(13, 0, 0, -1, 1)); };
    CASES["tangent/torus-through-a-square-slab"] = [] { return U(torus(10, 3), box(-13, -13, -1, 13, 13, 1)); };
    auto villarceau = [](double k) { return I(torus(5 * k, 3 * k), halfspace({0, 0, 0}, {3, 0, -4}, 40 * k)); };
    CASES["tangent/villarceau-half-torus"] = [villarceau] { return villarceau(1); };
    CASES["scale/villarceau-half-torus-ten-thousand-times-larger"] = [villarceau] { return villarceau(10000); };
    auto viv = [](double k, bop::Operation o) {
        return op(ball(10 * k, {0, 0, 0}), cylz(5 * k, 5 * k, 0, -12 * k, 12 * k), o);
    };
    CASES["tangent/viviani-common"] = [viv] { return viv(1, bop::Operation::Intersection); };
    CASES["tangent/viviani-cut"] = [viv] { return viv(1, bop::Operation::Difference); };
    CASES["tangent/viviani-union"] = [viv] { return viv(1, bop::Operation::Union); };
    CASES["scale/viviani-common-a-thousand-times-larger"] = [viv] { return viv(1000, bop::Operation::Intersection); };
    CASES["scale/viviani-cut-a-thousand-times-larger"] = [viv] { return viv(1000, bop::Operation::Difference); };
    CASES["scale/viviani-union-a-thousand-times-larger"] = [viv] { return viv(1000, bop::Operation::Union); };
    CASES["tangent/wedge-a-millionth-steep"] = [] { return I(box(-5, -5, -10, 5, 5, 0), halfspace({0, 0, 0}, {0, -1e-6, 1}, 40)); };
    for (const char* c : {"tangent/ball-in-a-paraboloid-cup", "tangent/paraboloid-tip-a-ten-thousandth-high", "tangent/paraboloid-tip-on-face"})
        REFUSE[c] = "session_cpp has no paraboloid primitive and no revolve of a curve";
}

static void cases_scale_singular_parts() {
    CASES["scale/balls-united-a-million-from-the-origin"] = [] {
        return U(ball(5, {600000, -800000, 0}), ball(4, {600002, -799997, 6}));
    };
    CASES["scale/balls-united-tens-of-metres-across"] = [] { return U(ball(50000, {0, 0, 0}), ball(40000, {20000, 30000, 60000})); };
    CASES["scale/micron-balls-united"] = [] { return U(ball(0.005, {0, 0, 0}), ball(0.004, {0.002, 0.003, 0.006})); };
    CASES["scale/cylinders-crossed-a-million-from-the-origin"] = [] {
        V3 c{600000, -800000, 0}, u{2.0 / 7, 3.0 / 7, 6.0 / 7}, v{3.0 / 7, -6.0 / 7, 2.0 / 7};
        return I(cyl(3, {c.x - 10 * u.x, c.y - 10 * u.y, c.z - 10 * u.z}, {20 * u.x, 20 * u.y, 20 * u.z}),
                 cyl(3, {c.x - 10 * v.x, c.y - 10 * v.y, c.z - 10 * v.z}, {20 * v.x, 20 * v.y, 20 * v.z}));
    };
    CASES["scale/micron-cylinders-crossed"] = [] {
        return I(cyl(0.003, {-0.01, 0, 0}, {0.02, 0, 0}), cyl(0.003, {0, -0.01, 0}, {0, 0.02, 0}));
    };

    CASES["singular/ball-cut-aslant-through-a-pole"] = [] { return D(ball(5, {0, 0, 0}), halfspace({2.5, 0, 2.5}, {1, 0, 1}, 20)); };
    CASES["singular/ball-dimpled-a-hair-from-its-cutters-pole"] = [] {
        double rho = std::sqrt(10.4 * 10.4 - 5.501 * 5.501), t = 120.0 * PI / 180.0;
        return D(ball(10, {0, 0, 0}), ball(0.8, {rho * std::cos(t), rho * std::sin(t), 5.501}));
    };
    CASES["singular/ball-halved-through-its-poles"] = [] { return D(ball(5, {0, 0, 0}), box(-6, -6, -6, 0, 6, 6)); };
    CASES["singular/balls-meeting-through-a-pole"] = [] { return U(ball(5, {0, 0, 0}), ball(5, {4.8, 0, 3.6})); };
    CASES["singular/cone-cut-aslant-through-its-apex"] = [] {
        return D(BRep::create_cone(5, 10), halfspace({0, 0, 10}, {4, 0, 1}, 40));
    };
    CASES["singular/cone-halved-through-its-apex"] = [] { return D(BRep::create_cone(5, 10), box(-6, -6, -1, 0, 6, 11)); };
    CASES["singular/cylinder-hoof"] = [] {
        BRep s = I(cylz(5, 0, 0, -1, 10), halfspace({0, 0, 0}, {0, 0, 1}, 40));
        return I(s, halfspace({0, 0, 0}, {std::tan(PI / 6), 0, -1}, 40));
    };
    CASES["singular/napkin-ring-poles-near-its-rims"] = [] { return D(ball(5, {0, 0, 0}, {3.1, 0, 4}), cylz(3, 0, 0, -6, 6)); };
    CASES["singular/napkin-ring-poles-on-its-rims"] = [] { return D(ball(5, {0, 0, 0}, {3, 0, 4}), cylz(3, 0, 0, -6, 6)); };
    auto sectors = [](double k) {
        // sector: the ball cut by the solid cone of half-angle 45 degrees, apex at the centre, opening along +z
        BRep cone = frustum(12 * k, 0, {0, 0, 12 * k}, {0, 0, -12 * k});
        BRep first = I(ball(10 * k, {0, 0, 0}), cone);
        BRep second = moved(first, Xform::rotation_y(PI / 3));
        return I(first, second);
    };
    CASES["singular/sectors-sharing-an-apex"] = [sectors] { return sectors(1); };
    CASES["singular/sectors-sharing-an-apex-ten-times-larger"] = [sectors] { return sectors(10); };
    REFUSE["singular/saddle-drum-cut-level-through-its-saddle"] = "not written: needs a face on a given B-spline surface, which only BRep's low-level builders could make";

    CASES["parts/flange"] = [] {
        BRep s = U(cylz(32, 0, 0, 0, 6), cylz(15, 0, 0, 6, 16));
        s = D(s, cylz(8, 0, 0, 0, 16));
        for (int i = 0; i < 6; ++i) {
            double t = i * PI / 3.0;
            s = D(s, cylz(3, 24 * std::cos(t), 24 * std::sin(t), -1, 7));
        }
        return s;
    };
    CASES["parts/pin-lug"] = [] { return D(box(0, -5, 0, 80, 5, 40), cyl(8, {60, -6, 20}, {0, 12, 0})); };
    CASES["parts/pocketed-tray"] = [] {
        BRep s = D(box(-36, 0, -24, 36, 16, 24), box(-33, 0, -21, 33, 13, 21));
        for (auto xz : std::vector<std::array<double, 2>>{{26, 14}, {-26, 14}, {-26, -14}, {26, -14}}) {
            BRep tube = D(cyl(5, {xz[0], 5, xz[1]}, {0, 8, 0}), cyl(2, {xz[0], 5, xz[1]}, {0, 8, 0}));
            s = U(s, tube);
        }
        return s;
    };
    CASES["parts/v-belt-pulley"] = [] {
        BRep s = U(cylz(12, 0, 0, -14, 14), cylz(28, 0, 0, -9, 9));
        s = D(s, cylz(6, 0, 0, -14, 14));
        // the revolved triangle, as the ring rho <= 28.5, |z| <= 6 less the two cones its flanks lie on
        // (no revolve; past rho = 28 the cutter differs from the triangle, but not inside the pulley)
        BRep flanks = U(frustum(22, 22 + 7.0 * 6 / 5, {0, 0, 0}, {0, 0, 6}), frustum(22, 22 + 7.0 * 6 / 5, {0, 0, 0}, {0, 0, -6}));
        BRep groove = D(cylz(28.5, 0, 0, -6, 6), flanks);
        return D(s, groove);
    };
    WORKAROUND["parts/v-belt-pulley"] = "no revolve";
    CASES["feature/hole-through-the-upper-arm"] = [] {
        // the C outline in the xz plane, extruded along +y: a prism over (x, z) turned so that its z runs along y
        BRep c = prism({{0, 0}, {40, 0}, {40, 6}, {6, 6}, {6, 24}, {40, 24}, {40, 30}, {0, 30}}, -10, 10);
        c = moved(c, Xform::rotation_x(PI / 2)); // (x, y, z) -> (x, -z, y): the outline's second coordinate becomes z
        return D(c, cylz(4, 28, 0, 20, 31));
    };
}

// Categories and cases this runner does not build, and why.
static std::string refusal(const std::string& id) {
    auto r = REFUSE.find(id);
    if (r != REFUSE.end()) return r->second;
    std::string cat = id.substr(0, id.find('/'));
    if (cat == "swept" || cat == "cnc") return "session_cpp has no sweep of a solid along a path (slide, turn or screw)";
    if (cat == "sweep") return "session_cpp has no sweep of a section along a path";
    if (cat == "fillet") return "session_cpp has no fillet (rolling-ball blend)";
    if (cat == "chamfer") return "session_cpp has no chamfer";
    if (cat == "draft") return "session_cpp has no draft";
    if (cat == "loft") return "session_cpp has no loft of sections into a solid";
    if (cat == "edit") return "session_cpp has no direct edit that moves a solid's faces";
    if (cat == "fill") return "session_cpp has no surface fill of a boundary";
    if (cat == "offset") return "not written in this runner: BRep::offset exists but these cases were not implemented here";
    if (cat == "shell") return "not written in this runner: BRep::hollow exists but these cases were not implemented here";
    if (cat == "thicken") return "not written in this runner: brep_thicken exists but these cases were not implemented here";
    if (cat == "nurbs" || cat == "spline" || cat == "integration")
        return "not written in this runner: needs faces on given NURBS surfaces or curves, which only BRep's low-level builders could make";
    if (cat == "geometry") return "session_cpp has no primitive for this surface and no extrude or revolve of a curve";
    if (cat == "parts") return "session_cpp has no revolve, extrude of a curved outline, fillet or draft";
    if (cat == "feature") return "session_cpp has no extrude or revolve up to a face";
    if (cat == "scale") {
        if (id.find("screwed") != std::string::npos || id.find("spun") != std::string::npos) return "session_cpp has no sweep of a solid";
        if (id.find("grown") != std::string::npos) return "not written in this runner: offset cases not implemented here";
        if (id.find("rounded") != std::string::npos) return "session_cpp has no fillet";
    }
    return "";
}

// ─────────────────────────────── runner ───────────────────────────────

static void pause_if_warm() {
    if (std::getenv("BREP_BENCH_WARM")) std::raise(SIGSTOP);
}

static std::string jstr(const std::string& s) {
    std::string o = "\"";
    for (char c : s) {
        if (c == '"' || c == '\\') o += '\\', o += c;
        else if (c == '\n' || c == '\r' || c == '\t') o += ' ';
        else o += c;
    }
    return o + "\"";
}

static void write_stl(const BRep& b, const std::string& path) {
    auto [pts, faces] = b.mesh().to_vertices_and_faces();
    std::ofstream f(path);
    f.precision(17);
    f << "solid s\n";
    for (const auto& t : faces) {
        if (t.size() != 3) continue;
        f << " facet normal 0 0 0\n  outer loop\n";
        for (size_t i : t) f << "   vertex " << pts[i][0] << " " << pts[i][1] << " " << pts[i][2] << "\n";
        f << "  endloop\n endfacet\n";
    }
    f << "endsolid s\n";
}

int main(int argc, char** argv) {
    if (argc >= 2 && std::string(argv[1]) == "--version") {
        std::cout << "session_cpp (bop::apply), brep-bench runner 0.1" << std::endl;
        return 0;
    }
    if (argc >= 2 && std::string(argv[1]) == "--list") {
        cases_boolean(), cases_primitives(), cases_tangent(), cases_scale_singular_parts();
        for (auto& [k, v] : CASES) std::cout << k << "\tbuilt" << (WORKAROUND.count(k) ? "\tworkaround: " + WORKAROUND[k] : "") << "\n";
        for (auto& [k, v] : REFUSE) std::cout << k << "\trefused\t" << v << "\n";
        return 0;
    }
    if (argc < 3) {
        std::cerr << "usage: bb_session CASE OUT.stl [OUT.step] | --version | --list" << std::endl;
        return 2;
    }
    std::string id = argv[1], out_stl = argv[2], out_step = argc >= 4 ? argv[3] : "";
    cases_boolean(), cases_primitives(), cases_tangent(), cases_scale_singular_parts();
    auto it = CASES.find(id);
    std::string why = it == CASES.end() ? refusal(id) : "";
    if (it == CASES.end() && why.empty()) {
        std::cerr << "no implementation of " << id << std::endl;
        return 3;
    }
    pause_if_warm();
    auto t0 = std::chrono::steady_clock::now();
    auto seconds = [&] { return std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count(); };
    std::ostringstream reply;
    reply.precision(17);
    if (!why.empty()) {
        double t = seconds();
        reply << "{\"status\": \"refused\", \"reason\": " << jstr(why) << ", \"seconds\": " << t << "}";
    } else {
        BRep b = it->second();
        if (b.face_count() == 0) {
            double t = seconds();
            reply << "{\"status\": \"refused\", \"reason\": "
                  << jstr("bop::apply returned an empty result" + (g_failure.empty() ? std::string() : ": " + g_failure))
                  << ", \"seconds\": " << t << "}";
        } else if (!out_step.empty() && file_step::write_file_step_brep(b, out_step)) {
            double t = seconds();
            reply << "{\"status\": \"ok\", \"seconds\": " << t << "}";
        } else {
            double t = seconds();
            double volume = b.volume_exact();
            double area = 0.0;
            for (const auto& fa : brep_measure::faces(b)) area += fa[0];
            write_stl(b, out_stl);
            reply << "{\"status\": \"ok\", \"volume\": " << volume << ", \"area\": " << area << ", \"valid\": "
                  << (b.is_solid() ? "true" : "false");
            if (!out_step.empty()) reply << ", \"step_error\": \"write_file_step_brep returned false\"";
            reply << ", \"seconds\": " << t << "}";
        }
    }
    std::cout << reply.str() << std::endl;
    if (!g_failure.empty()) std::cerr << "bop report failure (not graded): " << g_failure << std::endl;
    pause_if_warm();
    return 0;
}
