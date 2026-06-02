from __future__ import annotations


def normalize_interrogation_areas(values) -> tuple[list[object], int, str]:
    areas = []
    for val in values:
        if val == "none":
            areas.append(None)
            continue

        try:
            areas.append(int(val))
        except (TypeError, ValueError):
            return [], 0, f"Invalid value: {val}"

    if not areas or areas[0] is None:
        return [], 0, "設定錯誤: Int Area 1 未設定"

    num_passes = 0
    last_val = float("inf")

    for val in areas:
        if val is None:
            break
        if val > last_val:
            return [], 0, "設定錯誤: Int Area 1 至 Int Area 6 應依序變小"
        last_val = val
        num_passes += 1

    normalized = [val if val is not None else "none" for val in areas]
    return normalized, num_passes, ""


def validate_interrogation_areas(values) -> tuple[bool, int, str]:
    _, num_passes, error_msg = normalize_interrogation_areas(values)
    return error_msg == "", num_passes, error_msg
