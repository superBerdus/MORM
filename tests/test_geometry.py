"""Synthetic regression tests; these do NOT certify real-camera accuracy.
Run: python -m unittest discover -s tests -v
Blender Empty dimensions below model Blender's native image aspect behavior;
actual Blender viewport validation remains a separate acceptance test.
"""
import ast
import textwrap
import unittest
from types import SimpleNamespace

import cv2
import numpy as np
from core.rectifier import rectify_planar_image, scale_by_ruler_only, order_points, validate_quad, rectify_with_ruler_scale
from core.blender_gen import generate_blender_script


class GeometryTests(unittest.TestCase):
    def test_planar_reference_corners(self):
        image = np.full((500, 600, 3), 255, np.uint8)
        corners = np.float32([[95, 80], [475, 115], [520, 420], [55, 390]])
        output, meta = rectify_planar_image(image, corners.tolist(), 120, 80, 5, 2)
        self.assertEqual(output.shape[:2], (420, 620))
        mapped = cv2.perspectiveTransform(corners[None], np.array(meta['homography_matrix']))[0]
        # Current convention maps reference boundaries onto pixel centers.
        expected = np.float32([[10, 10], [609, 10], [609, 409], [10, 409]])
        np.testing.assert_allclose(mapped, expected, atol=1e-4)

    def test_independent_interior_points(self):
        image = np.full((500, 600, 3), 255, np.uint8)
        world = np.float32([[0, 0], [120, 0], [120, 80], [0, 80]])
        photographed = np.float32([[95, 80], [475, 115], [520, 420], [55, 390]])
        camera_h = cv2.getPerspectiveTransform(world, photographed)
        points = np.float32([[[20, 20], [70, 20], [20, 60]]])
        projected = cv2.perspectiveTransform(points, camera_h)
        _, meta = rectify_planar_image(image, photographed.tolist(), 120, 80, 10)
        recovered = cv2.perspectiveTransform(projected, np.array(meta['homography_matrix'])) / 10
        # Allows the known endpoint convention difference (< one output pixel).
        np.testing.assert_allclose(recovered, points, atol=0.1)

    def test_ruler_scaling_without_perspective(self):
        image = np.zeros((200, 300, 3), np.uint8)
        output, meta = scale_by_ruler_only(image, (20, 30), (120, 30), 50, 4)
        self.assertEqual(output.shape[:2], (400, 600))
        self.assertEqual(meta['width_mm'], 150)
        self.assertEqual(meta['height_mm'], 100)

    def test_rotated_diamond_keeps_unique_vertices(self):
        pts = order_points([[100, 0], [200, 100], [100, 200], [0, 100]])
        self.assertEqual(len(np.unique(pts, axis=0)), 4)
        self.assertTrue(cv2.isContourConvex(pts.reshape(-1,1,2)))

    def test_unknown_aspect_ruler_rectification_rejected(self):
        with self.assertRaises(ValueError):
            rectify_with_ruler_scale(np.zeros((200,300,3),np.uint8),
                                    [[0,0],[299,0],[299,199],[0,199]], (0,0),(100,0),50)

    def test_degenerate_quad_rejected(self):
        with self.assertRaises(ValueError):
            validate_quad([[0,0],[10,0],[20,0],[30,0]])

    def test_generated_script_syntax(self):
        ast.parse(generate_blender_script('example.png', {'width_mm': 210, 'height_mm': 297}))

    def test_blender_empty_physical_dimensions(self):
        for w_mm, h_mm, w_px, h_px in [(210,297,2100,2970), (297,210,2970,2100),
                                      (100,100,1000,1000), (85.60,53.98,856,540)]:
            with self.subTest(size=(w_mm, h_mm)):
                script = generate_blender_script('example.png', {'width_mm': w_mm, 'height_mm': h_mm})
                # Execute only generated sizing code, without Blender or filesystem actions.
                fragment = script.split('    # Blender\'da scale_length=0.001')[1]
                fragment = fragment.split('    empty_obj.show_empty_image_orthographic')[0]
                fragment = fragment.split('\n', 1)[1]
                obj = SimpleNamespace()
                scope = {'empty_obj': obj, 'TARGET_WIDTH_MM': w_mm, 'TARGET_HEIGHT_MM': h_mm,
                         'img': SimpleNamespace(size=(w_px,h_px))}
                exec(textwrap.dedent(fragment), scope)
                native_max = max(w_px, h_px)
                actual_w = obj.empty_display_size * w_px / native_max * obj.scale[0]
                actual_h = obj.empty_display_size * h_px / native_max * obj.scale[1]
                self.assertAlmostEqual(actual_w, w_mm, places=6)
                self.assertAlmostEqual(actual_h, h_mm, places=6)


if __name__ == '__main__':
    unittest.main()
