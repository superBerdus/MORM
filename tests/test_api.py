import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from fastapi.testclient import TestClient
import app.main as api


class APITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.uploads = Path(self.tmp.name)/'uploads'; self.uploads.mkdir()
        self.outputs = Path(self.tmp.name)/'outputs'; self.outputs.mkdir()
        self.p1 = patch.object(api, 'UPLOADS_DIR', self.uploads); self.p1.start()
        self.p2 = patch.object(api, 'OUTPUTS_DIR', self.outputs); self.p2.start()
        self.client = TestClient(api.app)

    def tearDown(self):
        self.client.close(); self.p1.stop(); self.p2.stop(); self.tmp.cleanup()

    def upload(self, orientation=None):
        img = Image.new('RGB',(300,200),'white')
        buf = io.BytesIO()
        exif = Image.Exif()
        if orientation: exif[274] = orientation
        img.save(buf,format='JPEG',exif=exif)
        res = self.client.post('/api/upload', files={'file':('sample.jpg',buf.getvalue(),'image/jpeg')})
        self.assertEqual(res.status_code,200,res.text)
        return res.json()

    def payload(self):
        return {'image_id':self.upload()['image_id'], 'mode':'custom',
                'corners':[[0,0],[299,0],[299,199],[0,199]],
                'custom_width_mm':60,'custom_height_mm':40, 'pixels_per_mm':5}

    def test_exif_normalization_and_detection_failure(self):
        d=self.upload(6)
        self.assertEqual((d['width'],d['height']),(200,300))
        self.assertFalse(d['detected'])
        saved=Image.open(self.uploads/d['image_id'])
        self.assertEqual(saved.size,(200,300)); self.assertIsNone(saved.getexif().get(274))

    def test_process_exports_and_metadata(self):
        res=self.client.post('/api/process',json=self.payload())
        self.assertEqual(res.status_code,200,res.text)
        d=res.json()
        self.assertFalse(d['metadata']['accuracy_verified'])
        for url in d['download'].values():
            self.assertEqual(self.client.get(url).status_code,200)
        png=Image.open(io.BytesIO(self.client.get(d['download']['png']).content))
        self.assertEqual(png.size,(300,200))
        self.assertAlmostEqual(png.info['dpi'][0],127,delta=.02)
        meta=self.client.get(d['download']['metadata']).json()
        self.assertEqual(meta['reference_corners_px'],[[0,0],[299,0],[299,199],[0,199]])
        self.assertEqual(meta['width_mm'],60)
        compile(d['blender_script_code'],'generated.py','exec')

    def test_invalid_dimensions_and_modes(self):
        p=self.payload()
        for update in [{'pixels_per_mm':0},{'custom_width_mm':-1},{'mode':'invalid'},
                       {'image_id':'../../etc/passwd'},{'ruler_length_mm':0}]:
            res=self.client.post('/api/process',json={**p,**update})
            self.assertEqual(res.status_code,422,res.text)

    def test_invalid_corners(self):
        p=self.payload()
        for points in [[[0,0]]*4, [[0,0],[299,199],[299,0],[0,199]], [[0,0],[500,0],[500,100],[0,100]]]:
            res=self.client.post('/api/process',json={**p,'corners':points})
            self.assertEqual(res.status_code,400,res.text)

    def test_resource_limit(self):
        p={**self.payload(),'custom_width_mm':10000,'custom_height_mm':10000}
        res=self.client.post('/api/process',json=p)
        self.assertEqual(res.status_code,400,res.text)

    def test_ruler_warning(self):
        p={**self.payload(),'mode':'ruler','ruler_pt1':[20,20],'ruler_pt2':[120,20], 'ruler_length_mm':50}
        res=self.client.post('/api/process',json=p)
        self.assertEqual(res.status_code,200,res.text)
        self.assertIn('perspective', res.json()['metadata']['warnings'][0])
        self.assertEqual(res.json()['metadata']['width_mm'],150)

    def test_real_redetection_endpoint(self):
        d=self.upload()
        res=self.client.get('/api/corners/'+d['image_id'])
        self.assertEqual(res.status_code,200)
        self.assertFalse(res.json()['detected'])

    def test_bad_image(self):
        res=self.client.post('/api/upload',files={'file':('broken.jpg',b'not an image','image/jpeg')})
        self.assertEqual(res.status_code,400)


if __name__=='__main__': unittest.main()
