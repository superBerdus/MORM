# MORM — Metric Orthophoto Reference Maker

A local tool for rectifying a photo against a **known, planar reference** and exporting a metric-scale image, SVG outline, processing metadata, and an optional Blender import script. It is not limited to Blender; the PNG can be imported into other CAD or 3D applications and scaled manually.

> **Sampling density is not measurement accuracy.** For example, 10 px/mm means 0.1 mm between output pixels, not 0.1 mm physical accuracy. This version does not perform camera/lens calibration.
>
> **User-reported practical result:** measurements are typically within approximately ±1 mm under ordinary conditions, with absolute error tending to increase as the measured distance grows. This is user feedback, not a standardized test result or accuracy guarantee. Results depend on the capture, reference, surface, and image region.

## Run locally

### Windows with Docker Desktop

1. Back up any existing project folder.
2. Extract this archive to a new folder; do not run it from inside the ZIP.
3. Start Docker Desktop.
4. If another MORM/MetricScanner instance is using port 8085, stop it first.
5. Run `start.bat` from the extracted folder, or use `docker compose up -d --build`.
6. Open `http://localhost:8085`. Use Ctrl+F5 if an older page is cached.

### Python development install

Python 3.11 or newer is expected by the project configuration:

```sh
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8085
```

The web application was tested on Python 3.13 and Chromium. Docker and Windows launcher execution have not been verified in this workspace. The first Docker build needs internet access. Google Fonts are optional; system fonts are used offline. Do not expose the unauthenticated local service to an untrusted network.

## Basic workflow

1. Place a **flat, known-size reference** in the same plane as the image area.
2. Upload the photo. EXIF orientation is normalized automatically.
3. Choose A4, A3, card, custom size, or Ruler mode.
4. For rectangle modes, place P1–P4 on the reference’s four actual outer corners. Enter the reference’s real dimensions in Custom Size when a preset does not apply.
5. Click **Detect Corners** for a suggestion, then inspect and adjust all four points.
6. Click **Rectify to Reference**.
7. Use **Independent Distance Check** to compare an unused, independently known physical length against the output. Check different regions and both directions where possible.

**Ruler mode** uses one known distance to apply uniform scaling only. It does not rectify perspective or correct lens distortion; it is best suited to a nearly front-facing, flat image.

**Photocopies:** an added physical ruler calibrates the current photocopy’s scale. It cannot recover the original physical size of an object printed on that copy unless the earlier print/copy scale is independently known.

## Blender compatibility and import

- **Tested Blender Python API:** official `bpy` 5.2.3 LTS wheel, the current stable Blender version on 2026-11-01 ([official Blender downloads](https://www.blender.org/download/)).
- The generated script passed a limited headless API smoke test: image load/pack, 210 × 297 mm Plane, scene scale, hidden image Empty, selected Plane, and material nodes.
- This does **not** test the full Blender desktop application or graphical viewport. Older Blender versions have not been tested; compatibility with every release is not claimed. See `tests/blender-runtime-results.txt`.
- The `.py` file is optional. When used, it runs inside Blender with Blender’s bundled Python API; no separate Python environment or extra package installation is needed. Alternatively, download the PNG, import it into Blender or another CAD/3D application, and set its dimensions manually. Verify the size inside the target application with an independent known distance.

For the generated Blender script, download the PNG and `.py` into the same folder. Run the script from a new/empty Blender scene. It sets the scene unit scale to `0.001` (one Blender unit represents one millimeter), so take care when using an existing scene. It creates a textured `MORM_Reference_Plane`; the image Empty starts hidden. The script searches local folders first and then attempts `http://localhost:8085` if the image is not found locally.

## Accuracy and limitations

- A four-corner homography corrects planar perspective, not lens distortion or non-planar surfaces.
- Reference dimensions and corner locations must be correct; the reference and measured region must be coplanar.
- A single ruler length cannot establish both physical axes in an oblique image.
- Independent checks should use known distances not used to set the output scale, at multiple positions and in both horizontal and vertical directions.
- A printed ruler inside a photocopy is not an independent physical reference unless its print scale is verified.
- No claim is made that the sample’s previously observed ~1.4 mm deviation has been eliminated or that <0.5 mm accuracy is achieved across the image.

The project limits uploads to 25 MB / 40 megapixels and outputs to 32 megapixels / 16,000 pixels per edge. Uploaded images and generated files are stored locally under `data/`; clear them when no longer needed.

## Tests

Python/API/geometric regression tests:

```sh
python -m unittest discover -s tests -v
```

Optional browser test (start the app first):

```sh
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python tests/browser_smoke.py
```

Optional Blender Python API smoke test, when a compatible `bpy` module is available:

```sh
python tests/blender_runtime_smoke.py
```

The Blender smoke test is not included in runtime dependencies and does not test the GUI/viewport. Latest recorded test results are in `tests/current-results.txt`, `tests/browser-results.txt`, and `tests/blender-runtime-results.txt`.

## License

MIT License — see LICENSE

## Project status

English is the current application interface language. The ruler tool remains available as a limited uniform-scaling mode. Camera calibration, lens correction, a bilingual language selector, and validated physical accuracy certification are not implemented.
