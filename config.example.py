"""
摄影天气助手 - 配置文件示例
===========================
复制本文件为 config.py 后，填写你的和风天气 API 信息。
config.py 已被 .gitignore 忽略，不会提交到代码仓库。

获取方式：
1. 访问 https://console.qweather.com 注册并登录
2. 创建项目，获取 API Host 和 API Key
3. 将下方配置项替换为你的真实值

认证方式二选一：
  - 方式一（推荐新手）：API Key 认证，填写 api_key 即可
  - 方式二（更安全）：JWT 认证，填写 jwt 相关字段
"""

# API Host（必填）
# 在控制台 -> 设置 中查看，格式如: abc1234xyz.def.qweatherapi.com
# 如果你仍在使用旧版公共地址，可填写:
#   免费订阅: devapi.qweather.com
#   付费订阅: api.qweather.com
#   GeoAPI:   geoapi.qweather.com
API_HOST = "your-api-host.qweatherapi.com"

# GeoAPI Host（城市搜索用，可能与 API_HOST 不同）
# 旧版公共地址为: geoapi.qweather.com
# 新版统一使用你的独立 API Host 即可
GEOAPI_HOST = "your-api-host.qweatherapi.com"

# 认证方式一：API Key（简单方式，二选一）
# 在控制台 -> 项目管理 -> 凭据 中获取
API_KEY = "your-api-key"

# 认证方式二：JWT（更安全，二选一）
# 如果填写了 JWT 相关配置，将优先使用 JWT 认证
JWT_KEY_ID = ""          # 凭据 ID (kid)
JWT_PROJECT_ID = ""      # 项目 ID (sub)
JWT_PRIVATE_KEY_PATH = ""  # Ed25519 私钥文件路径，如 "./ed25519-private.pem"

# 默认城市（可选）
# 支持城市名称（如 "北京"）或 LocationID（如 "101010100"）
# 留空则运行时手动输入
DEFAULT_CITY = "珠海"

# 请求配置
REQUEST_TIMEOUT = 10  # 请求超时时间（秒）
