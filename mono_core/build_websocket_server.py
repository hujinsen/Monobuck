import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
SPEC_FILE = ROOT / "websocket_server.spec"
DIST_EXE = ROOT / "dist"  / "websocket_server.exe"
TAURI_EXE = ROOT.parent / "src-tauri" / "resources" / "websocket_server.exe"


def run(cmd, cwd=None):
    print("[build] RUN:", " ".join(map(str, cmd)))
    subprocess.check_call(cmd, cwd=cwd or ROOT)


def main() -> int:
    # 1. 选择 Python 解释器：优先使用项目内 .venv
    python = VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)
    print(f"[build] use python: {python}")

    if not SPEC_FILE.exists():
        print(f"[build] ERROR: spec file not found: {SPEC_FILE}")
        return 1

    # 2. 调用 PyInstaller 生成 websocket_server.exe
    try:
        run([str(python), "-m", "PyInstaller", str(SPEC_FILE)])
    except subprocess.CalledProcessError as e:
        print("[build] PyInstaller failed", e)
        return e.returncode or 1

    # 3. 将生成的 exe 复制到 src-tauri/resources 下，供 Tauri 打包使用
    if not DIST_EXE.exists():
        print(f"[build] ERROR: dist exe not found: {DIST_EXE}")
        return 1

    TAURI_EXE.parent.mkdir(parents=True, exist_ok=True)
    import shutil

    shutil.copy2(DIST_EXE, TAURI_EXE)
    print(f"[build] copied: {DIST_EXE} -> {TAURI_EXE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
