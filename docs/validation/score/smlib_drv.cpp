// SMLib side of the scoreboard: smlib_drv <A.txt> <B.txt> <op>   (operands as smlib_ref.py exports them)
//   <op> <status> <faces> <edges> <vertices> <valid> <volume> <volA> <volB> [message]
// An operand is rebuilt in OCCT's topology with SmBrepConstructor (one region, one shell; edges shared by passing the
// existing edge; degenerated edges left out; pcurves as UV trim curves unless SM_NOUV=1), then SmApiBoolean.
// valid = AssertValid (level 1) and IsManifoldSolid (not asked of a xor, whose parts may touch along edges).
// SM_TOL=<zone tolerance> overrides SMLib's default of 1e-5; SM_WHY=1 prints the failed checks.
#include <SmApiBrep.h>
#include <SmApiGeneral.h>
#include <SmApiQueries.h>
#include <SmAssertArray.h>
#include <SmBSplineCurve.h>
#include <SmBSplineSurface.h>
#include <SmBrep.h>
#include <SmBrepData.h>
#include <SmEdge.h>
#include <SmFace.h>
#include <SmVertex.h>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

static void check(bool ok, const char* what) {
    if (!ok) throw std::runtime_error(what);
}

static SmBSplineCurve* curve(std::istream& in, const SmContext& ctx, int dim) {
    int degree, np, nk;
    in >> degree >> np >> nk;
    SmTArray<double> knots, weights;
    SmTArray<ULONG> mults;
    SmTArray<SmPoint3d> poles;
    for (int i = 0; i < nk; ++i) { double k; in >> k; knots.Add(k); }
    for (int i = 0; i < nk; ++i) { ULONG m; in >> m; mults.Add(m); }
    for (int i = 0; i < np; ++i) {
        double x, y, z = 0.0, w;
        in >> x >> y;
        if (dim == 3) in >> z;
        in >> w;
        poles.Add(SmPoint3d(x, y, z));
        weights.Add(w);
    }
    SmBSplineCurve* c = NULL;
    check(SmBSplineCurve::CreateCanonical(ctx, dim, degree, poles, SM_CF_UNSPECIFIED, mults, knots, SM_KT_UNSPECIFIED, &weights, NULL, c) == SM_SUCCESS && c, "curve not accepted");
    return c;
}

static SmBrep* load(const char* path, const SmContext& ctx) {
    std::ifstream in(path);
    check(in.good(), "operand file missing");
    std::string tag;
    int nv, ne, nf;
    in >> tag >> nv;
    SmBrepConstructor make;
    SmBrep* brep = make.StartBrep(ctx);
    check(brep, "StartBrep");
    if (const char* tol = std::getenv("SM_TOL")) brep->SetTolerance(std::atof(tol), FALSE);
    std::vector<SmVertex*> vertices(nv);
    for (int i = 0; i < nv; ++i) {
        double x, y, z;
        in >> x >> y >> z;
        vertices[i] = make.StartVertexOfLoop(SmPoint3d(x, y, z));
    }
    struct Edge { bool real; double t0, t1; int v0, v1; SmBSplineCurve* curve; SmEdge* edge; };
    in >> tag >> ne;
    std::vector<Edge> edges(ne);
    for (Edge& e : edges) {
        in >> e.real;
        e.edge = NULL;
        if (e.real) { in >> e.t0 >> e.t1 >> e.v0 >> e.v1; e.curve = curve(in, ctx, 3); }
    }
    check(make.StartRegion(TRUE, NULL), "StartRegion");
    SmShell *outer = NULL, *inner = NULL;
    check(make.StartShell(outer, inner) == SM_SUCCESS, "StartShell");
    in >> tag >> nf;
    const bool uv = !std::getenv("SM_NOUV");
    for (int f = 0; f < nf; ++f) {
        int same, du, dv, nu, nw, nku, nkv, loops;
        in >> same >> du >> dv >> nu >> nw >> nku >> nkv;
        SmTArray<double> uk, vk, weights;
        SmTArray<ULONG> um, vm;
        SmTArray<SmPoint3d> poles;
        for (int i = 0; i < nku; ++i) { double k; in >> k; uk.Add(k); }
        for (int i = 0; i < nku; ++i) { ULONG m; in >> m; um.Add(m); }
        for (int i = 0; i < nkv; ++i) { double k; in >> k; vk.Add(k); }
        for (int i = 0; i < nkv; ++i) { ULONG m; in >> m; vm.Add(m); }
        for (int i = 0; i < nu * nw; ++i) { double x, y, z, w; in >> x >> y >> z >> w; poles.Add(SmPoint3d(x, y, z)); weights.Add(w); }
        double u0, u1, v0, v1;
        in >> u0 >> u1 >> v0 >> v1 >> loops;
        SmBSplineSurface* surface = NULL;
        check(SmBSplineSurface::CreateCanonical(ctx, du, dv, poles, SM_SF_UNSPECIFIED, um, vm, uk, vk, SM_KT_UNSPECIFIED, &weights, NULL, surface) == SM_SUCCESS && surface,
              "surface not accepted");
        check(make.StartFace(same ? SM_OT_SAME : SM_OT_OPPOSITE), "StartFace");
        check(make.SetFaceSurface(surface, SmExtent2d(u0, v0, u1, v1)) == SM_SUCCESS, "SetFaceSurface");
        for (int l = 0; l < loops; ++l) {
            int uses;
            in >> uses;
            check(make.StartLoop(SM_OT_SAME), "StartLoop");
            for (int k = 0; k < uses; ++k) {
                int index, forward, has_trim;
                in >> index >> forward >> has_trim;
                SmBSplineCurve* trim = has_trim ? curve(in, ctx, 2) : NULL;
                Edge& e = edges[index];
                check(e.real, "loop uses a degenerated edge");
                const bool fresh = e.edge == NULL;
                SmEdge* made = make.StartEdge(forward ? SM_OT_SAME : SM_OT_OPPOSITE, e.edge, fresh ? vertices[e.v0] : NULL, fresh ? vertices[e.v1] : NULL);
                check(made, "StartEdge");
                if (fresh) {
                    e.edge = made;
                    check(make.SetEdgeCurve(e.curve, FALSE) == SM_SUCCESS, "SetEdgeCurve 3D");
                    check(make.SetLimits(SmVertexNode(e.t0), SmVertexNode(e.t1)) == SM_SUCCESS, "SetLimits");
                }
                if (uv && trim) check(make.SetEdgeCurve(trim, TRUE) == SM_SUCCESS, "SetEdgeCurve UV");
                else delete trim;
                check(make.EndEdge() == SM_SUCCESS, "EndEdge");
            }
            check(make.EndLoop() == SM_SUCCESS, "EndLoop");
        }
        check(make.EndFace() == SM_SUCCESS, "EndFace");
    }
    check(make.EndShell(FALSE) == SM_SUCCESS, "EndShell");
    check(make.EndRegion() == SM_SUCCESS, "EndRegion");
    check(make.EndBrep() == SM_SUCCESS, "EndBrep");
    return brep;
}

