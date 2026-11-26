#!/usr/bin/env python3
"""
XYZ HOSPITAL - Hospital Management Website
Run:  python app.py      then open  http://localhost:8000
Uses only Python's standard library (no pip install needed). Data is saved in hospital.db
"""
import sqlite3, html, datetime, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hospital.db")
HOSPITAL = "XYZ Hospital"
ROOM_RATES = {"General Ward": 1500, "Semi-Private": 3000, "Private Room": 5000, "ICU": 10000}
CURRENCY = "₹"


# ---------------------------------------------------------------- database
def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS patients(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, age INTEGER, gender TEXT, phone TEXT,
        address TEXT, blood_group TEXT, diagnosis TEXT, doctor TEXT, room_type TEXT, bed_no TEXT,
        admit_date TEXT, status TEXT DEFAULT 'Admitted', discharge_date TEXT, discharge_summary TEXT);
    CREATE TABLE IF NOT EXISTS routine(
        id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER, dt TEXT, bp TEXT, temp TEXT,
        pulse TEXT, spo2 TEXT, meal TEXT, notes TEXT, recorded_by TEXT);
    CREATE TABLE IF NOT EXISTS medicines(
        id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER, dt TEXT, name TEXT, dosage TEXT,
        amount TEXT, cost REAL, given_by TEXT);
    CREATE TABLE IF NOT EXISTS charges(
        id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER, description TEXT, amount REAL);
    """)
    if c.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 0:
        seed(c)
    c.commit()
    c.close()


def seed(c):
    today = datetime.date.today()
    d = lambda n: (today - datetime.timedelta(days=n)).isoformat()
    pats = [
        ("Rahul Sharma", 45, "Male", "9876543210", "12, MG Road, Hassan", "B+", "Typhoid Fever",
         "Dr. Anita Rao", "General Ward", "G-12", d(3), "Admitted", None, None),
        ("Priya Nair", 32, "Female", "9845012345", "45, Lake View, Mysuru", "O+", "Appendicitis (post-surgery care)",
         "Dr. Suresh Kumar", "Private Room", "P-04", d(5), "Admitted", None, None),
        ("Mohammed Irfan", 60, "Male", "9900112233", "7, Station Road, Bengaluru", "A-", "Pneumonia",
         "Dr. Meera Iyer", "Semi-Private", "S-08", d(7), "Discharged", d(1),
         "Recovered well. Continue oral antibiotics for 5 days. Review after one week. Avoid cold food and dust."),
    ]
    for p in pats:
        c.execute("""INSERT INTO patients(name,age,gender,phone,address,blood_group,diagnosis,doctor,
                     room_type,bed_no,admit_date,status,discharge_date,discharge_summary)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", p)
    routine = [
        (1, d(2) + " 08:00", "120/80", "101.2", "88", "97", "Breakfast - Idli", "Fever persists, IV fluids started", "Nurse Kavya"),
        (1, d(1) + " 08:00", "118/78", "99.8", "82", "98", "Breakfast - Porridge", "Fever reducing, patient comfortable", "Nurse Kavya"),
        (1, d(0) + " 08:00", "116/76", "98.6", "78", "98", "Breakfast - Idli", "Fever gone, appetite improving", "Nurse Deepa"),
        (2, d(4) + " 09:00", "110/70", "99.5", "84", "99", "Liquid diet", "Post-op day 1, pain managed", "Nurse Divya"),
        (2, d(1) + " 09:00", "112/72", "98.4", "76", "99", "Soft diet", "Wound dry and clean, walking with support", "Nurse Divya"),
        (3, d(6) + " 07:30", "135/85", "100.4", "96", "92", "Soup", "Oxygen support given, cough present", "Nurse Lakshmi"),
        (3, d(3) + " 07:30", "130/82", "99.0", "88", "95", "Breakfast - Upma", "Breathing improved, oxygen removed", "Nurse Lakshmi"),
    ]
    c.executemany("INSERT INTO routine(patient_id,dt,bp,temp,pulse,spo2,meal,notes,recorded_by) VALUES(?,?,?,?,?,?,?,?,?)", routine)
    meds = [
        (1, d(2) + " 09:00", "Paracetamol", "500 mg, twice daily", "1 tablet", 10, "Nurse Kavya"),
        (1, d(2) + " 10:00", "Ceftriaxone Injection", "1 g, once daily (IV)", "1 vial", 180, "Dr. Anita Rao"),
        (1, d(1) + " 09:00", "Pantoprazole", "40 mg, before breakfast", "1 tablet", 12, "Nurse Kavya"),
        (2, d(4) + " 11:00", "Tramadol", "50 mg, as needed", "1 capsule", 15, "Nurse Divya"),
        (2, d(3) + " 09:00", "Amoxicillin-Clavulanate", "625 mg, twice daily", "1 tablet", 38, "Nurse Divya"),
        (3, d(6) + " 08:00", "Azithromycin", "500 mg, once daily", "1 tablet", 45, "Dr. Meera Iyer"),
        (3, d(5) + " 08:00", "Salbutamol Nebulization", "2.5 mg, thrice daily", "1 respule", 25, "Nurse Lakshmi"),
    ]
    c.executemany("INSERT INTO medicines(patient_id,dt,name,dosage,amount,cost,given_by) VALUES(?,?,?,?,?,?,?)", meds)
    charges = [
        (1, "Doctor Consultation", 800), (1, "Blood Tests (Widal, CBC)", 1200),
        (2, "Surgery - Appendectomy", 35000), (2, "Operation Theatre Charges", 8000), (2, "Anaesthesia", 6000),
        (3, "Chest X-Ray", 700), (3, "Oxygen Support", 2400), (3, "Doctor Consultation", 1000),
    ]
    c.executemany("INSERT INTO charges(patient_id,description,amount) VALUES(?,?,?)", charges)


