#!/usr/bin/env python3
"""Time core/dense's f64 matrix product at n=1000 against OpenBLAS's.

compiler/tests/dense/README.md describes the method this carries out.
refine builds compiler/tests/dense/timing.ldn at `--optimize speed`; the C
compiler builds compiler/tests/dense/timing.c against the OpenBLAS of the
pinned nixpkgs, which `nix build --inputs-from .` fetches unless --openblas
names one.  Both multiply the same two 1000 by 1000 matrices laid out by
columns and print the product's checksum, which must agree, and the
nanoseconds the product alone took on the monotonic clock.  The two run
interleaved, --runs times each, pinned to one core with OpenBLAS held to
one thread, and the report gives each one's median, its rate and the
multiple of OpenBLAS's time.

    dense_timing.py --refine PATH --core 15 --output DIR

It writes DIR/results.json and prints the report.  Run it inside the
pinned environment, whose assembler and linker refine uses, alone on its
host, since it measures time.  Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import lane_refine  # noqa: E402
DENSE = ROOT / "compiler/tests/dense"
SIZE = 1000
LINE = re.compile(r"^checksum (-?\d+) nanoseconds (\d+)$")


class Failure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Failure(message)


def openblas(given: str | None) -> tuple[Path, Path]:
    """The library and the headers' store paths: --openblas's, or the
    pinned nixpkgs's."""
    if given:
        path = Path(given)
        return path, path
    done = subprocess.run(
        ["nix", "build", "--inputs-from", str(ROOT), "--no-link",
         "--print-out-paths", "nixpkgs#openblas", "nixpkgs#openblas.dev"],
        capture_output=True, text=True, cwd=ROOT)
    require(done.returncode == 0, "nix build of OpenBLAS failed:\n" + done.stderr)
    paths = done.stdout.split()
    require(len(paths) == 2, "nix build printed " + done.stdout)
    library = next(p for p in paths if not p.endswith("-dev"))
    headers = next(p for p in paths if p.endswith("-dev"))
    return Path(library), Path(headers)


def build(refine: str, cc: str, library: Path, headers: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    landin = out / "timing-landin"
    blas = out / "timing-openblas"
    commands = {
        "landin": [refine, "compile", "--optimize=speed", "--root", str(ROOT),
                   str(DENSE / "timing.ldn"), "-o", str(landin)],
        "openblas": [cc, "-O2", f"-I{headers / 'include'}", str(DENSE / "timing.c"),
                     f"-L{library / 'lib'}", "-lopenblas",
                     f"-Wl,-rpath,{library / 'lib'}", "-o", str(blas)],
    }
    for name, command in commands.items():
        done = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
        require(done.returncode == 0, f"{name}: {' '.join(command)}\n"
                                      f"{done.stdout}{done.stderr}")
    return {"landin": landin, "openblas": blas, "commands": commands}


def parse(output: str) -> tuple[int, int]:
    found = LINE.match(output.strip())
    require(found is not None, "unexpected output: " + output)
    return int(found.group(1)), int(found.group(2))


def run_once(image: Path, core: int | None) -> tuple[int, int]:
    command = [*(["taskset", "-c", str(core)] if core is not None else []), str(image)]
    environment = {**os.environ, "OPENBLAS_NUM_THREADS": "1", "LC_ALL": "C"}
    done = subprocess.run(command, capture_output=True, text=True, env=environment)
    require(done.returncode == 0, f"{image} exited {done.returncode}: {done.stderr}")
    return parse(done.stdout)


def summary(nanoseconds: list[int]) -> dict:
    median = statistics.median(nanoseconds)
    return {"runs": nanoseconds, "median_seconds": median / 1e9,
            "gflops": 2 * SIZE ** 3 / median}


def report(results: dict) -> str:
    landin = results["landin"]
    blas = results["openblas"]
    return "\n".join([
        f"f64 product, n={SIZE}, one core, median of {len(landin['runs'])} runs",
        f"  core/dense  {landin['median_seconds']:.3f} s  {landin['gflops']:.2f} GFLOP/s",
        f"  OpenBLAS    {blas['median_seconds']:.3f} s  {blas['gflops']:.2f} GFLOP/s",
        f"  core/dense takes {results['multiple']:.1f} times OpenBLAS's time",
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    lane_refine.argument(parser, help="the refine to build timing.ldn with")
    parser.add_argument("--cc", default="cc", help="the C compiler for timing.c")
    parser.add_argument("--openblas", help="an OpenBLAS store path holding lib/ and include/")
    parser.add_argument("--core", type=int, help="the core each run is pinned to")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--output", required=True, help="the directory for images and results")
    options = parser.parse_args(argv)
    try:
        out = Path(options.output)
        library, headers = openblas(options.openblas)
        images = build(str(options.refine), options.cc, library, headers, out)
        times: dict[str, list[int]] = {"landin": [], "openblas": []}
        checksums = set()
        for _ in range(options.runs):
            for name in ("landin", "openblas"):
                checksum, nanoseconds = run_once(images[name], options.core)
                checksums.add(checksum)
                times[name].append(nanoseconds)
        require(len(checksums) == 1, f"the products differ: checksums {sorted(checksums)}")
        results = {name: summary(values) for name, values in times.items()}
        results["multiple"] = (results["landin"]["median_seconds"]
                               / results["openblas"]["median_seconds"])
        results["host"] = {"machine": platform.machine(), "processor": cpu_name(),
                           "core": options.core, "openblas": str(library)}
        results["commands"] = images["commands"]
        (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
        print(report(results))
    except Failure as problem:
        print(f"dense_timing.py: {problem}", file=sys.stderr)
        return 1
    return 0


def cpu_name() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor()


if __name__ == "__main__":
    sys.exit(main())