static double volume(const SmBrep* b) {
    double v = std::nan("");
    if (SmApiBrepComputeVolume(b, 1e-8, v) != SM_SUCCESS) v = std::nan("");
    return v;
}

static int valid(const SmBrep* b, bool manifold = true) {
    SmAssertArray failures;
    const bool ok = b->AssertValid(&failures, SM_LEVEL_1, SM_WALK, NULL), solid = b->IsManifoldSolid();
    if (std::getenv("SM_WHY")) {
        std::cerr << "AssertValid " << ok << " manifold solid " << solid << "\n";
        for (ULONG i = 0; i < failures.GetSize() && i < 12; ++i) {
            TCHAR message[SM_TBLOCK_SIZE];
            failures.GetAt(i)->FormatLogMessage(message, SM_TBLOCK_SIZE);
            std::cerr << "  " << smos_FromTChar(failures.GetAt(i)->m_sOwnerTypeString) << " " << smos_FromTChar(failures.GetAt(i)->m_pName) << " - " << smos_FromTChar(message) << "\n";
        }
    }
    return ok && (solid || !manifold);
}

int main(int argc, char** argv) {
    if (argc < 4) { std::cerr << "usage: smlib_drv <A.txt> <B.txt> <op>\n"; return 2; }
    const std::string op = argv[3];
    std::cout.precision(15);
    SmApiCreateContext();
    const SmContext& ctx = *SmApiGetOrCreateContext();
    SmBrep *a = NULL, *b = NULL;
    double va = std::nan(""), vb = std::nan("");
    try {
        a = load(argv[1], ctx);
        b = load(argv[2], ctx);
        va = volume(a);
        vb = volume(b);
        if (op == "operands") {
            std::cout << "operands ok " << a->GetNumFaces() << " " << a->GetNumEdges() << " " << a->GetNumVertices() << " " << valid(a) << " " << va << " " << va << " " << vb << " B: "
                      << b->GetNumFaces() << " " << b->GetNumEdges() << " " << b->GetNumVertices() << " " << valid(b) << "\n";
            return 0;
        }
    } catch (const std::exception& e) {
        std::cout << op << " LOADFAIL 0 0 0 0 nan " << va << " " << vb << " " << e.what() << "\n";
        return 0;
    }
    const SmBooleanOperationType type = op == "intersection" ? SM_BO_INTERSECTION : op == "union" ? SM_BO_UNION : op == "xor" ? SM_BO_EXCLUSIVE_OR : SM_BO_DIFFERENCE;
    SmBrep* r = NULL;
    const SmApiStatus status = op == "b-a" ? SmApiBoolean(b, a, type, r) : SmApiBoolean(a, b, type, r);
    if (status != SM_SUCCESS || !r) {
        std::cout << op << " FAIL 0 0 0 0 nan " << va << " " << vb << " SmApiBoolean status " << int(status) << "\n";
        return 0;
    }
    const ULONG faces = r->GetNumFaces();
    std::cout << op << " ok " << faces << " " << r->GetNumEdges() << " " << r->GetNumVertices() << " " << (faces == 0 ? 1 : valid(r, op != "xor")) << " " << (faces == 0 ? 0.0 : volume(r)) << " " << va << " " << vb << "\n";
    return 0;
}
