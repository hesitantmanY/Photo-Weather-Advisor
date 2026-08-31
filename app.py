#!/usr/bin/env python3
"""
摄影天气助手 - Web 服务 (Flask)
================================
在浏览器中查询城市天气并分析摄影适合度。

使用方法：
  1. 在 config.py 中填写 API_HOST 和 API_KEY
  2. 安装依赖: pip install -r requirements.txt
  3. 运行: python app.py
  4. 浏览器打开: http://127.0.0.1:5000

复用已有模块：
  - weather_api.py  : 城市搜索、天气预报
  - photo_advisor.py: 摄影适合度分析
"""

from dataclasses import asdict

from flask import Flask, jsonify, render_template, request

from weather_api import lookup_city, get_daily_weather, get_hourly_weather, check_config
from photo_advisor import GENRES, analyze_daily
import config

app = Flask(__name__)


@app.route("/")
def index():
    """渲染单页界面。"""
    return render_template(
        "index.html",
        default_city=getattr(config, "DEFAULT_CITY", ""),
    )


@app.route("/api/analyze")
def api_analyze():
    """
    分析接口：根据城市和天数返回摄影建议。

    查询参数：
      city : 城市名称或 LocationID（留空则用默认城市）
      days : 预报天数，1/3/7/10/15（默认 3）
      genre: 摄影题材，landscape/portrait/astro/long_exposure（默认 landscape）

    返回 JSON：
      { ok, city, adm, country, location_id, days, advices: [...] }
    """
    # 1. 检查配置
    if not check_config():
        return jsonify({
            "ok": False,
            "error": "服务器未正确配置和风天气 API，请检查 config.py 中的 API_HOST / API_KEY。",
        }), 500

    # 2. 解析参数
    city_input = (request.args.get("city") or "").strip()
    if not city_input:
        city_input = (getattr(config, "DEFAULT_CITY", "") or "").strip()
    if not city_input:
        return jsonify({"ok": False, "error": "请输入城市名称。"}), 400

    try:
        days = int(request.args.get("days", 3))
    except (TypeError, ValueError):
        days = 3
    if days not in (1, 3, 7, 10, 15):
        days = 3
    genre = request.args.get("genre", "landscape")
    if genre not in GENRES:
        genre = "landscape"

    # 3. 查询城市
    city_info = lookup_city(city_input)
    if city_info is None:
        return jsonify({
            "ok": False,
            "error": f"未找到城市「{city_input}」，请检查名称，或直接使用 LocationID（如 101010100）。",
        }), 404

    city_name = city_info.get("name", city_input)
    location_id = city_info.get("id", "")
    adm = city_info.get("adm1", "")
    country = city_info.get("country", "")

    # 4. 获取天气
    daily_list = get_daily_weather(location_id, days=days)
    if daily_list is None:
        return jsonify({
            "ok": False,
            "error": "获取天气数据失败，请检查 API 配置和网络连接。",
        }), 502

    # 5. 分析（含逐小时数据与天文计算）
    hourly_list = get_hourly_weather(location_id, hours=168)
    hourly_by_date = {}
    for h in hourly_list or []:
        hourly_by_date.setdefault(h.get("fxTime", "")[:10], []).append(h)

    advices = [
        asdict(analyze_daily(
            daily,
            hourly_by_date=hourly_by_date,
            lat=city_info.get("lat"),
            lon=city_info.get("lon"),
            genre=genre,
        ))
        for daily in daily_list
    ]

    # 6. 计算总结信息（所选题材最佳日 / 最可能火烧云）
    best_day = max(advices, key=lambda a: a["genre_scores"][genre]["score"]) if advices else None
    best_fire = max(advices, key=lambda a: a["fire_cloud_score"]) if advices else None

    return jsonify({
        "ok": True,
        "city": city_name,
        "adm": adm,
        "country": country,
        "location_id": location_id,
        "days": len(advices),
        "genre": genre,
        "genre_label": GENRES.get(genre, genre),
        "advices": advices,
        "summary": {
            "best_day": best_day["date"] if best_day else "",
            "best_score": best_day["genre_scores"][genre]["score"] if best_day else 0,
            "best_level": best_day["genre_scores"][genre]["level"] if best_day else "",
            "best_fire_day": best_fire["date"] if best_fire else "",
            "best_fire_chance": best_fire["fire_cloud_chance"] if best_fire else "",
            "best_fire_score": best_fire["fire_cloud_score"] if best_fire else 0,
            "plan": best_day["plan"] if best_day else {},
        },
    })


if __name__ == "__main__":
    print("=" * 60)
    print("  摄影天气助手 Web 版已启动")
    print("  请在浏览器打开: http://127.0.0.1:5000")
    print("  数据来源: 和风天气 QWeather")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5000, debug=True)
