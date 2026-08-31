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

from weather_api import lookup_city, get_daily_weather, check_config
from photo_advisor import analyze_daily, PhotoAdvice


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


def _print_single_day(advice: PhotoAdvice, index: int):
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

    # 综合评分
    print(f"  综合摄影评分: {_print_score_bar(advice.overall_score)}")
    print(f"     评级: {advice.overall_level}")
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
    print(f"  风光摄影适合度: {_print_score_bar(advice.landscape_score, 10)}")
    print()

    # 摄影建议
    if advice.tips:
        print("  摄影建议:")
        for i, tip in enumerate(advice.tips, 1):
            print(f"     {i}. {tip}")
    print()


def _print_summary(city_name: str, advices: list):
    """打印总结信息。"""
    _print_divider("═")
    print(f"  城市: {city_name}")

    if not advices:
        print("  暂无可用的天气数据")
        return

    # 找出最佳拍摄日
    best = max(advices, key=lambda a: a.overall_score)
    print(f"  最佳拍摄日: {best.date}（评分 {best.overall_score}%，{best.overall_level}）")

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
        """,
    )
    parser.add_argument("--city", "-c", type=str, default="",
                        help="城市名称或 LocationID（留空使用 config.py 中的默认城市）")
    parser.add_argument("--days", "-d", type=int, default=3, choices=[1, 3, 7, 10, 15],
                        help="预报天数（默认3天）")

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

    # 分析摄影适合度
    print(f"\n  [4/4] 分析摄影适合度...")
    advices = []
    for daily in daily_list:
        advice = analyze_daily(daily)
        advices.append(advice)
    print("  分析完成")

    # 输出结果
    print()
    for i, advice in enumerate(advices, 1):
        _print_single_day(advice, i)

    _print_summary(f"{city_name}（{adm}）", advices)


if __name__ == "__main__":
    main()
