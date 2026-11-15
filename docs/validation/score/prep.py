# prep.py <data dir>: the scoreboard's fixed inputs, written once into <data dir>:
#   cases.tsv  suite case family tol specA specB occtA occtB   (1850/5 corpus + 785/5 timber + 70/5 chair cases)
#   ref.tsv    suite case op status faces edges vertices valid volume   (OCCT results)
# Timber *_rot cases whose second operand lacks the rotation of their OCCT spec get it, and their OCCT results are
# recomputed with occt_ref.py (occt_regen.tsv).
import os, re, subprocess, sys
D = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
S = '/tmp/claude-0/-home-user-wood-research/8b288b7c-72c4-56e2-9565-a39939e050f9/scratchpad'
PY = '/tmp/claude-0/-home-user/8b288b7c-72c4-56e2-9565-a39939e050f9/scratchpad/ocp/venv/bin/python'
BENCH = '/home/user/session_data/brep_boolean_bench'
CX = '/tmp/claude-0/-home-user/8b288b7c-72c4-56e2-9565-a39939e050f9/scratchpad/stepfix/cx/run/cases.tsv'
CX_OCCT = '/home/user/wood_research/docs/validation/complex_bench/raw/raw_occt.txt'
FAMILY = {'nist_edm': 'NIST', 'occt_data': 'OCCT data', 'occt_booltest': 'OCCT data', 'hf_brepground': 'BRepGround',
          'hf_zero_to_cad': 'Zero-To-CAD', 'mcneel_rebuilt': 'McNeel', 'hf_brepmfr': 'BRepMFR', 'github_misc': 'github',
          'forum': 'forum', 'pair': 'pair', 'elem': 'timber element', 'joint': 'timber joint', 'chair': 'chair', 'twisted': 'chair'}


def family(case):
    return FAMILY[re.match(r'[a-z_]+?(?=__|#|\d|_pose|_rot|_self|$)', case).group(0)]


def absolute(spec):
    return re.sub(r'(?<=step=)(?!/)', BENCH + '/', spec)


rows, fixed = [], []
for l in open(BENCH + '/results/cases.tsv'):
    w = l.rstrip('\n').split('\t')
    a, b = absolute(w[1]), absolute(w[2])
    rows.append(['corpus', w[0], family(w[0]), '1e-7', a, b, a, b])
for l in open(CX):
    name, title, tol, a, b, ca, cb = l.rstrip('\n').split('\t')
    ca, cb = ca.replace('$S', S), cb.replace('$S', S)
    if name.endswith('_rot') and '|m=' not in b and '|m=' in cb:
        b += cb[cb.index('|m='):]
        fixed.append(name)
    rows.append(['cx', name, family(name), tol, a, b, ca, cb])
with open(D + '/cases.tsv', 'w') as f:
    f.write('#suite\tcase\tfamily\ttol\tspecA\tspecB\tocctA\tocctB\n')
    for r in rows:
        f.write('\t'.join(r) + '\n')

ref = {}
for l in open(BENCH + '/results/bool_occt.txt'):
    c, _, rest = l.rstrip('\n').split('\t', 2)
    p = rest.split()
    ok = p[2] == 'ok'
    ref[('corpus', c, p[1])] = [p[2]] + (p[4:8] + [p[10]] if ok else ['0', '0', '0', '0', 'nan'])
for l in open(CX_OCCT):
    p = l.split()
    if p[1] != 'OP' or p[2] in ('xor', 'xor3'):
        continue
    op, ok = p[2].replace('xorcells', 'xor'), p[3] == 'ok'
    ref[('cx', p[0], op)] = [p[3]] + ([p[7], p[8], p[9], p[15], p[21]] if ok else ['0', '0', '0', '0', 'nan'])
regen = D + '/occt_regen.tsv'
have = {l.split('\t')[1] for l in open(regen)} if os.path.exists(regen) else set()
with open(regen, 'a') as f:
    for r in rows:
        if r[1] in fixed and r[1] not in have:
            out = subprocess.run(['timeout', '900', PY, '-I', HERE + '/occt_ref.py', 'bool', r[6], r[7]], capture_output=True, text=True).stdout
            for line in out.splitlines():
                f.write('%s\t%s\t%s\n' % (r[0], r[1], '\t'.join(line.split()[:7])))
for l in open(regen):
    w = l.rstrip('\n').split('\t')
    ref[(w[0], w[1], w[2])] = w[3:9]
with open(D + '/ref.tsv', 'w') as f:
    for k, v in sorted(ref.items()):
        f.write('\t'.join(list(k) + v) + '\n')
print(len(rows), 'cases,', len(ref), 'reference booleans, rotation added to', ' '.join(fixed) or 'none')
