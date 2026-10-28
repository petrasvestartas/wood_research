import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


SCRIPT = Path(__file__).with_name("workspace_storage.py")
spec = importlib.util.spec_from_file_location("workspace_storage", SCRIPT)
storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage)


def alive(pid):
    if os.name == "nt":
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x100000, False, pid)
        if not handle:
            return False
        try:
            kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            return kernel.WaitForSingleObject(handle, 0) == 258
        finally:
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        state = Path(f"/proc/{pid}/stat")
        return not state.exists() or state.read_text().split()[2] != "Z"
    except ProcessLookupError:
        return False


class StorageTests(unittest.TestCase):
    def put(self, root, name, size):
        file = root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b"x" * size)

    def cli(self, root, *args):
        env = os.environ.copy()
        for key in ("CARGO_INCREMENTAL", "CARGO_PROFILE_DEV_DEBUG", "CARGO_PROFILE_TEST_DEBUG"):
            env.pop(key, None)
        return subprocess.run([sys.executable, str(SCRIPT), "run", "--root", str(root),
                               "--reserve-gib", "0", *args], env=env, cwd=root,
                              capture_output=True, text=True, timeout=15)

    def test_counts_git_inside_generated_and_hardlinks_conservatively(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, size in [("src/main.rs", 11), ("build/a", 13), ("build/.git/objects/b", 17),
                               (".git/build/c", 19), ("dist_web/d", 23), ("node_modules/e", 29)]:
                self.put(root, name, size)
            os.link(root / "src/main.rs", root / "src/copy.rs")
            report = storage.scan(root)
            self.assertEqual(report["totalBytes"], 123)
            self.assertEqual(report["generatedBytes"], 65)
            self.assertEqual(report["gitBytes"], 36)
            self.assertEqual(report["errors"], [])

    def test_external_directory_link_is_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            self.put(Path(outside), "large", 1000)
            try:
                os.symlink(outside, root / "target", target_is_directory=True)
            except OSError as error:
                self.skipTest(f"Directory symlink unavailable: {error}")
            report = storage.scan(root)
            self.assertEqual(report["totalBytes"], 0)
            self.assertEqual(len(report["skippedLinks"]), 1)

    def test_invalid_root_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "file"
            file.write_text("source")
            self.assertTrue(storage.scan(file)["errors"])
            self.assertTrue(storage.scan(Path(tmp) / "missing")["errors"])

    def test_budget_rejects_before_starting_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.put(root, "src/source", 1)
            result = self.cli(root, "--total-gib", "0", "--", sys.executable, "-c",
                              "from pathlib import Path; Path('started').touch()")
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertFalse((root / "started").exists())

    def test_exit_code_and_explicit_environment_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = "import os; assert os.environ['CARGO_INCREMENTAL']=='0'; assert os.environ['CARGO_PROFILE_DEV_DEBUG']=='0'; raise SystemExit(7)"
            result = self.cli(Path(tmp), "--", sys.executable, "-c", code)
            self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
            env = os.environ.copy()
            env["CARGO_INCREMENTAL"] = "1"
            result = subprocess.run([sys.executable, str(SCRIPT), "run", "--root", tmp,
                                     "--reserve-gib", "0", "--", sys.executable, "-c",
                                     "import os; assert os.environ['CARGO_INCREMENTAL']=='1'"],
                                    env=env, cwd=tmp, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_monitor_root_does_not_change_command_working_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workspace"
            project = root / "project"
            project.mkdir(parents=True)
            result = subprocess.run([sys.executable, str(SCRIPT), "run", "--root", str(root),
                                     "--reserve-gib", "0", "--", sys.executable, "-c",
                                     "from pathlib import Path; import sys; assert Path.cwd()==Path(sys.argv[1])",
                                     str(project)], cwd=project, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_overgrowth_terminates_owned_child_and_grandchild(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = ("import os,subprocess,sys,time; from pathlib import Path; "
                    "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
                    "Path('pids').write_text(str(os.getpid())+' '+str(child.pid)); "
                    "Path('build').mkdir(); Path('build/big').write_bytes(b'x'*4194304); time.sleep(30)")
            sentinel = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
            try:
                result = self.cli(root, "--total-gib", "0.0009765625", "--generated-gib", "0.0009765625",
                                  "--interval", "0.05", "--", sys.executable, "-c", code)
                self.assertIsNone(sentinel.poll(), "An unrelated process was terminated")
            finally:
                sentinel.terminate()
                sentinel.wait(timeout=5)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            pids = [int(x) for x in (root / "pids").read_text().split()]
            deadline = time.monotonic() + 3
            while any(alive(pid) for pid in pids) and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertFalse(any(alive(pid) for pid in pids), "Owned process tree survived cap termination")
            reports = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
            self.assertTrue(any(row["phase"] == "monitor" and row["overBudget"] for row in reports))
            self.assertEqual(reports[-1]["phase"], "final")


if __name__ == "__main__":
    unittest.main()
