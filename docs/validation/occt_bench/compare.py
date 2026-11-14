# usage: compare.py <ours bench output> [occt bench output]   prints the speed table of ours against OCCT per pair
import shlex, sys
names = {0: "box", 1: "cylinder", 2: "sphere", 3: "cone", 4: "pyramid", 5: "torus", 6: "drilled block"}

def read(path):
    seconds, rows, order = {}, {}, []
    for line in open(path):
        if not line.startswith('"'):
            continue
        t = shlex.split(line)
        if t[0] not in seconds:
            order.append(t[0])
        seconds[t[0]] = seconds.get(t[0], 0.0) + float(t[3])
        rows[(t[0], t[1])] = (t[2], t[4:7], float(t[-1]) if t[2] == "ok" and t[-1] != "budget" else None)
    return seconds, rows, order

ours, our_rows, order = read(sys.argv[1])
occt, occt_rows, _ = read(sys.argv[2] if len(sys.argv) > 2 else __file__.replace("compare.py", "occt_bench_d3056ef8.txt"))
print("| Pair | OCCT s | ours s | ratio |\n| --- | --- | --- | --- |")
for label in sorted(order, key=lambda k: -ours[k]):
    a, b = (int(x) for x in label.split()[:2])
    print(f"| {names[a]} x {names[b]} ({label}) | {occt[label]:.3f} | {ours[label]:.2f} | {ours[label] / occt[label]:.0f} |")
print(f"| total, {len(order)} pairs | {sum(occt[k] for k in order):.1f} | {sum(ours.values()):.1f} | {sum(ours.values()) / sum(occt[k] for k in order):.0f} |")
same = sum(1 for k, r in our_rows.items() if r[1] == occt_rows[k][1])
ok = sum(1 for r in our_rows.values() if r[0] == "ok")
worst = max((abs(r[2] - occt_rows[k][2]) for k, r in our_rows.items() if r[2] is not None and occt_rows[k][2] is not None), default=0.0)
print(f"\nvalid {ok} of {len(our_rows)}; faces, edges and vertices as OCCT in {same}; largest volume difference at the digits printed {worst:.1e}")
