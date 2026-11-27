# ours_time.py <drv> <cases.tsv> <todo.tsv> <out.tsv>: our boolean time (BOOL line bool_s), one process each, sequential
import sys, subprocess, os
drv, cases_f, todo_f, out_f = sys.argv[1:5]
rows = {(w[0], w[1]): w for w in (l.rstrip('\n').split('\t') for l in open(cases_f) if not l.startswith('#'))}
done = {tuple(l.split('\t')[:3]) for l in open(out_f)} if os.path.exists(out_f) else set()
out = open(out_f, 'a')
for l in open(todo_f):
    s, c, op = l.rstrip('\n').split('\t')[:3]
    if (s, c, op) in done: continue
    w = rows[(s, c)]
    try:
        so = subprocess.run([drv, 'bool', w[4], w[5], op, w[3]], capture_output=True, text=True, timeout=120).stdout
        b = next((x.split() for x in so.splitlines() if x.startswith('BOOL ')), None)
        rec = [b[2], b[3], b[4]] if b else ['CRASH', 'nan', '0']
    except subprocess.TimeoutExpired:
        rec = ['TIMEOUT', '120', '0']
    load = open('/proc/loadavg').read().split()[0]
    out.write('\t'.join([s, c, op] + rec + [load]) + '\n'); out.flush()
