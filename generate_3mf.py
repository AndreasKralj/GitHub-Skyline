#!/usr/bin/env python3
"""
Generate Bambu Studio compatible 3MF files with multicolor support.
Takes a base STL and bars STL and creates a single 3MF with two parts
assigned to different extruders.
"""

import struct
import zipfile
import json
import os
import sys


def read_stl(filepath):
    """Read an STL file (auto-detects ASCII vs binary). Returns (vertices, triangles)."""
    with open(filepath, 'rb') as f:
        header = f.read(80)
    is_ascii = header.strip().startswith(b'solid') and b'\x00' not in header

    if is_ascii:
        return _read_ascii_stl(filepath)
    else:
        return _read_binary_stl(filepath)


def _read_ascii_stl(filepath):
    """Read an ASCII STL file."""
    import re
    vertices = []
    triangles = []
    vertex_map = {}

    with open(filepath, 'r') as f:
        tri_verts = []
        for line in f:
            line = line.strip()
            if line.startswith('vertex'):
                parts = line.split()
                v = (round(float(parts[1]), 6),
                     round(float(parts[2]), 6),
                     round(float(parts[3]), 6))
                if v not in vertex_map:
                    vertex_map[v] = len(vertices)
                    vertices.append(v)
                tri_verts.append(vertex_map[v])

                if len(tri_verts) == 3:
                    triangles.append(tuple(tri_verts))
                    tri_verts = []

    return vertices, triangles


def _read_binary_stl(filepath):
    """Read a binary STL file."""
    vertices = []
    triangles = []
    vertex_map = {}

    with open(filepath, 'rb') as f:
        f.read(80)  # header
        num_triangles = struct.unpack('<I', f.read(4))[0]

        for _ in range(num_triangles):
            data = struct.unpack('<12fH', f.read(50))
            v1 = (data[3], data[4], data[5])
            v2 = (data[6], data[7], data[8])
            v3 = (data[9], data[10], data[11])

            tri_indices = []
            for v in [v1, v2, v3]:
                key = (round(v[0], 6), round(v[1], 6), round(v[2], 6))
                if key not in vertex_map:
                    vertex_map[key] = len(vertices)
                    vertices.append(key)
                tri_indices.append(vertex_map[key])

            triangles.append(tuple(tri_indices))

    return vertices, triangles


def compute_bbox(vertices):
    """Compute bounding box min/max."""
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def compute_center(bbox):
    """Compute center of bounding box."""
    return (
        (bbox[0][0] + bbox[1][0]) / 2,
        (bbox[0][1] + bbox[1][1]) / 2,
        (bbox[0][2] + bbox[1][2]) / 2,
    )


def center_vertices(vertices, center):
    """Shift vertices so they're centered at origin."""
    return [
        (v[0] - center[0], v[1] - center[1], v[2] - center[2])
        for v in vertices
    ]


def mesh_to_xml(vertices, triangles, obj_id):
    """Convert mesh data to 3MF XML object element."""
    lines = []
    lines.append(f'  <object id="{obj_id}" type="model">')
    lines.append('   <mesh>')
    lines.append('    <vertices>')
    for v in vertices:
        lines.append(f'     <vertex x="{v[0]}" y="{v[1]}" z="{v[2]}"/>')
    lines.append('    </vertices>')
    lines.append('    <triangles>')
    for t in triangles:
        lines.append(f'     <triangle v1="{t[0]}" v2="{t[1]}" v3="{t[2]}"/>')
    lines.append('    </triangles>')
    lines.append('   </mesh>')
    lines.append('  </object>')
    return '\n'.join(lines)


