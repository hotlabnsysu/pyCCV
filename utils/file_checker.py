"""
file_checker.py - 檔案與資料夾掃描

DEPRECATED: 此模組已被 AnalysisService.get_image_pairs() 取代。
支援單資料夾與多子資料夾的影像檔案檢測
"""

import os
import warnings
from pathlib import Path
from typing import List, Tuple, Optional
from config import SUPPORTED_IMAGE_FORMATS


def file_checker(
    dir_input: str,
    img_formats: List[str] = None,
    select_folders: Optional[int | List[int]] = 0,
    select_files: Optional[int | List[int]] = 0,
) -> Tuple[List[str], int, str, bool]:
    """
    檢查並收集影像檔案清單

    Parameters
    ----------
    dir_input : str
        輸入目錄路徑
    img_formats : List[str], optional
        支援的影像格式 (預設使用 config 中的格式)
    select_folders : int | List[int]
        資料夾選擇 (0=全部, n=第n個, [a,b]=第a到b個)
    select_files : int | List[int]
        檔案選擇 (0=全部, n=第n個, [a,b]=第a到b個)

    Returns
    -------
    list_folders : List[str]
        資料夾清單
    num_results : int
        結果數量
    file_format : str
        檔案格式
    is_single_folder : bool
        是否為單資料夾模式
    """
    if img_formats is None:
        img_formats = SUPPORTED_IMAGE_FORMATS

    warnings.warn(
        "file_checker() is deprecated; use AnalysisService.get_image_pairs()",
        DeprecationWarning, stacklevel=2)
    dir_path = Path(dir_input)

    if not dir_path.exists():
        raise FileNotFoundError(f"目錄不存在: {dir_input}")

    list_folders = []
    num_results = 0
    file_format = ""
    is_single_folder = False

    # 嘗試多子資料夾模式
    for fmt in img_formats:
        # 搜尋所有子資料夾中的影像
        pattern = f"*/*{fmt}"
        files = list(dir_path.glob(pattern))

        if files:
            # 收集所有包含影像的子資料夾
            folders = set()
            for f in files:
                folders.add(f.parent.name)

            all_folders = sorted(list(folders))

            # 根據 select_folders 選擇
            if select_folders == 0:
                list_folders = all_folders
            elif isinstance(select_folders, int):
                if 0 < select_folders <= len(all_folders):
                    list_folders = [all_folders[select_folders - 1]]
            elif isinstance(select_folders, list) and len(select_folders) == 2:
                start, end = select_folders
                list_folders = all_folders[start - 1:end]

            # 計算結果數量
            if select_files == 0:
                for folder in list_folders:
                    folder_path = dir_path / folder
                    num_files = len(list(folder_path.glob(f"*{fmt}")))
                    num_results += num_files - 1  # PIV 結果數 = 檔案數 - 1
            elif isinstance(select_files, int):
                num_results = len(list_folders)
            elif isinstance(select_files, list) and len(select_files) == 2:
                num_results = (select_files[1] - select_files[0]) * len(list_folders)

            file_format = fmt
            is_single_folder = False
            break

    # 如果沒有找到多資料夾模式，嘗試單資料夾模式
    if not list_folders:
        for fmt in img_formats:
            pattern = f"*{fmt}"
            files = list(dir_path.glob(pattern))

            if files:
                list_folders = [dir_path.name]
                is_single_folder = True

                if select_files == 0:
                    num_results = len(files) - 1
                elif isinstance(select_files, int):
                    num_results = 1
                elif isinstance(select_files, list) and len(select_files) == 2:
                    num_results = select_files[1] - select_files[0]

                file_format = fmt
                break

    if not list_folders:
        raise ValueError("未找到影像檔案！請檢查目錄路徑。")

    return list_folders, num_results, file_format, is_single_folder


def get_image_pairs(
    dir_input: str,
    file_format: str,
    select_files: Optional[int | List[int]] = 0,
) -> List[Tuple[str, str]]:
    """
    取得影像對清單

    Parameters
    ----------
    dir_input : str
        輸入目錄
    file_format : str
        檔案格式
    select_files : int | List[int]
        檔案選擇

    Returns
    -------
    pairs : List[Tuple[str, str]]
        影像對清單 [(img1_path, img2_path), ...]
    """
    warnings.warn(
        "get_image_pairs() is deprecated; use AnalysisService.get_image_pairs()",
        DeprecationWarning, stacklevel=2)
    dir_path = Path(dir_input)
    files = sorted(dir_path.glob(f"*{file_format}"))

    if not files:
        return []

    # 根據 select_files 選擇範圍
    if select_files == 0:
        start, end = 0, len(files) - 1
    elif isinstance(select_files, int):
        start, end = select_files - 1, select_files
    elif isinstance(select_files, list) and len(select_files) == 2:
        start, end = select_files[0] - 1, select_files[1] - 1
    else:
        start, end = 0, len(files) - 1

    pairs = []
    for i in range(start, min(end, len(files) - 1)):
        pairs.append((str(files[i]), str(files[i + 1])))

    return pairs
