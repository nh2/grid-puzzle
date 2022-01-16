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

    gap_mm: float

    # OpenGL render tolerance for OpenSCAD visualisation
    eps: float = 0.01


# Large size (requires 4 Ender 3 3D printer bed prints for the field without frame)
large_grid_settings = GridSettings(
    tile_height_mm = 6.0,
    tile_side_mm = 6.0,
    gap_mm = 0.5,
)


# Small field size (just fits on Ender 3 3D printer bed):
small_grid_settings = GridSettings(
    tile_height_mm = 3.6,
    tile_side_mm = 3.6,
    gap_mm = 0.5,
)


@dataclass
class Grid:
    piece_objects: [object]  # all connected pieces as SCAD objects
    tile_to_piece_id_map: dict
    num_tiles_x: int
    num_tiles_y: int


def makeGrid(grid_settings: GridSettings, field_file: str):

    # Destructure grid settings
    tile_height_mm = grid_settings.tile_height_mm
    tile_side_mm = grid_settings.tile_side_mm
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
    # including the frame piece.
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

    def piece_color(piece_id):
        color_id = piece_color_map[piece_id]
        return rainbow_stop_rgb(color_id / num_used_colors)

    def tile_piece_color_object(tile, o):
        return color(list(piece_color(tile_to_piece_id_map[tile])))(o)


    # Note [Coordinate spaces]:
    #
    # * In the puzzle field, the top left corner is (0,0),
    #   downwards is +Y and right is +X.
    # * In OpenScad, we make the puzzle top left corner be at (0,0,0),
    #   downards is +X and right is +Y.
    #   We do that so that Y is up in openscad.

    # Generate SCAD objects for each piece
    piece_tile_objects = []  # maps from piece_id to SCAD objects
    for piece_id, tiles in enumerate(pieces):

        # Tiles
        tile_objects = []
        for tile in tiles:
            x, y = tile
            o = translate([y * tilegap_mm, x * tilegap_mm, 0])(
                    cube([tile_side_mm, tile_side_mm, tile_height_mm])
                )
            tile_objects.append(tile_piece_color_object(tile, o))
        piece_tile_objects.append(tile_objects)

    # Helper functions to map gaps and gap corners to pieces:
    #
    # If a gap is closed, the tiles on either side of it belong to the same piece.
    # So we can determine the piece_id that the closed gap belongs to
    # from either side, except fro the first/last gap in the lane, since
    # that has a tile on only one of the sides.
    def piece_id_of_horiz_gap(x, y):
        tile = (
            x if x < NUM_TILES_X - 1 else x-1,
            y,
        )
        return tile_to_piece_id_map[tile]
    def piece_id_of_vert_gap(x, y):
        tile = (
            x,
            y if y < NUM_TILES_Y - 1 else y-1,
        )
        return tile_to_piece_id_map[tile]
    def piece_id_of_gap_corner(x, y):
        tile = (
            x if x < NUM_TILES_X - 1 else x-1,
            y if y < NUM_TILES_Y - 1 else y-1,
        )
        return tile_to_piece_id_map[tile]

    # Closed gaps
    # We need to add each closed gap to the piece it belongs to.
    gap_objects = []
    piece_gap_objects = defaultdict(list)
    for y, lane in enumerate(horiz):
        for x, gap_active in enumerate(lane):
            if x >= tile_limit_debug[0]+1 or y >= tile_limit_debug[1]: break
            if not gap_active:  # render gap
                o = translate([y * tilegap_mm, x * tilegap_mm - gap_mm, 0])(
                        cube([tile_side_mm, gap_mm, tile_height_mm])
                    )
                piece_gap_objects[piece_id_of_horiz_gap(x, y)].append(o)
    for x, lane in enumerate(vert):
        for y, gap_active in enumerate(lane):
            if x >= tile_limit_debug[0] or y >= tile_limit_debug[1]+1: break
            if not gap_active:  # render gap
                o = translate([y * tilegap_mm - gap_mm, x * tilegap_mm, 0])(
                        cube([gap_mm, tile_side_mm, tile_height_mm])
                    )
                piece_gap_objects[piece_id_of_vert_gap(x, y)].append(o)
    # Gap corner hole fillers (small hole between 4 closed gaps)
    piece_gap_corner_objects = defaultdict(list)
    for x in range(NUM_TILES_X + 1):
        for y in range(NUM_TILES_Y + 1):
            any_adjacent_gap_active = any([
                (y != 0           and horiz[y-1][x  ]),  # Gap above
                (y != NUM_TILES_Y and horiz[y  ][x  ]),  # Gap below
                (x != 0           and vert [x-1][y  ]),  # Gap left
                (x != NUM_TILES_X and vert [x  ][y  ]),  # Gap right
            ])
            if not any_adjacent_gap_active:
                o = translate([y * tilegap_mm - gap_mm, x * tilegap_mm - gap_mm, 0])(
                        cube([gap_mm, gap_mm, tile_height_mm])
                    )
                piece_gap_corner_objects[piece_id_of_gap_corner(x, y)].append(o)

    # Add non-tile SCAD objects to the piece SCAD objects,
    # unioned together by what they are so we can more easily colorize
    # them different for debugging.
    piece_objects = []
    for piece_id, _ in enumerate(pieces):
        piece_object = union()(
            *piece_tile_objects[piece_id],
            *piece_gap_objects[piece_id],
            *piece_gap_corner_objects[piece_id],
        )
        piece_objects.append(color(list(piece_color(piece_id)))(piece_object))

    return Grid(
        piece_objects=piece_objects,
        tile_to_piece_id_map=tile_to_piece_id_map,
        num_tiles_x=NUM_TILES_X,
        num_tiles_y=NUM_TILES_Y,
    )


