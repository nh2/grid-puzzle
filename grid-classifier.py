import math
import json

from PIL import Image
import numpy as np


def read_grid(input_filepath, grid_offset_pixels, grid_spacing_pixels, drop_tiles, num_out_x, num_out_y):
    grid_offset_x, grid_offset_y = grid_offset_pixels
    grid_spacing_x, grid_spacing_y = grid_spacing_pixels
    drop_tiles_x, drop_tiles_y = drop_tiles

    img = Image.open(input_filepath)
    img.load()
    # Note [numpy-image-coordinates]
    # Note the numpy indexing representation has the X/Y axes swapped,
    # see: https://stackoverflow.com/questions/49720605/pixel-coordinates-vs-drawing-coordinates
    data = np.asarray(img, dtype="bool")  # black is False, white is True

    print(data)
    print(data.shape)
    dim_y, dim_x = data.shape  # see note [numpy-image-coordinates]

    x_rows = []
    for y_index in range(num_out_y):
        x_row = []  # 1 row, that is, along the x axis
        print(f"{y_index=}")
        for x_index in range(num_out_x):
            x_index_off = x_index + drop_tiles_x
            y_index_off = y_index + drop_tiles_y
            x = max(0, int(x_index_off * grid_spacing_x + grid_offset_x))
            y = max(0, int(y_index_off * grid_spacing_y + grid_offset_y))
            x_end = min(dim_x-1, int((x_index_off + 1) * grid_spacing_x + grid_offset_x))
            y_end = min(dim_y-1, int((y_index_off + 1) * grid_spacing_y + grid_offset_y))
            region = data[y:y_end, x:x_end]  # see note [numpy-image-coordinates]
            is_occupied = bool(np.any(np.logical_not(region)))
            x_row.append(is_occupied)
        x_rows.append(x_row)
    return x_rows


def main():
    tiles_x = 56
    tiles_y = 57

    input_filepath = "input-images/traced-1-horiz-gridded-bw.png"
    grid_offset_pixels = (3, 2)
    grid_spacing_pixels = (9.95, 9.95)
    drop_tiles = (2, 0)
    num_out_x = tiles_y
    num_out_y = tiles_x + 1
    gaps_horiz = read_grid(input_filepath, grid_offset_pixels, grid_spacing_pixels, drop_tiles, num_out_x, num_out_y)

    # ASCII art debug print
    # for lane in gaps_horiz:
    #     print(''.join(' | ' if o else '   ' for o in lane))

    input_filepath = "input-images/traced-1-vert-gridded-bw.png"
    grid_offset_pixels = (-3, -2)
    grid_spacing_pixels = (9.95, 9.95)
    drop_tiles = (3, 0)
    num_out_x = tiles_x
    num_out_y = tiles_y + 1
    gaps_vert_transposed = read_grid(input_filepath, grid_offset_pixels, grid_spacing_pixels, drop_tiles, num_out_x, num_out_y)
    gaps_vert = list(map(list, zip(*gaps_vert_transposed)))  # tanspose, see https://stackoverflow.com/questions/6473679/transpose-list-of-lists

    # ASCII art debug print
    lines = []
    for y in range(len(gaps_vert[0])):
        print(''.join(' - ' if gaps_vert[x][y] else '   ' for x in range(len(gaps_vert))))

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
