"""MORM API. Local image processing without a claim of certified accuracy."""
import io
import json
import uuid
from pathlib import Path
from typing import List, Tuple, Optional, Literal

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ConfigDict

from core.rectifier import rectify_planar_image, scale_by_ruler_only
from core.detector import auto_detect_paper_corners
from core.blender_gen import generate_blender_script
from core.vectorizer import extract_contours_to_svg

BASE_DIR = Path(__file__).resolve().parents[1]
UPLOADS_DIR = BASE_DIR / 'data/uploads'
OUTPUTS_DIR = BASE_DIR / 'data/outputs'
STATIC_DIR = BASE_DIR / 'static'
for directory in (UPLOADS_DIR, OUTPUTS_DIR, STATIC_DIR):
    directory.mkdir(parents=True, exist_ok=True)

app = FastAPI(title='MORM API', version='1.1.0')
STANDARD_SIZES = {
    'a4_portrait': (210., 297.), 'a4_landscape': (297., 210.),
    'a3_portrait': (297., 420.), 'a3_landscape': (420., 297.),
    'a5_portrait': (148., 210.), 'a5_landscape': (210., 148.),
    'card': (85.60, 53.98), 'card_vertical': (53.98, 85.60)
}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_INPUT_PIXELS = 40_000_000


class ProcessRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    image_id: str = Field(pattern=r'^[a-f0-9]{12}\.png$')
    corners: List[Tuple[float, float]] = Field(min_length=4, max_length=4)
    mode: Literal['a4_portrait', 'a4_landscape', 'a3_portrait', 'a3_landscape',
                  'a5_portrait', 'a5_landscape', 'card', 'card_vertical', 'custom', 'ruler']
    custom_width_mm: float = Field(default=210., gt=0, le=10000)
    custom_height_mm: float = Field(default=297., gt=0, le=10000)
    pixels_per_mm: float = Field(default=10., ge=1, le=15)
    margin_mm: float = Field(default=0., ge=0, le=50)
    ruler_pt1: Optional[Tuple[float, float]] = None
    ruler_pt2: Optional[Tuple[float, float]] = None
    ruler_length_mm: float = Field(default=100., gt=0, le=10000)


def safe_file(directory, name):
    if Path(name).name != name or '\\' in name:
        raise HTTPException(400, 'Invalid file name.')
    path = (directory / name).resolve()
    if path.parent != directory.resolve() or not path.is_file():
        raise HTTPException(404, 'File not found.')
    return path


def detect_response(img):
    corners = auto_detect_paper_corners(img)
    h, w = img.shape[:2]
    return {'corners': corners or [[w*.1,h*.1], [w*.9,h*.1], [w*.9,h*.9], [w*.1,h*.9]],
            'detected': corners is not None}


@app.post('/api/upload')
async def upload_image(file: UploadFile = File(...)):
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, 'The file must not exceed 25 MB.')
    try:
        with Image.open(io.BytesIO(data)) as original:
            if original.width * original.height > MAX_INPUT_PIXELS:
                raise HTTPException(413, 'The image must not exceed 40 megapixels.')
            # Browser and backend always see identical, orientation-normalized pixels.
            image = ImageOps.exif_transpose(original).convert('RGB')
            image.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(400, 'Could not read the image. Use JPEG, PNG, WebP, BMP, or TIFF.')
    file_id = f'{uuid.uuid4().hex[:12]}.png'
    image.save(UPLOADS_DIR / file_id, format='PNG')
    img = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
    return {'status': 'success', 'image_id': file_id, 'width': image.width, 'height': image.height,
            'image_url': f'/data/uploads/{file_id}', **detect_response(img)}


@app.get('/api/corners/{image_id}')
def detect_corners(image_id: str):
    path = safe_file(UPLOADS_DIR, image_id)
    img = cv2.imread(str(path))
    if img is None:
        raise HTTPException(400, 'Could not read the image.')
    return detect_response(img)


