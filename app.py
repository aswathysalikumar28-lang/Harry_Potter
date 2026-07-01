from flask import Flask, render_template, request, jsonify
from groq import Groq
import json
import re
import sqlite3
import os

app = Flask(__name__)
client = Groq(api_key="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")

DB = "hogwarts.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS houses (
        name TEXT PRIMARY KEY,
        points INTEGER DEFAULT 0,
        color TEXT,
        emoji TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT,
        house TEXT,
        done INTEGER DEFAULT 0,
        points INTEGER DEFAULT 0,
        reason TEXT DEFAULT ""
    )''')
    houses = [
        ("Gryffindor", 0, "#740001", "🦁"),
        ("Slytherin",  0, "#1a472a", "🐍"),
        ("Ravenclaw",  0, "#0e1a40", "🦅"),
        ("Hufflepuff", 0, "#ecb939", "🦡"),
    ]
    for h in houses:
        c.execute("INSERT OR IGNORE INTO houses (name, points, color, emoji) VALUES (?,?,?,?)", h)
    conn.commit()
    conn.close()

init_db()

def get_houses():
    conn = get_db()
    rows = conn.execute("SELECT * FROM houses").fetchall()
    conn.close()
    return {r["name"]: {"points": r["points"], "color": r["color"], "emoji": r["emoji"]} for r in rows}

def get_tasks():
    conn = get_db()
    rows = conn.execute("SELECT * FROM tasks").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.route("/")
def welcome():
    return render_template("welcome.html")

@app.route("/home")
def index():
    return render_template("index.html", houses=get_houses(), tasks=get_tasks())

@app.route("/sorting")
def sorting():
    return render_template("sorting.html")

@app.route("/sort_me", methods=["POST"])
def sort_me():
    name = request.json.get("name")
    prompt = f"""You are the Hogwarts Sorting Hat. Sort the student named '{name}' into one of the four houses: Gryffindor, Slytherin, Ravenclaw, or Hufflepuff.
Respond ONLY in this JSON format:
{{"house": "<house name>", "reason": "<two witty sentences explaining why in Sorting Hat's voice>"}}"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=1.0
    )
    raw = response.choices[0].message.content.strip()
    match = re.search(r'\{.*?\}', raw, re.DOTALL)
    result = json.loads(match.group())
    return jsonify(result)

@app.route("/spells")
def spells():
    return render_template("spells.html")

@app.route("/map")
def marauders_map():
    return render_template("map.html")

@app.route("/potions")
def potions():
    return render_template("potions.html")

@app.route("/patronus")
def patronus_page():
    return render_template("patronus.html")

@app.route("/generate_patronus", methods=["POST"])
def generate_patronus():
    memory = request.json.get("memory")
    prompt = f"""You are the Patronus Charm itself. Based on this happy memory: "{memory}", determine what animal Patronus this wizard/witch would produce.
Respond ONLY in this JSON format:
{{"animal": "<animal name>", "description": "<two evocative sentences describing the Patronus and why it matches their memory>"}}"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=1.0
    )
    raw = response.choices[0].message.content.strip()
    match = re.search(r'\{.*?\}', raw, re.DOTALL)
    result = json.loads(match.group())
    return jsonify(result)

@app.route("/prophet")
def prophet_page():
    return render_template("prophet.html")

@app.route("/generate_news", methods=["POST"])
def generate_news():
    prompt = """You are a journalist for the Daily Prophet. Write ONE short fictional dramatic news story (3-4 sentences) about something happening today at Hogwarts or in the wizarding world.
Respond ONLY in this JSON format:
{"headline": "<catchy headline>", "article": "<3-4 sentence article>"}"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=1.1
    )
    raw = response.choices[0].message.content.strip()
    match = re.search(r'\{.*?\}', raw, re.DOTALL)
    result = json.loads(match.group())
    return jsonify(result)

@app.route("/quidditch")
def quidditch():
    return render_template("quidditch.html")

@app.route("/halloffame")
def halloffame():
    houses = get_houses()
    sorted_houses = sorted(houses.items(), key=lambda x: x[1]["points"], reverse=True)
    completed_tasks = [t for t in get_tasks() if t["done"]]
    return render_template("halloffame.html", houses=sorted_houses, tasks=completed_tasks)

@app.route("/add_task", methods=["POST"])
def add_task():
    body = request.json
    task_text = body.get("task")
    house = body.get("house")
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO tasks (text, house, done, points, reason) VALUES (?,?,0,0,'')", (task_text, house))
    task_id = c.lastrowid
    conn.commit()
    conn.close()
    task = {"id": task_id, "text": task_text, "house": house, "done": False, "points": 0, "reason": ""}
    return jsonify({"success": True, "task": task})

@app.route("/complete_task", methods=["POST"])
def complete_task():
    task_id = request.json.get("id")
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not task or task["done"]:
        conn.close()
        return jsonify({"error": "Task not found or already done"}), 400

    prompt = f"""You are Professor Dumbledore awarding house points at Hogwarts.
A student from {task["house"]} just completed this task: "{task["text"]}".
Award between 5 and 50 points. Respond ONLY in this JSON format:
{{"points": <number>, "reason": "<one witty HP-flavored sentence explaining why>"}}"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9
    )
    raw = response.choices[0].message.content.strip()
    match = re.search(r'\{.*?\}', raw, re.DOTALL)
    result = json.loads(match.group())

    conn.execute("UPDATE tasks SET done=1, points=?, reason=? WHERE id=?",
                 (result["points"], result["reason"], task_id))
    conn.execute("UPDATE houses SET points = points + ? WHERE name=?",
                 (result["points"], task["house"]))
    conn.commit()

    houses = {r["name"]: {"points": r["points"], "color": r["color"], "emoji": r["emoji"]}
              for r in conn.execute("SELECT * FROM houses").fetchall()}
    updated_task = dict(conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())
    conn.close()

    return jsonify({"success": True, "task": updated_task, "houses": houses})

@app.route("/delete_task", methods=["POST"])
def delete_task():
    task_id = request.json.get("id")
    conn = get_db()
    conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(debug=True)