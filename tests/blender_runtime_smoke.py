"""Optional smoke test for the generated scene-import script.

Run with a Blender-bundled Python or the matching official bpy wheel, for example:
  PYTHONPATH=/path/to/bpy LD_LIBRARY_PATH=/path/to/bpy/lib \
    python tests/blender_runtime_smoke.py
This checks Blender's data API, not the graphical viewport or every Blender release.
"""
from __future__ import annotations

import math
import struct
import sys
import tempfile
import zlib
from pathlib import Path

try:
    import bpy
except ImportError as exc:
    raise SystemExit("This optional test requires Blender's Python API module (bpy).") from exc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.blender_gen import generate_blender_script  # noqa: E402


def _write_png(path: Path, width: int = 210, height: int = 297) -> None:
    """Create a small RGB PNG using only the Python standard library."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    row = b"\x00" + (b"\xe8\xe8\xe8" * width)
    raw = row * height
    payload = b"\x89PNG\r\n\x1a\n"
    payload += chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 2, 0, 0, 0))
    payload += chunk(b"IDAT", zlib.compress(raw))
    payload += chunk(b"IEND", b"")
    path.write_bytes(payload)


def main() -> None:
    version = bpy.app.version_string
    with tempfile.TemporaryDirectory(prefix="img4blender-bpy-test-") as tmp:
        folder = Path(tmp)
        image_path = folder / "smoke-reference.png"
        script_path = folder / "generated-reference.py"
        _write_png(image_path)
        script_path.write_text(
            generate_blender_script(
                image_path.name,
                {"width_mm": 210, "height_mm": 297, "pixels_per_mm": 10},
            ),
            encoding="utf-8",
        )
        exec(compile(script_path.read_text(encoding="utf-8"), str(script_path), "exec"),
             {"__name__": "__main__", "__file__": str(script_path)})

    plane = bpy.data.objects.get("MORM_Reference_Plane_smoke-reference.png")
    empty = bpy.data.objects.get("MORM_Reference_Empty_smoke-reference.png")
    assert plane is not None, "Generated textured Plane was not created"
    assert empty is not None, "Generated image Empty was not created"
    assert all(math.isclose(a, b, abs_tol=1e-4) for a, b in zip(plane.dimensions[:2], (210.0, 297.0))), tuple(plane.dimensions)
    assert math.isclose(bpy.context.scene.unit_settings.scale_length, 0.001, abs_tol=1e-7)
    assert empty.hide_get(), "Image Empty should start hidden to avoid double display"
    assert plane.select_get(), "Generated Plane should be selected"
    assert plane.data.materials and plane.data.materials[0].node_tree
    print(f"PASS Blender bpy API smoke test: {version}; Plane={tuple(round(x, 4) for x in plane.dimensions)} BU; scene scale={bpy.context.scene.unit_settings.scale_length}")


if __name__ == "__main__":
    main()
