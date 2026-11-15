// roundtrip <file> <outdir>: RT <file> i faces volume -> written file, read back faces volume, pcurves certified
#include "brep.h"
#include "file_step.h"
#include "curve_surface_intersection.h"
#include <iostream>
#include <cmath>
using namespace session_cpp;
static double vol(const BRep& b) { try { return b.volume_exact(); } catch (...) { return NAN; } }
int main(int argc, char** argv) {
    std::cout.precision(15);
    std::vector<BRep> in;
    try { in = file_step::read_file_step_breps(argv[1]); } catch (const std::exception& e) { std::cout << "RTFAIL " << argv[1] << " read " << e.what() << "\n"; return 0; }
    std::string base = argv[1]; base = base.substr(base.find_last_of('/') + 1);
    for (size_t i = 0; i < in.size(); ++i) {
        const std::string out = std::string(argv[2]) + "/" + base + "." + std::to_string(i) + ".step";
        const bool ok = file_step::write_file_step_brep(in[i], out);
        std::cout << "RT " << argv[1] << " " << i << " " << in[i].face_count() << " " << in[i].is_solid() << " " << vol(in[i]) << " " << out << " " << ok;
        try {
            const auto back = file_step::read_file_step_breps(out);
            int faces = 0; double v = 0; bool solid = !back.empty();
            for (const auto& b : back) { faces += b.face_count(); v += vol(b); solid = solid && b.is_solid(); }
            std::cout << " back " << back.size() << " " << faces << " " << solid << " " << v << "\n";
        } catch (const std::exception& e) { std::string m = e.what(); for (char& c : m) if (c == '\n') c = ' '; std::cout << " backfail " << m.substr(0, 150) << "\n"; }
    }
}
