import argparse
import json
import math
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys


GIB = 1024 ** 3
GENERATED = {"build", "target", "dist", "node_modules", ".venv", "venv", "__pycache__"}


def scan(root):
    root = Path(root).absolute()
    result = dict(root=str(root), totalBytes=0, generatedBytes=0, gitBytes=0,
                  largestRootDirectories=[], skippedLinks=[], errors=[])
    directories = {}
    pending = [(root, False, False)]
    while pending:
        entry, generated, git = pending.pop()
        try:
            info = entry.stat(follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                result["skippedLinks"].append(str(entry))
                if entry == root:
                    result["errors"].append("Workspace root is a link or reparse point")
                continue
            if entry == root and not stat.S_ISDIR(info.st_mode):
                result["errors"].append("Workspace root is not a directory")
                continue
            git = git or entry.name.casefold() == ".git"
            generated = not git and (generated or entry.name.casefold() in GENERATED
                                    or entry.name.casefold().startswith("dist_"))
            if stat.S_ISDIR(info.st_mode):
                with os.scandir(entry) as children:
                    pending.extend((Path(child.path), generated, git) for child in children)
            elif stat.S_ISREG(info.st_mode):
                size = info.st_size
                result["totalBytes"] += size
                result["gitBytes"] += size if git else 0
                result["generatedBytes"] += size if generated else 0
                relative = entry.relative_to(root)
                if len(relative.parts) > 1:
                    name = relative.parts[0]
                    directories[name] = directories.get(name, 0) + size
        except OSError as error:
            result["errors"].append(f"{entry}: {error}")
    result["largestRootDirectories"] = [dict(name=name, bytes=size) for name, size in
                                       sorted(directories.items(), key=lambda row: row[1], reverse=True)[:10]]
    return result


def check(root, total_limit, generated_limit, reserve=0, phase="check"):
    report = scan(root)
    report.update(phase=phase, totalLimitBytes=total_limit,
                  generatedLimitBytes=generated_limit, reserveBytes=reserve)
    report["overBudget"] = [name for name, size, limit in (
        ("total", report["totalBytes"], total_limit),
        ("generated", report["generatedBytes"], generated_limit)) if size + reserve > limit]
    print(json.dumps(report), flush=True)
    return not report["errors"] and not report["overBudget"]


def stop(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def run(args):
    if not check(args.root, args.total_limit, args.generated_limit, args.reserve, "preflight"):
        return 2
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        raise ValueError("run requires -- command [arguments...]")
    env = os.environ.copy()
    for name, value in {"CARGO_INCREMENTAL": "0", "CARGO_PROFILE_DEV_DEBUG": "0",
                        "CARGO_PROFILE_TEST_DEBUG": "0"}.items():
        env.setdefault(name, value)
    try:
        process = subprocess.Popen(command, env=env,
                                   start_new_session=os.name != "nt")
    except OSError as error:
        print(f"Cannot start command: {error}", file=sys.stderr)
        return 127 if check(args.root, args.total_limit, args.generated_limit, phase="final") else 2
    code = 2
    try:
        while True:
            try:
                code = process.wait(timeout=args.interval)
                break
            except subprocess.TimeoutExpired:
                if not check(args.root, args.total_limit, args.generated_limit, phase="monitor"):
                    stop(process)
                    code = 2
                    break
    except KeyboardInterrupt:
        stop(process)
        code = 130
    finally:
        if process.poll() is None:
            stop(process)
        if not check(args.root, args.total_limit, args.generated_limit, phase="final"):
            code = 2
    return code if code >= 0 else 128 - code


def nonnegative(value):
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("Must be a finite nonnegative number")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check workspace storage or guard one owned command; never deletes files.")
    modes = parser.add_subparsers(dest="mode", required=True)
    for name in ("check", "run"):
        mode = modes.add_parser(name)
        mode.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
        mode.add_argument("--total-gib", type=nonnegative, default=20)
        mode.add_argument("--generated-gib", type=nonnegative, default=8)
        if name == "run":
            mode.add_argument("--reserve-gib", type=nonnegative, default=1)
            mode.add_argument("--interval", type=nonnegative, default=5)
            mode.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    args.total_limit = int(args.total_gib * GIB)
    args.generated_limit = int(args.generated_gib * GIB)
    if args.mode == "check":
        return 0 if check(args.root, args.total_limit, args.generated_limit) else 2
    if args.interval == 0:
        parser.error("--interval must be greater than zero")
    args.reserve = int(args.reserve_gib * GIB)
    try:
        return run(args)
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    sys.exit(main())
