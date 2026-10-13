import os
from pathlib import Path
import struct, math, hashlib
from typing import Iterable


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def grid_arrays(grid: dict) -> dict:
    nx, ny, nz = (int(grid[k]) for k in ('nx', 'ny', 'nz'))
    dx, dy = grid['dx_m'], grid['dy_m']
    dz = [grid['first_dz_m'] * grid['vertical_stretch'] ** k for k in range(nz)]
    faces = [float(grid['terrain_height_m'])]
    for depth in dz:
        faces.append(faces[-1] + depth)
    # Match GUI float32 geometry while retaining mutually consistent dz and centers.
    faces = [round(value, 2) for value in faces]
    dz = [faces[k + 1] - faces[k] for k in range(nz)]
    centers = [(faces[k] + faces[k + 1]) * 0.5 for k in range(nz)]
    return {'nx': nx, 'ny': ny, 'nz': nz, 'dx_m': dx, 'dy_m': dy,
            'dz_m': dz, 'z_interfaces_m': faces, 'z_centers_m': centers,
            'x_interfaces_m': [i * dx for i in range(nx + 1)],
            'y_interfaces_m': [j * dy for j in range(ny + 1)]}

def write_geometry(path: Path, grid: dict) -> dict:
    """Binary sequence mirrors GUI IO_GGEOM.cs and engine GRID.cs."""
    g = grid_arrays(grid)
    nx, ny, nz = g['nx'], g['ny'], g['nz']
    dx, dy = g['dx_m'], g['dy_m']
    dz, zsp, z = g['dz_m'], g['z_centers_m'], g['z_interfaces_m']
    blocks = []
    with path.open('xb') as stream:
        stream.write(b'-99 \r\n')
        stream.write(struct.pack('<iii', nx, ny, nz))
        def floats(name: str, values: Iterable[float]) -> None:
            data = list(values)
            blocks.append({'name': name, 'offset_bytes': stream.tell(), 'count': len(data)})
            stream.write(struct.pack('<' + 'f' * len(data), *data))
        floats('AH', [grid['terrain_height_m']] * (nx * ny))
        floats('ZSP', (zsp[k] for k in range(nz) for j in range(ny) for i in range(nx)))
        floats('X', g['x_interfaces_m'])
        floats('Y', g['y_interfaces_m'])
        floats('Z', z)
        floats('VOL', (dx * dy * dz[k] for k in range(nz) for j in range(ny) for i in range(nx)))
        floats('AREAX', (dy * dz[k] for k in range(nz) for j in range(ny) for i in range(nx + 1)))
        floats('AREAY', (dx * dz[k] for k in range(nz) for j in range(ny + 1) for i in range(nx)))
        floats('AREAZX', [0.0] * (nx * ny * (nz + 1)))
        floats('AREAZY', [0.0] * (nx * ny * (nz + 1)))
        floats('AREAZ', [dx * dy] * (nx * ny * (nz + 1)))
        floats('DDX', [dx] * nx)
        floats('DDY', [dy] * ny)
        floats('ZAX', [dx] * nx)
        floats('ZAY', [dy] * ny)
        stream.write(struct.pack('<iid', grid['west_m'], grid['south_m'], 0.0))
        floats('AHE', (z[k] for k in range(nz + 1) for j in range(ny + 1) for i in range(nx + 1)))
    return {'blocks': blocks, 'geometry': g}

def validate_geometry(path: Path, grid: dict) -> dict:
    """Decode the written binary independently and check geometry identities."""
    raw = path.read_bytes()
    if raw[:6] != b'-99 \r\n':
        raise ValueError('Invalid ggeom binary header')
    nx, ny, nz = struct.unpack_from('<iii', raw, 6)
    if (nx, ny, nz) != tuple(grid[k] for k in ('nx', 'ny', 'nz')):
        raise ValueError('Geometry dimension mismatch')
    offset = 18
    arrays = {}
    counts = [('AH', nx * ny), ('ZSP', nx * ny * nz), ('X', nx + 1), ('Y', ny + 1),
              ('Z', nz + 1), ('VOL', nx * ny * nz), ('AREAX', (nx + 1) * ny * nz),
              ('AREAY', nx * (ny + 1) * nz), ('AREAZX', nx * ny * (nz + 1)),
              ('AREAZY', nx * ny * (nz + 1)), ('AREAZ', nx * ny * (nz + 1)),
              ('DDX', nx), ('DDY', ny), ('ZAX', nx), ('ZAY', ny)]
    for name, count in counts:
        arrays[name] = struct.unpack_from('<' + 'f' * count, raw, offset)
        offset += count * 4
        if not all(math.isfinite(value) for value in arrays[name]):
            raise ValueError('Nonfinite geometry: ' + name)
    west, south, angle = struct.unpack_from('<iid', raw, offset)
    offset += 16
    count = (nx + 1) * (ny + 1) * (nz + 1)
    ahe = struct.unpack_from('<' + 'f' * count, raw, offset)
    offset += count * 4
    if offset != len(raw):
        raise ValueError('Unexpected geometry trailing data')
    checks = {
        'dimensions': (nx, ny, nz) == tuple(grid[k] for k in ('nx', 'ny', 'nz')),
        'flat_zero_terrain': all(v == grid['terrain_height_m'] for v in arrays['AH']),
        'positive_volumes': min(arrays['VOL']) > 0,
        'positive_face_areas': all(min(arrays[k]) > 0 for k in ('AREAX', 'AREAY', 'AREAZ')),
        'zero_slope_projections': all(v == 0 for k in ('AREAZX', 'AREAZY') for v in arrays[k]),
        'strict_vertical_order': all(a < b for a, b in zip(arrays['Z'], arrays['Z'][1:])),
        'coordinate_origin': (west, south, angle) == (grid['west_m'], grid['south_m'], 0),
        'full_stream_consumed': offset == len(raw),
        'center_y_outside_six_cell_border': ny > 12,
    }
    for k in range(nz):
        depth = arrays['Z'][k + 1] - arrays['Z'][k]
        center = (arrays['Z'][k + 1] + arrays['Z'][k]) / 2
        checks[f'layer_{k + 1}_center_volume'] = all(
            math.isclose(v, center, abs_tol=0.002) for v in arrays['ZSP'][k * nx * ny:(k + 1) * nx * ny]
        ) and all(math.isclose(v, grid['dx_m'] * grid['dy_m'] * depth, rel_tol=2e-6)
                  for v in arrays['VOL'][k * nx * ny:(k + 1) * nx * ny])
    for k in range(nz + 1):
        slab = ahe[k * (nx + 1) * (ny + 1):(k + 1) * (nx + 1) * (ny + 1)]
        checks[f'interface_{k}_flat'] = all(v == arrays['Z'][k] for v in slab)
    if not all(checks.values()):
        raise ValueError('Geometry validation failed: ' + str([k for k, v in checks.items() if not v]))
    return {'status': 'pass', 'checks': checks, 'bytes': len(raw), 'sha256': sha256(path),
            'domain_width_m': nx * grid['dx_m'], 'domain_length_m': ny * grid['dy_m'],
            'domain_top_m': arrays['Z'][-1], 'lowest_center_m': arrays['ZSP'][0],
            'top_nudging_lowest_center_m': arrays['ZSP'][(nz - 4) * nx * ny],
            'interior_after_six_cell_border_xy': [nx - 12, ny - 12],
            'scope': 'binary layout, geometric identities, and border clearance; not solver or scientific validity'}