# ---------------------------------------------------------------- helpers
esc = lambda s: html.escape(str(s if s is not None else ""))
money = lambda v: f"{CURRENCY}{v:,.2f}"


def days_stayed(p):
    a = datetime.date.fromisoformat(p["admit_date"])
    b = datetime.date.fromisoformat(p["discharge_date"]) if p["discharge_date"] else datetime.date.today()
    return max(1, (b - a).days)


def bill_for(c, p):
    days = days_stayed(p)
    rate = ROOM_RATES.get(p["room_type"], 0)
    room = days * rate
    meds = c.execute("SELECT * FROM medicines WHERE patient_id=?", (p["id"],)).fetchall()
    chg = c.execute("SELECT * FROM charges WHERE patient_id=?", (p["id"],)).fetchall()
    med_total = sum(m["cost"] or 0 for m in meds)
    chg_total = sum(x["amount"] or 0 for x in chg)
    return dict(days=days, rate=rate, room=room, meds=meds, chg=chg, med_total=med_total,
                chg_total=chg_total, total=room + med_total + chg_total)


LOGO = """<svg class="logo" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-label="XYZ Hospital logo">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#14b8a6"/><stop offset="1" stop-color="#0369a1"/></linearGradient></defs>
<path d="M32 3 55 12v19c0 14-9.5 24.5-23 30C18.5 55.5 9 45 9 31V12z" fill="url(#g)" stroke="#fff" stroke-width="2"/>
<rect x="27" y="16" width="10" height="30" rx="2.5" fill="#fff"/><rect x="17" y="26" width="30" height="10" rx="2.5" fill="#fff"/></svg>"""

