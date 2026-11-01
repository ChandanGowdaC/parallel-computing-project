#!/usr/bin/env python3
"""
tile_maps.py — Generates constant-density tiled warehouse maps for scaling experiments.
"""
import os

def tile_kiva(src_path, dst_path, tiles_r, tiles_c):
    with open(src_path) as f:
        lines = [l.strip() for l in f if l.strip()]
    rows, cols = map(int, lines[0].split(","))
    num_endpoints = int(lines[1])
    num_home = int(lines[2])
    maxtime = int(lines[3])
    grid = lines[4:4+rows]

    new_rows = rows * tiles_r
    new_cols = cols * tiles_c
    new_endpoints = num_endpoints * tiles_r * tiles_c
    new_home = num_home * tiles_r * tiles_c

    new_grid = []
    for tr in range(tiles_r):
        for r in range(rows):
            row_str = ""
            for tc in range(tiles_c):
                row_str += grid[r]
            new_grid.append(row_str)

    os.makedirs(os.path.dirname(os.path.abspath(dst_path)), exist_ok=True)
    with open(dst_path, "w") as f:
        f.write(f"{new_rows},{new_cols}\n")
        f.write(f"{new_endpoints}\n")
        f.write(f"{new_home}\n")
        f.write(f"{maxtime}\n")
        for r_str in new_grid:
            f.write(r_str + "\n")
    print(f"Generated {dst_path}: {new_rows}x{new_cols} (cells={new_rows*new_cols}), endpoints={new_endpoints}, home={new_home}")

if __name__ == "__main__":
    tile_kiva("maps/kiva.map", "maps/tiled/kiva_1x1.map", 1, 1)
    tile_kiva("maps/kiva.map", "maps/tiled/kiva_2x1.map", 2, 1)
    tile_kiva("maps/kiva.map", "maps/tiled/kiva_2x2.map", 2, 2)
    tile_kiva("maps/kiva.map", "maps/tiled/kiva_4x2.map", 4, 2)
    tile_kiva("maps/kiva.map", "maps/tiled/kiva_4x4.map", 4, 4)
