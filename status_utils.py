import time
import math

SIZE_UNITS = ["B", "KB", "MB", "GB", "TB", "PB"]

def get_readable_file_size(size_in_bytes):
    if size_in_bytes is None or size_in_bytes == 0:
        return "0B"
    index = 0
    while size_in_bytes >= 1024 and index < len(SIZE_UNITS) - 1:
        size_in_bytes /= 1024
        index += 1
    return f"{size_in_bytes:.2f}{SIZE_UNITS[index]}"

def get_readable_time(seconds):
    if seconds is None:
        return "N/A"
    periods = [("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]
    result = ""
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            result += f"{int(period_value)}{period_name}"
    return result if result else "0s"

def get_progress_bar_string(pct):
    if isinstance(pct, str):
        pct = float(pct.strip("%"))
    p = min(max(pct, 0), 100)
    cFull = int(p // 10)
    p_str = '█' * cFull
    p_str += '░' * (10 - cFull)
    return f"[{p_str}]"
