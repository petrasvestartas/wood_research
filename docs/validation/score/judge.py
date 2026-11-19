# judge.py <run dir> [--prev <run dir>] [--data <dir>]: every boolean of <run dir>/results.tsv against OCCT (ref.tsv).
# equal: both valid, face/edge/vertex counts equal, volume within 1e-6 relative, within the operands' tolerance band or within
# |dA| + |dB|, how far our operands' measured volumes are from OCCT's (those equals are counted in the summary line);
# volume-only: volume within that bound, counts or validity differ; different: volume outside it; fail: no result.
# Counted only where OCCT succeeds with a valid shape and our operands match OCCT's (stepfix/operands.tsv when it
# exists, otherwise operand volumes measured here); the rest is listed apart. Where stepfix finds OCCT's GProp the
# outlier on an operand, a volume within the accuracy of OCCT's mesh volume of the result counts as within the bound.
# A case whose OCCT union is empty or breaks union = ∩ + A−B + B−A by over 1e-4 (unless GProp is the outlier there) is
# listed apart with OCCT failures.
# Failure classes are the messages with numbers and names stripped; results that are not equal are ranked by what is
# wrong (validity, closedness, volume, counts) and, for bop, the first note of its report.
# Second oracle, when <data>/smlib_ref.tsv exists (smlib_ref.py): SMLib's result on the operands OCCT built. It counts
# where SMLib's volumes of the converted operands equal OCCT's (1e-6 or the band) and its own results add up (∩ + A−B = A, ∩ + B−A = B,
# ∪ = ∩ + A−B + B−A within 1e-5); the oracles agree when their volumes are within 1e-5 relative or the band (SMLib
# works on the NURBS form at its tolerance of 1e-5). Booleans where they disagree are listed with the side ours is on
# (oracles.tsv); the one number stays against OCCT.
# Writes judged.tsv (and changed.tsv, oracles.tsv).
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
stepfix, outlier = collections.defaultdict(list), set()
for w in tsv(STEPFIX):
    if w[0] != 'bench':
        key = ('cx' if w[0] == 'timber' else w[0], w[1])
        stepfix[key].append((w[7] == 'yes', w[8]))
        if 'GProp is the outlier' in w[8]:
            outlier.add(key)
occt_bad = set()
for key in {k[:2] for k in ref}:
    v = {op: num(ref[key + (op,)][5]) for op in ('intersection', 'union', 'a-b', 'b-a') if ref.get(key + (op,), ['x'])[0] == 'ok'}
    if 'union' in v and (v['union'] == 0 or (key not in outlier and len(v) == 4 and abs(v['union'] - v['intersection'] - v['a-b'] - v['b-a']) > 1e-4 * abs(v['union']))):
        occt_bad.add(key)


sm = {tuple(w[:3]): w[3:] for w in tsv(D + '/smlib_ref.tsv')}
sm_case = {}
for key in {k[:2] for k in sm}:
    r = {op: sm[key + (op,)] for op in ('intersection', 'union', 'a-b', 'b-a', 'xor') if key + (op,) in sm}
    first = next(iter(r.values()))
    va, vb = num(first[6]), num(first[7])
    why = ''
    for side, v in (('A', va), ('B', vb)):
        vc, bc = occt_op.get(key + (side,), (float('nan'), 0.0))
        if first[0] == 'LOADFAIL' or not abs(v - vc) <= max(1e-6 * abs(vc), bc):
            why = why or "SMLib's operand %s differs" % side
    v = {op: num(x[5]) for op, x in r.items() if x[0] == 'ok'}
    sums = [('intersection', 'a-b', None, va), ('intersection', 'b-a', None, vb), ('intersection', 'a-b', 'b-a', v.get('union')), ('a-b', 'b-a', None, v.get('xor'))]
    if not why and any(a in v and b in v and (c is None or c in v) and t is not None and abs(v[a] + v[b] + (v[c] if c else 0) - t) > 1e-5 * abs(t) for a, b, c, t in sums):
        why = 'results do not add up'
    sm_case[key] = why


def oracle(k, o, vol, counts, good):
    # SMLib against OCCT, and ours against SMLib, for one boolean
    r = sm.get(k)
    if r is None:
        return '-', '-'
    if sm_case[k[:2]]:
        return sm_case[k[:2]], '-'
    if r[0] != 'ok':
        return 'fails', '-'
    bound = max(1e-5 * abs(num(r[5])), band[k[:2]])
    ours = '-' if vol is None else ('equal' if good and counts == r[1:4] and r[4] == '1' else 'volume-only') if abs(vol - num(r[5])) <= bound else 'different'
    if not o or o[0] != 'ok':
        return 'OCCT fails', ours
    if abs(num(o[5]) - num(r[5])) > bound:
        return 'disagrees', ours
    return 'agrees' if r[1:4] == o[1:4] and r[4] == '1' and (o[4] == '1' or o[1] == '0') else 'agrees in volume', ours


def operands_match(run_dir, results):
    ours = {(w[0], w[1]): w[2:] for w in tsv(run_dir + '/operands.tsv')}
    loadfail = {k[:2]: r[-1] for k, r in results.items() if r[0] == 'LOADFAIL'}
    out = {}
    for key in {k[:2] for k in results}:
        if key in loadfail:
            out[key] = (False, 'ours fails to load: ' + cls(loadfail[key]))
        elif key in stepfix:
            bad = [why for ok, why in stepfix[key] if not ok]
            out[key] = (not bad, 'stepfix: ' + (bad[0] if bad else 'equal'))
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


