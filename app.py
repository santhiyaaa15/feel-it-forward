from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import hashlib
import secrets
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Database setup
def init_db():
    conn = sqlite3.connect('feel_it_forward.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE,
        email TEXT UNIQUE,
        password TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS moods (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        emotion TEXT,
        context TEXT,
        date TEXT,
        supports INTEGER DEFAULT 0,
        ripples INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS follows (
        follower_id TEXT,
        followed_id TEXT,
        status TEXT DEFAULT 'pending',
        PRIMARY KEY(follower_id, followed_id),
        FOREIGN KEY(follower_id) REFERENCES users(id),
        FOREIGN KEY(followed_id) REFERENCES users(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS comments (
        id TEXT PRIMARY KEY,
        mood_id TEXT,
        user_id TEXT,
        content TEXT,
        timestamp TEXT,
        FOREIGN KEY(mood_id) REFERENCES moods(id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    conn.commit()
    conn.close()
    print("Databases and tables created or verified successfully!")

init_db()

# Utility functions
def generate_id():
    return secrets.token_hex(16)

# Routes
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    user_id = generate_id()
    hashed_password = hashlib.sha256(password.encode()).hexdigest()

    conn = sqlite3.connect('feel_it_forward.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (id, username, email, password) VALUES (?, ?, ?, ?)",
                  (user_id, username, email, hashed_password))
        conn.commit()
        return jsonify({"message": "User registered successfully", "user_id": user_id}), 201
    except sqlite3.IntegrityError:
        return jsonify({"message": "Username or email already exists"}), 400
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    hashed_password = hashlib.sha256(password.encode()).hexdigest()

    conn = sqlite3.connect('feel_it_forward.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username = ? AND password = ?", (username, hashed_password))
    user = c.fetchone()
    conn.close()

    if user:
        return jsonify({"message": "Login successful", "user_id": user[0]}), 200
    else:
        return jsonify({"message": "Invalid username or password"}), 401

@app.route('/api/forgot_password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email')

    conn = sqlite3.connect('feel_it_forward.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE email = ?", (email,))
    user = c.fetchone()
    conn.close()

    if user:
        reset_token = secrets.token_urlsafe(32)
        print(f"Password reset token for {email}: {reset_token}")
        return jsonify({"message": "Password reset link sent (simulated). Check terminal for token."}), 200
    else:
        return jsonify({"message": "Email not found"}), 404

@app.route('/api/mood', methods=['POST'])
def submit_mood():
    data = request.get_json()
    mood_id = generate_id()
    user_id = data.get('user_id')
    emotion = data.get('emotion')
    context = data.get('context')
    date = data.get('date')

    if not all([user_id, emotion, date]):
        return jsonify({"message": "Missing required fields"}), 400

    conn = sqlite3.connect('feel_it_forward.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO moods (id, user_id, emotion, context, date) VALUES (?, ?, ?, ?, ?)",
                  (mood_id, user_id, emotion, context, date))
        conn.commit()
        return jsonify({"message": "Mood submitted successfully", "id": mood_id}), 201
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

@app.route('/api/mood/history/<user_id>', methods=['GET'])
def get_mood_history(user_id):
    conn = sqlite3.connect('feel_it_forward.db')
    c = conn.cursor()
    c.execute("SELECT * FROM moods WHERE user_id = ? ORDER BY date DESC", (user_id,))
    moods = c.fetchall()
    conn.close()

    mood_list = [{"id": m[0], "user_id": m[1], "emotion": m[2], "context": m[3], "date": m[4],
                  "supports": m[5], "ripples": m[6]} for m in moods]
    return jsonify(mood_list), 200

@app.route('/api/moods', methods=['GET'])
def get_all_moods():
    conn = sqlite3.connect('feel_it_forward.db')
    c = conn.cursor()
    c.execute("SELECT * FROM moods ORDER BY date DESC")
    moods = c.fetchall()

    mood_list = []
    for m in moods:
        c.execute("SELECT * FROM comments WHERE mood_id = ? ORDER BY timestamp", (m[0],))
        comments = c.fetchall()
        comment_list = [{"id": cmt[0], "mood_id": cmt[1], "user_id": cmt[2], "content": cmt[3],
                         "timestamp": cmt[4]} for cmt in comments]
        mood_list.append({
            "id": m[0], "user_id": m[1], "emotion": m[2], "context": m[3], "date": m[4],
            "supports": m[5], "ripples": m[6], "comments": comment_list
        })
    conn.close()
    return jsonify(mood_list), 200

@app.route('/api/mood/<mood_id>', methods=['PUT'])
def update_mood(mood_id):
    data = request.get_json()
    supports = data.get('supports', 0)
    ripples = data.get('ripples', 0)

    conn = sqlite3.connect('feel_it_forward.db')
    c = conn.cursor()
    c.execute("UPDATE moods SET supports = supports + ?, ripples = ripples + ? WHERE id = ?",
              (supports, ripples, mood_id))
    conn.commit()
    conn.close()
    return jsonify({"message": "Mood updated successfully"}), 200

@app.route('/api/follow', methods=['POST'])
def follow():
    data = request.get_json()
    follower_id = data.get('follower_id')
    followed_id = data.get('followed_id')

    conn = sqlite3.connect('feel_it_forward.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO follows (follower_id, followed_id, status) VALUES (?, ?, 'pending')",
                  (follower_id, followed_id))
        conn.commit()
        return jsonify({"message": "Follow request sent"}), 200
    except sqlite3.IntegrityError:
        return jsonify({"message": "Already following or request pending"}), 400
    finally:
        conn.close()

@app.route('/api/unfollow', methods=['POST'])
def unfollow():
    data = request.get_json()
    follower_id = data.get('follower_id')
    followed_id = data.get('followed_id')

    conn = sqlite3.connect('feel_it_forward.db')
    c = conn.cursor()
    c.execute("DELETE FROM follows WHERE follower_id = ? AND followed_id = ?",
              (follower_id, followed_id))
    conn.commit()
    conn.close()
    return jsonify({"message": "Unfollowed successfully"}), 200

@app.route('/api/is_following/<follower_id>/<followed_id>', methods=['GET'])
def is_following(follower_id, followed_id):
    conn = sqlite3.connect('feel_it_forward.db')
    c = conn.cursor()
    c.execute("SELECT status FROM follows WHERE follower_id = ? AND followed_id = ? AND status = 'accepted'",
              (follower_id, followed_id))
    result = c.fetchone()
    conn.close()
    return jsonify({"is_following": bool(result)}), 200

@app.route('/api/follow_status/<follower_id>/<followed_id>', methods=['GET'])
def follow_status(follower_id, followed_id):
    conn = sqlite3.connect('feel_it_forward.db')
    c = conn.cursor()
    c.execute("SELECT status FROM follows WHERE follower_id = ? AND followed_id = ?",
              (follower_id, followed_id))
    result = c.fetchone()
    conn.close()
    return jsonify({"status": result[0] if result else "not_following"}), 200

@app.route('/api/accept_follow/<follower_id>/<followed_id>', methods=['POST'])
def accept_follow(follower_id, followed_id):
    conn = sqlite3.connect('feel_it_forward.db')
    c = conn.cursor()
    c.execute("UPDATE follows SET status = 'accepted' WHERE follower_id = ? AND followed_id = ? AND status = 'pending'",
              (follower_id, followed_id))
    if c.rowcount == 0:
        conn.close()
        return jsonify({"message": "No pending follow request found"}), 404
    conn.commit()
    conn.close()
    return jsonify({"message": "Follow request accepted"}), 200

@app.route('/api/pending_follow_requests/<user_id>', methods=['GET'])
def pending_follow_requests(user_id):
    conn = sqlite3.connect('feel_it_forward.db')
    c = conn.cursor()
    c.execute("SELECT follower_id FROM follows WHERE followed_id = ? AND status = 'pending'", (user_id,))
    requests = c.fetchall()
    conn.close()
    return jsonify([{"follower_id": req[0]} for req in requests]), 200

@app.route('/api/comment', methods=['POST'])
def add_comment():
    data = request.get_json()
    comment_id = generate_id()
    mood_id = data.get('mood_id')
    user_id = data.get('user_id')
    content = data.get('content')
    timestamp = datetime.utcnow().isoformat()

    if not all([mood_id, user_id, content]):
        return jsonify({"message": "Missing required fields"}), 400

    conn = sqlite3.connect('feel_it_forward.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO comments (id, mood_id, user_id, content, timestamp) VALUES (?, ?, ?, ?, ?)",
                  (comment_id, mood_id, user_id, content, timestamp))
        conn.commit()
        return jsonify({"message": "Comment added successfully", "id": comment_id}), 201
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

# New endpoints to fix the 404 error
@app.route('/api/following/<user_id>', methods=['GET'])
def get_following(user_id):
    conn = sqlite3.connect('feel_it_forward.db')
    c = conn.cursor()
    try:
        c.execute("""
            SELECT u.username
            FROM users u
            JOIN follows f ON u.id = f.followed_id
            WHERE f.follower_id = ? AND f.status = 'accepted'
        """, (user_id,))
        following = [{"username": row[0]} for row in c.fetchall()]
        return jsonify(following), 200
    except sqlite3.Error as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

@app.route('/api/followers/<user_id>', methods=['GET'])
def get_followers(user_id):
    conn = sqlite3.connect('feel_it_forward.db')
    c = conn.cursor()
    try:
        c.execute("""
            SELECT u.username
            FROM users u
            JOIN follows f ON u.id = f.follower_id
            WHERE f.followed_id = ? AND f.status = 'accepted'
        """, (user_id,))
        followers = [{"username": row[0]} for row in c.fetchall()]
        return jsonify(followers), 200
    except sqlite3.Error as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)