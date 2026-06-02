"""Common vector-file format helpers for pyCCV."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

import numpy as np

_MAT_VAR_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,62}$")


def _to_numpy_map(data: Dict[str, Any]) -> Dict[str, np.ndarray]:
    clean_data: Dict[str, np.ndarray] = {}
    for key, value in data.items():
        clean_data[key] = value if isinstance(value, np.ndarray) else np.asarray(value)
    return clean_data


def load_npz(path: Path) -> Dict[str, np.ndarray]:
    with np.load(path) as data:
        return dict(data)


def save_npz(path: Path, data: Dict[str, Any]) -> None:
    # Uncompressed savez: PIV vector fields compress poorly (1.3-1.8x) but pay
    # ~10x CPU cost; analysis throughput improves measurably with raw save.
    np.savez(path, **_to_numpy_map(data))


def load_mat(path: Path) -> Dict[str, np.ndarray]:
    from scipy.io import loadmat

    mat_data = loadmat(str(path))
    return {k: v for k, v in mat_data.items() if not k.startswith("__")}


def save_mat(path: Path, data: Dict[str, Any]) -> None:
    # do_compression=False: zlib + scipy savemat triggers a stack-overrun crash on
    # Windows for moderately-sized arrays. Variable names are also restricted to
    # MATLAB-compatible identifiers; non-conforming or object-dtype entries are
    # dropped silently to avoid corrupt .mat output.
    from scipy.io import savemat

    arrays = _to_numpy_map(data)
    clean: Dict[str, np.ndarray] = {}
    for key, arr in arrays.items():
        if not isinstance(key, str) or not _MAT_VAR_RE.match(key):
            continue
        if arr.dtype == object:
            continue
        clean[key] = arr
    savemat(str(path), clean, do_compression=False)


def load_raw_custom(path: Path) -> Dict[str, np.ndarray]:
    with open(path, "rb") as f:
        header_len_bytes = f.read(4)
        if not header_len_bytes:
            return {}
        header_len = np.frombuffer(header_len_bytes, dtype=np.uint32)[0]
        header_json = f.read(header_len)
        header = json.loads(header_json.decode("utf-8"))

        data: Dict[str, np.ndarray] = {}
        for i, field in enumerate(header["fields"]):
            dtype = np.dtype(header["dtypes"][i])
            shape = tuple(header["shapes"][i])
            size_bytes = header["sizes"][i]
            chunk = f.read(size_bytes)
            data[field] = np.frombuffer(chunk, dtype=dtype).reshape(shape)
        return data


def save_raw_custom(path: Path, data: Dict[str, Any]) -> None:
    arrays = _to_numpy_map(data)
    header_info = {"fields": [], "shapes": [], "dtypes": [], "sizes": []}

    for key, arr in arrays.items():
        header_info["fields"].append(key)
        header_info["shapes"].append(arr.shape)
        header_info["dtypes"].append(arr.dtype.str)
        header_info["sizes"].append(arr.nbytes)

    header_json = json.dumps(header_info).encode("utf-8")
    with open(path, "wb") as f:
        f.write(np.array([len(header_json)], dtype=np.uint32).tobytes())
        f.write(header_json)
        for key in header_info["fields"]:
            f.write(arrays[key].tobytes())


def load_flo(path: Path, with_grid: bool = False) -> Dict[str, np.ndarray]:
    with open(path, "rb") as f:
        magic = np.frombuffer(f.read(4), np.float32)[0]
        if magic != 202021.25:
            raise ValueError(f"Invalid .flo file: {path}")

        width = np.frombuffer(f.read(4), np.int32)[0]
        height = np.frombuffer(f.read(4), np.int32)[0]
        flow = np.frombuffer(f.read(), np.float32).reshape((height, width, 2))

        result: Dict[str, np.ndarray] = {
            "u": flow[..., 0],
            "v": flow[..., 1],
        }
        if with_grid:
            x_grid, y_grid = np.meshgrid(np.arange(width), np.arange(height))
            result["x"] = x_grid.astype(np.float32)
            result["y"] = y_grid.astype(np.float32)
        return result


def save_flo(path: Path, data: Dict[str, Any]) -> None:
    arrays = _to_numpy_map(data)
    if "u" not in arrays or "v" not in arrays:
        raise ValueError("data does not contain 'u' and 'v'")

    u = np.asarray(arrays["u"], dtype=np.float32)
    v = np.asarray(arrays["v"], dtype=np.float32)
    if u.shape != v.shape:
        raise ValueError("u, v shape mismatch")
    if u.ndim != 2:
        raise ValueError(f"u, v must be 2D arrays for .flo format, got {u.ndim}D")

    height, width = u.shape
    with open(path, "wb") as f:
        f.write(np.array([202021.25], np.float32).tobytes())
        f.write(np.array([width], np.int32).tobytes())
        f.write(np.array([height], np.int32).tobytes())
        f.write(np.stack([u, v], axis=-1).tobytes())