CSS = """
:root{--teal:#0d9488;--blue:#0369a1;--navy:#0c2d48;--bg:#f0f9fa;--card:#fff;--ink:#1e293b;--mute:#64748b;--line:#e2e8f0;--red:#dc2626;--green:#16a34a;--amber:#d97706}
*{box-sizing:border-box}body{margin:0;font-family:'Segoe UI',system-ui,Arial,sans-serif;background:var(--bg);color:var(--ink)}
header{background:linear-gradient(120deg,var(--navy),var(--blue) 60%,var(--teal));color:#fff;box-shadow:0 2px 12px #0003}
.top{max-width:1180px;margin:auto;padding:14px 20px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.logo{width:52px;height:52px;filter:drop-shadow(0 2px 4px #0005)}
.brand h1{margin:0;font-size:1.5rem;letter-spacing:.5px}.brand small{opacity:.85;letter-spacing:2px;font-size:.7rem}
nav{margin-left:auto;display:flex;gap:6px;flex-wrap:wrap}
nav a{color:#fff;text-decoration:none;padding:9px 16px;border-radius:8px;font-weight:600;font-size:.92rem}
nav a:hover,nav a.on{background:#ffffff2b}
main{max-width:1180px;margin:22px auto;padding:0 20px}
h2{color:var(--navy);margin:0 0 14px}h3{margin:0 0 12px;color:var(--blue)}
.card{background:var(--card);border-radius:14px;padding:20px;box-shadow:0 2px 10px #0c2d4814;margin-bottom:20px;border-top:4px solid var(--teal)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:20px}
.stat{background:var(--card);border-radius:14px;padding:18px;box-shadow:0 2px 10px #0c2d4814;display:flex;gap:14px;align-items:center}
.stat .ic{font-size:1.9rem;width:54px;height:54px;border-radius:12px;display:grid;place-items:center;background:#ccfbf1}
.stat b{font-size:1.7rem;display:block;color:var(--navy)}.stat span{color:var(--mute);font-size:.85rem}
table{width:100%;border-collapse:collapse;font-size:.92rem}
th{background:#e6f6f7;color:var(--navy);text-align:left;padding:10px;font-size:.8rem;text-transform:uppercase;letter-spacing:.6px}
td{padding:10px;border-bottom:1px solid var(--line);vertical-align:top}tr:hover td{background:#f8fdfd}
.wrap{overflow-x:auto}
.badge{padding:4px 12px;border-radius:99px;font-size:.78rem;font-weight:700}
.badge.Admitted{background:#dcfce7;color:var(--green)}.badge.Discharged{background:#e0e7ff;color:#4338ca}
.btn{display:inline-block;background:linear-gradient(120deg,var(--teal),var(--blue));color:#fff;border:0;padding:10px 20px;border-radius:9px;font-weight:700;cursor:pointer;text-decoration:none;font-size:.9rem}
.btn:hover{filter:brightness(1.1)}.btn.red{background:linear-gradient(120deg,#ef4444,#b91c1c)}.btn.sm{padding:6px 12px;font-size:.8rem}.btn.grey{background:#64748b}
form.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}
label{font-size:.8rem;font-weight:700;color:var(--mute);display:block;margin-bottom:4px}
input,select,textarea{width:100%;padding:10px;border:1.5px solid var(--line);border-radius:8px;font:inherit;background:#fff}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--teal);box-shadow:0 0 0 3px #14b8a62e}
.full{grid-column:1/-1}
.info{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.info div{background:#f1fafb;padding:10px 14px;border-radius:10px}.info small{color:var(--mute);display:block;font-size:.72rem;text-transform:uppercase;letter-spacing:.5px}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px}
.tabs a{padding:9px 18px;border-radius:99px;background:#fff;color:var(--blue);text-decoration:none;font-weight:700;box-shadow:0 1px 5px #0001;font-size:.9rem}
.tabs a.on{background:linear-gradient(120deg,var(--teal),var(--blue));color:#fff}
.total td{font-weight:800;font-size:1.05rem;background:#e6f6f7}
.search{display:flex;gap:10px;margin-bottom:14px}
footer{text-align:center;color:var(--mute);font-size:.82rem;padding:24px}
.note{background:#fff7ed;border-left:4px solid var(--amber);padding:12px 16px;border-radius:8px;margin-bottom:14px}
.invoice-head{display:flex;align-items:center;gap:14px;border-bottom:2px solid var(--teal);padding-bottom:12px;margin-bottom:14px}
.invoice-head .logo{width:60px;height:60px}
@media print{header,.tabs,.noprint,footer,.btn{display:none!important}body{background:#fff}.card{box-shadow:none;border:1px solid #ccc}}
"""


def page(title, body, active=""):
    def n(href, label, key):
        return f'<a href="{href}" class="{"on" if active == key else ""}">{label}</a>'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} | {HOSPITAL}</title>