def dict_key_with_max_value(d):
    return max(d, key=d.get)


def main():
    grid_settings = large_grid_settings
    # grid_settings = small_grid_settings

    puzzle_grid = makeGrid(grid_settings, field_file='fields/field-manual-3-custom-5-complete-th-with-frame.json')

    if len(puzzle_grid.piece_objects) == 0:
        raise Exception("Empty puzzle objects")

    lower_frame_grid_settings = grid_settings
    lower_frame_grid_settings.add_frame = False
    lower_frame_grid = makeGrid(lower_frame_grid_settings, field_file='fields/field-frame-lower.json')

    # If enabled, don't join upper and lower frame parts into joint SCAD objects.
    # That is for a simpler rendering/debugging.
    SEPARATE_LAYER_OBJECTS = False

    puzzle_with_frame = None  # both `if` branches assign this

    if SEPARATE_LAYER_OBJECTS:
        frame = color([0,1,0])(
            translate([0,0,-lower_frame_grid_settings.tile_height_mm])(
                union()(
                    *lower_frame_grid.piece_objects,
                )
            )
        )

        puzzle_with_frame = union()(
            *puzzle_grid.piece_objects,
            frame,
        )
    else:
        # Find the pieces in the puzzle that constitute the upper frame,
        # that is, all pieces in which an outermost tile partitipates.
        # For each one find the corresponding lower frame piece with the
        # most overlap in outermost tiles.

        nx, ny = puzzle_grid.num_tiles_x, puzzle_grid.num_tiles_y
        # Find outermost tiles.
        outermost_tiles = [
            *[(x     , 0     ) for x in range(0, nx)],
            *[(x     , ny - 1) for x in range(0, nx)],
            *[(0     , y     ) for y in range(0, ny)],
            *[(nx - 1, y     ) for y in range(0, ny)],
        ]

        # Find upper frame pieces.
        upper_frame_pieces_with_tiles = defaultdict(list)  # map from `piece_id` to [tile]
        for tile in outermost_tiles:
            upper_piece_id = puzzle_grid.tile_to_piece_id_map[tile]
            upper_frame_pieces_with_tiles[upper_piece_id].append(tile)

        # For each upper frame piece, find highest-overlap lower frame piece.
        best_lower_piece_for_upper_piece = {}  # map from upper `piece_id` to lower `piece_id`
        for upper_piece_id, tiles in upper_frame_pieces_with_tiles.items():
            lower_frame_piece_overlap_counter = defaultdict(int)  # map from `piece_id` to `int`
            for tile in tiles:
                lower_piece_id = lower_frame_grid.tile_to_piece_id_map.get(tile)
                if lower_piece_id is not None:
                    lower_frame_piece_overlap_counter[lower_piece_id] += 1
            best_lower_piece_id = dict_key_with_max_value(lower_frame_piece_overlap_counter)
            best_lower_piece_for_upper_piece[upper_piece_id] = best_lower_piece_id

        # Moves a SCAD object to the lower frame's plane.
        def translate_to_lower(o):
            return translate([0, 0, -(grid_settings.tile_height_mm)])(o)

        # Get the SCAD puzzle piece objects that don't belong to the frame.
        puzzle_non_frame_objects = {  # map from `piece_id` to SCAD object
            i: o
            for i, o in enumerate(puzzle_grid.piece_objects)
            if i not in best_lower_piece_for_upper_piece
        }
        # Get the lower frame piece objects that don't belong to the circumference.
        lower_frame_non_circumference_objects = {  # map from `piece_id` to SCAD object
            i: translate_to_lower(o)
            for i, o in enumerate(lower_frame_grid.piece_objects)
            if i not in best_lower_piece_for_upper_piece.values()
        }

        # Create gap between puzzle and lower frame.
        frame_gap_vertical_mm = 1

        # Join the matching pieces as SCAD objects.
        joint_frame_objects = {  # map from `piece_id` to SCAD object
            upper_piece_id: union()(
                puzzle_grid.piece_objects[upper_piece_id],
                translate_to_lower(
                    lower_frame_grid.piece_objects[lower_piece_id],
                ),
            )
            for upper_piece_id, lower_piece_id in best_lower_piece_for_upper_piece.items()
        }

        all_objects = [  # ordered highest to lowest in the explosion rendering, if enabled below
            *puzzle_non_frame_objects.values(),
            *joint_frame_objects.values(),
            *lower_frame_non_circumference_objects.values(),
        ]

        # If true, render the objects vertically offset like an explosion diagram.
        EXPLODE = False

        puzzle_with_frame = union()(
            *(all_objects if not EXPLODE else
                [translate([0, 0, i])(obj) for i, obj in enumerate(reversed(all_objects))]
            )
        )

    scad_render_to_file(puzzle_with_frame, "puzzle.scad")


if __name__ == '__main__':
    main()
