import json

from collections import defaultdict
from dataclasses import dataclass

# solidpython
from solid import *
from solid.utils import *


def load_grid(save_file_path='field.json'):
    print(f"Loading {save_file_path}")
    with open(save_file_path, 'r') as f:
        state = json.load(f)
    return state


@dataclass
class GridSettings:
    tile_height_mm: float
    tile_side_mm: float
    frame_margin_mm: float

    gap_mm: float

    add_frame: bool

    # OpenGL render tolerance for OpenSCAD visualisation
    eps: float = 0.01


# Large size (requires 4 Ender 3 3D printer bed prints for the field without frame)
large_grid_settings = GridSettings(
    tile_height_mm = 6.0,
    tile_side_mm = 6.0,
    frame_margin_mm = 5,
    gap_mm = 0.5,
    add_frame = True,
)


# Small field size (just fits on Ender 3 3D printer bed):
small_grid_settings = GridSettings(
    tile_height_mm = 3.6,
    tile_side_mm = 3.6,
    frame_margin_mm = 3.2,
    gap_mm = 0.5,
    add_frame = True,
)


@dataclass
class Grid:
    scad_object: object
    num_tiles_x: int
    num_tiles_y: int


def makeGrid(grid_settings: GridSettings, field_file: str):

    # Destructure grid settings
    tile_height_mm = grid_settings.tile_height_mm
    tile_side_mm = grid_settings.tile_side_mm
    frame_margin_mm = grid_settings.frame_margin_mm
    gap_mm = grid_settings.gap_mm
    eps = grid_settings.eps

    tilegap_mm = tile_side_mm + gap_mm

    g = load_grid(field_file)
    horiz = g['horiz']
    vert = g['vert']

    enable_tile_limit_debug = False
    tile_limit_debug = (8, 8) if enable_tile_limit_debug else (10000, 10000)

    # Number of tiles
    NUM_TILES_X = min(tile_limit_debug[0], len(horiz[0]) - 1)
    NUM_TILES_Y = min(tile_limit_debug[1], len(vert[0]) - 1)

    print(f"{NUM_TILES_X=} {NUM_TILES_Y=}")

    # Finds direct neighbors of a tile, no matter if connected or not (thus up to 4).
    def direct_neighbor_tiles(tile):
        x, y = tile
        neighbors = []
        if x > 0              : neighbors.append((x-1, y  ))
        if x < NUM_TILES_X - 1: neighbors.append((x+1, y  ))
        if y > 0              : neighbors.append((x,   y-1))
        if y < NUM_TILES_Y - 1: neighbors.append((x,   y+1))
        return neighbors

    # Finds direct neighbors of a tile, connected by closed cap (thus up to 4).
    def connected_direct_neighbor_tiles(tile):
        x, y = tile
        neighbors = []
        #                      not (gap_active?)
        if x > 0               and not horiz[y][x  ]: neighbors.append((x-1, y  ))
        if x < NUM_TILES_X - 1 and not horiz[y][x+1]: neighbors.append((x+1, y  ))
        if y > 0               and not vert [x][y  ]: neighbors.append((x,   y-1))
        if y < NUM_TILES_Y - 1 and not vert [x][y+1]: neighbors.append((x,   y+1))
        return neighbors

    # Connected components algorithm:
    # We need to know which tiles are connected together in a "piece"
    # (including which gaps and corners belong to them) such that we
    # can e.g. give each piece a separate colour.
    # Conceptually, the field is an undirected graph, in which
    # {tiles, gaps, corners} all are nodes, and an edge exists between:
    # * a tile and a gap if and only if the corresponding field gap is active;
    # * a gap and a corner if and only if the corresponding field gap is active.
    # Computing connected components on this computes the puzzle pieces,
    # and the frame piece.
    # Equivalently, and simpler (which we do here):
    #
    # Floodfill:
    #
    # Keep a stack or queue of tiles to visit next,
    # and remember for each tile if it was already visited.
    # Iterate over all tiles.
    # * If the tile was already visited, skip it.
    # * Otherwise, create a new piece stack; add the tile to it.
    #   While the stack isn't empty:
    #     * Pop a tile from it; mark it as visited.
    #       Find all direct neighbor tiles connected by a closed gap;
    #       add those to the stack.
    #   All tiles that were added to (and thus popped from) the stack
    #   constitute a puzzle piece.
    visited_tiles = set()  # set of tiles; each tile is a (x, y) coordinate
    def floodfill_piece_from(start_tile):
        piece = []  # list of tiles
        stack = [start_tile]
        while len(stack) > 0:
            tile = stack.pop()
            visited_tiles.add(tile)
            piece.append(tile)
            neighbors = connected_direct_neighbor_tiles(tile)
            stack += [n for n in neighbors if n not in visited_tiles]
        return piece

    # Determine pieces by floodfilling.
    pieces = []  # list of tiles; each tile is a (x, y) coordinate
    for x in range(NUM_TILES_X):
        for y in range(NUM_TILES_Y):
            tile = (x, y)
            if tile not in visited_tiles:
                piece = floodfill_piece_from(tile)
                pieces.append(piece)

    print(f"Num pieces: {len(pieces)}")

    tile_to_piece_id_map = {
        tile: piece_id
        for piece_id, piece in enumerate(pieces)
        for tile in piece
    }

    # Find which pieces border each other.
    bordering_pieces_map = defaultdict(set)  # map of `piece_id` to set of bordering piece IDs
    for x in range(NUM_TILES_X):
        for y in range(NUM_TILES_Y):
            tile = (x, y)
            piece_id = tile_to_piece_id_map[tile]
            for n in direct_neighbor_tiles(tile):
                neighbor_piece_id = tile_to_piece_id_map[n]
                if neighbor_piece_id != piece_id:
                    bordering_pieces_map[piece_id].add(neighbor_piece_id)
                    bordering_pieces_map[neighbor_piece_id].add(piece_id)

    def rainbow_stop_rgb(h: float):  # input: [0, 1.0]; output: triple (r, g, b)
        # Inspired by http://blog.adamcole.ca/2011/11/simple-javascript-rainbow-color.html
        def f(n):
            k = (n + h * 12) % 12
            return .5 - .5 * max(min(k - 3, 9 - k, 1), -1)
        return (f(0), f(8), f(4))

    # Coloring:
    # Assign colors to pieces so that nearby pieces don't have similar colors.
    piece_color_map = {}  # input: `piece_id`; output: triple (r, g, b)
    # The "Four color theorem" states there's always a way to use only 4 colors,
    # but finding the color assignment is O(n^2):
    # * https://en.wikipedia.org/wiki/Four_color_theorem#Simplification_and_verification
    # * https://thomas.math.gatech.edu/PAP/fcstoc.pdf
    # So we make up new colors as necessary, to make it log-linear.
    num_used_colors = 0
    for piece_id, _ in enumerate(pieces):
        bordering_colors = {piece_color_map.get(b) for b in bordering_pieces_map[piece_id]}
        used_existing_color = False
        for c in range(num_used_colors):
            if c not in bordering_colors:
                piece_color_map[piece_id] = c
                used_existing_color = True
                break
        if not used_existing_color:
            piece_color_map[piece_id] = num_used_colors
            num_used_colors += 1

    print(f"Colors needed for pieces: {num_used_colors}")

    def tile_piece_color(tile, o):
        piece_id = tile_to_piece_id_map[tile]
        color_id = piece_color_map[piece_id]
        return color(list(rainbow_stop_rgb(color_id / num_used_colors)))(o)


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
            tile_objects.append(tile_piece_color((x,y), o))

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

    eps = 0.02

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

    unioned = union()(
        *tile_objects,
        *gap_objects,
        *gap_corner_objects,
        *(positioned_frame_objects if grid_settings.add_frame else []),
    )
    return Grid(
        scad_object=unioned,
        num_tiles_x=NUM_TILES_X,
        num_tiles_y=NUM_TILES_Y,
    )