def generate_3mf(base_stl_path, bars_stl_path, output_path, display_name,
                  project_settings_path=None):
    """Generate a Bambu Studio compatible 3MF with two-color parts."""

    base_name = os.path.basename(base_stl_path)
    bars_name = os.path.basename(bars_stl_path)

    # Read meshes
    base_verts, base_tris = read_stl(base_stl_path)
    bars_verts, bars_tris = read_stl(bars_stl_path)

    # Compute centers
    base_bbox = compute_bbox(base_verts)
    bars_bbox = compute_bbox(bars_verts)
    base_center = compute_center(base_bbox)
    bars_center = compute_center(bars_bbox)

    # Center meshes at origin
    base_verts_c = center_vertices(base_verts, base_center)
    bars_verts_c = center_vertices(bars_verts, bars_center)

    # Bars offset relative to base center
    bo = (
        bars_center[0] - base_center[0],
        bars_center[1] - base_center[1],
        bars_center[2] - base_center[2],
    )

    # Build plate position (Bambu A1 plate is 256x256)
    plate_x = 128.0
    plate_y = 128.0
    plate_z = base_center[2]

    # ---- 3D/Objects/object_3.model (mesh data) ----
    object_model = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US"'
        ' xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"'
        ' xmlns:BambuStudio="http://schemas.bambulab.com/package/2021"'
        ' xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06"'
        ' requiredextensions="p">\n'
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
        ' <resources>\n'
        f'{mesh_to_xml(base_verts_c, base_tris, 1)}\n'
        f'{mesh_to_xml(bars_verts_c, bars_tris, 2)}\n'
        ' </resources>\n'
        '</model>'
    )

    # ---- 3D/3dmodel.model (main model with components) ----
    main_model = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US"'
        ' xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"'
        ' xmlns:BambuStudio="http://schemas.bambulab.com/package/2021"'
        ' xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06"'
        ' requiredextensions="p">\n'
        ' <metadata name="Application">BambuStudio-02.05.00.66</metadata>\n'
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
        ' <metadata name="Copyright"></metadata>\n'
        ' <metadata name="CreationDate">2026-04-07</metadata>\n'
        ' <metadata name="Description"></metadata>\n'
        ' <metadata name="Designer"></metadata>\n'
        ' <metadata name="DesignerCover"></metadata>\n'
        ' <metadata name="DesignerUserId"></metadata>\n'
        ' <metadata name="License"></metadata>\n'
        ' <metadata name="ModificationDate">2026-04-07</metadata>\n'
        ' <metadata name="Origin"></metadata>\n'
        ' <metadata name="ProfileCover"></metadata>\n'
        ' <metadata name="ProfileDescription"></metadata>\n'
        ' <metadata name="ProfileTitle"></metadata>\n'
        f' <metadata name="Title">{display_name} GitLab Skyline</metadata>\n'
        ' <resources>\n'
        '  <object id="3" p:UUID="00000003-61cb-4c03-9d28-80fed5dfa1dc" type="model">\n'
        '    <components>\n'
        '      <component p:path="/3D/Objects/object_3.model" objectid="1"'
        ' p:UUID="00030000-b206-40ff-9872-83e8017abed1"'
        ' transform="1 0 0 0 1 0 0 0 1 0 0 0"/>\n'
        '      <component p:path="/3D/Objects/object_3.model" objectid="2"'
        ' p:UUID="00030001-b206-40ff-9872-83e8017abed1"'
        f' transform="1 0 0 0 1 0 0 0 1 {bo[0]} {bo[1]} {bo[2]}"/>\n'
        '    </components>\n'
        '  </object>\n'
        ' </resources>\n'
        f' <build p:UUID="2c7c17d8-22b5-4d84-8835-1976022ea369">\n'
        f'  <item objectid="3" p:UUID="00000003-b1ec-4553-aec9-835e5b724bb4"'
        f' transform="1 0 0 0 1 0 0 0 1 {plate_x} {plate_y} {plate_z}" printable="1"/>\n'
        ' </build>\n'
        '</model>'
    )

    # ---- Metadata/model_settings.config ----
    bars_matrix = f"1 0 0 {bo[0]} 0 1 0 {bo[1]} 0 0 1 {bo[2]} 0 0 0 1"

    model_settings = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<config>\n'
        '  <object id="3">\n'
        f'    <metadata key="name" value="{base_name}"/>\n'
        '    <metadata key="extruder" value="1"/>\n'
        f'    <metadata face_count="{len(base_tris) + len(bars_tris)}"/>\n'
        '    <part id="1" subtype="normal_part">\n'
        f'      <metadata key="name" value="{base_name}"/>\n'
        '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
        f'      <metadata key="source_file" value="{base_name}"/>\n'
        '      <metadata key="source_object_id" value="0"/>\n'
        '      <metadata key="source_volume_id" value="0"/>\n'
        f'      <metadata key="source_offset_x" value="{base_center[0]}"/>\n'
        f'      <metadata key="source_offset_y" value="{base_center[1]}"/>\n'
        f'      <metadata key="source_offset_z" value="{base_center[2]}"/>\n'
        f'      <mesh_stat face_count="{len(base_tris)}" edges_fixed="0"'
        ' degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>\n'
        '    </part>\n'
        '    <part id="2" subtype="normal_part">\n'
        f'      <metadata key="name" value="{bars_name}"/>\n'
        f'      <metadata key="matrix" value="{bars_matrix}"/>\n'
        f'      <metadata key="source_file" value="{bars_name}"/>\n'
        '      <metadata key="source_object_id" value="0"/>\n'
        '      <metadata key="source_volume_id" value="1"/>\n'
        f'      <metadata key="source_offset_x" value="{bars_center[0]}"/>\n'
        f'      <metadata key="source_offset_y" value="{bars_center[1]}"/>\n'
        f'      <metadata key="source_offset_z" value="{bars_center[2]}"/>\n'
        '      <metadata key="extruder" value="2"/>\n'
        f'      <mesh_stat face_count="{len(bars_tris)}" edges_fixed="0"'
        ' degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>\n'
        '    </part>\n'
        '  </object>\n'
        '  <plate>\n'
        '    <metadata key="plater_id" value="1"/>\n'
        '    <metadata key="plater_name" value=""/>\n'
        '    <metadata key="locked" value="false"/>\n'
        '    <metadata key="filament_map_mode" value="Auto For Flush"/>\n'
        '    <metadata key="filament_maps" value="1 1"/>\n'
        '    <metadata key="filament_volume_maps" value="0 0"/>\n'
        '    <metadata key="thumbnail_file" value="Metadata/plate_1.png"/>\n'
        '    <metadata key="thumbnail_no_light_file" value="Metadata/plate_no_light_1.png"/>\n'
        '    <metadata key="top_file" value="Metadata/top_1.png"/>\n'
        '    <metadata key="pick_file" value="Metadata/pick_1.png"/>\n'
        '    <model_instance>\n'
        '      <metadata key="object_id" value="3"/>\n'
        '      <metadata key="instance_id" value="0"/>\n'
        '      <metadata key="identify_id" value="165"/>\n'
        '    </model_instance>\n'
        '  </plate>\n'
        '  <assemble>\n'
        '   <assemble_item object_id="3" instance_id="0"'
        f' transform="1 0 0 0 1 0 0 0 1 180 0 10" offset="0 0 0" />\n'
        '  </assemble>\n'
        '</config>'
    )

    # ---- Static metadata files ----
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        '<Default Extension="rels" ContentType='
        '"application/vnd.openxmlformats-package.relationships+xml"/>\n'
        '<Default Extension="model" ContentType='
        '"application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
        '</Types>'
    )

    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '<Relationship Target="/3D/3dmodel.model" Id="rel-1"'
        ' Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
        '</Relationships>'
    )

    model_rels = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '<Relationship Target="/3D/Objects/object_3.model" Id="rel-1"'
        ' Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
        '</Relationships>'
    )

    slice_info = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<config>\n'
        '  <header>\n'
        '    <header_item key="X-BBL-Client-Type" value="slicer"/>\n'
        '    <header_item key="X-BBL-Client-Version" value="02.05.00.66"/>\n'
        '  </header>\n'
        '</config>'
    )

    cut_info = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<objects>\n'
        ' <object id="1">\n'
        '  <cut_id id="0" check_sum="1" connectors_cnt="0"/>\n'
        ' </object>\n'
        '</objects>'
    )

    plate_json_data = {
        "bbox_all": [
            plate_x - base_center[0],
            plate_y - base_center[1],
            plate_x + base_center[0],
            plate_y + base_center[1]
        ],
        "bbox_objects": [{
            "area": (base_center[0] * 2) * (base_center[1] * 2),
            "bbox": [
                plate_x - base_center[0],
                plate_y - base_center[1],
                plate_x + base_center[0],
                plate_y + base_center[1]
            ],
            "id": 287,
            "layer_height": 0.2,
            "name": base_name
        }],
        "bed_type": "textured_plate",
        "filament_colors": [],
        "filament_ids": [],
        "first_extruder": 0,
        "first_layer_time": 222.3,
        "is_seq_print": False,
        "nozzle_diameter": 0.4,
        "version": 2
    }

    # Package into 3MF (ZIP)
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', content_types)
        zf.writestr('_rels/.rels', rels)
        zf.writestr('3D/3dmodel.model', main_model)
        zf.writestr('3D/_rels/3dmodel.model.rels', model_rels)
        zf.writestr('3D/Objects/object_3.model', object_model)
        zf.writestr('Metadata/model_settings.config', model_settings)
        zf.writestr('Metadata/slice_info.config', slice_info)
        zf.writestr('Metadata/cut_information.xml', cut_info)
        zf.writestr('Metadata/plate_1.json', json.dumps(plate_json_data))
        zf.writestr('Metadata/filament_sequence.json',
                     '{"plate_1":{"sequence":[]}}')

        # Include project settings if available (preserves printer config)
        if project_settings_path and os.path.exists(project_settings_path):
            with open(project_settings_path, 'r') as f:
                zf.writestr('Metadata/project_settings.config', f.read())

    print(f"Generated 3MF: {output_path}")


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <base.stl> <bars.stl> <output.3mf>"
              " [display_name] [project_settings.config]")
        sys.exit(1)

    base_stl = sys.argv[1]
    bars_stl = sys.argv[2]
    output = sys.argv[3]
    name = sys.argv[4] if len(sys.argv) > 4 else "GitLab Skyline"
    settings = sys.argv[5] if len(sys.argv) > 5 else None

    generate_3mf(base_stl, bars_stl, output, name, settings)
