# judge.py <run dir> [--prev <run dir>] [--data <dir>]: every boolean of <run dir>/results.tsv against OCCT (ref.tsv).
# equal: both valid, face/edge/vertex counts equal, volume within 1e-6 relative or within the operands' tolerance band;
# volume-only: volume within that bound, counts or validity differ; different: volume outside it; fail: no result.
# Counted only where OCCT succeeds with a valid shape and our operands match OCCT's (stepfix/operands.tsv when it
# exists, otherwise operand volumes measured here); the rest is listed apart. Writes judged.tsv (and changed.tsv).
import os, re, sys, collections
run = sys.argv[1]
opt = dict(zip(sys.argv[2::2], sys.argv[3::2]))
S = '/tmp/claude-0/-home-user-wood-research/8b288b7c-72c4-56e2-9565-a39939e050f9/scratchpad'
D = opt.get('--data', S + '/score')
STEPFIX = S + '/stepfix/operands.tsv'
CATS = ['equal', 'volume-only', 'different', 'fail']


def num(x):
    try:
        return float(x.replace('(mesh)', ''))
    except ValueError:
        return float('nan')


def tsv(f):
    return [l.rstrip('\n').split('\t') for l in open(f) if l.strip() and not l.startswith('#')] if os.path.exists(f) else []


def cls(msg):
    m = re.split(r'; | \{|\(|\[|=|, ', msg)[0]
    keep = []
    for seg in m.split(': '):
        if re.search(r'\d{2}|[{}]', seg) or len(': '.join(keep + [seg])) > 120:
            break
        keep.append(seg)
    return re.sub(r'-?\d[\d.e+-]*', 'N', ': '.join(keep) or m[:60]).strip(' :')


family = {(w[0], w[1]): w[2] for w in tsv(D + '/cases.tsv')}
ref = {tuple(w[:3]): w[3:] for w in tsv(D + '/ref.tsv')}
band = collections.defaultdict(float)
occt_op = {}
for w in tsv(D + '/occt_operands.tsv'):
    occt_op[(w[0], w[1], w[2])] = (num(w[3]), num(w[5]) if w[5] != 'nan' else 0.0)
    band[(w[0], w[1])] += occt_op[(w[0], w[1], w[2])][1]
stepfix = collections.defaultdict(list)
for w in tsv(STEPFIX):
    yes = [x.strip().lower() for x in w if x.strip().lower() in ('yes', 'no')]
    if yes:
        stepfix[w[0]].append((yes[-1] == 'yes', w[-1] if yes[-1] == 'no' else ''))


def operands_match(run_dir, results):
    ours = {(w[0], w[1]): w[2:] for w in tsv(run_dir + '/operands.tsv')}
    loadfail = {k[:2]: r[-1] for k, r in results.items() if r[0] == 'LOADFAIL'}
    out = {}
    for key in {k[:2] for k in results}:
        if key[1] in stepfix:
            bad = [why for ok, why in stepfix[key[1]] if not ok]
            out[key] = (not bad, 'stepfix: ' + (bad[0] if bad else ''))
        elif key in loadfail:
            out[key] = (False, 'ours fails to load: ' + cls(loadfail[key]))
        elif key not in ours:
            out[key] = (True, 'unmeasured')
        else:
            w, why = ours[key], ''
            for i, side in enumerate('AB'):
                vo, valid = num(w[2 * i]), w[2 * i + 1]
                vc, bc = occt_op.get(key + (side,), (float('nan'), 0.0))
                if valid != '1':
                    why = why or 'ours operand %s not a valid solid' % side
                elif not abs(vo - vc) <= max(1e-6 * abs(vc), bc):
                    why = why or 'operand %s volume ours %.9g OCCT %.9g' % (side, vo, vc)
            out[key] = (not why, why)
    return out


