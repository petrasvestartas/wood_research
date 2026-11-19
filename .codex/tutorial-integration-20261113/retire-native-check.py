import hashlib
import json
import shutil
from pathlib import Path

root = Path('C:/pc/3_code/code_rust/wood_research')
proofs = root / '.codex/tutorial-integration-20261113'
candidate = proofs / 'native-check-cache-candidates.json'
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert digest(candidate) == '81b9a123c9f3629fe76c174c60be4852aa155d2646efcb69b7f1dd8cee5f993c'
data = json.loads(candidate.read_text())
source = Path(data['root']).resolve()
assert source == (root / 'session/session_viewer/target/course-cargo').resolve()
destination = Path('C:/pc/tmp/tutorial-accepted-artifacts-20261113/native-check').resolve()
protection = Path(data['protection'])
assert digest(protection) == data['protectionSha256']
protected = json.loads(protection.read_text(encoding='utf-8-sig'))
protected = set(protected['baselinePaths']) | set(protected['currentViewerCompilerPathRequirements'])
plan = []
for entry in data['files']:
    assert entry['path'].startswith('x86_64-pc-windows-msvc/debug/')
    assert entry['path'] not in protected
    src = (source / entry['path']).resolve()
    dst = (destination / entry['path']).resolve()
    assert src.is_relative_to(source) and dst.is_relative_to(destination)
    assert src.is_file() and not dst.exists()
    assert src.stat().st_size == entry['bytes'] and digest(src) == entry['sha256']
    plan.append(dict(entry, source=str(src), destination=str(dst)))
(proofs / 'native-check-retirement-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
for entry in plan:
    src, dst = Path(entry['source']), Path(entry['destination'])
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(src, dst)
    assert digest(dst) == entry['sha256'] and not src.exists()
result = dict(files=len(plan), bytes=sum(e['bytes'] for e in plan), allHashesVerified=True,
              candidateSha256=digest(candidate), destination=str(destination))
(proofs / 'native-check-retirement-result.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
