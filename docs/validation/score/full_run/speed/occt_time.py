# occt_time.py <cases.tsv> <todo.tsv: suite case op> <out.tsv> [repeats]: OCCT boolean time only (best of repeats)
import sys, time
sys.path.insert(0, '/home/user/wood_research/docs/validation/score')
import occt_ref as R
cases_f, todo_f, out_f = sys.argv[1:4]
rep = int(sys.argv[4]) if len(sys.argv) > 4 else 3
rows = {(w[0], w[1]): w for w in (l.rstrip('\n').split('\t') for l in open(cases_f) if not l.startswith('#'))}
todo = {}
for l in open(todo_f):
    if l.strip() and not l.startswith('#'):
        s, c, op = l.rstrip('\n').split('\t')[:3]
        todo.setdefault((s, c), []).append(op)
out = open(out_f, 'a')
def one(op, a, b):
    if op == 'xor':
        x = R.BRepAlgoAPI_Cut(a, b); y = R.BRepAlgoAPI_Cut(b, a)
        algo = R.BRepAlgoAPI_Fuse(x.Shape(), y.Shape())
    else:
        algo = {'intersection': R.BRepAlgoAPI_Common, 'union': R.BRepAlgoAPI_Fuse, 'a-b': R.BRepAlgoAPI_Cut}.get(op, R.BRepAlgoAPI_Cut)(*((b, a) if op == 'b-a' else (a, b)))
    return algo
for key, ops in todo.items():
    w = rows[key]
    try:
        a, b = R.build(w[6]), R.build(w[7])
    except Exception as e:
        for op in ops: out.write('\t'.join(list(key) + [op, 'LOADFAIL', 'nan', '0']) + '\n')
        continue
    for op in ops:
        best, st, nf = float('inf'), 'ok', 0
        for i in range(rep):
            t0 = time.perf_counter()
            try:
                algo = one(op, a, b)
                t = time.perf_counter() - t0
                if not algo.IsDone(): st = 'FAIL'
                else: nf = R.count(algo.Shape(), R.TopAbs_FACE)
            except Exception:
                t = time.perf_counter() - t0; st = 'FAIL'
            best = min(best, t)
        out.write('\t'.join(list(key) + [op, st, '%.6f' % best, str(nf)]) + '\n'); out.flush()