def judge(run_dir):
    results = {tuple(w[:3]): w[3:] for w in tsv(run_dir + '/results.tsv')}
    match = operands_match(run_dir, results)
    out = {}
    for k, r in results.items():
        o = ref.get(k)
        status, faces, valid, solid, vol, msg = r[0], r[3], r[6], r[7], num(r[8]), r[9] if len(r) > 9 else ''
        if r[0] == 'ok':
            bound = max(1e-6 * abs(num(o[5])), band[k[:2]]) if o else 0
            same_v = o is not None and abs(vol - num(o[5])) <= bound
            good = faces == '0' or (valid == '1' and solid == '1')
            cat = 'equal' if same_v and good and r[3:6] == o[1:4] else 'volume-only' if same_v else 'different'
        else:
            cat = 'fail'
        if not o or o[0] != 'ok' or (o[4] != '1' and o[1] != '0'):
            where = 'occt'
        elif not match[k[:2]][0]:
            where = 'operands'
        else:
            where = 'N'
        label = '' if cat != 'fail' else cls(msg) if status == 'FAIL' else 'timeout' if status == 'TIMEOUT' else status.lower() + ': ' + cls(msg)
        out[k] = (cat, where, label, match[k[:2]][1], r)
    return out


now = judge(run)
tally = {w: collections.Counter() for w in ('N', 'operands', 'occt')}
classes, fam = collections.Counter(), collections.defaultdict(collections.Counter)
for k, (cat, where, c, why, r) in now.items():
    tally[where][cat] += 1
    if where == 'N':
        fam[family.get(k[:2], '?')][cat] += 1
        if c:
            classes[c] += 1
t = tally['N']
n = sum(t.values())
print('equal %d / %d (%.1f %%), volume-only %d, different %d, fail %d' % (t['equal'], n, 100.0 * t['equal'] / max(n, 1), t['volume-only'], t['different'], t['fail']))
for w, label in (('operands', 'apart, operands differ from OCCT'), ('occt', 'apart, OCCT fails or invalid')):
    print('  %s: %d (%s)' % (label, sum(tally[w].values()), ', '.join('%s %d' % (c, tally[w][c]) for c in CATS)))
unmeasured = sum(1 for v in now.values() if v[3] == 'unmeasured')
if unmeasured:
    print('  operands unmeasured (counted): %d booleans' % unmeasured)
print('  per family: ' + '; '.join('%s %d/%d' % (f, c['equal'], sum(c.values())) for f, c in sorted(fam.items())))
print('failure classes:')
for c, k in classes.most_common(15):
    print('  %4d  %s' % (k, c.strip()))
if len(classes) > 15:
    print('  %4d  (%d more classes)' % (sum(classes.values()) - sum(k for _, k in classes.most_common(15)), len(classes) - 15))
with open(run + '/judged.tsv', 'w') as f:
    for k, (cat, where, c, why, r) in sorted(now.items()):
        f.write('\t'.join(list(k) + [family.get(k[:2], '?'), cat, where, c, why]) + '\n')
if '--prev' in opt:
    before = judge(opt['--prev'])
    common = [k for k in now if k in before]
    moves = collections.Counter((before[k][0], now[k][0]) for k in common if before[k][0] != now[k][0])
    tb = collections.Counter(before[k][0] for k in common if before[k][1] == 'N' and now[k][1] == 'N')
    tn = collections.Counter(now[k][0] for k in common if before[k][1] == 'N' and now[k][1] == 'N')
    print('change against %s on %d common booleans: %s' % (opt['--prev'], len(common), ', '.join('%s %+d' % (c, tn[c] - tb[c]) for c in CATS)))
    for (a, b), k in moves.most_common():
        print('  %4d  %s -> %s' % (k, a, b))
    changed = collections.defaultdict(list)
    for k in common:
        a, b = before[k], now[k]
        if a[0] != b[0] or (a[0] != 'fail' and (a[4][3:6] != b[4][3:6] or abs(num(a[4][8]) - num(b[4][8])) > 1e-6 * abs(num(b[4][8])))):
            changed[k[:2]].append('%s %s->%s' % (k[2], a[0], b[0]))
    with open(run + '/changed.tsv', 'w') as f:
        for k, v in sorted(changed.items()):
            f.write('\t'.join(list(k) + ['; '.join(sorted(v))]) + '\n')
    print('  %d cases changed (changed.tsv)' % len(changed))
