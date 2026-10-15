"""Build API4 receiver and execute actual component gates before packaging. No devices."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parents[1]
REPO = BASE.parents[1]
spec = importlib.util.spec_from_file_location("legacy_build", BASE / "tools/build_local.py")
legacy = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(BASE / "tools"))
spec.loader.exec_module(legacy)


def run(name, command, env, logs, timeout=None, expected=0):
    result = subprocess.run(command, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=timeout)
    (logs / (name + ".txt")).write_bytes(result.stdout)
    if result.returncode != expected:
        sys.stderr.buffer.write(result.stdout)
        raise RuntimeError(f"{name}: exit {result.returncode}, expected {expected}")
    print(name + ": passed", flush=True)
    return result.stdout.decode("utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--package", action="store_true")
    parser.add_argument("--reproduce-api3", action="store_true")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    if not (args.test or args.package or args.reproduce_api3):
        parser.error("choose --test, --package or --reproduce-api3")
    cargo, env, native = legacy.configuration()
    cache = REPO / ".cache/s5-transfer-research/runtime-probe"
    logs = cache / "api4-build-logs"
    logs.mkdir(parents=True, exist_ok=True)
    if args.test:
        cmd = [cargo, "test", "--locked", "--manifest-path", str(BASE / "Cargo.toml")]
        if native:
            cmd += ["--target", native]
        run("shared-protocol-and-ui-tests", cmd, env, logs)
    if native:
        # Only the existing task-local compiler is used. No installations or global changes.
        compiler = cache / "compiler/zig-x86_64-windows-0.14.1"
        if not compiler.is_dir():
            raise RuntimeError("Runtime tests need a C compiler; see runtime-tests/README.md")
        env["PATH"] = str(compiler) + os.pathsep + env["PATH"]
        env["ZIG_LOCAL_CACHE_DIR"] = str(cache / "zig-local-cache")
        env["ZIG_GLOBAL_CACHE_DIR"] = str(cache / "zig-global-cache")
        proxy = cache / "dlltool-proxy.exe"
        run("task-local-compiler-proxy", [str(compiler / "zig.exe"), "cc", "-O2", "-municode",
            str(ROOT / "runtime-tests/windows/tool-proxy.c"), "-o", str(proxy)], env, logs)
        for name in ["cc", "ar"]:
            shutil.copyfile(proxy, cache / (name + "-proxy.exe"))
        env["CC"] = str(cache / "cc-proxy.exe")
        env["AR"] = str(cache / "ar-proxy.exe")
        env["CARGO_TARGET_X86_64_PC_WINDOWS_GNU_RUSTFLAGS"] += " -C dlltool=" + str(proxy)
    env["CARGO_PROFILE_DEV_DEBUG"] = "0"
    component_env = dict(env, CARGO_TARGET_DIR=str(cache / "candidate-target"))
    run("api4-component-build", [cargo, "build", "--locked", "--manifest-path", str(ROOT / "Cargo.toml"),
        "--target", "wasm32-wasip2", "--lib", "--features", "astrobox", "--release"], component_env, logs)
    wasm = cache / "candidate-target/wasm32-wasip2/release/imus5_receiver_api4.wasm"
    host_env = dict(env, CARGO_TARGET_DIR=str(cache / "target"))
    command = [cargo, "build", "--locked", "--manifest-path", str(ROOT / "runtime-tests/Cargo.toml")]
    if native:
        command += ["--target", native]
    run("api4-runtime-build", command, host_env, logs)
    executable = cache / "target" / (native or "") / "debug" / ("imus5-runtime-check" + (".exe" if os.name == "nt" else ""))
    scenarios = {}
    for name, extra in [("success", []), ("registration-denied", ["deny"]), ("busy", ["busy"])]:
        scenarios[name] = run("actual-component-" + name, [str(executable), str(wasm), *extra], host_env, logs, timeout=100)
        if "PASS actual component:" not in scenarios[name]:
            raise RuntimeError("Runtime did not reach its acceptance assertions")
    if args.reproduce_api3:
        reproduce_api3(cargo, env, native, cache, logs)
    if args.package:
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        old = json.loads((BASE / "manifest.json").read_text(encoding="utf-8"))
        assert (manifest["api_level"], manifest["wasi_version"]) == (4, 3)
        assert manifest["permissions"] == old["permissions"]
        assert manifest["name"] == old["name"]
        output = Path(args.output_dir).resolve() if args.output_dir else ROOT / ("dist/receiver-" + manifest["version"])
        if not output.is_relative_to((ROOT / "dist").resolve()):
            raise ValueError("Output must stay inside this variant dist directory")
        output.mkdir(parents=True, exist_ok=False)
        assets = {"manifest.json": (ROOT / "manifest.json").read_bytes(), manifest["entry"]: wasm.read_bytes(),
            "icon.png": (REPO / "collection/watch-s5-probe/variants/research-ui/src/common/icon.png").read_bytes(),
            "THIRD_PARTY_LICENSES.txt": (ROOT / "SDK_LICENSE.txt").read_bytes()}
        assert assets[manifest["entry"]][:8] == b"\x00asm\x0d\x00\x01\x00"
        package = output / ("IMU-S5-Receiver-" + manifest["version"] + ".abp")
        with zipfile.ZipFile(package, "x", zipfile.ZIP_DEFLATED) as archive:
            for name, data in assets.items():
                archive.writestr(name, data)
        report = {"sha256": hashlib.sha256(package.read_bytes()).hexdigest(), "bytes": package.stat().st_size,
            "files": {n: hashlib.sha256(b).hexdigest() for n, b in assets.items()}, "manifest": manifest,
            "runtime": {"engine": "48.0.2", "actual_component_synthetic_host_scenarios": list(scenarios),
                "render_check_cycles_per_scenario": 64, "android_astrobox": "not tested", "bluetooth": "not tested",
                "real_permissions_and_system_save": "not tested"}, "no_device_tools": True}
        (output / "build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(package)


def reproduce_api3(cargo, env, native, cache, logs):
    fixture = ROOT / "runtime-tests/api3"
    guest_env = dict(env, CARGO_TARGET_DIR=str(cache / "guest-target"))
    for label, features in [("sync", []), ("async", ["--features", "async-export"])]:
        run("api3-" + label + "-build", [cargo, "build", "--locked", "--manifest-path", str(fixture / "guest/Cargo.toml"),
            "--target", "wasm32-wasip2", "--release", *features], guest_env, logs)
        shutil.copyfile(cache / "guest-target/wasm32-wasip2/release/s5_api3_guest_probe.wasm", cache / (label + "-regression.wasm"))
    host_env = dict(env, CARGO_TARGET_DIR=str(cache / "target"))
    cmd = [cargo, "build", "--locked", "--manifest-path", str(fixture / "host/Cargo.toml")]
    if native:
        cmd += ["--target", native]
    run("api3-host-build", cmd, host_env, logs)
    binary = cache / "target" / (native or "") / "debug" / ("s5-api3-host-probe" + (".exe" if os.name == "nt" else ""))
    sync = run("api3-sync-no-worker", [str(binary), str(cache / "sync-regression.wasm")], host_env, logs, timeout=30)
    if "42" in sync or "consumed=[\"complete\"]" in sync:
        raise RuntimeError("Expected queued-only legacy baseline was not reproduced")
    async_result = run("api3-async-known-failure", [str(binary), str(cache / "async-regression.wasm")], host_env, logs, timeout=30, expected=1)
    if "state.guest_task.is_none()" not in async_result:
        raise RuntimeError("Exact runtime assertion was not reproduced")


if __name__ == "__main__":
    main()
