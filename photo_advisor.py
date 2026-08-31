"""
摄影天气助手 - 摄影适合度分析模块
==================================
根据天气数据分析是否适合摄影，
包括日出日落、火烧云/晚霞、风光摄影等场景的评估。
"""

from dataclasses import dataclass, field
from typing import Optional

from astro import direction_text, moon_illumination, sun_events


# ============================================================
# 天气状况图标代码映射（和风天气图标代码）
# 参考: https://icons.qweather.com/
# ============================================================
WEATHER_ICON_MAP = {
    "100": "晴",
    "101": "多云",
    "102": "少云",
    "103": "晴间多云",
    "104": "阴",
    "150": "晴",       # 夜间
    "151": "多云",      # 夜间
    "153": "晴间多云",  # 夜间
    "300": "阵雨",
    "301": "强阵雨",
    "302": "雷阵雨",
    "303": "雷阵雨伴有冰雹",
    "304": "雷阵雨",
    "305": "小雨",
    "306": "中雨",
    "307": "大雨",
    "308": "极端降雨",
    "309": "毛毛雨",
    "310": "暴雨",
    "311": "大暴雨",
    "312": "特大暴雨",
    "313": "冻雨",
    "314": "小到中雨",
    "315": "中到大雨",
    "316": "大到暴雨",
    "399": "雨",
    "400": "小雪",
    "401": "中雪",
    "402": "大雪",
    "403": "暴雪",
    "404": "雨夹雪",
    "405": "雨雪天气",
    "406": "阵雨夹雪",
    "407": "阵雪",
    "499": "雪",
    "500": "薄雾",
    "501": "雾",
    "502": "霾",
    "503": "扬沙",
    "504": "沙尘暴",
    "507": "沙尘暴",
    "508": "特强沙尘暴",
    "509": "浓雾",
    "510": "强浓雾",
    "511": "中度霾",
    "512": "重度霾",
    "513": "严重霾",
    "514": "大雾",
    "515": "特强浓雾",
    "900": "热",
    "901": "冷",
    "999": "未知",
}

# 适合摄影的天气文字（白天）
GOOD_PHOTO_WEATHER = {"晴", "多云", "少云", "晴间多云"}
# 可能出现火烧云的天气
FIRE_CLOUD_WEATHER = {"多云", "少云", "晴间多云"}
# 不适合摄影的天气
BAD_PHOTO_WEATHER = {
    "阵雨", "强阵雨", "雷阵雨", "雷阵雨伴有冰雹",
    "小雨", "中雨", "大雨", "极端降雨", "毛毛雨",
    "暴雨", "大暴雨", "特大暴雨", "冻雨",
    "小到中雨", "中到大雨", "大到暴雨", "雨",
    "小雪", "中雪", "大雪", "暴雪", "雨夹雪", "雨雪天气",
    "阵雨夹雪", "阵雪", "雪",
    "雾", "浓雾", "强浓雾", "大雾", "特强浓雾",
    "霾", "中度霾", "重度霾", "严重霾",
    "扬沙", "沙尘暴", "特强沙尘暴",
}


@dataclass
class PhotoAdvice:
    """摄影建议结果"""
    date: str                           # 日期
    overall_score: int = 0              # 综合评分 (0-100)
    overall_level: str = "未知"          # 综合评级
    sunrise_time: str = ""              # 日出时间
    sunset_time: str = ""               # 日落时间
    sunrise_advice: str = ""            # 日出拍摄建议
    sunset_advice: str = ""             # 日落拍摄建议
    fire_cloud_chance: str = "极低"      # 火烧云/晚霞概率
    fire_cloud_score: int = 0           # 火烧云评分 (0-100)
    landscape_score: int = 0            # 风光摄影评分 (0-100)
    weather_desc: str = ""              # 天气描述
    temperature: str = ""               # 温度范围
    humidity: str = ""                  # 湿度
    wind: str = ""                      # 风力
    visibility: str = ""                # 能见度
    cloud_cover: str = ""               # 云量
    tips: list = field(default_factory=list)  # 摄影建议

    # 题材评分
    portrait_score: int = 0
    portrait_level: str = "未知"
    astro_score: int = 0
    astro_level: str = "未知"
    long_exposure_score: int = 0
    long_exposure_level: str = "未知"
    morning_glow_score: int = 0         # 朝霞评分
    genre_scores: dict = field(default_factory=dict)

    # 天文信息
    golden_morning: tuple = ("", "")
    golden_evening: tuple = ("", "")
    blue_morning: tuple = ("", "")
    blue_evening: tuple = ("", "")
    sunrise_azimuth: str = ""
    sunset_azimuth: str = ""
    moon_phase: str = ""
    moonrise: str = ""
    moonset: str = ""
    moon_illumination: float = 0.0
    night_cloud: int = 0
    fog_chance: str = "低"
    frost_chance: str = "低"

    # 拍摄计划卡（所选题材）
    plan: dict = field(default_factory=dict)


