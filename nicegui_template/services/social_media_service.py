"""
Social Media Insights Service - Instagram & TikTok API integration.
Handles token management, data fetching, and caching for dashboard.
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

import requests

# Paths
CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "streamlit_template" / "data" / "social_media_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = CACHE_DIR / "social_media_config.json"

# API Endpoints
IG_GRAPH_API = "https://graph.facebook.com/v19.0"
TIKTOK_API = "https://open.tiktokapis.com/v2"


# CONFIG MANAGEMENT

def _load_config() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_config(cfg: dict):
    tmp = str(CONFIG_PATH) + ".tmp." + str(os.getpid())
    try:
        with open(tmp, "w") as f:
            json.dump(cfg, f, indent=2, default=str)
        os.replace(tmp, str(CONFIG_PATH))
    except Exception as e:
        print(f"[social_media] Error saving config: {e}")


def get_ig_config() -> dict:
    cfg = _load_config()
    return cfg.get("instagram", {})


def set_ig_config(access_token: str, ig_user_id: str, page_id: str = ""):
    cfg = _load_config()
    cfg["instagram"] = {
        "access_token": access_token,
        "ig_user_id": ig_user_id,
        "page_id": page_id,
        "updated_at": datetime.now().isoformat(),
    }
    _save_config(cfg)


def get_tiktok_config() -> dict:
    cfg = _load_config()
    return cfg.get("tiktok", {})


def set_tiktok_config(access_token: str, refresh_token: str, open_id: str):
    cfg = _load_config()
    cfg["tiktok"] = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "open_id": open_id,
        "updated_at": datetime.now().isoformat(),
    }
    _save_config(cfg)


# CACHE MANAGEMENT

def _get_cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def _load_cache(key: str, max_age_hours: int = 6) -> Optional[dict]:
    path = _get_cache_path(key)
    if not path.exists():
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
        if datetime.now() - cached_at > timedelta(hours=max_age_hours):
            return None
        return data.get("data")
    except Exception:
        return None


def _save_cache(key: str, data: dict):
    path = _get_cache_path(key)
    tmp = str(path) + ".tmp." + str(os.getpid())
    try:
        with open(tmp, "w") as f:
            json.dump({
                "cached_at": datetime.now().isoformat(),
                "data": data,
            }, f, indent=2, default=str)
        os.replace(tmp, str(path))
    except Exception as e:
        print(f"[social_media] Error saving cache {key}: {e}")


# INSTAGRAM API

def _ig_request(endpoint: str, params: dict = None) -> dict:
    cfg = get_ig_config()
    token = cfg.get("access_token")
    if not token:
        return {"error": "Instagram access_token not configured"}
    url = f"{IG_GRAPH_API}/{endpoint}"
    params = params or {}
    params["access_token"] = token
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def ig_get_profile() -> dict:
    cached = _load_cache("ig_profile", max_age_hours=12)
    if cached:
        return cached
    cfg = get_ig_config()
    ig_user_id = cfg.get("ig_user_id")
    if not ig_user_id:
        return {"error": "ig_user_id not configured"}
    data = _ig_request(ig_user_id, {
        "fields": "id,username,name,biography,followers_count,follows_count,media_count,profile_picture_url"
    })
    if "error" not in data:
        _save_cache("ig_profile", data)
    return data


def ig_get_insights(period: str = "day", days_back: int = 30) -> dict:
    cache_key = f"ig_insights_{period}_{days_back}"
    cached = _load_cache(cache_key, max_age_hours=6)
    if cached:
        return cached
    cfg = get_ig_config()
    ig_user_id = cfg.get("ig_user_id")
    if not ig_user_id:
        return {"error": "ig_user_id not configured"}
    metrics = "impressions,reach,profile_views,follower_count"
    data = _ig_request(f"{ig_user_id}/insights", {
        "metric": metrics,
        "period": period,
        "since": (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d"),
        "until": datetime.now().strftime("%Y-%m-%d"),
    })
    if "error" not in data:
        _save_cache(cache_key, data)
    return data


def ig_get_media(limit: int = 50) -> List[dict]:
    cached = _load_cache("ig_media", max_age_hours=6)
    if cached:
        return cached
    cfg = get_ig_config()
    ig_user_id = cfg.get("ig_user_id")
    if not ig_user_id:
        return []
    data = _ig_request(f"{ig_user_id}/media", {
        "fields": "id,caption,media_type,like_count,comments_count,timestamp,permalink,media_url,thumbnail_url",
        "limit": limit,
    })
    if "error" in data:
        return []
    media_list = data.get("data", [])
    _save_cache("ig_media", media_list)
    return media_list


def ig_get_audience() -> dict:
    cached = _load_cache("ig_audience", max_age_hours=24)
    if cached:
        return cached
    cfg = get_ig_config()
    ig_user_id = cfg.get("ig_user_id")
    if not ig_user_id:
        return {"error": "ig_user_id not configured"}
    metrics = "audience_city,audience_country,audience_gender_age,audience_locale"
    data = _ig_request(f"{ig_user_id}/insights", {
        "metric": metrics,
        "period": "lifetime",
    })
    if "error" not in data:
        _save_cache("ig_audience", data)
    return data


# TIKTOK API

def _tiktok_request(endpoint: str, params: dict = None) -> dict:
    cfg = get_tiktok_config()
    token = cfg.get("access_token")
    open_id = cfg.get("open_id")
    if not token or not open_id:
        return {"error": "TikTok credentials not configured"}
    url = f"{TIKTOK_API}{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Client-ID": os.getenv("TIKTOK_CLIENT_ID", ""),
    }
    params = params or {}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def tiktok_get_user_info() -> dict:
    cached = _load_cache("tiktok_profile", max_age_hours=12)
    if cached:
        return cached
    data = _tiktok_request("/user/info/", {
        "fields": "display_name,avatar_url,profile_deep_link"
    })
    if "error" not in data:
        _save_cache("tiktok_profile", data.get("data", {}))
    return data.get("data", data)


def tiktok_get_user_stats() -> dict:
    cached = _load_cache("tiktok_stats", max_age_hours=6)
    if cached:
        return cached
    data = _tiktok_request("/user/info/stats/", {
        "fields": "follower_count,following_count,likes_count,video_count"
    })
    if "error" not in data:
        _save_cache("tiktok_stats", data.get("data", {}))
    return data.get("data", data)


def tiktok_get_videos(max_count: int = 50) -> List[dict]:
    cached = _load_cache("tiktok_videos", max_age_hours=6)
    if cached:
        return cached
    data = _tiktok_request("/video/list/", {
        "fields": "id,title,create_time,cover_image_url,embed_link,duration,view_count,like_count,comment_count,share_count",
        "max_count": max_count,
    })
    if "error" in data:
        return []
    videos = data.get("data", {}).get("videos", [])
    _save_cache("tiktok_videos", videos)
    return videos


# AGGREGATED DATA FOR DASHBOARD

def get_dashboard_data() -> dict:
    cached = _load_cache("dashboard_all", max_age_hours=6)
    if cached:
        return cached
    data = {
        "instagram": {
            "profile": ig_get_profile(),
            "insights": ig_get_insights(),
            "media": ig_get_media(limit=30),
            "audience": ig_get_audience(),
        },
        "tiktok": {
            "profile": tiktok_get_user_info(),
            "stats": tiktok_get_user_stats(),
            "videos": tiktok_get_videos(max_count=30),
        },
        "last_sync": datetime.now().isoformat(),
    }
    _save_cache("dashboard_all", data)
    return data


def refresh_all_data():
    for cache_file in CACHE_DIR.glob("*.json"):
        if cache_file.name != "social_media_config.json":
            try:
                cache_file.unlink()
            except Exception:
                pass
    return get_dashboard_data()


def get_sync_status() -> dict:
    try:
        with open(_get_cache_path("dashboard_all")) as f:
            data = json.load(f)
            return {
                "last_sync": data.get("cached_at"),
                "status": "ok",
            }
    except Exception:
        return {
            "last_sync": None,
            "status": "no_data",
        }
