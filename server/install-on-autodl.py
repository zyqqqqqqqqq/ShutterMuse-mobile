#!/usr/bin/env python3
"""Create server/ tree under ShutterMuse repo on AutoDL. Run from repo root."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILES = {
    "requirements-server.txt": ROOT / "requirements-server.txt",
    "app/__init__.py": ROOT / "app" / "__init__.py",
    "app/main.py": ROOT / "app" / "main.py",
    "app/inference.py": ROOT / "app" / "inference.py",
    "app/schemas.py": ROOT / "app" / "schemas.py",
    "app/pose_mapper.py": ROOT / "app" / "pose_mapper.py",
    "app/response_mapper.py": ROOT / "app" / "response_mapper.py",
    "app/subject_parse.py": ROOT / "app" / "subject_parse.py",
}

if __name__ == "__main__":
    repo = Path("/root/autodl-tmp/ShutterMuse")
    dest = repo / "server"
    dest.mkdir(parents=True, exist_ok=True)
    for rel, src in FILES.items():
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            out.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            print("wrote", out)
        else:
            print("MISSING", src)
    print("Done. ls:", list((dest / "app").glob("*.py")))