def _safe_int(value: str, default: int = 0) -> int:
    """安全地将字符串转为整数。"""
    try:
        return int(value) if value else default
    except (ValueError, TypeError):
        return default


def _safe_float(value: str, default: float = 0.0) -> float:
    """安全地将字符串转为浮点数。"""
    try:
        return float(value) if value else default
    except (ValueError, TypeError):
        return default


def _fire_score(cloud: float, text: str, precip: float, vis: float,
                humidity: int, trend_cloud: Optional[float] = None) -> tuple:
    """
    火烧云/朝霞评分，返回 (分数, 因子拆解)。

    形成条件（气象学依据）：
    - 中高云量（30%-70%）：云层是火烧云的载体
    - 天气以晴到多云为主：不能有降水
    - 能见度好：大气通透
    - 湿度适中
    - 午后云量高于傍晚（转晴趋势）加分
    """
    factors = {}
    if 30 <= cloud <= 70:
        factors["云量"] = 40
    elif 20 <= cloud < 30 or 70 < cloud <= 80:
        factors["云量"] = 20
    elif 10 <= cloud < 20 or 80 < cloud <= 90:
        factors["云量"] = 8
    else:
        factors["云量"] = 0

    if text in FIRE_CLOUD_WEATHER:
        factors["天气"] = 25
    elif text in GOOD_PHOTO_WEATHER:
        factors["天气"] = 15
    else:
        factors["天气"] = 0

    factors["降水"] = -30 if precip > 0 else 0

    if vis >= 25:
        factors["能见度"] = 15
    elif vis >= 15:
        factors["能见度"] = 10
    elif vis >= 10:
        factors["能见度"] = 5
    else:
        factors["能见度"] = 0

    if 40 <= humidity <= 70:
        factors["湿度"] = 10
    elif 30 <= humidity < 40 or 70 < humidity <= 80:
        factors["湿度"] = 5
    else:
        factors["湿度"] = 0

    if trend_cloud is not None and trend_cloud >= 40 and cloud <= trend_cloud:
        factors["午后转晴"] = 10

    score = sum(factors.values())
    return max(0, min(100, score)), factors


def _calc_landscape_score(text_day: str, cloud: int, vis: float, precip: float,
                          humidity: int, wind_speed: float, uv_index: int,
                          has_golden: bool) -> tuple:
    """风光摄影评分，返回 (分数, 因子拆解)。"""
    factors = {}
    if text_day in GOOD_PHOTO_WEATHER:
        factors["天气"] = 20
    elif text_day in BAD_PHOTO_WEATHER:
        factors["天气"] = -30
    else:
        factors["天气"] = 5

    if vis >= 25:
        factors["能见度"] = 15
    elif vis >= 15:
        factors["能见度"] = 10
    elif vis >= 10:
        factors["能见度"] = 5
    else:
        factors["能见度"] = -15

    factors["降水"] = -20 if precip > 0 else 0

    if wind_speed <= 5:
        factors["风力"] = 10
    elif wind_speed <= 15:
        factors["风力"] = 5
    elif wind_speed <= 25:
        factors["风力"] = -5
    else:
        factors["风力"] = -15

    if 30 <= humidity <= 70:
        factors["湿度"] = 5
    elif humidity > 85:
        factors["湿度"] = -10

    if uv_index >= 5:
        factors["日照"] = 5

    if has_golden:
        factors["黄金时刻"] = 10

    score = 50 + sum(factors.values())
    return max(0, min(100, score)), factors


