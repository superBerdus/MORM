"""
MORM - Blender Script Generator
The generated importer passed a limited headless smoke test with Blender 5.2.3 LTS bpy.
The full GUI/viewport and other Blender versions have not been verified.
"""

from typing import Dict, Any


def generate_blender_script(
    image_filename: str,
    metadata: Dict[str, Any]
) -> str:
    """
    Creates a Python script to run inside Blender. It loads the image locally or
    from http://localhost:8085, adds a metric-scale image Empty and textured Plane,
    and configures the 3D Viewport to display the image texture.
    """
    width_mm = float(metadata.get("width_mm", 210.0))
    height_mm = float(metadata.get("height_mm", 297.0))
    pixels_per_mm = float(metadata.get("pixels_per_mm", 10.0))

    script_content = f'''# ==============================================================================
# MORM - Import a 1:1 metric reference image and Plane
# Image: {image_filename}
# Reference dimensions: {width_mm:.2f} mm x {height_mm:.2f} mm
# Sampling density: {pixels_per_mm} px/mm (not a measurement-accuracy guarantee)
# ==============================================================================
# HOW TO RUN
# 1. Open Blender.
# 2. Select the 'Scripting' workspace.
# 3. Click '+ New' in the Text Editor.
# 4. Paste this script and click 'Run Script' (or press Alt + P).
# 5. Press Numpad 7 for a top orthographic view.
# ==============================================================================

import bpy
import os
import tempfile
import urllib.request

def setup_metric_reference():
    print("----------------------------------------------------------------------")
    print("MORM: Configuring the scene for metric dimensions…")

    # 1. Set scene units to metric millimeters
    # Use in a new/empty scene: changing units affects how existing objects are interpreted.
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.length_unit = 'MILLIMETERS'
    scene.unit_settings.scale_length = 0.001  # 1 Blender unit (BU) = 1 mm

    # 2. Locate the image or download it automatically
    TARGET_FILENAME = "{image_filename}"
    SERVER_URL = "http://localhost:8085/data/outputs/{image_filename}"
    
    # Search the script folder, Blender Text Editor paths, then common local paths.
    script_dirs = []
    if globals().get('__file__'):
        script_dirs.append(os.path.dirname(os.path.abspath(__file__)))
    for text in bpy.data.texts:
        if text.filepath:
            script_dirs.append(os.path.dirname(bpy.path.abspath(text.filepath)))
    candidate_paths = [os.path.join(folder, TARGET_FILENAME) for folder in script_dirs]
    candidate_paths += [
        os.path.join(os.path.expanduser("~"), "Downloads", TARGET_FILENAME),
        os.path.join(os.path.dirname(bpy.data.filepath), TARGET_FILENAME) if bpy.data.filepath else "",
        os.path.join(tempfile.gettempdir(), TARGET_FILENAME),
        TARGET_FILENAME
    ]

    image_path = None
    for p in candidate_paths:
        if p and os.path.exists(p):
            image_path = p
            print(f" Image found locally: {{image_path}}")
            break

    # If not found locally, try the running MORM server.
    if not image_path or not os.path.exists(image_path):
        try:
            print(f" Downloading image from local server: {{SERVER_URL}}…")
            temp_path = os.path.join(tempfile.gettempdir(), TARGET_FILENAME)
            urllib.request.urlretrieve(SERVER_URL, temp_path)
            if os.path.exists(temp_path):
                image_path = temp_path
                print(f" Image downloaded: {{image_path}}")
        except Exception as net_err:
            print(f" [WARNING] Could not download from the local server: {{net_err}}")

    if not image_path or not os.path.exists(image_path):
        print(f"[ERROR] Could not find '{{TARGET_FILENAME}}'.")
        print("Download the scaled PNG from the MORM web interface and save it beside this script.")
        return

    # Load the image into Blender and pack it into the project
    try:
        img = bpy.data.images.load(image_path, check_existing=True)
        img.pack()  # Embed the image in the .blend file so it remains available if moved.
        print(" Image loaded and packed into the Blender project.")
    except Exception as e:
        print(f"[ERROR] Could not load the image into Blender: {{e}}")
        return

    TARGET_WIDTH_MM = {width_mm:.4f}
    TARGET_HEIGHT_MM = {height_mm:.4f}

    # 3. METHOD A: metric-scale image Empty
    # Native Blender reference image; visible in supported view modes
    empty_name = "MORM_Reference_Empty_{image_filename}"
    old_empty = bpy.data.objects.get(empty_name)
    if old_empty:
        bpy.data.objects.remove(old_empty, do_unlink=True)

    empty_obj = bpy.data.objects.new(empty_name, None)
    empty_obj.empty_display_type = 'IMAGE'
    empty_obj.data = img

    # Blender'da scale_length=0.001 iken display_size mm birimindedir
    max_dim_mm = max(TARGET_WIDTH_MM, TARGET_HEIGHT_MM)
    empty_obj.empty_display_size = max_dim_mm

    empty_obj.location = (0.0, 0.0, 0.0)
    empty_obj.rotation_euler = (0.0, 0.0, 0.0)

    # Blender image Empties already apply the image pixel aspect ratio.
    # Applying it twice compresses the short axis. Only correct for
    # the difference between the natural image size and the target dimensions;
    # this also accounts for output pixel rounding.
    pixel_width, pixel_height = img.size[:]
    if pixel_width <= 0 or pixel_height <= 0:
        raise ValueError("The reference image has invalid pixel dimensions.")
    pixel_max = max(pixel_width, pixel_height)
    native_width = max_dim_mm * pixel_width / pixel_max
    native_height = max_dim_mm * pixel_height / pixel_max
    empty_obj.scale = (
        TARGET_WIDTH_MM / native_width,
        TARGET_HEIGHT_MM / native_height,
        1.0
    )

    empty_obj.show_empty_image_orthographic = True
    empty_obj.show_empty_image_perspective = True
    empty_obj.color[3] = 0.90  # 90% opacity

    scene.collection.objects.link(empty_obj)
    empty_obj.hide_set(True)  # Avoid a duplicate display; enable it in the Outliner if needed.

    # 4. METHOD B: metric-scale textured mesh Plane
    # Place the textured Plane 0.1 mm below the origin.
    plane_name = "MORM_Reference_Plane_{image_filename}"
    old_plane = bpy.data.objects.get(plane_name)
    if old_plane:
        bpy.data.objects.remove(old_plane, do_unlink=True)

    # Create a unit Plane
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.0, 0.0, -0.1))
    plane = bpy.context.active_object
    plane.name = plane_name
    plane.dimensions = (TARGET_WIDTH_MM, TARGET_HEIGHT_MM, 0.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    # Create and assign an image-textured emission material
    mat_name = "MORM_Material_{image_filename}"
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = bpy.data.materials.new(name=mat_name)
        # Blender 5.0+ materials have node trees enabled by default; the legacy
        # use_nodes property is deprecated there and scheduled for removal.
        if bpy.app.version < (5, 0, 0):
            mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        node_out = nodes.new(type='ShaderNodeOutputMaterial')
        node_emit = nodes.new(type='ShaderNodeEmission')
        node_tex = nodes.new(type='ShaderNodeTexImage')
        node_tex.image = img

        links.new(node_tex.outputs['Color'], node_emit.inputs['Color'])
        links.new(node_emit.outputs['Emission'], node_out.inputs['Surface'])

    plane.data.materials.clear()
    plane.data.materials.append(mat)

    # 5. Configure the 3D Viewport to display the image texture
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        # Display the texture in Solid shading
                        space.shading.color_type = 'TEXTURE'
                        # Switch to Material Preview
                        space.shading.type = 'MATERIAL'

    # Select the Plane
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    bpy.context.view_layer.objects.active = plane
    plane.select_set(True)

    print("======================================================================")
    print(" SUCCESS: Metric reference image added to the scene.")
    print(f" Dimensions: {{TARGET_WIDTH_MM:.2f}} mm x {{TARGET_HEIGHT_MM:.2f}} mm")
    print(" 3D Viewport switched to Material Preview.")
    print(" Press Numpad 7 for a top orthographic view.")
    print("======================================================================")

if __name__ == "__main__":
    setup_metric_reference()
'''
    return script_content
