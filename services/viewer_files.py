"""Vector/image pair scanning service for the VIEWER tab."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple, Optional

from config import SUPPORTED_IMAGE_FORMATS, VECTOR_FILE_FORMATS


class ViewerFileService:
    """Scans a directory for vector result files and attempts to pair them with images."""

    def scan_pairs(
        self,
        vector_dir: str,
        image_dir: Optional[str] = None,
    ) -> List[Tuple[Path, Optional[Path], Optional[Path]]]:
        """Return list of (vector_path, img1_path, img2_path).

        img1_path / img2_path may be None if no matching image is found.
        If image_dir is None or empty, vector_dir is used for image lookup.
        """
        vdir = Path(vector_dir)
        idir = Path(image_dir) if image_dir else vdir

        if not vdir.is_dir():
            return []

        # Collect all vector files, sorted by name
        vector_files = sorted(
            p for p in vdir.iterdir()
            if p.is_file() and p.suffix.lower() in VECTOR_FILE_FORMATS
        )

        if not vdir.is_dir():
            return []

        # Build a set of image filenames for quick lookup
        image_names: set[str] = set()
        if idir.is_dir():
            image_names = {
                p.name for p in idir.iterdir()
                if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_FORMATS
            }

        pairs: List[Tuple[Path, Optional[Path], Optional[Path]]] = []
        for vfile in vector_files:
            stem = vfile.stem
            num_str, num = self._parse_number(stem)
            if num is not None and num_str:
                img1 = self._find_image_path(idir, stem, num_str, num, image_names)
                img2 = self._find_image_path(idir, stem, num_str, num + 1, image_names)
            else:
                img1 = self._find_image_path_by_stem(idir, stem, image_names)
                img2 = None
            pairs.append((vfile, img1, img2))

        return pairs

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_number(self, stem: str):
        """Return (num_str, int) for the trailing numeric part of stem, or (None, None)."""
        # Pattern 1: prefix_NNN  (underscore-separated)
        m = re.search(r'_(\d+)$', stem)
        if m:
            return m.group(1), int(m.group(1))
        # Pattern 2: prefixNNN  (non-digit prefix + trailing digits)
        m = re.search(r'^([^\d]+)(\d+)$', stem)
        if m:
            return m.group(2), int(m.group(2))
        return None, None

    def _find_image_path(
        self,
        idir: Path,
        stem: str,
        num_str: str,
        num: int,
        image_names: set,
    ) -> Optional[Path]:
        """Try several zero-padding widths and all supported extensions."""
        # Derive the filename prefix by stripping the trailing number from stem
        prefix = stem[: len(stem) - len(num_str)]
        # Candidate zero-padded strings
        candidates = {
            str(num).zfill(len(num_str)),  # original padding
            str(num).zfill(6),              # 6-digit padding
            str(num),                       # no padding
        }
        for cand in candidates:
            for ext in SUPPORTED_IMAGE_FORMATS:
                name = f"{prefix}{cand}{ext}"
                if name in image_names:
                    return idir / name
        return None

    def _find_image_path_by_stem(
        self,
        idir: Path,
        stem: str,
        image_names: set,
    ) -> Optional[Path]:
        """Try all extensions for an exact stem match."""
        for ext in SUPPORTED_IMAGE_FORMATS:
            name = f"{stem}{ext}"
            if name in image_names:
                return idir / name
        return None
