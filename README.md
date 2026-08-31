# Photo Weather Advisor

摄影天气助手（Photo Weather Advisor）

通过和风天气 API 获取当地天气数据，分析未来几天是否适合摄影，重点关注日出日落、火烧云、晚霞和风光摄影等场景。项目同时提供命令行和 Web 两种使用方式。

## 功能

- 城市搜索，支持城市名称或 LocationID
- 获取未来 1 / 3 / 7 / 10 / 15 天天气预报
- 综合摄影评分及评级
- 日出、日落时间与拍摄建议
- 火烧云 / 晚霞概率评估
- 风光摄影适合度评分
- 个性化摄影建议
- 命令行工具与 Flask Web 页面

## 目录结构

- `main.py`：命令行入口
- `app.py`：Flask Web 服务入口
- `weather_api.py`：和风天气 API 调用封装（支持 API Key 与 JWT 认证）
- `photo_advisor.py`：摄影适合度分析逻辑
- `config.py`：本地配置（已被 gitignore，不提交到仓库）
- `config.example.py`：配置示例，复制为 `config.py` 后填写真实信息
- `templates/index.html`：Web 页面模板

## 环境要求

- Python 3.9 或更高版本
- 和风天气开发者账号及 API 凭据

## 安装

```bash
git clone https://github.com/hesitantmanY/Weather-.git
cd Weather-
pip install -r requirements.txt
```

## 配置

1. 访问和风天气控制台（https://console.qweather.com）注册并登录
2. 创建项目，获取 API Host 和 API Key（或 JWT 凭据）
3. 复制配置示例并填写真实信息：

```bash
cp config.example.py config.py
```

在 `config.py` 中至少需要填写：

- `API_HOST`：你的独立 API Host，例如 `abc1234xyz.def.qweatherapi.com`
- `API_KEY`：API Key 认证方式下填写
- `DEFAULT_CITY`：默认查询城市，支持城市名称或 LocationID

JWT 认证为可选，如需使用请填写 `JWT_KEY_ID`、`JWT_PROJECT_ID` 和 `JWT_PRIVATE_KEY_PATH`。

## 使用

### 命令行

```bash
python main.py
```

可选参数：

```bash
python main.py --city 上海
python main.py --city 101010100
python main.py --days 7
```

### Web 页面

```bash
python app.py
```

浏览器打开 http://127.0.0.1:5000 即可查询城市并查看摄影建议，也可直接调用分析接口：

```text
GET /api/analyze?city=上海&days=3
```

## 数据来源

- 和风天气（https://www.qweather.com）
- 天气图标代码说明：https://icons.qweather.com/

## 许可证

本项目基于 MIT License 开源，详见 [LICENSE](LICENSE)。
