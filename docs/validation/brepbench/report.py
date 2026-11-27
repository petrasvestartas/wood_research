"""report.py <repo copy> <board.json> <out dir>: our brep-bench grades beside OCCT's and SMLib's from the board.

Reads <repo copy>/results/session_cpp.json (harness/run.py's whole-suite run), the cases' headers for their expected
values and tags (through the copy's harness/suite.py, run with -I from outside it), and board.json's codes per kernel.
Writes results.tsv (one row per case) and results.md (counts and the wrong/crashed list)."""
import collections
import json
import os
import sys

repo, board_path, out = sys.argv[1:4]
sys.path.insert(0, os.path.join(repo, "harness"))
from suite import cases  # noqa: E402

ours = {c["case"]: c for c in json.load(open(os.path.join(repo, "results", "session_cpp.json")))["cases"]}
board = json.load(open(board_path))
names = {v: k for k, v in board["outcomes"].items()}
ids = [c[0] for c in board["cases"]]


def board_kernel(name):
    r = board["results"][name]
    return {cid: (names.get(code, "missing"), r["own"][i] if r.get("own") else None, r["seconds"][i])
            for i, (cid, code) in enumerate(zip(ids, r["codes"]))}


occt, smlib = board_kernel("occt"), board_kernel("smlib")
spec = {c["id"]: c for c in cases()}
ORDER = ["pass", "built", "refused", "wrong", "crashed", "timeout", "missing"]


def tally(sel, src):
    t = collections.Counter(src(cid) for cid in sel)
    return " / ".join(f"{t[o]}" for o in ORDER)


rows = []
for cid in sorted(spec):
    o = ours.get(cid, {})
    e = spec[cid]["expect"] or {}
    rows.append({
        "case": cid,
        "boolean": "boolean" in spec[cid]["tags"],
        "ours": o.get("outcome", "missing"),
        "occt": occt.get(cid, ("missing",))[0],
        "smlib": smlib.get(cid, ("missing",))[0],
        "our_s": o.get("own_seconds") if o.get("own_seconds") is not None else o.get("seconds"),
        "occt_s": occt.get(cid, (None, None))[1],
        "vol": o.get("volume"), "vol_exp": e.get("volume", {}).get("value"),
        "area": o.get("area"), "area_exp": e.get("area", {}).get("value"),
        "why": (o.get("why") or "").replace("\t", " ").replace("\n", " "),
    })

os.makedirs(out, exist_ok=True)
with open(os.path.join(out, "results.tsv"), "w") as f:
    cols = ["case", "boolean", "ours", "occt", "smlib", "our_s", "occt_s", "vol", "vol_exp", "area", "area_exp", "why"]
    f.write("\t".join(cols) + "\n")
    for r in rows:
        f.write("\t".join("" if r[c] is None else (f"{r[c]:.9g}" if isinstance(r[c], float) else str(r[c])) for c in cols) + "\n")

attempted = [r["case"] for r in rows if r["ours"] != "refused" or "bop::apply" in r["why"]]
sets = {
    "all cases": [r["case"] for r in rows],
    "boolean-tagged": [r["case"] for r in rows if r["boolean"]],
    "boolean/ category": [r["case"] for r in rows if r["case"].startswith("boolean/")],
    "cases we implemented": attempted,
}
by = {r["case"]: r for r in rows}
md = ["# session_cpp on brep-bench", "",
      "Counts are " + " / ".join(ORDER) + ". OCCT and SMLib from the board (board.json); ours from harness/run.py.", "",
      "| cases | n | session_cpp | OCCT | SMLib |", "|---|---|---|---|---|"]
for label, sel in sets.items():
    md.append(f"| {label} | {len(sel)} | {tally(sel, lambda c: by[c]['ours'])} | {tally(sel, lambda c: by[c]['occt'])} "
              f"| {tally(sel, lambda c: by[c]['smlib'])} |")
md += ["", "## Wrong and crashed", "",
       "| case | ours | OCCT | SMLib | volume (ours / expected) | area (ours / expected) | why | our s | OCCT s |",
       "|---|---|---|---|---|---|---|---|---|"]
fmt = lambda x: "" if x is None else f"{x:.6g}"  # noqa: E731
for r in rows:
    if r["ours"] in ("wrong", "crashed", "timeout"):
        md.append(f"| {r['case']} | {r['ours']} | {r['occt']} | {r['smlib']} | {fmt(r['vol'])} / {fmt(r['vol_exp'])} | "
                  f"{fmt(r['area'])} / {fmt(r['area_exp'])} | {r['why'][:90]} | {fmt(r['our_s'])} | {fmt(r['occt_s'])} |")
md += ["", "## Implemented cases: time (kernel's own seconds)", "", "| case | ours | OCCT | our s | OCCT s |", "|---|---|---|---|---|"]
for c in attempted:
    r = by[c]
    md.append(f"| {c} | {r['ours']} | {r['occt']} | {fmt(r['our_s'])} | {fmt(r['occt_s'])} |")
with open(os.path.join(out, "results.md"), "w") as f:
    f.write("\n".join(md) + "\n")
print("\n".join(md[:12]))
