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

    tile_height_mm = 5
    tile_side_mm = 5
    gap_mm = 0.8
    tilegap_mm = tile_side_mm + gap_mm

    g = load_grid()
    horiz = g['horiz']
    vert = g['vert']
    # Number of tiles
    NUM_TILES_X = len(horiz[0]) - 1
    NUM_TILES_Y = len(vert[0]) - 1

    print(f"{NUM_TILES_X=} {NUM_TILES_Y=}")

    # Coordinate spaces:
    #
    # * In the puzzle field, the top left corner is (0,0),
    #   downwards is +Y and right is +X.
    # * In OpenScad, we make the puzzle top left corner be at (0,0,0),
    #   downards is +X and right is +Y.
    #   We do that so that Y is up in openscad.

    # Tiles
    objects = []
    for x in range(NUM_TILES_X):
        for y in range(NUM_TILES_Y):
            o = translate([y * tilegap_mm, x * tilegap_mm, 0])(
                    cube([tile_side_mm, tile_side_mm, tile_height_mm])
                )
            objects.append(o)

    # Gaps
    for y, lane in enumerate(horiz):
        for x, gap_active in enumerate(lane):
            if not gap_active:
                o = translate([y * tilegap_mm, x * tilegap_mm - gap_mm, 0])(
                        cube([tile_side_mm, gap_mm, tile_height_mm])
                    )
                objects.append(o)
    for x, lane in enumerate(vert):
        for y, gap_active in enumerate(lane):
            if not gap_active:
                print(f"{x=} {y=}")
                o = translate([y * tilegap_mm - gap_mm, x * tilegap_mm, 0])(
                        cube([gap_mm, tile_side_mm, tile_height_mm])
                    )
                objects.append(o)

    d = union()(
        *objects
    )

    scad_render_to_file(d, "puzzle.scad")


if __name__ == '__main__':
    main()
