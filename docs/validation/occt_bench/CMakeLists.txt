cmake_minimum_required(VERSION 3.20)
project(occt_bench CXX)
set(CMAKE_CXX_STANDARD 17)
# OCCT is the oracle here and nowhere else: OCCT_BUILD is the build directory of an OCCT checkout.
set(OCCT_BUILD "" CACHE PATH "OCCT build directory")
add_executable(occt_bench occt_bench.cpp)
target_include_directories(occt_bench PRIVATE ${OCCT_BUILD}/include/opencascade)
target_link_directories(occt_bench PRIVATE ${OCCT_BUILD}/lin64/gcc/lib)
target_link_libraries(occt_bench PRIVATE TKBO TKOffset TKPrim TKTopAlgo TKGeomAlgo TKBRep TKGeomBase TKG3d TKG2d TKMath TKernel)
