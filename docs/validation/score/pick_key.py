# pick_key.py <judged old run dir> <key.tsv> [n=30]: the first tier, about 30 distinct booleans chosen once: the named
# ones below (one situation each), then one per failure class of the old run by size, then one per family not yet
# there; one boolean per case, the five operations rotating, the cheapest of a class first. Booleans where OCCT is set
# apart are not taken.
import sys, collections
run, out = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 30
NAMED = [('cx', 'joint00', 'intersection', 'loose-tolerance timber joint'), ('cx', 'joint00_rot', 'a-b', 'timber joint, rotated'),
         ('cx', 'elem21_cyl', 'a-b', 'timber element, cylinder cutter'), ('cx', 'elem21_self', 'union', 'coincident faces: element with its copy'),
         ('cx', 'chair_pose3', 'union', 'chair pose'), ('cx', 'chair_self', 'xor', 'chair with itself'),
         ('corpus', 'github_misc__nema-17-bracket#box', 'intersection', 'NEMA bracket and box'),
         ('corpus', 'github_misc__nema-17-bracket#rot5z', 'union', 'rotated copy, coincident and near-coincident faces'),
         ('corpus', 'nist_edm__bellow#box', 'a-b', 'bellows'), ('corpus', 'nist_edm__bellow#cyl', 'intersection', 'bellows, cylinder cutter'),
         ('corpus', 'github_misc__as1-ac-214#box', 'b-a', 'assembly part, planar'), ('corpus', 'forum213347#lining_frame', 'a-b', 'clean planar part'),
         ('corpus', 'forum163125#box_cyl_side', 'union', 'box and cylinder at its side'),
         ('corpus', 'pair#sample_round_vs_1', 'intersection', 'round part against round part'),
         ('corpus', 'hf_brepground__00042148_fillet_11#sph', 'a-b', 'sphere cutter on a fillet part'),
         ('corpus', 'mcneel_rebuilt__threaded_rod_cutter#cyl', 'a-b', 'threaded rod'), ('corpus', 'forum123416#mesh_cone', 'xor', 'cone and faceted part')]
rows = {}
for l in open(run + '/judged.tsv'):
    w = l.rstrip('\n').split('\t')
    rows[tuple(w[:3])] = {'family': w[3], 'cat': w[4], 'where': w[5], 'cls': w[6]}
for l in open(run + '/results.tsv'):
    w = l.rstrip('\n').split('\t')
    if tuple(w[:3]) in rows:
        rows[tuple(w[:3])]['cost'] = float(w[4])
chosen, ops = [], collections.Counter()


def take(k, why):
    if k in rows and rows[k]['where'] == 'N' and all(k[:2] != c[:2] for c in chosen) and len(chosen) < n:
        chosen.append(k)
        rows[k]['why'] = why
        ops[k[2]] += 1
        return True


for s, c, op, why in NAMED:
    take((s, c, op), why) or print('not taken:', c, op, rows.get((s, c, op), 'not in the run'))
ok = [k for k in sorted(rows) if rows[k]['where'] == 'N' and rows[k].get('cost', 99) < 10]
for cls, _ in collections.Counter(rows[k]['cls'] for k in ok if rows[k]['cat'] == 'fail').most_common():
    if not any(rows[k]['cls'] == cls for k in chosen):
        pool = sorted((k for k in ok if rows[k]['cls'] == cls), key=lambda k: (ops[k[2]], rows[k]['cost']))
        any(take(k, 'class') for k in pool)
for fam in sorted({r['family'] for r in rows.values()}):
    if not any(rows[k]['family'] == fam for k in chosen):
        any(take(k, 'family') for k in sorted((k for k in ok if rows[k]['family'] == fam), key=lambda k: (ops[k[2]], rows[k]['cost'])))
with open(out, 'w') as o:
    o.write('#suite\tcase\top\tfamily\told outcome\told class\twhy\n')
    for k in sorted(chosen):
        r = rows[k]
        o.write('\t'.join(list(k) + [r['family'], r['cat'], r['cls'], r['why']]) + '\n')
print(len(chosen), 'booleans;', dict(ops), dict(collections.Counter(rows[k]['family'] for k in chosen)), 'old run %.0f s' % sum(rows[k].get('cost', 0) for k in chosen))