def main():
    grid_settings = large_grid_settings
    # grid_settings = small_grid_settings

    puzzle_grid = makeGrid(grid_settings, field_file='field.json')

    # Scale frame bottom, because because it is designed without
    # frame and we cannot add a frame because then the bottom would
    # not be separate pieces as desired.
    # It's not great, perhaps I should rather have designed it so that
    # the frame is part of the puzzle already in the puzzle editor.
    puzzle_width_without_frame_x = (
        puzzle_grid.num_tiles_x * grid_settings.tile_side_mm
        +
        (puzzle_grid.num_tiles_x + 1) * grid_settings.gap_mm
    )
    puzzle_width_without_frame_y = (
        puzzle_grid.num_tiles_y * grid_settings.tile_side_mm
        +
        (puzzle_grid.num_tiles_y + 1) * grid_settings.gap_mm
    )
    puzzle_width_with_frame_x = puzzle_width_without_frame_x + 2 * grid_settings.frame_margin_mm
    puzzle_width_with_frame_y = puzzle_width_without_frame_y + 2 * grid_settings.frame_margin_mm
    frame_scale_x = puzzle_width_with_frame_x / puzzle_width_without_frame_x
    frame_scale_y = puzzle_width_with_frame_y / puzzle_width_without_frame_y

    frame_grid_settings = grid_settings
    frame_grid_settings.add_frame = False
    frame_grid = makeGrid(frame_grid_settings, field_file='fields/field-frame-lower.json')
    frame = color([0,1,0])(
        translate([0,0,-frame_grid_settings.tile_height_mm])(
            translate([-frame_grid_settings.frame_margin_mm, -frame_grid_settings.frame_margin_mm, 0])(
                scale([frame_scale_y, frame_scale_y, 1])(
                    frame_grid.scad_object
                )
            )
        )
    )

    puzzle_with_frame = union()(
        puzzle_grid.scad_object,
        frame,
    )

    scad_render_to_file(puzzle_with_frame, "puzzle.scad")


if __name__ == '__main__':
    main()
