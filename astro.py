"""
摄影天文计算（纯标准库）
========================
太阳高度角/方位角、黄金时刻/蓝调时刻、月相亮度。
"""

import math
from datetime import datetime, timedelta, timezone


# ponytail: 固定东八区（当前数据源均为中国城市），扩展到其他时区时再加 tz 参数
_LOCAL_TZ = timezone(timedelta(hours=8))

# QWeather 月相文本 -> 近似照度（0-1）
# ponytail: 按月相名粗估亮度，需要精确值时可换天文计算
_PHASE_ILLUM = {
    "新月": 0.05,
    "娥眉月": 0.2,
    "上弦月": 0.5,
    "盈凸月": 0.75,
    "满月": 0.98,
    "亏凸月": 0.75,
    "下弦月": 0.5,
    "残月": 0.2,
}

_DIRS = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]


def _local(date: str, hhmm: str = "12:00") -> datetime:
    """把 YYYY-MM-DD 和 HH:MM 组合成东八区 aware datetime。"""
    hour, minute = (int(x) for x in hhmm.split(":"))
    year, month, day = (int(x) for x in date.split("-"))
    return datetime(year, month, day, hour, minute, tzinfo=_LOCAL_TZ)


def solar_position(dt: datetime, lat: float, lon: float):
    """
    计算太阳高度角和方位角。

    Returns:
        (高度角, 方位角)，方位角自正北顺时针（0-360）
    """
    lat_r, lon_r = math.radians(lat), math.radians(lon)
    day_of_year = dt.timetuple().tm_yday
    n = day_of_year - 1 + (dt.hour + dt.minute / 60 + dt.second / 3600) / 24

    # 太阳赤纬与均时差
    gamma = 2 * math.pi / 365 * (n - 1)
    decl = (0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma)
            - 0.006758 * math.cos(2 * gamma) + 0.000907 * math.sin(2 * gamma)
            - 0.002697 * math.cos(3 * gamma) + 0.00148 * math.sin(3 * gamma))
    eot = 229.18 * (0.000075 + 0.001868 * math.cos(gamma) - 0.032077 * math.sin(gamma)
                    - 0.014615 * math.cos(2 * gamma) - 0.040849 * math.sin(2 * gamma))

    # 真太阳时（小时）：UTC + 经度/15 + 均时差/60
    utc = dt.astimezone(timezone.utc)
    utc_hour = utc.hour + utc.minute / 60 + utc.second / 3600
    lst = utc_hour + lon / 15 + eot / 60

    hour_angle = math.radians(15 * (lst - 12))
    sin_elev = (math.sin(lat_r) * math.sin(decl)
                + math.cos(lat_r) * math.cos(decl) * math.cos(hour_angle))
    elev = math.degrees(math.asin(max(-1, min(1, sin_elev))))

    cos_az = ((math.sin(decl) * math.cos(lat_r)
               - math.cos(decl) * math.sin(lat_r) * math.cos(hour_angle))
              / max(math.cos(math.radians(elev)), 1e-9))
    az = math.degrees(math.acos(max(-1, min(1, cos_az))))
    if lst % 24 > 12:
        az = 360 - az
    return elev, az


def _crossings(date: str, lat: float, lon: float, targets=(-6, -4, 0, 6)) -> dict:
    """
    扫描当天每 1 分钟的高度角，插值求出各目标高度的穿越时刻。

    Returns:
        {target: [HH:MM, ...]}，按时间升序
    """
    result = {t: [] for t in targets}
    start = _local(date, "02:00")
    prev_t, prev_e = start, solar_position(start, lat, lon)[0]
    t = start
    end = start + timedelta(hours=22)
    while t < end:
        nxt = t + timedelta(minutes=1)
        e = solar_position(nxt, lat, lon)[0]
        for target in targets:
            if (prev_e - target) * (e - target) <= 0 and prev_e != e:
                frac = (target - prev_e) / (e - prev_e)
                cross = prev_t + timedelta(minutes=frac)
                result[target].append(cross.strftime("%H:%M"))
        prev_t, prev_e = nxt, e
        t = nxt
    return result


def _split_morning_evening(crosses: list) -> tuple:
    """把穿越时刻分为上午和下午两组。"""
    morning, evening = [], []
    for hhmm in crosses:
        (morning if hhmm < "12:00" else evening).append(hhmm)
    return morning, evening


def sun_events(date: str, lat: float, lon: float) -> dict:
    """
    计算一天的太阳事件窗口。

    Returns:
        {
          "golden_morning": ("HH:MM", "HH:MM"),   # 日出黄金时刻
          "golden_evening": ("HH:MM", "HH:MM"),   # 日落黄金时刻
          "blue_morning": ("HH:MM", "HH:MM"),     # 日出蓝调时刻
          "blue_evening": ("HH:MM", "HH:MM"),     # 日落蓝调时刻
          "sunrise_az": int, "sunset_az": int,    # 方位角
        }
        窗口缺失时为 ("", "")
    """
    crosses = _crossings(date, lat, lon)
    m6_m, m6_e = _split_morning_evening(crosses[-6])
    m4_m, m4_e = _split_morning_evening(crosses[-4])
    m0_m, m0_e = _split_morning_evening(crosses[0])
    p6_m, p6_e = _split_morning_evening(crosses[6])

    golden_morning = (m4_m[0], p6_m[0]) if m4_m and p6_m else ("", "")
    golden_evening = (p6_e[-1], m4_e[-1]) if p6_e and m4_e else ("", "")
    blue_morning = (m6_m[0], m4_m[0]) if m6_m and m4_m else ("", "")
    blue_evening = (m4_e[-1], m6_e[-1]) if m4_e and m6_e else ("", "")

    sunrise_az = sunset_az = None
    if m0_m and m0_e:
        sunrise_az = round(solar_position(_local(date, m0_m[0]), lat, lon)[1])
        sunset_az = round(solar_position(_local(date, m0_e[-1]), lat, lon)[1])

    return {
        "golden_morning": golden_morning,
        "golden_evening": golden_evening,
        "blue_morning": blue_morning,
        "blue_evening": blue_evening,
        "sunrise_az": sunrise_az,
        "sunset_az": sunset_az,
    }


def moon_illumination(phase_text: str) -> float:
    """月相文本 -> 近似照度 0-1。"""
    return _PHASE_ILLUM.get(phase_text, 0.0)


def direction_text(azimuth) -> str:
    """方位角 -> 中文 8 方位。"""
    if azimuth is None:
        return ""
    idx = int((azimuth + 22.5) // 45) % 8
    return _DIRS[idx]


if __name__ == "__main__":
    # 自检：珠海 2026-08-31，日出方位约东偏北 80 度，正午高度约 67 度
    zhuhai = (22.27, 113.58)
    events = sun_events("2026-08-31", *zhuhai)
    elev_noon, _ = solar_position(_local("2026-08-31", "12:30"), *zhuhai)
    assert 70 < elev_noon < 82, f"noon elevation {elev_noon}"
    assert 75 < events["sunrise_az"] < 90, events["sunrise_az"]
    assert 270 < events["sunset_az"] < 300, events["sunset_az"]
    assert events["golden_evening"][0] and events["blue_evening"][1], events
    assert moon_illumination("满月") > 0.9
    assert direction_text(273) == "西"
    print("astro self-check OK")
