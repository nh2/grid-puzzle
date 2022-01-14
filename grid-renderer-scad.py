import json

from dataclasses import dataclass

# solidpython
from solid import *
from solid.utils import *


def load_grid():
    save_file_path = 'field.json'
    print(f"Loading {save_file_path}")
    with open(save_file_path, 'r') as f:
        state = json.load(f)
    return state



def main():

    # Large size (requires 4 Ender 3 3D printer bed prints for the field without frame)
    tile_height_mm = 6.0
    tile_side_mm = 6.0
    frame_margin_mm = 5

    # Small field size (just fits on Ender 3 3D printer bed):
    # tile_height_mm = 3.6
    # tile_side_mm = 3.6
    # frame_margin_mm = 3.2

    gap_mm = 0.5

    eps = 0.01  # OpenGL render tolerance for OpenSCAD visualisation

    tilegap_mm = tile_side_mm + gap_mm

    g = load_grid()
    horiz = g['horiz']
    vert = g['vert']

    enable_tile_limit_debug = False
    tile_limit_debug = (8, 8) if enable_tile_limit_debug else (10000, 10000)

    # Number of tiles
    NUM_TILES_X = min(tile_limit_debug[0], len(horiz[0]) - 1)
    NUM_TILES_Y = min(tile_limit_debug[1], len(vert[0]) - 1)

    print(f"{NUM_TILES_X=} {NUM_TILES_Y=}")

    # Note [Coordinate spaces]:
    #
    # * In the puzzle field, the top left corner is (0,0),
    #   downwards is +Y and right is +X.
    # * In OpenScad, we make the puzzle top left corner be at (0,0,0),
    #   downards is +X and right is +Y.
    #   We do that so that Y is up in openscad.

    # Tiles
    tile_objects = []
    for x in range(NUM_TILES_X):
        for y in range(NUM_TILES_Y):
            o = translate([y * tilegap_mm, x * tilegap_mm, 0])(
                    cube([tile_side_mm, tile_side_mm, tile_height_mm])
                )
            tile_objects.append(o)

    # Closed gaps
    gap_objects = []
    for y, lane in enumerate(horiz):
        for x, gap_active in enumerate(lane):
            if x >= tile_limit_debug[0]+1 or y >= tile_limit_debug[1]: break
            if not gap_active:  # render gap
                o = translate([y * tilegap_mm, x * tilegap_mm - gap_mm, 0])(
                        cube([tile_side_mm, gap_mm, tile_height_mm])
                    )
                gap_objects.append(o)
    for x, lane in enumerate(vert):
        for y, gap_active in enumerate(lane):
            if x >= tile_limit_debug[0] or y >= tile_limit_debug[1]+1: break
            if not gap_active:  # render gap
                o = translate([y * tilegap_mm - gap_mm, x * tilegap_mm, 0])(
                        cube([gap_mm, tile_side_mm, tile_height_mm])
                    )
                gap_objects.append(o)
    # Gap corner hole fillers (small hole between 4 closed gaps)
    gap_corner_objects = []
    for x in range(NUM_TILES_X + 1):
        for y in range(NUM_TILES_Y + 1):
            any_adjacent_gap_active = any([
                (y != 0           and horiz[y-1][x  ]),  # Gap above
                (y != NUM_TILES_Y and horiz[y  ][x  ]),  # Gap below
                (x != 0           and vert [x-1][y  ]),  # Gap left
                (x != NUM_TILES_X and vert [x  ][y  ]),  # Gap right
            ])
            o = translate([y * tilegap_mm - gap_mm, x * tilegap_mm - gap_mm, 0])(
                    cube([gap_mm, gap_mm, tile_height_mm])
                )
            if not any_adjacent_gap_active:
                gap_corner_objects.append(o)

    # Frame
    frame_hole_width_x = NUM_TILES_Y * tilegap_mm + gap_mm  # see note [Coordinate spaces]
    frame_hole_width_y = NUM_TILES_X * tilegap_mm + gap_mm
    frame_hole = translate([0,0,-eps])(cube([
        frame_hole_width_x,
        frame_hole_width_y,
        tile_height_mm + 2*eps,
    ]))
    frame = cube([
        frame_hole_width_x + 2*frame_margin_mm,
        frame_hole_width_y + 2*frame_margin_mm,
        tile_height_mm,
    ]) - translate([frame_margin_mm, frame_margin_mm, 0])(frame_hole)
    positioned_frame = translate([
        -frame_margin_mm - gap_mm,
        -frame_margin_mm - gap_mm,
        0,
    ])(frame)
    positioned_frame_objects = [
        color([1,0,0])(translate([0,0,-eps])(positioned_frame))
    ]

    d = union()(
        *tile_objects,
        *gap_objects,
        *gap_corner_objects,
        *positioned_frame_objects,
    )

    scad_render_to_file(d, "puzzle.scad")


if __name__ == '__main__':
    main()
