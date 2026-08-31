"""
摄影天气助手 - 摄影适合度分析模块
==================================
根据天气数据分析是否适合摄影，
包括日出日落、火烧云/晚霞、风光摄影等场景的评估。
"""

from dataclasses import dataclass, field


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


def _calc_fire_cloud_score(cloud: int, text_day: str, text_night: str,
                           precip: float, vis: float, humidity: int) -> int:
    """
    计算火烧云/晚霞出现概率评分。

    火烧云形成条件（气象学依据）：
    - 中高云量（30%-70%）：云层是火烧云的载体，太少无云可烧，太多则遮蔽天空
    - 天气以晴到多云为主：不能有降水
    - 能见度好：大气通透，光线穿透力强
    - 湿度适中：过高则雾霾遮挡，过低则云层不够丰富
    """
    score = 0

    # 云量评分（核心因素，权重最高）
    if 30 <= cloud <= 70:
        score += 40  # 最佳云量区间
    elif 20 <= cloud < 30 or 70 < cloud <= 80:
        score += 25  # 次优区间
    elif 10 <= cloud < 20 or 80 < cloud <= 90:
        score += 10  # 勉强
    else:
        score += 0   # 云量太少或太多

    # 天气状况评分
    if text_day in FIRE_CLOUD_WEATHER or text_night in FIRE_CLOUD_WEATHER:
        score += 25
    elif text_day in GOOD_PHOTO_WEATHER or text_night in GOOD_PHOTO_WEATHER:
        score += 15

    # 降水扣分（有降水基本不可能出现火烧云）
    if precip > 0:
        score -= 30

    # 能见度评分
    if vis >= 25:
        score += 20
    elif vis >= 15:
        score += 15
    elif vis >= 10:
        score += 8
    else:
        score += 0

    # 湿度评分
    if 40 <= humidity <= 70:
        score += 15
    elif 30 <= humidity < 40 or 70 < humidity <= 80:
        score += 8
    else:
        score += 0

    return max(0, min(100, score))


def _calc_landscape_score(text_day: str, cloud: int, vis: float,
                          precip: float, humidity: int, wind_speed: float,
                          uv_index: int) -> int:
    """
    计算风光摄影适合度评分。

    风光摄影偏好：
    - 晴天或多云（光线充足，层次丰富）
    - 能见度高（远景清晰）
    - 无降水
    - 微风（长曝光时植物不会过度晃动）
    - 湿度适中
    """
    score = 50  # 基础分

    # 天气状况
    if text_day in GOOD_PHOTO_WEATHER:
        score += 20
    elif text_day in BAD_PHOTO_WEATHER:
        score -= 30
    else:
        score += 5

    # 能见度
    if vis >= 25:
        score += 15
    elif vis >= 15:
        score += 10
    elif vis >= 10:
        score += 5
    else:
        score -= 15

    # 降水
    if precip > 0:
        score -= 20

    # 风力（微风适合，大风不适合）
    if wind_speed <= 5:
        score += 10
    elif wind_speed <= 15:
        score += 5
    elif wind_speed <= 25:
        score -= 5
    else:
        score -= 15

    # 湿度
    if 30 <= humidity <= 70:
        score += 5
    elif humidity > 85:
        score -= 10

    # UV指数（高UV意味着晴天，光线好）
    if uv_index >= 5:
        score += 5

    return max(0, min(100, score))


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


def analyze_daily(daily: dict) -> PhotoAdvice:
    """
    分析单天的天气数据，生成摄影建议。

    Args:
        daily: 和风天气每日预报数据

    Returns:
        PhotoAdvice 对象
    """
    # 提取天气数据
    cloud = _safe_int(daily.get("cloud", "0"))
    precip = _safe_float(daily.get("precip", "0"))
    humidity = _safe_int(daily.get("humidity", "0"))
    vis = _safe_float(daily.get("vis", "0"))
    wind_speed = _safe_float(daily.get("windSpeedDay", "0"))
    uv_index = _safe_int(daily.get("uvIndex", "0"))
    text_day = daily.get("textDay", "")
    text_night = daily.get("textNight", "")
    temp_max = daily.get("tempMax", "")
    temp_min = daily.get("tempMin", "")
    sunrise = daily.get("sunrise", "")
    sunset = daily.get("sunset", "")

    # 计算各项评分
    fire_score = _calc_fire_cloud_score(cloud, text_day, text_night, precip, vis, humidity)
    landscape_score = _calc_landscape_score(text_day, cloud, vis, precip, humidity, wind_speed, uv_index)

    # 综合评分 = 火烧云权重30% + 风光权重50% + 基础天气20%
    weather_base = 50 if text_day in GOOD_PHOTO_WEATHER else (20 if text_day in BAD_PHOTO_WEATHER else 35)
    overall_score = int(fire_score * 0.3 + landscape_score * 0.5 + weather_base * 0.2)

    # 生成建议
    tips = _generate_tips(daily, fire_score, landscape_score)

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

    return PhotoAdvice(
        date=daily.get("fxDate", ""),
        overall_score=overall_score,
        overall_level=_get_overall_level(overall_score),
        sunrise_time=sunrise,
        sunset_time=sunset,
        sunrise_advice=sunrise_advice,
        sunset_advice=sunset_advice,
        fire_cloud_chance=_get_fire_cloud_chance(fire_score),
        fire_cloud_score=fire_score,
        landscape_score=landscape_score,
        weather_desc=f"{text_day} / 夜间{text_night}",
        temperature=f"{temp_min}°C ~ {temp_max}°C",
        humidity=f"{humidity}%",
        wind=f"{daily.get('windDirDay', '')} {daily.get('windScaleDay', '')}级",
        visibility=f"{vis}km",
        cloud_cover=f"{cloud}%",
        tips=tips,
    )
