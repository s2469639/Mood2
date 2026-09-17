from __future__ import annotations
import random
from typing import Any, Dict, List, Optional
import urllib.parse
import requests

MINIMUM_POPULARITY_THRESHOLD = 150000

VERIFIED_MAINSTREAM_FALLBACK = [
    {
        "title": "밤편지",
        "artist": "아이유",
        "artwork": "https://is1-ssl.mzstatic.com/image/thumb/Music118/v4/b8/b5/0b/b8b50b73-030a-3ecb-665e-bc8e20235940/cover_IU_ThroughTheNight.jpg/600x600bb.jpg",
        "album_art": "https://is1-ssl.mzstatic.com/image/thumb/Music118/v4/b8/b5/0b/b8b50b73-030a-3ecb-665e-bc8e20235940/cover_IU_ThroughTheNight.jpg/600x600bb.jpg",
        "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview115/v4/b7/c1/9d/b7c19d4e-1282-1cbe-41bf-3df08e9a2be9/mzaf_10526084092497793448.plus.aac.p.m4a",
        "yt_music_url": "https://music.youtube.com/search?q=%EC%95%84%EC%9D%B4%EC%9C%A0+%EB%B0%A4%ED%8E%B8%EC%A7%80",
        "popularity": 900000
    },
    {
        "title": "Ditto",
        "artist": "NewJeans",
        "artwork": "https://is1-ssl.mzstatic.com/image/thumb/Music113/v4/4c/76/85/4c768571-0847-f32f-b48a-a3a8309df507/cover_NewJeans_OMG.jpg/600x600bb.jpg",
        "album_art": "https://is1-ssl.mzstatic.com/image/thumb/Music113/v4/4c/76/85/4c768571-0847-f32f-b48a-a3a8309df507/cover_NewJeans_OMG.jpg/600x600bb.jpg",
        "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview122/v4/e5/22/07/e52207a7-5431-1e96-a836-8cb9622d100a/mzaf_3990812977823908953.plus.aac.p.m4a",
        "yt_music_url": "https://music.youtube.com/search?q=NewJeans+Ditto",
        "popularity": 950000
    },
    {
        "title": "Square (2017)",
        "artist": "백예린",
        "artwork": "https://is1-ssl.mzstatic.com/image/thumb/Music113/v4/48/80/4f/48804f58-6934-8c70-6644-33827ec32f5d/cover_YerinBaek_Square.jpg/600x600bb.jpg",
        "album_art": "https://is1-ssl.mzstatic.com/image/thumb/Music113/v4/48/80/4f/48804f58-6934-8c70-6644-33827ec32f5d/cover_YerinBaek_Square.jpg/600x600bb.jpg",
        "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview125/v4/71/bf/20/71bf2092-be29-d055-6b58-e4905d41a7d6/mzaf_4840898517227447814.plus.aac.p.m4a",
        "yt_music_url": "https://music.youtube.com/search?q=%EB%B0%B1%EC%98%88%EB%A6%B0+Square",
        "popularity": 850000
    },
    {
        "title": "That's What I Like",
        "artist": "Bruno Mars",
        "artwork": "https://is1-ssl.mzstatic.com/image/thumb/Music115/v4/c3/84/6b/c3846b0a-f0f5-3006-25f0-6c9fa1ec329f/075679901452.jpg/600x600bb.jpg",
        "album_art": "https://is1-ssl.mzstatic.com/image/thumb/Music115/v4/c3/84/6b/c3846b0a-f0f5-3006-25f0-6c9fa1ec329f/075679901452.jpg/600x600bb.jpg",
        "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview115/v4/64/43/16/64431697-3a1e-8e47-e234-a0da61f67f6b/mzaf_2089408719056637375.plus.aac.p.m4a",
        "yt_music_url": "https://music.youtube.com/search?q=Bruno+Mars+That%27s+What+I+Like",
        "popularity": 920000
    }
]

def search_deezer_track(title: str, artist: str) -> Optional[Dict[str, Any]]:
    base_url = "https://api.deezer.com/search"
    query = f'track:"{title}" artist:"{artist}"'
    params = {"q": query, "limit": 3, "order": "RANKING"}

    try:
        resp = requests.get(base_url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        
        if not data:
            resp = requests.get(base_url, params={"q": f"{artist} {title}", "limit": 3, "order": "RANKING"}, timeout=5)
            data = resp.json().get("data", [])

        if not data:
            return None

        best_match = max(data, key=lambda x: x.get("rank", 0))
        album = best_match.get("album") or {}
        artwork = album.get("cover_big") or album.get("cover_medium") or ""
        q_enc = urllib.parse.quote(f"{best_match.get('artist', {}).get('name', artist)} {best_match.get('title', title)}")

        return {
            "title": best_match.get("title", title),
            "artist": best_match.get("artist", {}).get("name", artist),
            "artwork": artwork,
            "album_art": artwork,
            "preview_url": best_match.get("preview", ""),
            "yt_music_url": f"https://music.youtube.com/search?q={q_enc}",
            "popularity": best_match.get("rank", 0)
        }
    except Exception as e:
        print(f"[Deezer Match Error] {artist} - {title}: {e}")
        return None

def search_itunes_track(title: str, artist: str) -> Optional[Dict[str, Any]]:
    base_url = "https://itunes.apple.com/search"
    term = f"{artist} {title}"
    params = {"term": term, "media": "music", "entity": "song", "limit": 3, "country": "KR"}
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        resp = requests.get(base_url, params=params, headers=headers, timeout=5)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return None

        track = results[0]
        raw_art = track.get("artworkUrl100", "")
        art = raw_art.replace("100x100bb.jpg", "600x600bb.jpg") if raw_art else ""
        q_enc = urllib.parse.quote(f"{track.get('artistName', artist)} {track.get('trackName', title)}")

        return {
            "title": track.get("trackName", title),
            "artist": track.get("artistName", artist),
            "artwork": art,
            "album_art": art,
            "preview_url": track.get("previewUrl", ""),
            "yt_music_url": f"https://music.youtube.com/search?q={q_enc}",
            "popularity": 500000
        }
    except Exception as e:
        print(f"[iTunes Match Error] {artist} - {title}: {e}")
        return None

def curate_mainstream_songs(candidates: List[Dict[str, str]], limit: int = 4) -> List[Dict[str, Any]]:
    resolved_tracks: List[Dict[str, Any]] = []
    seen_artists = set()

    for item in candidates:
        artist_name = item.get("artist", "").strip()
        song_title = item.get("title", "").strip()
        if not artist_name or not song_title:
            continue

        artist_key = artist_name.lower().replace(" ", "")
        if artist_key in seen_artists:
            continue

        track_data = search_deezer_track(song_title, artist_name)
        if not track_data:
            track_data = search_itunes_track(song_title, artist_name)

        if track_data and track_data.get("artwork"):
            resolved_tracks.append(track_data)
            seen_artists.add(artist_key)

    resolved_tracks.sort(key=lambda x: x.get("popularity", 0), reverse=True)

    if len(resolved_tracks) < limit:
        for fallback in VERIFIED_MAINSTREAM_FALLBACK:
            fb_artist_key = fallback["artist"].lower().replace(" ", "")
            if fb_artist_key not in seen_artists:
                resolved_tracks.append(fallback)
                seen_artists.add(fb_artist_key)
            if len(resolved_tracks) >= limit:
                break

    return resolved_tracks[:limit]
