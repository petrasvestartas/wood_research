# session_cpp on brep-bench

Counts are pass / built / refused / wrong / crashed / timeout / missing. OCCT and SMLib from the board (board.json); ours from harness/run.py.

| cases | n | session_cpp | OCCT | SMLib |
|---|---|---|---|---|
| all cases | 581 | 83 / 0 / 473 / 24 / 1 / 0 / 0 | 432 / 3 / 58 / 35 / 9 / 1 / 43 | 85 / 1 / 2 / 18 / 0 / 0 / 475 |
| boolean-tagged | 199 | 72 / 0 / 102 / 24 / 1 / 0 / 0 | 157 / 1 / 27 / 3 / 1 / 0 / 10 | 44 / 0 / 1 / 13 / 0 / 0 / 141 |
| boolean/ category | 34 | 29 / 0 / 2 / 3 / 0 / 0 / 0 | 34 / 0 / 0 / 0 / 0 / 0 / 0 | 28 / 0 / 0 / 1 / 0 / 0 / 5 |
| cases we implemented | 111 | 83 / 0 / 3 / 24 / 1 / 0 / 0 | 105 / 0 / 0 / 0 / 0 / 0 / 6 | 50 / 0 / 1 / 12 / 0 / 0 / 48 |

## Wrong and crashed

