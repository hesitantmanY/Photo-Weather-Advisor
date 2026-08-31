"""
摄影天气助手 - 和风天气 API 调用模块
====================================
封装城市搜索、每日天气预报等接口调用。
支持 API Key 和 JWT 两种认证方式。
"""

import time
from typing import Optional

import requests

import config


def _generate_jwt_token() -> str:
    """
    使用 Ed25519 私钥生成 JWT Token。
    需要安装 PyJWT 和 cryptography 库。
    """
    import jwt

    # 读取私钥文件
    with open(config.JWT_PRIVATE_KEY_PATH, "r") as f:
        private_key = f.read()

    now = int(time.time())
    payload = {
        "iat": now - 30,       # 签发时间提前30秒，防止时钟偏差
        "exp": now + 900,      # 15分钟后过期
        "sub": config.JWT_PROJECT_ID,
    }
    headers = {
        "kid": config.JWT_KEY_ID,
    }

    token = jwt.encode(payload, private_key, algorithm="EdDSA", headers=headers)
    return token


def _get_auth_headers() -> dict:
    """
    根据配置生成认证请求头。
    优先使用 JWT，其次使用 API Key。
    """
    # 优先 JWT 认证
    if config.JWT_KEY_ID and config.JWT_PROJECT_ID and config.JWT_PRIVATE_KEY_PATH:
        token = _generate_jwt_token()
        return {"Authorization": f"Bearer {token}"}

    # 其次 API Key 认证
    if config.API_KEY and config.API_KEY != "你的API_KEY":
        return {"X-QW-Api-Key": config.API_KEY}

    raise ValueError(
        "未配置有效的认证信息！\n"
        "请在 config.py 中填写 API_KEY 或 JWT 相关配置。\n"
        "获取方式：https://console.qweather.com"
    )


def _build_url(host: str, path: str) -> str:
    """构建完整的 API URL。"""
    host = host.strip()
    if not host.startswith("http"):
        host = f"https://{host}"
    return f"{host}{path}"


def lookup_city(city_name: str) -> Optional[dict]:
    """
    城市搜索：根据城市名称查询 LocationID 和城市信息。

    Args:
        city_name: 城市名称，如 "北京"、"上海"

    Returns:
        城市信息字典，包含 name, id, lat, lon 等字段；未找到返回 None
    """
    url = _build_url(config.GEOAPI_HOST, "/geo/v2/city/lookup")
    params = {
        "location": city_name,
        "lang": "zh",
        "number": 1,
    }

    try:
        headers = _get_auth_headers()
        resp = requests.get(url, params=params, headers=headers, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") == "200" and data.get("location"):
            return data["location"][0]
        else:
            print(f"  [警告] 城市搜索失败: code={data.get('code')}")
            return None

    except requests.exceptions.Timeout:
        print("  [错误] 城市搜索请求超时，请检查网络连接")
        return None
    except requests.exceptions.ConnectionError:
        print("  [错误] 无法连接到和风天气 API，请检查 API_HOST 配置")
        return None
    except Exception as e:
        print(f"  [错误] 城市搜索异常: {e}")
        return None


def get_daily_weather(location: str, days: int = 3) -> Optional[list]:
    """
    获取每日天气预报。

    Args:
        location: LocationID 或经纬度坐标（如 "101010100" 或 "116.41,39.92"）
        days: 预报天数，支持 3/7/10/15/30

    Returns:
        每日预报数据列表，每个元素包含 fxDate, tempMax, tempMin,
        textDay, textNight, cloud, humidity, vis, precip, sunrise, sunset 等
    """
    days_map = {1: "3d", 3: "3d", 7: "7d", 10: "10d", 15: "15d", 30: "30d"}
    days_param = days_map.get(days, "3d")

    url = _build_url(config.API_HOST, f"/v7/weather/{days_param}")
    params = {
        "location": location,
        "lang": "zh",
    }

    try:
        headers = _get_auth_headers()
        resp = requests.get(url, params=params, headers=headers, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") == "200" and data.get("daily"):
            return data["daily"]
        else:
            print(f"  [警告] 天气查询失败: code={data.get('code')}")
            return None

    except requests.exceptions.Timeout:
        print("  [错误] 天气查询请求超时")
        return None
    except requests.exceptions.ConnectionError:
        print("  [错误] 无法连接到和风天气 API，请检查 API_HOST 配置")
        return None
    except Exception as e:
        print(f"  [错误] 天气查询异常: {e}")
        return None


def check_config() -> bool:
    """
    检查配置是否有效。

    Returns:
        配置是否有效
    """
    # 检查 API Host
    if config.API_HOST in ("你的API_HOST", "", None):
        print("=" * 50)
        print("  请先在 config.py 中配置你的 API_HOST")
        print("  获取方式：登录 https://console.qweather.com")
        print("  在 控制台 -> 设置 中查看你的 API Host")
        print("=" * 50)
        return False

    # 检查认证信息
    has_api_key = config.API_KEY not in ("你的API_KEY", "", None)
    has_jwt = all([
        config.JWT_KEY_ID,
        config.JWT_PROJECT_ID,
        config.JWT_PRIVATE_KEY_PATH,
    ])

    if not has_api_key and not has_jwt:
        print("=" * 50)
        print("  请先在 config.py 中配置认证信息（二选一）：")
        print("  方式一：填写 API_KEY（推荐新手）")
        print("  方式二：填写 JWT_KEY_ID, JWT_PROJECT_ID, JWT_PRIVATE_KEY_PATH")
        print("  获取方式：登录 https://console.qweather.com")
        print("=" * 50)
        return False

    return True