<style>{CSS}</style></head><body>
<header><div class="top">{LOGO}
<div class="brand"><h1>{HOSPITAL.upper()}</h1><small>CARING FOR LIFE, EVERY DAY</small></div>
<nav>{n('/', '🏠 Dashboard', 'home')}{n('/admit', '➕ Admit Patient', 'admit')}</nav></div></header>
<main>{body}</main><footer>© {datetime.date.today().year} {HOSPITAL} · Hospital Management System</footer></body></html>"""


# ---------------------------------------------------------------- pages
def dashboard(q):
    c = db()
    search = q.get("q", [""])[0].strip()
    rows = c.execute("SELECT * FROM patients WHERE name LIKE ? OR diagnosis LIKE ? OR doctor LIKE ? ORDER BY id DESC",
                     (f"%{search}%",) * 3).fetchall()
    total = c.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    adm = c.execute("SELECT COUNT(*) FROM patients WHERE status='Admitted'").fetchone()[0]
    dis = total - adm
    meds = c.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]
    tr = "".join(f"""<tr><td>#{r['id']}</td><td><b>{esc(r['name'])}</b><br><small>{r['age']} yrs · {esc(r['gender'])}</small></td>
        <td>{esc(r['diagnosis'])}</td><td>{esc(r['doctor'])}</td><td>{esc(r['room_type'])}<br><small>Bed {esc(r['bed_no'])}</small></td>
        <td>{esc(r['admit_date'])}</td><td><span class="badge {r['status']}">{r['status']}</span></td>
        <td><a class="btn sm" href="/patient?id={r['id']}">Open</a></td></tr>""" for r in rows)
    c.close()
    body = f"""<h2>Dashboard</h2><div class="stats">
    <div class="stat"><div class="ic">🧑‍⚕️</div><div><b>{total}</b><span>Total Patients</span></div></div>
    <div class="stat"><div class="ic">🛏️</div><div><b>{adm}</b><span>Currently Admitted</span></div></div>
    <div class="stat"><div class="ic">✅</div><div><b>{dis}</b><span>Discharged</span></div></div>
    <div class="stat"><div class="ic">💊</div><div><b>{meds}</b><span>Medicines Given</span></div></div></div>
    <div class="card"><h3>Patient Records</h3>
    <form class="search" method="get"><input name="q" placeholder="Search by patient, diagnosis or doctor…" value="{esc(search)}">
    <button class="btn">Search</button></form>
    <div class="wrap"><table><tr><th>ID</th><th>Patient</th><th>Diagnosis</th><th>Doctor</th><th>Room</th><th>Admitted</th><th>Status</th><th></th></tr>
    {tr or '<tr><td colspan=8>No patients found.</td></tr>'}</table></div></div>"""
    return page("Dashboard", body, "home")


def admit_form():
    rooms = "".join(f"<option>{r}</option>" for r in ROOM_RATES)
    body = f"""<h2>Patient Admission</h2><div class="card"><form class="grid" method="post" action="/admit">
    <div><label>Patient Name *</label><input name="name" required></div>
    <div><label>Age *</label><input name="age" type="number" min="0" max="120" required></div>
    <div><label>Gender</label><select name="gender"><option>Male</option><option>Female</option><option>Other</option></select></div>
    <div><label>Phone</label><input name="phone"></div>
    <div><label>Blood Group</label><select name="blood_group">{''.join(f'<option>{b}</option>' for b in ['A+','A-','B+','B-','O+','O-','AB+','AB-'])}</select></div>
    <div><label>Admission Date</label><input name="admit_date" type="date" value="{datetime.date.today()}"></div>
    <div><label>Doctor In Charge *</label><input name="doctor" required></div>
    <div><label>Room Type</label><select name="room_type">{rooms}</select></div>
    <div><label>Bed No.</label><input name="bed_no"></div>
    <div class="full"><label>Address</label><input name="address"></div>
    <div class="full"><label>Diagnosis / Reason for Admission *</label><textarea name="diagnosis" rows="3" required></textarea></div>
    <div class="full"><button class="btn">Admit Patient</button></div></form></div>"""
    return page("Admit Patient", body, "admit")


def patient_page(pid, tab, msg=""):
    c = db()
    p = c.execute("SELECT * FROM patients WHERE id=?", (pid,)).fetchone()
    if not p:
        c.close()
        return page("Not found", '<div class="card">Patient not found.</div>')
    admitted = p["status"] == "Admitted"
    head = f"""<h2>{esc(p['name'])} <span class="badge {p['status']}">{p['status']}</span></h2>
    <div class="card"><div class="info">
    <div><small>Patient ID</small>#{p['id']}</div><div><small>Age / Gender</small>{p['age']} / {esc(p['gender'])}</div>
    <div><small>Blood Group</small>{esc(p['blood_group'])}</div><div><small>Phone</small>{esc(p['phone'])}</div>
    <div><small>Doctor</small>{esc(p['doctor'])}</div><div><small>Room / Bed</small>{esc(p['room_type'])} / {esc(p['bed_no'])}</div>
    <div><small>Admitted On</small>{esc(p['admit_date'])}</div><div><small>Diagnosis</small>{esc(p['diagnosis'])}</div>
    <div style="grid-column:1/-1"><small>Address</small>{esc(p['address'])}</div></div></div>"""
    tabs = "".join(f'<a href="/patient?id={pid}&tab={k}" class="{"on" if tab == k else ""}">{l}</a>'
                   for k, l in [("routine", "📋 Daily Routine"), ("meds", "💊 Medicines"), ("bill", "🧾 Bill"), ("discharge", "🚪 Discharge")])
    flash = f'<div class="note">{esc(msg)}</div>' if msg else ""
    inner = ""
    now_local = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M')

    if tab == "routine":
        rows = c.execute("SELECT * FROM routine WHERE patient_id=? ORDER BY dt DESC", (pid,)).fetchall()
        tr = "".join(f"""<tr><td>{esc(r['dt'])}</td><td>{esc(r['bp'])}</td><td>{esc(r['temp'])}</td><td>{esc(r['pulse'])}</td>
            <td>{esc(r['spo2'])}</td><td>{esc(r['meal'])}</td><td>{esc(r['notes'])}</td><td>{esc(r['recorded_by'])}</td></tr>""" for r in rows)
        add = f"""<div class="card noprint"><h3>Add Daily Routine Entry</h3><form class="grid" method="post" action="/routine/add">
        <input type="hidden" name="pid" value="{pid}">
        <div><label>Date & Time</label><input type="datetime-local" name="dt" value="{now_local}"></div>
        <div><label>Blood Pressure</label><input name="bp" placeholder="120/80"></div>
        <div><label>Temperature (°F)</label><input name="temp" placeholder="98.6"></div>
        <div><label>Pulse (bpm)</label><input name="pulse" placeholder="78"></div>
        <div><label>SpO₂ (%)</label><input name="spo2" placeholder="98"></div>
        <div><label>Meal / Diet</label><input name="meal" placeholder="Breakfast - Idli"></div>
        <div><label>Recorded By</label><input name="recorded_by" required placeholder="Nurse name"></div>
        <div class="full"><label>Notes / Condition</label><textarea name="notes" rows="2"></textarea></div>
        <div class="full"><button class="btn">Save Entry</button></div></form></div>""" if admitted else ""
        inner = f"""{add}<div class="card"><h3>Daily Routine Log</h3><div class="wrap"><table>
        <tr><th>Date & Time</th><th>BP</th><th>Temp °F</th><th>Pulse</th><th>SpO₂</th><th>Meal</th><th>Notes</th><th>Recorded By</th></tr>
        {tr or '<tr><td colspan=8>No entries yet.</td></tr>'}</table></div></div>"""

    elif tab == "meds":
        rows = c.execute("SELECT * FROM medicines WHERE patient_id=? ORDER BY dt DESC", (pid,)).fetchall()
        tr = "".join(f"""<tr><td>{esc(r['dt'])}</td><td><b>{esc(r['name'])}</b></td><td>{esc(r['dosage'])}</td>
            <td>{esc(r['amount'])}</td><td>{money(r['cost'] or 0)}</td><td>👤 {esc(r['given_by'])}</td></tr>""" for r in rows)
        add = f"""<div class="card noprint"><h3>Record Medicine Given</h3><form class="grid" method="post" action="/meds/add">
        <input type="hidden" name="pid" value="{pid}">
        <div><label>Date & Time</label><input type="datetime-local" name="dt" value="{now_local}"></div>
        <div><label>Medicine Name *</label><input name="name" required></div>
        <div><label>Dosage (strength & frequency) *</label><input name="dosage" required placeholder="500 mg, twice daily"></div>
        <div><label>Amount Given</label><input name="amount" placeholder="1 tablet"></div>
        <div><label>Cost ({CURRENCY})</label><input name="cost" type="number" step="0.01" value="0"></div>
        <div><label>Given By (Doctor / Nurse) *</label><input name="given_by" required></div>
        <div class="full"><button class="btn">Save Medicine</button></div></form></div>""" if admitted else ""
        inner = f"""{add}<div class="card"><h3>Medicines Given</h3><div class="wrap"><table>
        <tr><th>Date & Time</th><th>Medicine</th><th>Dosage</th><th>Amount</th><th>Cost</th><th>Given By</th></tr>
        {tr or '<tr><td colspan=6>No medicines recorded.</td></tr>'}</table></div></div>"""

    elif tab == "bill":
        b = bill_for(c, p)
        crow = "".join(f"""<tr><td>{esc(x['description'])}</td><td style="text-align:right">{money(x['amount'])}</td>
            <td class="noprint"><a class="btn sm red" href="/charge/del?pid={pid}&id={x['id']}" onclick="return confirm('Remove this charge?')">✕</a></td></tr>""" for x in b["chg"])
        add = f"""<div class="card noprint"><h3>Add Service / Treatment Charge</h3><form class="grid" method="post" action="/charge/add">
        <input type="hidden" name="pid" value="{pid}"><div><label>Description</label><input name="description" required placeholder="X-Ray, Surgery, Lab test…"></div>
        <div><label>Amount ({CURRENCY})</label><input name="amount" type="number" step="0.01" required></div>
        <div style="align-self:end"><button class="btn">Add Charge</button></div></form></div>""" if admitted else ""
        status_txt = f"Discharged: {esc(p['discharge_date'])}" if p["discharge_date"] else "Status: Still admitted"
        inner = f"""{add}<div class="card" id="invoice"><div class="invoice-head">{LOGO}<div><h2 style="margin:0">{HOSPITAL.upper()}</h2>
        <small>PATIENT BILL / INVOICE</small></div><div style="margin-left:auto;text-align:right"><b>Bill No: XYZ-{pid:04d}</b><br>
        <small>Date: {datetime.date.today()}</small></div></div>
        <p><b>Patient:</b> {esc(p['name'])} &nbsp; <b>Doctor:</b> {esc(p['doctor'])} &nbsp; <b>Admitted:</b> {esc(p['admit_date'])}
        &nbsp; <b>{status_txt}</b></p>
        <div class="wrap"><table><tr><th>Description</th><th style="text-align:right">Amount</th><th class="noprint"></th></tr>
        <tr><td>Room charges – {esc(p['room_type'])} ({b['days']} day(s) × {money(b['rate'])})</td><td style="text-align:right">{money(b['room'])}</td><td class="noprint"></td></tr>
        {crow}
        <tr><td>Medicines ({len(b['meds'])} item(s) – see Medicines tab)</td><td style="text-align:right">{money(b['med_total'])}</td><td class="noprint"></td></tr>
        <tr class="total"><td>TOTAL AMOUNT</td><td style="text-align:right">{money(b['total'])}</td><td class="noprint"></td></tr></table></div>
        <p class="noprint"><button class="btn grey" onclick="window.print()">🖨️ Print Bill</button></p></div>"""

    elif tab == "discharge":
        if admitted:
            inner = f"""<div class="card"><h3>Discharge Patient</h3><form class="grid" method="post" action="/discharge">
            <input type="hidden" name="pid" value="{pid}">
            <div><label>Discharge Date</label><input type="date" name="discharge_date" value="{datetime.date.today()}"></div>
            <div class="full"><label>Discharge Summary / Advice *</label>
            <textarea name="summary" rows="4" required placeholder="Condition at discharge, medicines to continue, follow-up date…"></textarea></div>
            <div class="full"><button class="btn red" onclick="return confirm('Discharge this patient?')">Discharge Patient</button></div></form></div>"""
        else:
            inner = f"""<div class="card"><h3>Discharge Details</h3><div class="info">
            <div><small>Discharge Date</small>{esc(p['discharge_date'])}</div><div><small>Days Stayed</small>{days_stayed(p)}</div>
            <div style="grid-column:1/-1"><small>Summary / Advice</small>{esc(p['discharge_summary'])}</div></div>
            <p><a class="btn" href="/patient?id={pid}&tab=bill">View Final Bill</a></p></div>"""

    c.close()
    return page(p["name"], f'{head}<div class="tabs">{tabs}</div>{flash}{inner}', "home")


# ---------------------------------------------------------------- server
class H(BaseHTTPRequestHandler):
    def send(self, content, code=200):
        data = content.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def go(self, url):
        self.send_response(303)
        self.send_header("Location", url)
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == "/":
                self.send(dashboard(q))
            elif u.path == "/admit":
                self.send(admit_form())
            elif u.path == "/patient":
                self.send(patient_page(int(q.get("id", ["0"])[0]), q.get("tab", ["routine"])[0], q.get("msg", [""])[0]))
            elif u.path == "/charge/del":
                pid = int(q["pid"][0])
                c = db(); c.execute("DELETE FROM charges WHERE id=? AND patient_id=?", (int(q["id"][0]), pid)); c.commit(); c.close()
                self.go(f"/patient?id={pid}&tab=bill")
            else:
                self.send(page("Not found", '<div class="card">Page not found.</div>'), 404)
        except Exception as e:
            self.send(page("Error", f'<div class="card">Something went wrong: {esc(e)}</div>'), 500)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        f = {k: v[0].strip() for k, v in parse_qs(self.rfile.read(n).decode("utf-8")).items()}
        c = db()
        try:
            if self.path == "/admit":
                cur = c.execute("""INSERT INTO patients(name,age,gender,phone,address,blood_group,diagnosis,doctor,room_type,bed_no,admit_date)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (f["name"], int(f["age"]), f.get("gender"), f.get("phone"), f.get("address"),
                    f.get("blood_group"), f["diagnosis"], f["doctor"], f.get("room_type"), f.get("bed_no"),
                    f.get("admit_date") or str(datetime.date.today())))
                c.commit(); pid = cur.lastrowid
                self.go(f"/patient?id={pid}&tab=routine&msg=Patient+admitted+successfully")
            elif self.path == "/routine/add":
                pid = int(f["pid"])
                c.execute("INSERT INTO routine(patient_id,dt,bp,temp,pulse,spo2,meal,notes,recorded_by) VALUES(?,?,?,?,?,?,?,?,?)",
                          (pid, f["dt"].replace("T", " "), f.get("bp"), f.get("temp"), f.get("pulse"), f.get("spo2"),
                           f.get("meal"), f.get("notes"), f["recorded_by"]))
                c.commit(); self.go(f"/patient?id={pid}&tab=routine&msg=Entry+saved")
            elif self.path == "/meds/add":
                pid = int(f["pid"])
                c.execute("INSERT INTO medicines(patient_id,dt,name,dosage,amount,cost,given_by) VALUES(?,?,?,?,?,?,?)",
                          (pid, f["dt"].replace("T", " "), f["name"], f["dosage"], f.get("amount"), float(f.get("cost") or 0), f["given_by"]))
                c.commit(); self.go(f"/patient?id={pid}&tab=meds&msg=Medicine+recorded")
            elif self.path == "/charge/add":
                pid = int(f["pid"])
                c.execute("INSERT INTO charges(patient_id,description,amount) VALUES(?,?,?)", (pid, f["description"], float(f["amount"])))
                c.commit(); self.go(f"/patient?id={pid}&tab=bill&msg=Charge+added")
            elif self.path == "/discharge":
                pid = int(f["pid"])
                c.execute("UPDATE patients SET status='Discharged', discharge_date=?, discharge_summary=? WHERE id=?",
                          (f.get("discharge_date") or str(datetime.date.today()), f["summary"], pid))
                c.commit(); self.go(f"/patient?id={pid}&tab=bill&msg=Patient+discharged.+Final+bill+is+ready")
            else:
                self.send(page("Not found", '<div class="card">Not found.</div>'), 404)
        except Exception as e:
            self.send(page("Error", f'<div class="card">Could not save: {esc(e)}</div>'), 400)
        finally:
            c.close()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 8000))
    print(f"{HOSPITAL} running at http://localhost:{port}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
