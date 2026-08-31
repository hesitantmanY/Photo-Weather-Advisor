import app as web_app
import config


def test_initial_page_does_not_prefill_or_auto_query_default_city():
    client = web_app.app.test_client()

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="city" placeholder="城市名 / Location ID"' in html
    assert 'value="珠海"' not in html
    assert "requestSubmit()" not in html
    assert "可留空使用默认城市" in html


def test_empty_city_falls_back_to_configured_default_city(monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_CITY", "珠海")
    monkeypatch.setattr(web_app, "check_config", lambda: True)

    captured = {}
    daily = {
        "date": "2026-08-31",
        "genre_scores": {"landscape": {"score": 80, "level": "适合"}},
        "fire_cloud_score": 10,
        "fire_cloud_chance": "低",
        "plan": {},
    }

    def lookup_city(city):
        captured["city"] = city
        return {
            "name": "珠海",
            "id": "101280701",
            "adm1": "广东省",
            "country": "中国",
            "lat": 22.27,
            "lon": 113.57,
        }

    monkeypatch.setattr(web_app, "lookup_city", lookup_city)
    monkeypatch.setattr(web_app, "get_daily_weather", lambda location, days=3: [daily])
    monkeypatch.setattr(web_app, "get_hourly_weather", lambda location, hours=168: [])
    monkeypatch.setattr(web_app, "analyze_daily", lambda daily_record, **kwargs: daily_record)
    monkeypatch.setattr(web_app, "asdict", lambda advice: advice)

    client = web_app.app.test_client()
    response = client.get("/api/analyze", query_string={"days": 3, "genre": "landscape"})

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["city"] == "珠海"
    assert captured["city"] == "珠海"


def test_development_server_avoids_macos_airplay_port(monkeypatch):
    captured = {}
    monkeypatch.setattr(web_app.app, "run", lambda **kwargs: captured.update(kwargs))

    web_app.main()

    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 5001
