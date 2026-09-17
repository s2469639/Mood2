from __future__ import annotations
import os
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session

from analyzer import analyze_mood
from auth import hash_password, verify_password
from database import (
    add_friend,
    create_user,
    get_calendar_history,
    get_diary_month,
    get_diary_note,
    get_friends,
    get_user_by_username,
    init_db,
    remove_friend,
    save_history,
    upsert_diary_note,
)
from music import curate_mainstream_songs

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
init_db()

def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401
        return view_func(*args, **kwargs)
    return wrapped

@app.route("/")
def index():
    logged_in = "user_id" in session
    username = session.get("username", "")
    return render_template("index.html", logged_in=logged_in, username=username)

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    invited_by = (data.get("invited_by") or "").strip()

    if not username or not password:
        return jsonify({"success": False, "message": "아이디와 비밀번호를 입력해주세요."}), 400
    if len(password) < 4:
        return jsonify({"success": False, "message": "비밀번호는 4자 이상이어야 합니다."}), 400

    user_id = create_user(username, hash_password(password))
    if user_id is None:
        return jsonify({"success": False, "message": "이미 사용 중인 아이디입니다."}), 409

    if invited_by and invited_by != username:
        inviter = get_user_by_username(invited_by)
        if inviter:
            add_friend(user_id, inviter["id"])

    session["user_id"] = user_id
    session["username"] = username
    return jsonify({"success": True, "username": username})

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    user = get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        return jsonify({"success": False, "message": "아이디 또는 비밀번호가 올바르지 않습니다."}), 401

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    return jsonify({"success": True, "username": user["username"]})

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/recommend", methods=["POST"])
@login_required
def recommend():
    try:
        data = request.get_json(silent=True) or {}
        user_text = data.get("text", "").strip()
        favorite_artist = (data.get("favorite_artist") or "").strip()
        favorite_genre = (data.get("favorite_genre") or "").strip()

        if not user_text:
            return jsonify({"success": False, "message": "문장을 입력해주세요."}), 400

        analysis_result = analyze_mood(user_text, favorite_artist, favorite_genre)
        candidates = analysis_result.get("recommended_candidates", [])

        songs = curate_mainstream_songs(candidates, limit=4)
        save_history(session["user_id"], user_text, songs)

        return jsonify({
            "success": True,
            "analysis": analysis_result,
            "songs": songs
        })
    except Exception as e:
        app.logger.error(f"추천 파이프라인 오류: {e}")
        return jsonify({"success": False, "message": "서버 처리 중 오류가 발생했습니다."}), 500

@app.route("/api/calendar", methods=["GET"])
@login_required
def calendar():
    try:
        year = int(request.args.get("year"))
        month = int(request.args.get("month"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "year, month 파라미터가 필요합니다."}), 400

    grouped = get_calendar_history(session["user_id"], year, month)
    return jsonify({"success": True, "calendar": grouped})

@app.route("/api/diary", methods=["GET"])
@login_required
def diary_get():
    date_str = request.args.get("date", "")
    if not date_str:
        return jsonify({"success": False, "message": "date 파라미터가 필요합니다."}), 400
    note = get_diary_note(session["user_id"], date_str)
    return jsonify({"success": True, "date": date_str, "note": note})

@app.route("/api/diary", methods=["POST"])
@login_required
def diary_save():
    data = request.get_json(silent=True) or {}
    date_str = (data.get("date") or "").strip()
    note = (data.get("note") or "").strip()
    if not date_str:
        return jsonify({"success": False, "message": "date가 필요합니다."}), 400
    upsert_diary_note(session["user_id"], date_str, note)
    return jsonify({"success": True})

@app.route("/api/diary/month", methods=["GET"])
@login_required
def diary_month():
    try:
        year = int(request.args.get("year"))
        month = int(request.args.get("month"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "year, month 파라미터가 필요합니다."}), 400

    notes = get_diary_month(session["user_id"], year, month)
    return jsonify({"success": True, "notes": notes})

@app.route("/api/friends", methods=["GET"])
@login_required
def friends_list():
    friends = get_friends(session["user_id"])
    return jsonify({"success": True, "friends": friends})

@app.route("/api/friends/add", methods=["POST"])
@login_required
def friends_add():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()

    if not username:
        return jsonify({"success": False, "message": "친구 아이디를 입력해주세요."}), 400
    if username == session.get("username"):
        return jsonify({"success": False, "message": "자기 자신은 추가할 수 없습니다."}), 400

    target = get_user_by_username(username)
    if not target:
        return jsonify({"success": False, "message": "존재하지 않는 아이디입니다."}), 404

    ok = add_friend(session["user_id"], target["id"])
    if not ok:
        return jsonify({"success": False, "message": "이미 친구로 등록되어 있습니다."}), 409

    return jsonify({"success": True})

@app.route("/api/friends/<int:friend_user_id>", methods=["DELETE"])
@login_required
def friends_remove(friend_user_id):
    remove_friend(session["user_id"], friend_user_id)
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
