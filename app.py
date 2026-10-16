# -*- coding: utf-8 -*-
import base64
import json
import mimetypes
import os
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

import requests
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

BASE = Path(__file__).resolve().parent
DB = BASE / "family_medical.db"
UPLOADS = BASE / "uploads"
UPLOADS.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("FAMILY_MEDICAL_SECRET", "local-family-medical-change-me")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

ALLOWED = {
    "png", "jpg", "jpeg", "webp", "gif", "pdf",
    "txt", "csv", "doc", "docx", "xls", "xlsx"
}

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY CHECK(id=1),
        base_url TEXT NOT NULL DEFAULT 'https://api.gapgpt.app/v1',
        api_key TEXT NOT NULL DEFAULT '',
        model TEXT NOT NULL DEFAULT 'gpt-4o',
        system_prompt TEXT NOT NULL DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS family_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        nickname TEXT,
        gender TEXT,
        birth_date TEXT,
        national_id TEXT,
        blood_type TEXT,
        marital_status TEXT,
        occupation TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        emergency_name TEXT,
        emergency_relation TEXT,
        emergency_phone TEXT,
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS conditions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        status TEXT,
        diagnosis_date TEXT,
        severity TEXT,
        details TEXT,
        medications TEXT,
        FOREIGN KEY(member_id) REFERENCES family_members(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS surgeries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        date TEXT,
        hospital TEXT,
        surgeon TEXT,
        indication TEXT,
        outcome TEXT,
        complications TEXT,
        FOREIGN KEY(member_id) REFERENCES family_members(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS hospitalizations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        admission_date TEXT,
        discharge_date TEXT,
        hospital TEXT,
        reason TEXT,
        diagnosis TEXT,
        notes TEXT,
        FOREIGN KEY(member_id) REFERENCES family_members(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS allergies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        allergen TEXT NOT NULL,
        reaction TEXT,
        severity TEXT,
        FOREIGN KEY(member_id) REFERENCES family_members(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS medications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        dose TEXT,
        frequency TEXT,
        route TEXT,
        start_date TEXT,
        end_date TEXT,
        reason TEXT,
        prescriber TEXT,
        notes TEXT,
        FOREIGN KEY(member_id) REFERENCES family_members(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS family_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        relative TEXT NOT NULL,
        condition TEXT NOT NULL,
        age_at_diagnosis TEXT,
        status TEXT,
        notes TEXT,
        FOREIGN KEY(member_id) REFERENCES family_members(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS habits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        value TEXT,
        quantity TEXT,
        frequency TEXT,
        since_date TEXT,
        notes TEXT,
        FOREIGN KEY(member_id) REFERENCES family_members(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS vaccinations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        vaccine TEXT NOT NULL,
        date TEXT,
        dose TEXT,
        provider TEXT,
        notes TEXT,
        FOREIGN KEY(member_id) REFERENCES family_members(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        specialty TEXT,
        name TEXT NOT NULL,
        clinic TEXT,
        phone TEXT,
        last_visit TEXT,
        notes TEXT,
        FOREIGN KEY(member_id) REFERENCES family_members(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS medical_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        event_date TEXT NOT NULL,
        event_time TEXT,
        event_type TEXT NOT NULL,
        title TEXT NOT NULL,
        details TEXT,
        source TEXT,
        FOREIGN KEY(member_id) REFERENCES family_members(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        original_name TEXT NOT NULL,
        stored_name TEXT NOT NULL,
        mime_type TEXT,
        category TEXT,
        document_date TEXT,
        uploaded_at TEXT NOT NULL,
        description TEXT,
        ai_analysis TEXT,
        FOREIGN KEY(member_id) REFERENCES family_members(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS ai_analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        document_id INTEGER,
        created_at TEXT NOT NULL,
        model TEXT NOT NULL,
        request_summary TEXT,
        response_json TEXT NOT NULL,
        FOREIGN KEY(member_id) REFERENCES family_members(id) ON DELETE CASCADE,
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS action_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        analysis_id INTEGER,
        due_date TEXT,
        due_time TEXT,
        priority TEXT,
        category TEXT,
        action TEXT NOT NULL,
        reason TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        FOREIGN KEY(member_id) REFERENCES family_members(id) ON DELETE CASCADE,
        FOREIGN KEY(analysis_id) REFERENCES ai_analyses(id) ON DELETE SET NULL
    );

    INSERT OR IGNORE INTO settings(id, base_url, model) VALUES(1, 'https://api.gapgpt.app/v1', 'gpt-4o');
    """)
    con.commit()
    con.close()

def get_settings():
    con = db()
    row = con.execute("SELECT * FROM settings WHERE id=1").fetchone()
    con.close()
    return dict(row)

def get_member(member_id):
    con = db()
    row = con.execute("SELECT * FROM family_members WHERE id=?", (member_id,)).fetchone()
    con.close()
    return row

def get_member_data(member_id):
    con = db()
    tables = ["conditions","surgeries","hospitalizations","allergies","medications",
              "family_history","habits","vaccinations","doctors","medical_events","documents","action_items"]
    data = {}
    for t in tables:
        data[t] = [dict(r) for r in con.execute(f"SELECT * FROM {t} WHERE member_id=? ORDER BY id DESC", (member_id,))]
    data["member"] = dict(con.execute("SELECT * FROM family_members WHERE id=?", (member_id,)).fetchone())
    data["analyses"] = [dict(r) for r in con.execute(
        "SELECT * FROM ai_analyses WHERE member_id=? ORDER BY id DESC", (member_id,)
    )]
    con.close()
    return data

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED

def file_to_data_url(path, mime):
    raw = path.read_bytes()
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"

def make_prompt(member_data, document=None):
    schema = {
        "summary": "خلاصه ساختاریافته و محتاطانه از اطلاعات موجود؛ بدون تشخیص قطعی",
        "red_flags": [{"item": "", "reason": "", "urgency": "emergency|urgent|routine"}],
        "observations": [{"finding": "", "reason": "", "source": ""}],
        "suggested_questions_for_doctor": [""],
        "suggested_tests_or_followups": [
            {"test_or_action": "", "reason": "", "timing": "مثلاً 1-2 هفته یا طبق نظر پزشک"}
        ],
        "timeline": [
            {"date": "YYYY-MM-DD", "time": "", "priority": "high|medium|low", "action": "", "reason": ""}
        ],
        "medication_review_points": [{"item": "", "reason": ""}],
        "lifestyle_points": [{"item": "", "reason": ""}],
        "uncertainties": [""],
        "disclaimer": "این خروجی جایگزین تشخیص یا توصیه پزشک نیست."
    }
    extra_system = settings_prompt = get_settings().get("system_prompt","").strip()
    text = (
        "شما دستیار سازمان‌دهی اطلاعات پزشکی هستید. اطلاعات زیر را بررسی کن. "
        "تشخیص قطعی، تجویز دارو یا تغییر دوز انجام نده. موارد اورژانسی را فقط به‌صورت هشدار "
        "برای مراجعه فوری مطرح کن. هر پیشنهاد را با دلیل و سطح فوریت بیان کن. "
        "اگر داده کافی نیست صریحاً بگو. خروجی فقط JSON معتبر مطابق این schema باشد.\n\n"
        f"SCHEMA:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        f"PATIENT DATA:\n{json.dumps(member_data, ensure_ascii=False, indent=2)}"
    )
    if extra_system:
        text += "\n\nCUSTOM INSTRUCTIONS:\n" + extra_system
    if document:
        text += "\n\nDOCUMENT CONTEXT:\n" + json.dumps(document, ensure_ascii=False, indent=2)
    return text

def call_ai(member_id, document_id=None):
    settings = get_settings()
    if not settings["api_key"].strip():
        raise RuntimeError("API Key در تنظیمات وارد نشده است.")

    data = get_member_data(member_id)
    document = None
    content = []
    if document_id:
        con = db()
        row = con.execute("SELECT * FROM documents WHERE id=? AND member_id=?", (document_id, member_id)).fetchone()
        con.close()
        if not row:
            raise RuntimeError("سند پیدا نشد.")
        document = dict(row)
        prompt = make_prompt(data, document)
        content.append({"type": "text", "text": prompt})
        p = UPLOADS / row["stored_name"]
        if p.exists() and row["mime_type"] and row["mime_type"].startswith("image/"):
            content.append({"type": "image_url", "image_url": {"url": file_to_data_url(p, row["mime_type"])}})
    else:
        prompt = make_prompt(data)
        content = prompt

    base = settings["base_url"].rstrip("/")
    url = base + "/chat/completions"
    payload = {
        "model": settings["model"] or "gpt-4o",
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.1
    }
    headers = {"Authorization": "Bearer " + settings["api_key"].strip(), "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json=payload, timeout=180)
    if r.status_code >= 400:
        raise RuntimeError(f"API error {r.status_code}: {r.text[:1200]}")
    obj = r.json()
    raw = obj.get("choices", [{}])[0].get("message", {}).get("content", "")
    if isinstance(raw, list):
        raw = "".join(x.get("text","") for x in raw if isinstance(x, dict))
    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I | re.S)
    try:
        parsed = json.loads(clean)
    except Exception:
        parsed = {"summary": raw, "parse_warning": "پاسخ مدل JSON معتبر نبود.", "raw": raw}

    con = db()
    cur = con.execute(
        "INSERT INTO ai_analyses(member_id, document_id, created_at, model, request_summary, response_json) VALUES(?,?,?,?,?,?)",
        (member_id, document_id, now(), settings["model"], "تحلیل پرونده پزشکی" + (" + سند" if document_id else ""), json.dumps(parsed, ensure_ascii=False))
    )
    analysis_id = cur.lastrowid
    timeline = parsed.get("timeline", []) if isinstance(parsed, dict) else []
    for item in timeline:
        con.execute(
            "INSERT INTO action_items(member_id, analysis_id, due_date, due_time, priority, category, action, reason) VALUES(?,?,?,?,?,?,?,?)",
            (member_id, analysis_id, item.get("date"), item.get("time"), item.get("priority"),
             "AI Timeline", item.get("action",""), item.get("reason",""))
        )
    if document_id:
        con.execute("UPDATE documents SET ai_analysis=? WHERE id=?", (json.dumps(parsed, ensure_ascii=False), document_id))
    con.commit()
    con.close()
    return parsed

@app.route("/")
def index():
    con = db()
    members = con.execute("SELECT * FROM family_members ORDER BY first_name, last_name").fetchall()
    con.close()
    return render_template("index.html", members=members)

@app.route("/settings", methods=["GET","POST"])
def settings():
    if request.method == "POST":
        base_url = request.form.get("base_url","").strip().rstrip("/")
        api_key = request.form.get("api_key","").strip()
        model = request.form.get("model","gpt-4o").strip()
        system_prompt = request.form.get("system_prompt","").strip()
        con = db()
        con.execute("UPDATE settings SET base_url=?, api_key=?, model=?, system_prompt=? WHERE id=1",
                    (base_url, api_key, model, system_prompt))
        con.commit(); con.close()
        flash("تنظیمات ذخیره شد.", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html", settings=get_settings())

@app.route("/member/new", methods=["GET","POST"])
def new_member():
    if request.method == "POST":
        fields = ["first_name","last_name","nickname","gender","birth_date","national_id","blood_type",
                  "marital_status","occupation","phone","email","address","emergency_name",
                  "emergency_relation","emergency_phone","notes"]
        vals = [request.form.get(f,"").strip() for f in fields]
        if not vals[0] or not vals[1]:
            flash("نام و نام خانوادگی الزامی است.", "danger")
            return render_template("member_form.html", member=None)
        con = db()
        cur = con.execute(
            "INSERT INTO family_members("+",".join(fields)+",created_at,updated_at) VALUES("+",".join(["?"]*len(fields))+",?,?)",
            vals + [now(), now()]
        )
        mid = cur.lastrowid
        con.commit(); con.close()
        return redirect(url_for("member", member_id=mid))
    return render_template("member_form.html", member=None)

@app.route("/member/<int:member_id>")
def member(member_id):
    m = get_member(member_id)
    if not m: abort(404)
    return render_template("member.html", member=m, data=get_member_data(member_id))

@app.route("/member/<int:member_id>/edit", methods=["GET","POST"])
def edit_member(member_id):
    m = get_member(member_id)
    if not m: abort(404)
    if request.method == "POST":
        fields = ["first_name","last_name","nickname","gender","birth_date","national_id","blood_type",
                  "marital_status","occupation","phone","email","address","emergency_name",
                  "emergency_relation","emergency_phone","notes"]
        vals = [request.form.get(f,"").strip() for f in fields]
        con = db()
        con.execute("UPDATE family_members SET "+",".join(f"{f}=?" for f in fields)+",updated_at=? WHERE id=?",
                    vals+[now(),member_id])
        con.commit(); con.close()
        flash("پروفایل به‌روزرسانی شد.", "success")
        return redirect(url_for("member", member_id=member_id))
    return render_template("member_form.html", member=m)

@app.post("/member/<int:member_id>/delete")
def delete_member(member_id):
    con=db(); con.execute("DELETE FROM family_members WHERE id=?", (member_id,)); con.commit(); con.close()
    return redirect(url_for("index"))

FIELD_MAP = {
    "condition": ("conditions", ["name","status","diagnosis_date","severity","details","medications"]),
    "surgery": ("surgeries", ["title","date","hospital","surgeon","indication","outcome","complications"]),
    "hospitalization": ("hospitalizations", ["admission_date","discharge_date","hospital","reason","diagnosis","notes"]),
    "allergy": ("allergies", ["allergen","reaction","severity"]),
    "medication": ("medications", ["name","dose","frequency","route","start_date","end_date","reason","prescriber","notes"]),
    "family_history": ("family_history", ["relative","condition","age_at_diagnosis","status","notes"]),
    "habit": ("habits", ["category","value","quantity","frequency","since_date","notes"]),
    "vaccination": ("vaccinations", ["vaccine","date","dose","provider","notes"]),
    "doctor": ("doctors", ["specialty","name","clinic","phone","last_visit","notes"]),
    "event": ("medical_events", ["event_date","event_time","event_type","title","details","source"])
}

@app.post("/member/<int:member_id>/add/<kind>")
def add_record(member_id, kind):
    if kind not in FIELD_MAP: abort(404)
    table, fields = FIELD_MAP[kind]
    vals=[request.form.get(f,"").strip() for f in fields]
    if not vals[0]:
        flash("فیلد اصلی این بخش الزامی است.", "danger")
        return redirect(url_for("member", member_id=member_id))
    con=db()
    con.execute(f"INSERT INTO {table}(member_id,{','.join(fields)}) VALUES(?,{','.join(['?']*len(fields))})",
                [member_id]+vals)
    con.commit(); con.close()
    return redirect(url_for("member", member_id=member_id))

@app.post("/member/<int:member_id>/delete/<table>/<int:record_id>")
def delete_record(member_id, table, record_id):
    allowed=set(v[0] for v in FIELD_MAP.values()) | {"documents","action_items"}
    if table not in allowed: abort(404)
    con=db(); con.execute(f"DELETE FROM {table} WHERE id=? AND member_id=?", (record_id,member_id)); con.commit(); con.close()
    return redirect(url_for("member", member_id=member_id))

@app.post("/member/<int:member_id>/upload")
def upload(member_id):
    f=request.files.get("file")
    if not f or not f.filename:
        flash("فایلی انتخاب نشده است.", "danger"); return redirect(url_for("member", member_id=member_id))
    if not allowed_file(f.filename):
        flash("نوع فایل پشتیبانی نمی‌شود.", "danger"); return redirect(url_for("member", member_id=member_id))
    original=secure_filename(f.filename)
    ext=original.rsplit(".",1)[1].lower()
    stored=f"{uuid.uuid4().hex}.{ext}"
    f.save(UPLOADS/stored)
    mime=f.mimetype or mimetypes.guess_type(original)[0] or "application/octet-stream"
    con=db()
    cur=con.execute(
        "INSERT INTO documents(member_id,original_name,stored_name,mime_type,category,document_date,uploaded_at,description) VALUES(?,?,?,?,?,?,?,?)",
        (member_id,original,stored,mime,request.form.get("category","سایر"),request.form.get("document_date",""),now(),request.form.get("description",""))
    )
    con.commit(); con.close()
    flash("سند با موفقیت ثبت شد.", "success")
    return redirect(url_for("member", member_id=member_id))

@app.route("/uploads/<path:name>")
def uploaded(name):
    return send_from_directory(UPLOADS, name, as_attachment=False)

@app.post("/member/<int:member_id>/analyze")
def analyze_member(member_id):
    try:
        result=call_ai(member_id)
        flash("تحلیل پرونده انجام شد و Timeline به‌روزرسانی شد.", "success")
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for("member", member_id=member_id))

@app.post("/member/<int:member_id>/document/<int:document_id>/analyze")
def analyze_document(member_id, document_id):
    try:
        call_ai(member_id, document_id)
        flash("تحلیل سند انجام شد.", "success")
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for("member", member_id=member_id))

@app.post("/action/<int:action_id>/toggle")
def toggle_action(action_id):
    con=db()
    row=con.execute("SELECT status FROM action_items WHERE id=?", (action_id,)).fetchone()
    if row:
        new="done" if row["status"]!="done" else "pending"
        con.execute("UPDATE action_items SET status=? WHERE id=?", (new,action_id))
        con.commit()
    con.close()
    return redirect(request.referrer or url_for("index"))

@app.route("/member/<int:member_id>/report")
def report(member_id):
    m=get_member(member_id)
    if not m: abort(404)
    return render_template("report.html", member=m, data=get_member_data(member_id), print_mode=True)

@app.errorhandler(413)
def too_large(_):
    flash("حجم فایل بیش از 25MB است.", "danger")
    return redirect(request.referrer or url_for("index"))

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
