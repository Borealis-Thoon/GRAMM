"""Run an unmodified GRAMM console process in a hidden Windows console."""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
import os
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

DOTNET = Path(os.environ.get('DOTNET_EXE','dotnet'))

class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def process_metrics(handle):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    get_times = kernel.GetProcessTimes
    get_times.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    get_times.restype = wintypes.BOOL
    creation, exit_time, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
    if not get_times(int(handle), ctypes.byref(creation), ctypes.byref(exit_time),
                     ctypes.byref(kernel_time), ctypes.byref(user_time)):
        raise ctypes.WinError(ctypes.get_last_error())
    ticks = lambda value: (value.dwHighDateTime << 32) | value.dwLowDateTime
    metrics = {"lifetime_seconds": (ticks(exit_time) - ticks(creation)) / 10_000_000,
               "process_cpu_seconds": (ticks(kernel_time) + ticks(user_time)) / 10_000_000}
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    get_memory = psapi.GetProcessMemoryInfo
    get_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
    get_memory.restype = wintypes.BOOL
    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(counters)
    if get_memory(int(handle), ctypes.byref(counters), counters.cb):
        metrics["peak_working_set_bytes"] = counters.PeakWorkingSetSize
    else:
        metrics["peak_working_set_bytes"] = None
        metrics["memory_query_error"] = ctypes.get_last_error()
    return metrics


def run_hidden_console(assembly: Path, case: Path, *, timeout: float = 90, first: int = 1, last: int = 1, env: dict[str, str] | None = None):
    assembly = assembly.resolve(strict=True)
    case = case.resolve(strict=True)
    startup = subprocess.STARTUPINFO()
    startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0  # SW_HIDE
    command = [str(DOTNET), str(assembly), str(first), str(last)] if assembly.suffix.lower() == ".dll" else [str(assembly), str(first), str(last)]
    # No redirected standard handles: Console.CursorTop needs the new console's output handle.
    started = time.perf_counter()
    process = subprocess.Popen(command, cwd=case, startupinfo=startup,
                               creationflags=subprocess.CREATE_NEW_CONSOLE, close_fds=True,
                               env=None if env is None else {**os.environ, **env})
    timed_out = False
    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        returncode = process.wait(timeout=10)
    metrics = process_metrics(process._handle)
    elapsed = time.perf_counter() - started
    outputs = []
    for path in sorted(case.iterdir()):
        if path.is_file() and path.suffix.lower() in {".wnd", ".scl", ".tsf", ".grd"}:
            outputs.append({"name": path.name, "bytes": path.stat().st_size,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    result = {"status": "pass" if returncode == 0 and not timed_out and outputs else "fail",
              "returncode": returncode, "timed_out": timed_out, "elapsed_seconds": elapsed,
              "pid": process.pid, "assembly": str(assembly),
              "assembly_sha256": hashlib.sha256(assembly.read_bytes()).hexdigest(),
              "case": str(case), "command": command, "hidden_console": True,
              "redirected_standard_handles": False, "outputs": outputs, **metrics}
    (case / "native_run_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("assembly", type=Path)
    parser.add_argument("case", type=Path)
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--make-case", action="store_true")
    parser.add_argument("--duration", type=float, default=60)
    parser.add_argument("--threads", type=int, default=1)
    args = parser.parse_args()
    if args.make_case:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "work"))
        from fixture import make_case
        make_case(args.case, nx=24, ny=20, nz=16, duration=args.duration, threads=args.threads)
    result = run_hidden_console(args.assembly, args.case, timeout=args.timeout)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "pass" else 1)
