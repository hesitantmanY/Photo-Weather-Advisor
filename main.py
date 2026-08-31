#!/usr/bin/env python3
"""
摄影天气助手 (Photo Weather Advisor)
=====================================
通过和风天气 API 获取当地天气数据，
分析当天是否适合摄影（日出日落、火烧云、晚霞、风光等）。

使用方法：
  1. 在 config.py 中填写你的 API_HOST 和 API_KEY
  2. 安装依赖: pip install -r requirements.txt
  3. 运行: python main.py
  4. 可选参数: python main.py --city 上海

数据来源：和风天气 (https://www.qweather.com)
"""

import argparse
import sys

from weather_api import lookup_city, get_daily_weather, get_hourly_weather, check_config
from photo_advisor import GENRES, analyze_daily, PhotoAdvice


# ============================================================
# 终端输出格式化
# ============================================================

def _print_header():
    """打印程序标题。"""
    print()
    print("=" * 60)
    print("       摄影天气助手  Photo Weather Advisor")
    print("       数据来源：和风天气 QWeather")
    print("=" * 60)


def _print_divider(char="-", width=60):
    """打印分隔线。"""
    print(char * width)


def _print_score_bar(score: int, width: int = 20) -> str:
    """生成文本进度条。"""
    filled = int(score / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {score}%"


def _print_single_day(advice: PhotoAdvice, index: int, genre: str):
    """打印单天的摄影建议。"""
    print()
    _print_divider("─")
    print(f"  日期: {advice.date}  (第{index}天)")
    _print_divider("─")

    # 天气概况
    print(f"  天气: {advice.weather_desc}")
    print(f"  温度: {advice.temperature}")
    print(f"  湿度: {advice.humidity}")
    print(f"  风力: {advice.wind}")
    print(f"  能见度: {advice.visibility}")
    print(f"  云量: {advice.cloud_cover}")
    print()

    # 所选题材评分 + 因子拆解
    gs = advice.genre_scores.get(genre, {})
    label = GENRES.get(genre, genre)
    print(f"  {label}摄影评分: {_print_score_bar(gs.get('score', 0))}")
    print(f"     评级: {gs.get('level', '未知')}")
    factors = gs.get("factors", {})
    if factors:
        detail = ", ".join(f"{k} {v:+d}" for k, v in factors.items())
        print(f"     评分依据: {detail}")
    print()

    # 黄金时刻 / 蓝调时刻
    if advice.golden_evening[0]:
        print(f"  日落黄金时刻: {advice.golden_evening[0]} - {advice.golden_evening[1]}  "
              f"(方位 {advice.sunset_azimuth})")
    if advice.golden_morning[0]:
        print(f"  日出黄金时刻: {advice.golden_morning[0]} - {advice.golden_morning[1]}  "
              f"(方位 {advice.sunrise_azimuth})")
    print()

    # 日出日落
    print("  ┌─ 日出日落 ─────────────────────────────────┐")
    if advice.sunrise_advice:
        print(f"  │ {advice.sunrise_advice}")
    else:
        print("  │ 今日无日出数据（高纬度地区或极夜）")
    if advice.sunset_advice:
        print(f"  │ {advice.sunset_advice}")
    else:
        print("  │ 今日无日落数据（高纬度地区或极昼）")
    print("  └──────────────────────────────────────────────┘")
    print()

    # 火烧云/晚霞
    fire_mark = {
        "极高": "***",
        "较高": "**",
        "中等": "*",
        "较低": "-",
        "极低": "x",
    }
    mark = fire_mark.get(advice.fire_cloud_chance, "")
    print(f"  {mark} 火烧云/晚霞概率: {advice.fire_cloud_chance}  "
          f"{_print_score_bar(advice.fire_cloud_score, 10)}")
    print(f"  朝霞评分: {_print_score_bar(advice.morning_glow_score, 10)}")
    if advice.moon_phase:
        print(f"  月相: {advice.moon_phase}（照度 {advice.moon_illumination:.0%}）"
              f"  月出 {advice.moonrise}  月落 {advice.moonset}  夜间云量 {advice.night_cloud}%")
    if advice.fog_chance != "低" or advice.frost_chance != "低":
        print(f"  晨雾概率: {advice.fog_chance}  霜冻概率: {advice.frost_chance}")
    print()

    # 摄影建议
    if advice.tips:
        print("  摄影建议:")
        for i, tip in enumerate(advice.tips, 1):
            print(f"     {i}. {tip}")
    print()


def _print_plan(plan: dict):
    """打印拍摄计划卡。"""
    print()
    print(f"  拍摄计划 ({plan.get('genre_label', '')})")
    print("  " + "-" * 30)
    print(f"  日期: {plan.get('date', '')}  (评分 {plan.get('score', 0)}  {plan.get('level', '')})")
    if plan.get("time_window"):
        print(f"  时段: {plan['time_window']}  ({plan.get('window_label', '')})")
    if plan.get("direction"):
        print(f"  方向: {plan['direction']}")
    if plan.get("gear"):
        print(f"  器材: {', '.join(plan['gear'])}")
    if plan.get("risks"):
        print(f"  风险: {'；'.join(plan['risks'])}")
    if plan.get("summary"):
        print(f"  摘要: {plan['summary']}")


def _print_summary(city_name: str, advices: list, genre: str):
    """打印总结信息。"""
    _print_divider("═")
    print(f"  城市: {city_name}")
    label = GENRES.get(genre, genre)

    if not advices:
        print("  暂无可用的天气数据")
        return

    # 找出所选题材的最佳拍摄日
    best = max(advices, key=lambda a: a.genre_scores[genre]["score"])
    best_score = best.genre_scores[genre]["score"]
    best_level = best.genre_scores[genre]["level"]
    print(f"  最佳拍摄日（{label}）: {best.date}（评分 {best_score}，{best_level}）")
    _print_plan(best.plan)

    # 找出火烧云概率最高的一天
    best_fire = max(advices, key=lambda a: a.fire_cloud_score)
    if best_fire.fire_cloud_score >= 40:
        print(f"  最可能出现火烧云: {best_fire.date}"
              f"（概率 {best_fire.fire_cloud_chance}，评分 {best_fire.fire_cloud_score}%）")
    else:
        print("  未来几天火烧云概率均较低")

    _print_divider("═")
    print()
    print("  提示: 评分仅供参考，实际天气变化多端，建议结合实时观察。")
    print("  数据来源: 和风天气 QWeather (https://www.qweather.com)")
    print()


def main():
    """主程序入口。"""
    parser = argparse.ArgumentParser(
        description="摄影天气助手 - 分析和风天气数据，判断是否适合摄影",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                  # 使用默认城市
  python main.py --city 上海      # 查询上海
  python main.py --city 101010100 # 使用 LocationID
  python main.py --days 7         # 查看未来7天
  python main.py --genre astro    # 星空题材
        """,
    )
    parser.add_argument("--city", "-c", type=str, default="",
                        help="城市名称或 LocationID（留空使用 config.py 中的默认城市）")
    parser.add_argument("--days", "-d", type=int, default=3, choices=[1, 3, 7, 10, 15],
                        help="预报天数（默认3天）")
    parser.add_argument("--genre", "-g", type=str, default="landscape",
                        choices=list(GENRES),
                        help="摄影题材: landscape 风光 / portrait 人像 / astro 星空 / long_exposure 长曝光（默认 landscape）")

    args = parser.parse_args()

    _print_header()

    # 检查配置
    print("\n  [1/4] 检查配置...")
    if not check_config():
        sys.exit(1)
    print("  配置检查通过")

    # 确定查询城市
    city_input = args.city.strip() if args.city else ""
    if not city_input:
        from config import DEFAULT_CITY
        city_input = DEFAULT_CITY.strip() if DEFAULT_CITY else ""

    if not city_input:
        city_input = input("\n  请输入城市名称（如 北京、上海）: ").strip()
        if not city_input:
            print("  未输入城市名称，退出。")
            sys.exit(0)

    # 查询城市信息
    print(f"\n  [2/4] 查询城市: {city_input}")
    city_info = lookup_city(city_input)

    if city_info is None:
        print(f"  未找到城市「{city_input}」，请检查名称是否正确")
        print("  提示: 也可以直接使用 LocationID，如 101010100（北京）")
        sys.exit(1)

    city_name = city_info.get("name", city_input)
    location_id = city_info.get("id", "")
    adm = city_info.get("adm1", "")
    country = city_info.get("country", "")
    print(f"  找到: {city_name}，{adm}，{country}（ID: {location_id}）")

    # 获取天气预报
    print(f"\n  [3/4] 获取未来 {args.days} 天天气预报...")
    daily_list = get_daily_weather(location_id, days=args.days)

    if daily_list is None:
        print("  获取天气数据失败，请检查 API 配置和网络连接")
        sys.exit(1)
    print(f"  获取到 {len(daily_list)} 天的天气数据")

    # 获取逐小时预报（火烧云/星空/晨雾用）
    hourly_list = get_hourly_weather(location_id, hours=168)
    hourly_by_date = {}
    for h in hourly_list or []:
        hourly_by_date.setdefault(h.get("fxTime", "")[:10], []).append(h)

    # 分析摄影适合度
    print(f"\n  [4/4] 分析摄影适合度（题材: {GENRES.get(args.genre, args.genre)}）...")
    advices = []
    for daily in daily_list:
        advice = analyze_daily(
            daily,
            hourly_by_date=hourly_by_date,
            lat=city_info.get("lat"),
            lon=city_info.get("lon"),
            genre=args.genre,
        )
        advices.append(advice)
    print("  分析完成")

    # 输出结果
    print()
    for i, advice in enumerate(advices, 1):
        _print_single_day(advice, i, args.genre)

    _print_summary(f"{city_name}（{adm}）", advices, args.genre)


if __name__ == "__main__":
    main()
