# pick_subset.py <judged old run dir> <subset.tsv> [n=150] [budget_s=600]: the fixed stratified subset, chosen once.
# Every failure class of the old run (twice for classes of 30 or more, three times for 100 or more), every family x
# outcome, then the rest spread over families; the five operations rotate, the cheapest boolean of a stratum first,
# and the estimated time (bool + volume + 1 s per boolean) stays under the budget.
import sys, random, collections
run, out = sys.argv[1], sys.argv[2]
n, budget = int(sys.argv[3]) if len(sys.argv) > 3 else 150, float(sys.argv[4]) if len(sys.argv) > 4 else 600
rows = {}
for l in open(run + '/judged.tsv'):
    w = l.rstrip('\n').split('\t')
    if w[5] == 'N' and not w[1].startswith(('joint26_rot', 'joint28_rot', 'joint29_rot')):
        rows[tuple(w[:3])] = {'family': w[3], 'cat': w[4], 'cls': w[6]}
for l in open(run + '/results.tsv'):
    w = l.rstrip('\n').split('\t')
    if tuple(w[:3]) in rows:
        rows[tuple(w[:3])]['cost'] = 61.0 if w[3] == 'TIMEOUT' else 1.0 + float(w[4])
rng = random.Random(2026)
keys = sorted(rows)
rng.shuffle(keys)
chosen, spent, ops = [], 0.0, collections.Counter()


def take(pool, why, k=1):
    global spent
    pool = [x for x in pool if x not in chosen and (rows[x]['cost'] < 30 or rows[x]['cls'] == 'timeout')]
    for _ in range(k):
        if not pool:
            return
        x = min(pool, key=lambda x: (ops[x[2]], rows[x]['cost'] > 8, rng.random()))
        if spent + rows[x]['cost'] > budget and rows[x]['cls'] != 'timeout':
            return
        chosen.append(x)
        rows[x]['why'] = why
        spent += rows[x]['cost']
        ops[x[2]] += 1
        pool.remove(x)


classes = collections.Counter(r['cls'] for r in rows.values() if r['cls'])
for c, k in classes.most_common():
    take([x for x in keys if rows[x]['cls'] == c], 'class', 1 + (k >= 30) + (k >= 100))
families = sorted({r['family'] for r in rows.values()})
for f in families:
    for cat in ('equal', 'volume-only', 'different', 'fail'):
        if not any(rows[x]['family'] == f and rows[x]['cat'] == cat for x in chosen):
            take([x for x in keys if rows[x]['family'] == f and rows[x]['cat'] == cat], 'family')
size = collections.Counter(r['family'] for r in rows.values())
while len(chosen) < n:
    have = collections.Counter(rows[x]['family'] for x in chosen)
    f = min(families, key=lambda f: have[f] / size[f] ** 0.5)
    before = len(chosen)
    take([x for x in keys if rows[x]['family'] == f and rows[x]['cost'] < 8], 'fill')
    if len(chosen) == before:
        families.remove(f)
        if not families:
            break
with open(out, 'w') as o:
    o.write('#suite\tcase\top\tfamily\told outcome\told class\twhy\n')
    for x in sorted(chosen):
        r = rows[x]
        o.write('\t'.join(list(x) + [r['family'], r['cat'], r['cls'], r['why']]) + '\n')
print(len(chosen), 'booleans, estimated %.0f s;' % spent, dict(ops), dict(collections.Counter(rows[x]['family'] for x in chosen)))
