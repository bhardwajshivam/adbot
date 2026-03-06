import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run project tests via pytest.")
    parser.add_argument("--target", default="apps/api/tests", help="Pytest target path (default: apps/api/tests).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Use verbose pytest output.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, "-m", "pytest", args.target]
    cmd.append("-vv" if args.verbose else "-q")

    print(f"Running from: {repo_root}")
    print("Command:", " ".join(cmd))

    result = subprocess.run(cmd, cwd=repo_root)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