@app.post('/api/process')
def process_image(req: ProcessRequest):
    path = safe_file(UPLOADS_DIR, req.image_id)
    img = cv2.imread(str(path))
    if img is None:
        raise HTTPException(400, 'Could not read the image.')
    h, w = img.shape[:2]
    selected = req.corners if req.mode != 'ruler' else [req.ruler_pt1, req.ruler_pt2]
    if any(p is None or not (0 <= p[0] <= w-1 and 0 <= p[1] <= h-1) for p in selected):
        raise HTTPException(400, 'Reference points must be inside the image.')
    try:
        if req.mode == 'ruler':
            warped, meta = scale_by_ruler_only(img, req.ruler_pt1, req.ruler_pt2,
                                               req.ruler_length_mm, req.pixels_per_mm)
        else:
            tw, th = ((req.custom_width_mm, req.custom_height_mm) if req.mode == 'custom'
                      else STANDARD_SIZES[req.mode])
            warped, meta = rectify_planar_image(img, req.corners, tw, th,
                                               req.pixels_per_mm, req.margin_mm)
    except (ValueError, cv2.error) as exc:
        raise HTTPException(400, str(exc))

    warnings = ['Output pixel density is not measurement accuracy; verify with independent known distances.',
                'No lens calibration was applied. The reference and measured surface must be coplanar.']
    if req.mode == 'ruler':
        warnings.insert(0, 'Ruler mode applies uniform scaling only; it does not correct perspective or lens distortion.')
    else:
        warnings.append('The four corners must belong to a real rectangular reference. Verify photocopied content scale separately.')
    meta.update({'mode': req.mode, 'accuracy_verified': False, 'lens_correction_applied': False,
                 'warnings': warnings, 'source_image_id': req.image_id,
                 'source_size_px': [w, h], 'reference_corners_px': req.corners,
                 'ruler_points_px': [req.ruler_pt1, req.ruler_pt2] if req.mode == 'ruler' else None,
                 'ruler_length_mm': req.ruler_length_mm if req.mode == 'ruler' else None,
                 'pixel_coordinate_convention': 'pixel centers; reference endpoints span W*ppm-1 pixels',
                 'software_version': '1.1.0'})
    out_id = f'rect_{uuid.uuid4().hex[:10]}'
    png_name, py_name, svg_name, json_name = (out_id+'.png', out_id+'_blender.py',
                                            out_id+'_contour.svg', out_id+'_metadata.json')
    Image.fromarray(cv2.cvtColor(warped, cv2.COLOR_BGR2RGB)).save(
        OUTPUTS_DIR / png_name, dpi=(req.pixels_per_mm*25.4,)*2)
    script = generate_blender_script(png_name, meta)
    (OUTPUTS_DIR / py_name).write_text(script, encoding='utf-8')
    (OUTPUTS_DIR / svg_name).write_text(extract_contours_to_svg(warped, meta), encoding='utf-8')
    (OUTPUTS_DIR / json_name).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'status': 'success', 'metadata': meta, 'png_url': f'/data/outputs/{png_name}',
            'blender_script_url': f'/data/outputs/{py_name}', 'blender_script_code': script,
            'svg_url': f'/data/outputs/{svg_name}',
            'download': {'png': f'/api/download/png/{png_name}', 'blender': f'/api/download/script/{py_name}',
                         'svg': f'/api/download/svg/{svg_name}', 'metadata': f'/api/download/json/{json_name}'}}


@app.get('/api/download/{file_type}/{filename}')
def download_file(file_type: str, filename: str):
    path = safe_file(OUTPUTS_DIR, filename)
    media = {'png': 'image/png', 'script': 'text/x-python', 'svg': 'image/svg+xml',
             'json': 'application/json'}.get(file_type, 'application/octet-stream')
    return FileResponse(path, media_type=media, filename=filename)


app.mount('/data/uploads', StaticFiles(directory=UPLOADS_DIR), name='uploads')
app.mount('/data/outputs', StaticFiles(directory=OUTPUTS_DIR), name='outputs')
app.mount('/', StaticFiles(directory=STATIC_DIR, html=True), name='static')