| case | ours | OCCT | SMLib | volume (ours / expected) | area (ours / expected) | why | our s | OCCT s |
|---|---|---|---|---|---|---|---|---|
| boolean/reuleaux-tetrahedron | wrong | pass | pass |  / 422.158 |  / 297.547 | its STEP's faces do not close into a solid | 0.233161 | 0.039363 |
| boolean/steinmetz-common | wrong | pass | pass | 2356.19 / 666.667 | 1099.56 / 400 | volume 2356.19449019 against 666.666666667 (its STEP's); area 1099.55742876 against 400 (i | 0.0194462 | 0.00986423 |
| boolean/steinmetz-union | wrong | pass | pass | 2356.19 / 4045.72 | 1099.56 / 1799.11 | volume 2356.19449019 against 4045.72231372 (its STEP's); area 1099.55742876 against 1799.1 | 0.00882858 | 0.0111454 |
| scale/micron-cylinders-crossed | wrong | pass | missing | 5.65487e-07 / 1.44e-07 | 0.00043354 / 0.000144 | volume 5.65486677646e-07 against 1.44e-07 (its STEP's); area 0.000433539786195 against 0.0 | 0.018295 | 0.00725074 |
| scale/viviani-common-a-thousand-times-larger | wrong | missing | missing |  / 1.20551e+12 |  / 6.28319e+08 | its STEP's faces do not close into a solid | 0.101525 |  |
| scale/viviani-cut-a-thousand-times-larger | wrong | missing | missing |  / 2.98328e+12 |  / 1.42832e+09 | its STEP's faces do not close into a solid | 0.103473 |  |
| scale/viviani-union-a-thousand-times-larger | wrong | missing | missing |  / 4.86824e+12 |  / 1.53938e+09 | its STEP's faces do not close into a solid | 0.104847 |  |
| singular/ball-halved-through-its-poles | wrong | pass | missing |  / 261.799 |  / 235.619 | its STEP's faces do not close into a solid | 0.0147908 | 0.00460652 |
| singular/balls-meeting-through-a-pole | wrong | pass | missing | 523.599 / 938.289 | 314.159 / 502.655 | volume 523.598775598 against 938.289005872 (its STEP's); area 314.159265359 against 502.65 | 0.00622494 | 0.0092022 |
| singular/cone-cut-aslant-through-its-apex | wrong | pass | missing |  / 210.617 |  / 224.899 | its STEP's faces do not close into a solid | 0.01092 | 0.00481455 |
| singular/cone-halved-through-its-apex | wrong | pass | missing |  / 130.9 |  / 177.08 | its STEP's faces do not close into a solid | 0.00640933 | 0.00481005 |
| singular/napkin-ring-poles-on-its-rims | crashed | pass | missing |  / 268.083 |  / 402.124 | exit -11 | 0.0347876 | 0.00828319 |
| singular/sectors-sharing-an-apex | wrong | pass | missing |  / 146.516 |  / 179.057 | its STEP's faces do not close into a solid | 0.133613 | 0.0383963 |
| singular/sectors-sharing-an-apex-ten-times-larger | wrong | missing | missing |  / 146516 |  / 17905.7 | its STEP's faces do not close into a solid | 0.153043 |  |
| tangent/ball-in-band | wrong | pass | pass |  / 580.147 |  / 370.708 | its STEP's faces do not close into a solid | 0.0445489 | 0.00628635 |
| tangent/cylinder-inscribed-through-a-cube | wrong | pass | pass | 1570.8 / 1785.4 | 785.398 / 914.159 | volume 1570.79632679 against 1785.3981634 (its STEP's); area 785.398163397 against 914.159 | 0.0196781 | 0.0109463 |
| tangent/half-balls-overlapping | wrong | pass | pass |  / 392.699 |  / 314.159 | its STEP's faces do not close into a solid | 0.0297839 | 0.00811876 |
| tangent/midsphere-common | wrong | pass | pass | 1000 / 965.069 | 600 / 547.467 | volume 1000 against 965.068858215 (its STEP's); area 600 against 547.46671805 (its STEP's) | 0.0550457 | 0.0410376 |
| tangent/small-cylinder-slid-a-fiftieth-common | wrong | pass | missing | 2.65072e-09 / 2.61697e-09 | 1.06029e-05 / 1.05129e-05 | volume 2.65071880147e-09 against 2.61696936397e-09 (its STEP's); area 1.06028752059e-05 ag | 0.020498 | 0.0109941 |
| tangent/small-cylinder-slid-a-fiftieth-united | wrong | pass | missing | 2.66197e-09 / 2.68447e-09 | 1.06479e-05 / 1.06929e-05 | volume 2.66196889421e-09 against 2.68446823896e-09 (its STEP's); area 1.06478755768e-05 ag | 0.0565277 | 0.0118052 |
| tangent/torus-through-a-square-slab | wrong | pass | pass | 1352 / 2388.75 | 1560 / 1777.26 | volume 1352 against 2388.75166741 (its STEP's); area 1560 against 1777.26026487 (its STEP' | 0.039949 | 0.0185564 |
| tangent/villarceau-half-torus | wrong | pass | wrong |  / 444.132 |  / 408.438 | its STEP's faces do not close into a solid | 0.0415802 | 0.0393456 |
| tangent/viviani-common | wrong | pass | wrong |  / 1205.51 |  / 628.319 | its STEP's faces do not close into a solid | 0.0588823 | 0.0364323 |
| tangent/viviani-cut | wrong | pass | wrong |  / 2983.28 |  / 1428.32 | its STEP's faces do not close into a solid | 0.0600513 | 0.0372925 |
| tangent/viviani-union | wrong | pass | wrong |  / 4868.24 |  / 1539.38 | its STEP's faces do not close into a solid | 0.0601095 | 0.0386091 |

## Implemented cases: time (kernel's own seconds)

| case | ours | OCCT | our s | OCCT s |
|---|---|---|---|---|
| boolean/boss-on-a-lobe-of-the-same-radius | pass | pass | 0.242659 | 0.0146815 |
| boolean/box-minus-through-cylinder | pass | pass | 0.00615711 | 0.00565663 |
| boolean/boxes-common | pass | pass | 0.00515292 | 0.00590275 |
| boolean/boxes-cut | pass | pass | 0.00596144 | 0.00618175 |
| boolean/boxes-sharing-a-face | pass | pass | 0.00640462 | 0.00542334 |
| boolean/boxes-sharing-part-of-a-face | pass | pass | 0.00703633 | 0.00607635 |
| boolean/boxes-union | pass | pass | 0.00798742 | 0.00725952 |
| boolean/chain-of-three-balls | pass | pass | 0.0316756 | 0.0176422 |
| boolean/chain-of-three-balls-halved | pass | pass | 0.0692095 | 0.0230288 |
| boolean/countersink-undercutting-a-counterbore | pass | pass | 0.053488 | 0.0249992 |
| boolean/cross-drilled-cube | refused | pass | 0.854585 | 0.324606 |
| boolean/drilled-plate | pass | pass | 0.105872 | 0.0276078 |
| boolean/golf-ball | pass | pass | 23.1765 | 1.26487 |
| boolean/half-cylinder-boss-tangent | pass | pass | 0.0129719 | 0.00789092 |
| boolean/half-torus | pass | pass | 0.00486461 | 0.00475227 |
| boolean/hemisphere | pass | pass | 0.00346073 | 0.0041331 |
| boolean/indexed-pattern | pass | pass | 0.0612494 | 0.0170396 |
| boolean/linked-tori | pass | pass | 0.0540597 | 0.00807058 |
| boolean/napkin-ring | pass | pass | 0.00570508 | 0.00508802 |
| boolean/nested-shells | pass | pass | 0.107769 | 0.00620291 |
| boolean/offset-hole-sphere | pass | pass | 0.012575 | 0.0292291 |
| boolean/reuleaux-tetrahedron | wrong | pass | 0.233161 | 0.039363 |
| boolean/ring-of-balls | pass | pass | 0.724155 | 0.0844742 |
| boolean/sphere-lens | pass | pass | 0.00971699 | 0.0104631 |
| boolean/sphere-pocket | pass | pass | 0.00520018 | 0.00518163 |
| boolean/spheres-union | pass | pass | 0.0104335 | 0.0108662 |
| boolean/steinmetz-common | wrong | pass | 0.0194462 | 0.00986423 |
| boolean/steinmetz-union | wrong | pass | 0.00882858 | 0.0111454 |
| boolean/stepped-shaft | pass | pass | 0.00613813 | 0.00444961 |
| boolean/tori-common | pass | pass | 0.04782 | 0.0130418 |
| boolean/tube | pass | pass | 0.0061416 | 0.0051207 |
| boolean/tube-flush-ends | pass | pass | 0.0086131 | 0.00508279 |
| boolean/unequal-lens-aslant | pass | pass | 0.0105044 | 0.0152104 |
| feature/hole-through-the-upper-arm | pass | pass | 0.0101058 | 0.00723381 |
| geometry/horn-torus | pass | pass | 0.000156989 | 0.00260759 |
| geometry/torus-nearly-horn | pass | pass | 0.000237835 | 0.00260414 |
| parts/flange | pass | pass | 0.164751 | 0.021096 |
| parts/pin-lug | pass | pass | 0.00635939 | 0.0055671 |
| parts/pocketed-tray | pass | pass | 0.0860362 | 0.0198256 |
| parts/v-belt-pulley | pass | pass | 0.152487 | 0.00841948 |
| primitives/box | pass | pass | 0.000286371 | 0.00336998 |
| primitives/cone-frustum | pass | pass | 0.000229096 | 0.00275344 |
| primitives/cylinder | pass | pass | 0.000197034 | 0.00265502 |
| primitives/extruded-l | pass | pass | 0.00105475 | 0.00391702 |
| primitives/revolved-sector | pass | pass | 0.0328599 | 0.00393166 |
| primitives/revolved-washer | pass | pass | 0.00659067 | 0.0033394 |
| primitives/sphere | pass | pass | 0.000134335 | 0.00239663 |
| primitives/torus | pass | pass | 0.000147505 | 0.002528 |
| scale/balls-united-a-million-from-the-origin | pass | pass | 0.0148336 | 0.0125188 |
| scale/balls-united-tens-of-metres-across | pass | pass | 0.0272361 | 0.016149 |
| scale/cylinders-crossed-a-million-from-the-origin | pass | pass | 0.0633286 | 0.0115613 |
| scale/micron-balls-united | pass | pass | 0.00988705 | 0.00834762 |
| scale/micron-cylinders-crossed | wrong | pass | 0.018295 | 0.00725074 |
| scale/villarceau-half-torus-ten-thousand-times-larger | pass | missing | 0.118575 |  |
| scale/viviani-common-a-thousand-times-larger | wrong | missing | 0.101525 |  |
| scale/viviani-cut-a-thousand-times-larger | wrong | missing | 0.103473 |  |
| scale/viviani-union-a-thousand-times-larger | wrong | missing | 0.104847 |  |
| singular/ball-cut-aslant-through-a-pole | pass | pass | 0.0286239 | 0.00685678 |
| singular/ball-dimpled-a-hair-from-its-cutters-pole | pass | missing | 0.0156566 |  |
| singular/ball-halved-through-its-poles | wrong | pass | 0.0147908 | 0.00460652 |
| singular/balls-meeting-through-a-pole | wrong | pass | 0.00622494 | 0.0092022 |
| singular/cone-cut-aslant-through-its-apex | wrong | pass | 0.01092 | 0.00481455 |
| singular/cone-halved-through-its-apex | wrong | pass | 0.00640933 | 0.00481005 |
| singular/cylinder-hoof | pass | pass | 0.0084805 | 0.00709641 |
| singular/napkin-ring-poles-near-its-rims | pass | pass | 0.0190978 | 0.0167078 |
| singular/napkin-ring-poles-on-its-rims | crashed | pass | 0.0347876 | 0.00828319 |
| singular/sectors-sharing-an-apex | wrong | pass | 0.133613 | 0.0383963 |
| singular/sectors-sharing-an-apex-ten-times-larger | wrong | missing | 0.153043 |  |
| tangent/ball-in-band | wrong | pass | 0.0445489 | 0.00628635 |
| tangent/bore-a-micron-from-the-wall | pass | pass | 0.0102413 | 0.00507604 |
| tangent/coaxial-overlap | pass | pass | 0.00594741 | 0.00534341 |
| tangent/cone-hollowed-to-a-thousandth-wall | pass | pass | 0.0149946 | 0.0299512 |
| tangent/cone-tip-on-face | pass | pass | 0.0051582 | 0.00559642 |
| tangent/cube-turned-a-hair | pass | pass | 0.0318944 | 0.0121684 |
| tangent/cylinder-bored-to-a-ten-thousandth-wall | pass | pass | 0.0160439 | 0.0249821 |
| tangent/cylinder-bored-to-a-thirty-thousandth-wall | pass | pass | 0.0149892 | 0.01738 |
| tangent/cylinder-bored-to-a-thousandth-wall | pass | pass | 0.0156443 | 0.050914 |
| tangent/cylinder-inscribed-through-a-cube | wrong | pass | 0.0196781 | 0.0109463 |
| tangent/grazing-cylinders | pass | pass | 0.00475004 | 0.0124386 |
| tangent/hairline-slot | pass | pass | 0.00665699 | 0.00744461 |
| tangent/half-balls-overlapping | wrong | pass | 0.0297839 | 0.00811876 |
| tangent/half-tori-overlapping | pass | pass | 0.0262072 | 0.0162207 |
| tangent/ice-cream-cone | pass | pass | 0.0153012 | 0.00713306 |
| tangent/inscribed-ball-common | pass | pass | 0.0389272 | 0.00485108 |
| tangent/inscribed-ball-union | pass | pass | 0.0400661 | 0.00556965 |
| tangent/knife-edge-dish | pass | pass | 0.00998485 | 0.00491352 |
| tangent/midsphere-common | wrong | pass | 0.0550457 | 0.0410376 |
| tangent/pole-cap-a-ten-thousandth-high | pass | pass | 0.00398335 | 0.00408358 |
| tangent/small-box-widened-a-hundredth-cut | pass | pass | 0.0073613 | 0.00594035 |
| tangent/small-cone-widened-a-hundredth-cut | pass | pass | 0.0238198 | 0.00870083 |
| tangent/small-cube-raised-a-hundredth-common | pass | pass | 0.00586912 | 0.00628075 |
| tangent/small-cube-raised-a-hundredth-cut | pass | pass | 0.00575281 | 0.00577047 |
| tangent/small-cube-raised-a-hundredth-united | pass | pass | 0.0081363 | 0.00696103 |
| tangent/small-cube-turned-about-its-edge-common | pass | pass | 0.00721107 | 0.00664143 |
| tangent/small-cylinder-raised-a-hundredth-common | pass | pass | 0.0211792 | 0.00459453 |
| tangent/small-cylinder-raised-a-hundredth-cut | pass | pass | 0.0223335 | 0.00442547 |
| tangent/small-cylinder-raised-a-hundredth-united | pass | pass | 0.024772 | 0.00475298 |
| tangent/small-cylinder-slid-a-fiftieth-common | wrong | pass | 0.020498 | 0.0109941 |
| tangent/small-cylinder-slid-a-fiftieth-cut | refused | pass | 0.0185625 | 0.0107947 |
| tangent/small-cylinder-slid-a-fiftieth-united | wrong | pass | 0.0565277 | 0.0118052 |
| tangent/small-cylinder-widened-a-hundredth-cut | pass | pass | 0.0170815 | 0.00644196 |
| tangent/tangent-tee-common | pass | pass | 0.0217063 | 0.0309219 |
| tangent/tangent-tee-union | pass | pass | 0.0217063 | 0.0329574 |
| tangent/thin-lens | pass | pass | 0.00883674 | 0.00568397 |
| tangent/torus-in-drum | pass | pass | 0.0766676 | 0.0238308 |
| tangent/torus-through-a-square-slab | wrong | pass | 0.039949 | 0.0185564 |
| tangent/villarceau-half-torus | wrong | pass | 0.0415802 | 0.0393456 |
| tangent/viviani-common | wrong | pass | 0.0588823 | 0.0364323 |
| tangent/viviani-cut | wrong | pass | 0.0600513 | 0.0372925 |
| tangent/viviani-union | wrong | pass | 0.0601095 | 0.0386091 |
| tangent/wedge-a-millionth-steep | refused | pass | 0.00352193 | 0.00544417 |
