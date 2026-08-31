# 题材切换 + 拍摄计划卡 + 摄影师视角指标 实施计划

> 执行方式：内联执行（仓库小、改动耦合度高；不派子代理）。

**Goal:** 让工具按题材（风光/人像/星空/长曝光）给出独立评分、可解释的因子拆解和一张可直接照做的拍摄计划卡，并接入逐小时数据重写火烧云模型、补充黄金时刻/方位角/月相/晨雾霜冻等摄影师指标。

**Architecture:** 新增纯标准库天文模块 `astro.py`（太阳位置、黄金/蓝调时刻、方位角、月相亮度）；`weather_api.py` 增加 168h 逐小时接口与 TTL 缓存；`photo_advisor.py` 扩展为多题材评分 + 因子 + 计划卡；`main.py` 与 Flask/前端消费新字段。

**Tech Stack:** Python 3 标准库 + 现有 requests/Flask，不新增依赖。

## Global Constraints

- 项目内禁止任何 emoji（代码、文案、README、提交说明）。
- 不新增第三方依赖；天文计算用标准库数学实现。
- 现有 CLI/Web 使用方式保持兼容，只加参数与字段。
- 题材标识固定为：`landscape` 风光、`portrait` 人像、`astro` 星空、`long_exposure` 长曝光。
- 评分模型为启发式，透明展示因子拆解；不可解释的权重变化一律标 `ponytail:` 注释说明简化点。
- 非平凡逻辑（太阳位置、评分、计划生成）留下一个可运行的 assert 自检入口。

---

## Task 1: weather_api.py 增加逐小时接口与缓存

**Files:** `weather_api.py`

**Interfaces:**
- `get_hourly_weather(location: str, hours: int = 168) -> Optional[list]`：请求 `/v7/weather/{24h|72h|168h}`，返回 hourly 列表。
- `_cached(key, ttl, fn)`：模块级 dict + 时间戳 TTL 缓存（geo 24h / daily 6h / hourly 30min）。
- 抽出 `_request_json(host, path, params) -> Optional[dict]` 复用请求/异常处理（gzip 由 requests 自动处理）。

检查点：venv 中 `python -c "import weather_api; print(len(weather_api.get_hourly_weather('101280701')))"` 输出 168。

## Task 2: astro.py 天文计算

**Files:** 新建 `astro.py`

**Interfaces:**
- `solar_position(dt, lat, lon) -> (elev_deg, az_deg)`：Wikipedia 太阳位置公式（赤纬、时角、高度角、方位角），本地时间按 UTC+8 处理。
- `sun_events(date, lat, lon) -> dict`：扫描每日 04:00-22:00 每分钟高度角，插值求 -6/-4/0/6 度穿越时刻，输出：
  `golden_morning (start,end)`、`golden_evening`、`blue_morning`、`blue_evening`（HH:MM）。
- `azimuth_at(hhmm, date, lat, lon) -> (az_deg, direction_text)`。
- `moon_illumination(phase_text) -> float`：QWeather 月相文本到 0-1 亮度映射。
- `direction_text(az) -> str`：8 方位中文。
- `__main__` assert 自检：珠海 2026-08-31 太阳正午高度约 67 度、日出方位约 80 度（允许 ±3 度容差）。

## Task 3: photo_advisor.py 多题材评分 + 因子 + 计划卡

**Files:** `photo_advisor.py`

**签名变化：** `analyze_daily(daily, hourly_by_date=None, lat=None, lon=None, genre="landscape") -> PhotoAdvice`

**新字段（PhotoAdvice）：**
- `genres: dict`：`{genre: {"score", "level", "factors": {中文因子: int}}}`，`factors` 如 `{"云量": 40, "天气": 25, "降水": -30}`。
- 顶层兼容字段：`overall_score/overall_level` = 所选题材分数；`landscape_score`、`fire_cloud_score/chance` 保留。
- `portrait_score/astro_score/long_exposure_score` 及各 level。
- `morning_glow_score`（朝霞）、`fog_chance/frost_chance`（高/中/低）。
- `golden_morning/golden_evening/blue_morning/blue_evening`、`sunrise_azimuth/sunset_azimuth`（含中文方向）、`moon_phase/moonrise/moonset/moon_illumination`、`night_cloud`。
- `plan: dict`：所选题材最佳日计划卡 `{genre, genre_label, date, score, level, time_window, window_label, direction, gear: [..], risks: [..], summary}`。

**评分规则（启发式，全部返回因子）：**
- 火烧云/朝霞：取日落/日出 ±1h 窗口内的逐小时云量均值、天气文本、降水、pop；窗口内云量 30-70 加 40 分，20-30/70-85 加 20；天气好加 25；有降水 -30；能见度 >=25 加 15、>=15 加 10；湿度 40-70 加 10；午后云量回落趋势加 10。无逐小时数据时回退旧日级模型。
- 人像：多云/少云/晴间多云 +20、晴 +10、恶劣 -30；黄金时刻窗口 +10；风力 <=8 +10；降水 -30；湿度 >85 -5。
- 星空：基础 100；夜间云量（21:00-03:00 均值）按百分比扣；月光按亮度*40 扣（月亮不在夜间窗口则不扣）；夜间降水 -20；能见度 <15 -10。
- 长曝光：微风 <=3 +30、<=8 +20；无降水 +20；云量 30-80 +15；黄金时刻 +15；能见度 >=15 +10。
- 晨雾/霜冻：05:00-08:00 气温-露点 <=2 且湿度 >=85 且风速 <=10 判高，<=3 且 >=80 判中；霜冻再加最低温 <=1/<=4 条件。

**计划卡规则：**
- 风光/人像/长曝光优先取日落黄金时刻，其次日出；星空取夜间窗口（按月出月落裁剪）。
- 方向：日落/日出方位角转中文 8 方位；星空给“面向远离城市光害方向”。
- 器材：长曝光/星空/大风必给三脚架；长曝光给 ND；湿度高或晨雾高给镜头布；降水给防雨罩；人像晴天给反光板；低温给备用电池。
- 风险：降水、大风、高湿、强月光（星空）、云量高（星空）。

检查点：`python photo_advisor.py` 无输出直接退出不报错；venv 中跑 CLI 能看到各题材分数与因子。

## Task 4: main.py CLI 题材参数与计划卡输出

**Files:** `main.py`

- 新增 `--genre`（choices: landscape/portrait/astro/long_exposure，默认 landscape）。
- 单日输出显示所选题材分数 + 因子行 + 黄金时刻/月相/晨雾；总结取所选题材最佳日并打印计划卡。
- 保留现有无 emoji 输出风格。

## Task 5: app.py + templates/index.html 题材切换、计划卡、因子展示

**Files:** `app.py`, `templates/index.html`

- `/api/analyze` 新增 `genre` 参数（默认 landscape），summary 的 best_day 按所选题材计算，返回 `genre` 与计划卡字段。
- 前端：查询条加题材下拉；结果页加“拍摄计划”卡片（时间/方向/器材/风险）；每日条目展示所选题材分数、因子行、黄金时刻/月相/晨雾/朝霞；保持现有黑白编辑风格，无 emoji。

## Task 6: 验证、README、提交推送

- `python -m py_compile` 全部 py 文件；`astro.py` assert 自检通过。
- 临时 venv 安装 requirements，真实跑 CLI（珠海）与 Flask `/api/analyze?genre=astro`。
- 全文件 emoji 扫描为 0。
- 更新 README（无 emoji）说明题材、计划卡、新参数。
- `git add -A && git commit && git push origin main`。
