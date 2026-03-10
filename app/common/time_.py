# app/common/timezone.py
"""时间处理工具模块。

提供时区相关的时间处理功能：
- 时区信息定义（Asia/Shanghai）
- 当前时间获取
- 时间差转换为人类可读格式
- 时间格式化工具

统一使用中国时区，便于业务时间展示和计算。
"""

from datetime import datetime
from zoneinfo import ZoneInfo

zone_info: ZoneInfo = ZoneInfo("Asia/Shanghai")  # 默认使用上海时区


def time_now() -> datetime:
    """返回当前时区时间

    Returns:
        datetime: 系统时区的当前时间
    """
    return datetime.now(zone_info)


def human_duration(seconds: float) -> str:
    """将秒数转换为人类可读的时间格式字符串

    该函数将给定的秒数转换为包含天、小时、分钟、秒和毫秒的中文时间格式字符串。
    格式示例： "1天02小时30分45秒123毫秒" 或 "02小时30分45秒"

    Args:
        seconds (float): 需要转换的秒数，可以是小数

    Returns:
        str: 格式化后的人类可读时间字符串，包含相应的中文时间单位
    """
    secs = int(seconds)
    ms = int(round((seconds - secs) * 1000))
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)

    parts = []
    if days:
        parts.append(f"{days}天")
    parts.append(f"{hours:02d}小时{minutes:02d}分{secs:02d}秒")
    if ms:
        parts.append(f"{ms:03d}毫秒")
    return "".join(parts)