def _calc_portrait_score(text_day: str, cloud: int, vis: float, precip: float,
                         wind_speed: float, uv_index: int, humidity: int,
                         has_golden: bool) -> tuple:
    """人像摄影评分，返回 (分数, 因子拆解)。"""
    factors = {}
    if text_day in {"多云", "少云", "晴间多云"}:
        factors["光线"] = 20          # 天然柔光罩
    elif text_day == "晴":
        factors["光线"] = 10          # 晴天需补光或避开正午
    elif text_day in BAD_PHOTO_WEATHER:
        factors["天气"] = -30
    else:
        factors["光线"] = 5

    if has_golden:
        factors["黄金时刻"] = 10

    if wind_speed <= 8:
        factors["风力"] = 10
    elif wind_speed <= 15:
        factors["风力"] = 5
    else:
        factors["风力"] = -10

    factors["降水"] = -30 if precip > 0 else 0
    factors["湿度"] = -5 if humidity > 85 else 0
    factors["能见度"] = 5 if vis >= 15 else 0

    score = 50 + sum(factors.values())
    return max(0, min(100, score)), factors


def _calc_astro_score(night_cloud: float, night_precip: float, vis: float,
                      humidity: int, wind_speed: float,
                      moon_illum: float, moon_up: bool) -> tuple:
    """星空摄影评分，返回 (分数, 因子拆解)。"""
    factors = {}
    factors["夜间云量"] = -int(night_cloud / 100 * 50)
    factors["月光"] = -int(moon_illum * 40) if moon_up else 0
    factors["夜间降水"] = -20 if night_precip > 0 else 0
    factors["能见度"] = -10 if vis < 15 else 0
    factors["湿度"] = -5 if humidity > 85 else 0
    factors["大风"] = -5 if wind_speed > 25 else 0

    score = 100 + sum(factors.values())
    return max(0, min(100, score)), factors


def _calc_long_exposure_score(text_day: str, cloud: int, vis: float, precip: float,
                              wind_speed: float, humidity: int,
                              has_golden: bool) -> tuple:
    """长曝光摄影评分，返回 (分数, 因子拆解)。"""
    factors = {}
    if wind_speed <= 3:
        factors["风力"] = 30
    elif wind_speed <= 8:
        factors["风力"] = 20
    elif wind_speed <= 15:
        factors["风力"] = 10
    else:
        factors["风力"] = -20

    factors["降水"] = 20 if precip <= 0 else -30

    if 30 <= cloud <= 80:
        factors["云层"] = 15          # 云有流动感
    elif cloud <= 10:
        factors["云层"] = 5           # 水面可拍平
    elif cloud > 90:
        factors["云层"] = -10
    else:
        factors["云层"] = 8

    if has_golden:
        factors["黄金时刻"] = 15
    factors["能见度"] = 10 if vis >= 15 else 0
    factors["湿度"] = -5 if humidity > 85 else 0

    score = 50 + sum(factors.values())
    return max(0, min(100, score)), factors


def _to_min(hhmm: str) -> int:
    """HH:MM -> 分钟数。"""
    h, m = (int(x) for x in hhmm.split(":"))
    return h * 60 + m