widened = set()


def judge(run_dir):
    results = {tuple(w[:3]): w[3:] for w in tsv(run_dir + '/results.tsv')}
    match = operands_match(run_dir, results)
    # how far our operands' volumes are from OCCT's: a result may differ from OCCT's by that much
    gap = collections.defaultdict(float)
    for w in tsv(run_dir + '/operands.tsv'):
        for i, side in enumerate('AB'):
            d = abs(num(w[2 + 2 * i]) - occt_op.get((w[0], w[1], side), (float('nan'), 0.0))[0])
            gap[(w[0], w[1])] += d if d == d else 0.0
    out = {}
    for k, r in results.items():
        o = ref.get(k)
        status, faces, valid, solid, vol, msg = r[0], r[3], r[6], r[7], num(r[8]), r[9] if len(r) > 9 else ''
        if r[0] == 'ok':
            bound = max(1e-6 * abs(num(o[5])), band[k[:2]]) if o else 0
            same_v = o is not None and (abs(vol - num(o[5])) <= bound or (k[:2] in outlier and abs(vol - num(o[6])) <= num(o[7])))
            if o is not None and not same_v and abs(vol - num(o[5])) <= gap[k[:2]]:
                same_v = True
                widened.add(k)
            good = faces == '0' or (valid == '1' and solid == '1')
            cat = 'equal' if same_v and good and r[3:6] == o[1:4] else 'volume-only' if same_v else 'different'
        else:
            cat = 'fail'
        if not o or o[0] != 'ok' or (o[4] != '1' and o[1] != '0') or k[:2] in occt_bad:
            where = 'occt'
        elif not match[k[:2]][0]:
            where = 'operands'
        else:
            where = 'N'
        if cat == 'fail':
            label = cls(msg) if status == 'FAIL' else 'timeout' if status == 'TIMEOUT' else status.lower() + ': ' + cls(msg)
        elif cat == 'equal':
            label = ''
        else:
            label = ('result not valid' if valid != '1' else 'result not a closed solid' if solid != '1' else 'volume differs' if cat == 'different'
                     else 'counts differ') + (', noted: ' + cls(msg.split('; ')[0]) if msg else '')
        out[k] = (cat, where, label, match[k[:2]][1], r) + oracle(k, o, vol if status == 'ok' else None, r[3:6], status == 'ok' and good)
    return out


now = judge(run)
tally = {w: collections.Counter() for w in ('N', 'operands', 'occt')}
classes, reasons, fam = collections.Counter(), collections.Counter(), collections.defaultdict(collections.Counter)
for k, (cat, where, c, why, r, _, _) in now.items():
    tally[where][cat] += 1
    if where == 'N':
        fam[family.get(k[:2], '?')][cat] += 1
        if c:
            (classes if cat == 'fail' else reasons)[c] += 1
t = tally['N']
n = sum(t.values())
wide = sum(1 for k in widened if k in now and now[k][0] == 'equal' and now[k][1] == 'N')
print('equal %d / %d (%.1f %%)%s, volume-only %d, different %d, fail %d' % (t['equal'], n, 100.0 * t['equal'] / max(n, 1), ', of which %d within operand difference' % wide if wide else '', t['volume-only'], t['different'], t['fail']))
for w, label in (('operands', 'apart, operands differ from OCCT'), ('occt', 'apart, OCCT fails, invalid or inconsistent')):
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
print('volume-only and different, by what is wrong:')
for c, k in reasons.most_common(10):
    print('  %4d  %s' % (k, c))
with open(run + '/judged.tsv', 'w') as f:
    for k, (cat, where, c, why, r, smv, smo) in sorted(now.items()):
        f.write('\t'.join(list(k) + [family.get(k[:2], '?'), cat, where, c, why, smv, smo]) + '\n')
if sm:
    with_sm = {k: v for k, v in now.items() if v[5] != '-'}
    t = collections.Counter(v[5] for v in with_sm.values())
    print('SMLib as second oracle on %d of these booleans: %s' % (len(with_sm), ', '.join('%s %d' % x for x in t.most_common())))
    split = [k for k, v in sorted(with_sm.items()) if v[5] in ('disagrees', 'OCCT fails')]
    side = collections.Counter(('OCCT' if now[k][0] in ('equal', 'volume-only') and now[k][1] != 'occt' else 'SMLib' if now[k][6] in ('equal', 'volume-only') else
                                'neither' if now[k][0] != 'fail' else 'no result') for k in split)
    print('  where OCCT and SMLib disagree or OCCT has no result (%d): ours with %s' % (len(split), ', '.join('%s %d' % x for x in side.most_common()) or '-'))
    both = [v for v in with_sm.values() if v[5] in ('agrees', 'agrees in volume') and v[1] == 'N']
    print('  where both oracles agree (%d counted): %s' % (len(both), ', '.join('%s %d' % (c, sum(1 for v in both if v[0] == c)) for c in CATS)))
    with open(run + '/oracles.tsv', 'w') as f:
        f.write('#suite\tcase\top\tours\tours against SMLib\tOCCT faces edges vertices valid volume\tSMLib faces edges vertices valid volume\tours faces edges vertices volume\n')
        for k in split:
            o, r = ref.get(k, ['-'] * 6), now[k][4]
            f.write('\t'.join(list(k) + [now[k][0], now[k][6], ' '.join(o[1:6]), ' '.join(sm[k][1:6]), ' '.join(r[3:6] + [r[8]])]) + '\n')
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
