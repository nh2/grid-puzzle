import math
import json

from PIL import Image
import numpy as np


def read_grid(input_filepath, grid_offset_pixels, grid_spacing_pixels, drop_tiles, num_lanes, num_offsets):
    grid_offset_x, grid_offset_y = grid_offset_pixels
    grid_spacing_x, grid_spacing_y = grid_spacing_pixels
    drop_tiles_x, drop_tiles_y = drop_tiles

    img = Image.open(input_filepath)
    img.load()
    # Note the numpy indexing representation has the X/Y axes swapped,
    # see: https://stackoverflow.com/questions/49720605/pixel-coordinates-vs-drawing-coordinates
    data = np.asarray(img, dtype="bool")  # black is False, white is True

    print(data)
    print(data.shape)

    gaps = []
    for x_index in range(num_lanes):
        lane = []
        print(f"{x_index=}")
        for y_index in range(num_offsets):
            x_index_off = x_index + drop_tiles_x
            y_index_off = y_index + drop_tiles_y
            x = int(x_index_off * grid_spacing_x + grid_offset_x)
            y = int(y_index_off * grid_spacing_y + grid_offset_y)
            x_end = int((x_index_off + 1) * grid_spacing_x + grid_offset_x)
            y_end = int((y_index_off + 1) * grid_spacing_y + grid_offset_y)
            region = data[x:x_end, y:y_end]
            is_occupied = bool(np.any(np.logical_not(region)))
            # print(x_index_off, y_index_off, is_occupied)
            # if x_index_off == 0 and y_index_off == 3:
            #     print(region)
            #     print(is_occupied)
            lane.append(is_occupied)
        gaps.append(lane)
    return gaps


def main():
    tiles_x = 56
    tiles_y = 57

    input_filepath = "/home/niklas/3d-models/mind-bending-aztec-labyrinth-puzzle/traced-1-horiz-gridded-bw.png"
    grid_offset_pixels = (3, 2)
    grid_spacing_pixels = (9.95, 9.95)
    # For horiz direction, lanes are the X axis in the image (inner for loop).
    drop_tiles = (0, 2)
    num_lanes = tiles_y
    num_offsets = tiles_x + 1
    gaps_horiz = read_grid(input_filepath, grid_offset_pixels, grid_spacing_pixels, drop_tiles, num_lanes, num_offsets)

    # for lane in gaps_horiz:
    #     print(''.join(' | ' if o else '   ' for o in lane))

    # print(len(gaps_horiz), len(gaps_horiz[0]))

    input_filepath = "/home/niklas/3d-models/mind-bending-aztec-labyrinth-puzzle/traced-1-vert-gridded-bw.png"
    grid_offset_pixels = (-3, -2)
    grid_spacing_pixels = (9.95, 9.95)
    # For vert direction, lanes are the X axis in the image.
    drop_tiles = (0, 3)
    num_lanes = tiles_y + 1
    num_offsets = tiles_x
    gaps_vert_transposed = read_grid(input_filepath, grid_offset_pixels, grid_spacing_pixels, drop_tiles, num_lanes, num_offsets)
    gaps_vert = list(map(list, zip(*gaps_vert_transposed)))  # tanspose, see https://stackoverflow.com/questions/6473679/transpose-list-of-lists

    lines = []
    for y in range(len(gaps_vert[0])):
        print(''.join(' - ' if gaps_vert[x][y] else '   ' for x in range(len(gaps_vert))))

    # print(len(gaps_vert), len(gaps_vert[0]))

    save_file_path = "field.json"
    state = {
        'horiz': gaps_horiz,
        'vert': gaps_vert,
    }
    with open(save_file_path, 'w') as f:
        json.dump(state, f, sort_keys=True, indent=2)
    print(f"Saved to {save_file_path}")


if __name__ == '__main__':
      main()