def _hourly_window_stats(hourly_day: list, center_hhmm: str,
                         before_min: int, after_min: int) -> Optional[dict]:
    """取某时刻前后窗口内的逐小时数据统计。"""
    if not hourly_day or not center_hhmm:
        return None
    center = _to_min(center_hhmm)
    items = []
    for h in hourly_day:
        hhmm = h.get("fxTime", "")[11:16]
        if len(hhmm) == 5 and center - before_min <= _to_min(hhmm) <= center + after_min:
            items.append(h)
    if not items:
        return None
    return {
        "cloud": sum(int(h.get("cloud", 0)) for h in items) / len(items),
        "precip": max(float(h.get("precip", 0)) for h in items),
        "humidity": sum(int(h.get("humidity", 0)) for h in items) / len(items),
        "text": items[len(items) // 2].get("text", ""),
    }


def _afternoon_cloud(hourly_day: list) -> Optional[float]:
    """14:00-16:00 平均云量，用于“午后转晴”趋势判断。"""
    clouds = []
    for h in hourly_day:
        hhmm = h.get("fxTime", "")[11:16]
        if "14:00" <= hhmm <= "16:00":
            clouds.append(int(h.get("cloud", 0)))
    return sum(clouds) / len(clouds) if clouds else None


def _night_cloud_stats(hourly_day: list, fallback_cloud: int) -> tuple:
    """21:00-03:00 的夜间云量均值与最大降水。"""
    clouds, precip = [], 0.0
    for h in hourly_day:
        hhmm = h.get("fxTime", "")[11:16]
        if hhmm >= "21:00" or hhmm <= "03:00":
            clouds.append(int(h.get("cloud", 0)))
            precip = max(precip, float(h.get("precip", 0)))
    if not clouds:
        return fallback_cloud, 0.0
    return sum(clouds) / len(clouds), precip


def _calc_fog_frost(hourly_day: list, temp_min: int) -> tuple:
    """05:00-08:00 温露差/湿度/风速 -> (晨雾概率, 霜冻概率)。"""
    fog, frost = "低", "低"
    if not hourly_day:
        if temp_min <= 4:
            fog = "中"
        return fog, frost

    spreads, hums, winds, temps = [], [], [], []
    for h in hourly_day:
        hhmm = h.get("fxTime", "")[11:16]
        if "05:00" <= hhmm <= "08:00":
            temp = int(h.get("temp", 0))
            spreads.append(temp - int(h.get("dew", 0)))
            hums.append(int(h.get("humidity", 0)))
            winds.append(int(h.get("windSpeed", 0)))
            temps.append(temp)
    if not spreads:
        return fog, frost

    avg_spread = sum(spreads) / len(spreads)
    avg_hum = sum(hums) / len(hums)
    max_wind = max(winds)
    min_temp = min(temps)

    if avg_spread <= 2 and avg_hum >= 85 and max_wind <= 10:
        fog = "高"
    elif avg_spread <= 3 and avg_hum >= 80:
        fog = "中"
    if min_temp <= 1 and avg_spread <= 2:
        frost = "高"
    elif min_temp <= 4 and avg_spread <= 3:
        frost = "中"
    return fog, frost


def _moon_up_night(moonrise: str, moonset: str) -> bool:
    """夜间窗口 21:00-03:00 内月亮是否在地平线上。"""
    if not moonrise or not moonset:
        return False
    return moonset >= "21:00" or moonrise <= "03:00"


GENRES = {
    "landscape": "风光",
    "portrait": "人像",
    "astro": "星空",
    "long_exposure": "长曝光",
}


def _build_plan(genre: str, advice, daily: dict, hourly_day: list) -> dict:
    """为某题材生成拍摄计划卡。"""
    label = GENRES.get(genre, genre)
    precip = _safe_float(daily.get("precip", "0"))
    wind = _safe_float(daily.get("windSpeedDay", "0"))
    humidity = _safe_int(daily.get("humidity", "0"))
    temp_min = _safe_int(daily.get("tempMin", "0"))

    time_window, window_label = "", ""
    if genre == "astro":
        time_window, window_label = "21:00 - 03:00", "星空窗口"
    else:
        for key, name in (("golden_evening", "日落黄金时刻"),
                          ("golden_morning", "日出黄金时刻"),
                          ("blue_evening", "日落蓝调时刻"),
                          ("blue_morning", "日出蓝调时刻")):
            start, end = getattr(advice, key)
            if start and end:
                time_window, window_label = f"{start} - {end}", name
                break

    if genre == "astro":
        direction = "面向远离城市光害的方向"
    elif window_label.startswith("日落"):
        direction = advice.sunset_azimuth
    elif window_label.startswith("日出"):
        direction = advice.sunrise_azimuth
    else:
        direction = ""

    gear = []
    if genre in ("astro", "long_exposure") or wind > 15:
        gear.append("三脚架")
    if genre == "long_exposure":
        gear.append("ND 减光镜")
    if humidity > 85 or advice.fog_chance == "高":
        gear.append("镜头布")
    if precip > 0:
        gear.append("防雨罩")
    if genre == "portrait" and daily.get("textDay") == "晴":
        gear.append("反光板或柔光附件")
    if genre == "astro":
        gear.append("广角大光圈镜头")
    if genre == "astro" or temp_min <= 5:
        gear.append("备用电池")
    gear = gear or ["相机与镜头"]

    risks = []
    if precip > 0:
        risks.append("可能有降水")
    if wind > 20:
        risks.append("风力较大，注意机位稳定")
    if humidity > 85:
        risks.append("湿度高，镜头易起雾")
    if genre == "astro":
        if advice.moon_illumination > 0.5 and _moon_up_night(advice.moonrise, advice.moonset):
            risks.append("月光较强，星野会受影响")
        if advice.night_cloud > 60:
            risks.append("夜间云量偏高")
    if advice.fog_chance == "高":
        risks.append("晨间可能有雾")
    if advice.frost_chance == "高":
        risks.append("可能有霜冻，注意保暖")

    current = advice.genre_scores.get(genre, {})
    level = current.get("level", "未知")
    if genre == "astro":
        moon_note = "较强" if advice.moon_illumination > 0.5 else "较弱"
        summary = (f"夜间云量 {advice.night_cloud}%，月光{moon_note}，星空条件{level}")
    else:
        direction_note = advice.sunset_azimuth or advice.sunrise_azimuth or "合适方向"
        summary = f"{window_label} {time_window}，{direction_note}，整体条件{level}"

    return {
        "genre": genre,
        "genre_label": label,
        "date": advice.date,
        "score": current.get("score", 0),
        "level": level,
        "time_window": time_window,
        "window_label": window_label,
        "direction": direction,
        "gear": gear,
        "risks": risks,
        "summary": summary,
    }


def _get_fire_cloud_chance(score: int) -> str:
    """根据评分返回火烧云概率描述。"""
    if score >= 80:
        return "极高"
    elif score >= 60:
        return "较高"
    elif score >= 40:
        return "中等"
    elif score >= 20:
        return "较低"
    else:
        return "极低"


def _get_overall_level(score: int) -> str:
    """根据综合评分返回评级。"""
    if score >= 85:
        return "极佳"
    elif score >= 70:
        return "良好"
    elif score >= 50:
        return "一般"
    elif score >= 30:
        return "较差"
    else:
        return "不适合"


def _generate_tips(daily: dict, fire_score: int, landscape_score: int) -> list:
    """根据天气数据生成摄影建议。"""
    tips = []
    cloud = _safe_int(daily.get("cloud", "0"))
    precip = _safe_float(daily.get("precip", "0"))
    humidity = _safe_int(daily.get("humidity", "0"))
    vis = _safe_float(daily.get("vis", "0"))
    wind_speed = _safe_float(daily.get("windSpeedDay", "0"))
    text_day = daily.get("textDay", "")

    # 火烧云相关建议
    if fire_score >= 60:
        tips.append("今日有较大概率出现火烧云/晚霞，建议在日落前30分钟到达拍摄点")
    if fire_score >= 80:
        tips.append("火烧云概率极高！推荐朝西方开阔方向拍摄，注意捕捉云层边缘的金红色光芒")

    # 天气相关建议
    if text_day == "晴" and cloud <= 10:
        tips.append("今日天空晴朗少云，光线硬朗，适合拍摄建筑、人像（注意补光）")
    if "多云" in text_day or "少云" in text_day:
        tips.append("云层可充当天然柔光罩，光线柔和均匀，适合户外人像和风光摄影")

    # 能见度相关
    if vis >= 25:
        tips.append("能见度极佳，适合拍摄远景、山景、城市天际线")
    elif vis < 10 and vis > 0:
        tips.append("能见度较低，远景可能模糊，建议拍摄近景或利用雾气营造氛围感")

    # 降水相关
    if precip > 0:
        tips.append("今日有降水，注意器材防水；雨后初晴时容易出现彩虹和火烧云")

    # 湿度相关
    if humidity > 85:
        tips.append("湿度较高，镜头容易起雾，建议携带镜头布并注意温差变化")

    # 风力相关
    if wind_speed > 20:
        tips.append("风力较大，长焦拍摄和长曝光可能受影响，建议使用三脚架和防风措施")
    elif wind_speed <= 3:
        tips.append("几乎无风，适合长曝光拍摄水面、云层等")

    # 通用建议
    if daily.get("sunrise"):
        tips.append(f"日出时间 {daily['sunrise']}，建议提前20-30分钟到位（蓝调时刻更佳）")
    if daily.get("sunset"):
        tips.append(f"日落时间 {daily['sunset']}，日落后20分钟内的余晖往往最精彩")

    return tips


def analyze_daily(daily: dict, hourly_by_date: Optional[dict] = None,
                  lat: Optional[float] = None, lon: Optional[float] = None,
                  genre: str = "landscape") -> PhotoAdvice:
    """
    分析单天天气，生成多题材评分、因子拆解与拍摄计划卡。

    Args:
        daily: 和风天气每日预报数据
        hourly_by_date: {fxDate: [逐小时数据]}，用于火烧云/朝霞/星空/晨雾等
        lat/lon: 城市经纬度，用于黄金时刻与方位角计算
        genre: 所选题材（landscape/portrait/astro/long_exposure）

    Returns:
        PhotoAdvice 对象
    """
    date = daily.get("fxDate", "")
    hourly_day = (hourly_by_date or {}).get(date, [])

    cloud = _safe_int(daily.get("cloud", "0"))
    precip = _safe_float(daily.get("precip", "0"))
    humidity = _safe_int(daily.get("humidity", "0"))
    vis = _safe_float(daily.get("vis", "0"))
    wind_speed = _safe_float(daily.get("windSpeedDay", "0"))
    uv_index = _safe_int(daily.get("uvIndex", "0"))
    temp_min = _safe_int(daily.get("tempMin", "0"))
    text_day = daily.get("textDay", "")
    text_night = daily.get("textNight", "")
    temp_max = daily.get("tempMax", "")
    sunrise = daily.get("sunrise", "")
    sunset = daily.get("sunset", "")

    # 天文事件（黄金时刻/蓝调时刻/方位角）
    events = {"golden_morning": ("", ""), "golden_evening": ("", ""),
              "blue_morning": ("", ""), "blue_evening": ("", ""),
              "sunrise_az": None, "sunset_az": None}
    if lat is not None and lon is not None:
        events = sun_events(date, float(lat), float(lon))

    # 火烧云（日落）与朝霞（日出）：优先用窗口内逐小时数据
    sunset_win = _hourly_window_stats(hourly_day, sunset, 60, 30) if sunset else None
    sunrise_win = _hourly_window_stats(hourly_day, sunrise, 30, 60) if sunrise else None
    trend = _afternoon_cloud(hourly_day)

    if sunset_win:
        fire_score, fire_factors = _fire_score(
            sunset_win["cloud"], sunset_win["text"], sunset_win["precip"],
            vis, sunset_win["humidity"], trend)
    else:
        fire_score, fire_factors = _fire_score(cloud, text_day, precip, vis, humidity, trend)

    if sunrise_win:
        glow_score, _ = _fire_score(
            sunrise_win["cloud"], sunrise_win["text"], sunrise_win["precip"],
            vis, sunrise_win["humidity"])
    else:
        glow_score, _ = _fire_score(cloud, text_day, precip, vis, humidity)

    # 星空相关
    night_cloud, night_precip = _night_cloud_stats(hourly_day, cloud)
    moon_phase = daily.get("moonPhase", "")
    moon_illum = moon_illumination(moon_phase)
    moon_up = _moon_up_night(daily.get("moonrise", ""), daily.get("moonset", ""))

    # 晨雾/霜冻
    fog_chance, frost_chance = _calc_fog_frost(hourly_day, temp_min)

    has_golden = any(
        v[0] for v in (events["golden_morning"], events["golden_evening"],
                       events["blue_morning"], events["blue_evening"]))

    landscape_score, landscape_factors = _calc_landscape_score(
        text_day, cloud, vis, precip, humidity, wind_speed, uv_index, has_golden)
    portrait_score, portrait_factors = _calc_portrait_score(
        text_day, cloud, vis, precip, wind_speed, uv_index, humidity, has_golden)
    astro_score, astro_factors = _calc_astro_score(
        night_cloud, night_precip, vis, humidity, wind_speed, moon_illum, moon_up)
    long_exposure_score, long_factors = _calc_long_exposure_score(
        text_day, cloud, vis, precip, wind_speed, humidity, has_golden)

    genre_scores = {
        "landscape": {"score": landscape_score,
                      "level": _get_overall_level(landscape_score),
                      "factors": landscape_factors},
        "portrait": {"score": portrait_score,
                     "level": _get_overall_level(portrait_score),
                     "factors": portrait_factors},
        "astro": {"score": astro_score,
                  "level": _get_overall_level(astro_score),
                  "factors": astro_factors},
        "long_exposure": {"score": long_exposure_score,
                          "level": _get_overall_level(long_exposure_score),
                          "factors": long_factors},
    }
    current = genre_scores.get(genre, genre_scores["landscape"])

    # 生成建议
    tips = _generate_tips(daily, fire_score, landscape_score)
    if fog_chance == "高":
        tips.append("晨间雾气概率高，适合拍雾景；注意镜头防雾")
    if frost_chance == "高":
        tips.append("清晨可能有霜冻，注意保暖与电池续航")
    if genre == "astro":
        tips.append(
            f"夜间云量约 {round(night_cloud)}%"
            + ("，月光较弱，适合星野" if moon_illum <= 0.5 else "，月光较强，建议拍月亮或地景"))
    if events["golden_evening"][0]:
        tips.append(f"日落黄金时刻 {events['golden_evening'][0]} - {events['golden_evening'][1]}，"
                    f"蓝调时刻 {events['blue_evening'][0]} - {events['blue_evening'][1]}")
    if events["golden_morning"][0]:
        tips.append(f"日出黄金时刻 {events['golden_morning'][0]} - {events['golden_morning'][1]}")

    # 日出日落建议
    sunrise_advice = ""
    sunset_advice = ""
    if sunrise:
        if text_day in GOOD_PHOTO_WEATHER:
            sunrise_advice = f"日出 {sunrise}，天气条件良好，推荐拍摄"
        elif text_day in BAD_PHOTO_WEATHER:
            sunrise_advice = f"日出 {sunrise}，但天气不佳，拍摄效果可能受限"
        else:
            sunrise_advice = f"日出 {sunrise}，可尝试拍摄"

    if sunset:
        fire_chance = _get_fire_cloud_chance(fire_score)
        sunset_advice = f"日落 {sunset}，晚霞/火烧云概率: {fire_chance}"

    def _az_text(az):
        if az is None:
            return ""
        return f"{direction_text(az)} ({az}°)"

    advice = PhotoAdvice(
        date=date,
        overall_score=current["score"],
        overall_level=current["level"],
        sunrise_time=sunrise,
        sunset_time=sunset,
        sunrise_advice=sunrise_advice,
        sunset_advice=sunset_advice,
        fire_cloud_chance=_get_fire_cloud_chance(fire_score),
        fire_cloud_score=fire_score,
        landscape_score=landscape_score,
        portrait_score=portrait_score,
        portrait_level=_get_overall_level(portrait_score),
        astro_score=astro_score,
        astro_level=_get_overall_level(astro_score),
        long_exposure_score=long_exposure_score,
        long_exposure_level=_get_overall_level(long_exposure_score),
        morning_glow_score=glow_score,
        genre_scores=genre_scores,
        golden_morning=events["golden_morning"],
        golden_evening=events["golden_evening"],
        blue_morning=events["blue_morning"],
        blue_evening=events["blue_evening"],
        sunrise_azimuth=_az_text(events["sunrise_az"]),
        sunset_azimuth=_az_text(events["sunset_az"]),
        moon_phase=moon_phase,
        moonrise=daily.get("moonrise", ""),
        moonset=daily.get("moonset", ""),
        moon_illumination=moon_illum,
        night_cloud=round(night_cloud),
        fog_chance=fog_chance,
        frost_chance=frost_chance,
        weather_desc=f"{text_day} / 夜间{text_night}",
        temperature=f"{temp_min}°C ~ {temp_max}°C",
        humidity=f"{humidity}%",
        wind=f"{daily.get('windDirDay', '')} {daily.get('windScaleDay', '')}级",
        visibility=f"{vis}km",
        cloud_cover=f"{cloud}%",
        tips=tips,
    )
    advice.plan = _build_plan(genre, advice, daily, hourly_day)
    return advice


if __name__ == "__main__":
    # 自检：样本数据应产出 4 个题材评分与星空计划卡
    sample = {
        "fxDate": "2026-08-31", "sunrise": "06:09", "sunset": "18:45",
        "moonPhase": "亏凸月", "moonrise": "20:29", "moonset": "08:39",
        "tempMax": "30", "tempMin": "26", "textDay": "多云", "textNight": "多云",
        "cloud": "50", "humidity": "70", "vis": "22", "precip": "0",
        "windSpeedDay": "10", "windDirDay": "东南", "windScaleDay": "3",
        "uvIndex": "6",
    }
    sample_hourly = [
        {"fxTime": f"2026-08-31T{h:02d}:00+08:00", "temp": "28", "text": "多云",
         "cloud": "50", "precip": "0", "pop": "0", "humidity": "70",
         "dew": "22", "windSpeed": "10"}
        for h in range(24)
    ]
    check = analyze_daily(sample, {"2026-08-31": sample_hourly}, 22.27, 113.58, "astro")
    assert len(check.genre_scores) == 4
    assert check.plan["genre_label"] == "星空"
    assert check.plan["time_window"] == "21:00 - 03:00"
    assert check.golden_evening[0]
    assert check.night_cloud == 50
    assert check.genre_scores["landscape"]["factors"]["黄金时刻"] == 10
    print("photo_advisor self-check OK")
