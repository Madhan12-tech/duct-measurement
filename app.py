from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import sqlite3
from datetime import datetime
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

app = Flask(__name__)
app.secret_key = 'secretkey'

def init_db():
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_name TEXT, enquiry_no TEXT, office_no TEXT,
        site_engineer TEXT, site_contact TEXT, location TEXT,
        timestamp DATETIME
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS duct_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER, duct_no TEXT, duct_type TEXT,
        width1 REAL, height1 REAL, width2 REAL, height2 REAL,
        length_or_radius REAL, quantity INTEGER, degree_or_offset REAL,
        factor REAL DEFAULT 1.0, gauge TEXT, area REAL,
        nuts_bolts INTEGER, cleat INTEGER, gasket REAL,
        corner_pieces INTEGER, timestamp DATETIME
    )''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    conn = sqlite3.connect('data.db')
    projects = conn.execute("SELECT * FROM projects ORDER BY id DESC").fetchall()
    conn.close()
    return render_template('home.html', projects=projects)

@app.route('/save_project', methods=['POST'])
def save_project():
    form = request.form
    conn = sqlite3.connect('data.db')
    conn.execute('''INSERT INTO projects (project_name, enquiry_no, office_no,
        site_engineer, site_contact, location, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (form['project_name'], form['enquiry_no'], form['office_no'],
         form['site_engineer'], form['site_contact'], form['location'], datetime.now()))
    conn.commit()
    pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return redirect(url_for('home', project_id=pid))

@app.route('/home/<int:project_id>')
def home(project_id):
    conn = sqlite3.connect('data.db')
    project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    entries = conn.execute("SELECT * FROM duct_entries WHERE project_id=? ORDER BY id DESC", (project_id,)).fetchall()
    conn.close()
    def total(i): return sum(e[i] for e in entries if e[i])
    def area_by_gauge(g): return sum(e[13] for e in entries if e[12] == g)
    return render_template('duct_entry.html', project=project, entries=entries, project_id=project_id,
        total_qty=total(9), total_area=total(13), total_bolts=total(14),
        total_cleat=total(15), total_gasket=total(16), total_corner=total(17),
        area_24g=area_by_gauge('24g'), area_22g=area_by_gauge('22g'),
        area_20g=area_by_gauge('20g'), area_18g=area_by_gauge('18g'))

@app.route('/add_duct', methods=['POST'])
def add_duct():
    f = request.form
    pid = int(f['project_id'])
    dt = f['duct_type']
    factor = float(f['factor']) if dt in ['RED','OFFSET','SHOE','ELB'] else 1.0
    w1, h1 = float(f['width1']), float(f['height1'])
    w2, h2 = float(f.get('width2') or 0), float(f.get('height2') or 0)
    l = float(f['length_or_radius'])
    qty = int(f['quantity'])
    deg = float(f.get('degree_or_offset') or 0)

    # gauge logic using width1 and height1 separately
    def gauge_calc(v): return '24g' if v <= 375 else '22g' if v <= 600 else '20g' if v <= 900 else '18g'
    gauge = gauge_calc(w1) if gauge_calc(w1) > gauge_calc(h1) else gauge_calc(h1)

    if dt == 'ST':
        area = 2 * (w1 + h1) / 1000 * (l / 1000) * qty
    elif dt == 'RED':
        area = (w1 + h1 + w2 + h2) / 1000 * (l / 1000) * qty * factor
    elif dt == 'DUM':
        area = (w1 * h1) / 1_000_000 * qty
    elif dt == 'OFFSET':
        area = (w1 + h1 + w2 + h2) / 1000 * ((l + deg) / 1000) * qty * factor
    elif dt == 'SHOE':
        area = (w1 + h1) * 2 / 1000 * (l / 1000) * qty * factor
    elif dt == 'VANES':
        area = w1 / 1000 * (2 * 3.14 * (w1 / 1000) / 2) / 4 * qty
    elif dt == 'ELB':
        area = 2 * (w1 + h1) / 1000 * ((h1 / 2 / 1000) + (l / 1000) * (3.14 * (deg / 180))) * qty * factor
    else:
        area = 0

    bolts = qty * 4
    cleat = qty * (4 if gauge == '24g' else 8 if gauge == '22g' else 10 if gauge == '20g' else 12)
    gasket = (w1 + h1 + w2 + h2) / 1000 * qty
    corners = 0 if dt == 'DUM' else qty * 8

    conn = sqlite3.connect('data.db')
    if f.get('id'):
        conn.execute('''UPDATE duct_entries SET project_id=?, duct_no=?, duct_type=?, width1=?, height1=?, width2=?, height2=?,
            length_or_radius=?, quantity=?, degree_or_offset=?, factor=?, gauge=?, area=?, nuts_bolts=?, cleat=?, gasket=?, corner_pieces=?, timestamp=?
            WHERE id=?''',
            (pid, f['duct_no'], dt, w1, h1, w2, h2, l, qty, deg, factor, gauge, area, bolts, cleat, gasket, corners, datetime.now(), f['id']))
        flash("Entry updated!")
    else:
        conn.execute('''INSERT INTO duct_entries (project_id, duct_no, duct_type, width1, height1, width2, height2,
            length_or_radius, quantity, degree_or_offset, factor, gauge, area, nuts_bolts, cleat, gasket, corner_pieces, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (pid, f['duct_no'], dt, w1, h1, w2, h2, l, qty, deg, factor, gauge, area, bolts, cleat, gasket, corners, datetime.now()))
        flash("Entry added!")
    conn.commit()
    conn.close()
    return redirect(url_for('home', project_id=pid))

@app.route('/edit/<int:id>')
def edit_duct(id):
    conn = sqlite3.connect('data.db')
    entry = conn.execute("SELECT * FROM duct_entries WHERE id=?", (id,)).fetchone()
    if not entry: return redirect('/')
    pid = entry[1]
    project = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    entries = conn.execute("SELECT * FROM duct_entries WHERE project_id=? ORDER BY id DESC", (pid,)).fetchall()
    conn.close()
    def total(i): return sum(e[i] for e in entries if e[i])
    def area_by_gauge(g): return sum(e[13] for e in entries if e[12] == g)
    return render_template('duct_entry.html', edit_entry=entry, project=project, entries=entries, project_id=pid,
        total_qty=total(9), total_area=total(13), total_bolts=total(14),
        total_cleat=total(15), total_gasket=total(16), total_corner=total(17),
        area_24g=area_by_gauge('24g'), area_22g=area_by_gauge('22g'),
        area_20g=area_by_gauge('20g'), area_18g=area_by_gauge('18g'))

@app.route('/delete/<int:id>')
def delete_duct(id):
    conn = sqlite3.connect('data.db')
    pid = conn.execute("SELECT project_id FROM duct_entries WHERE id=?", (id,)).fetchone()[0]
    conn.execute("DELETE FROM duct_entries WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Deleted entry.")
    return redirect(url_for('home', project_id=pid))

@app.route('/export_excel/<int:project_id>')
def export_excel(project_id):
    conn = sqlite3.connect('data.db')
    project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    df = pd.read_sql_query("SELECT * FROM duct_entries WHERE project_id=?", conn, params=(project_id,))
    conn.close()
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')
    info = pd.DataFrame([{
        'Project Name': project[1], 'Enquiry No': project[2], 'Engineer': project[4],
        'Site Contact': project[5], 'Location': project[6], 'Timestamp': project[7]
    }])
    info.to_excel(writer, index=False, sheet_name='Duct Entries', startrow=0)
    df.to_excel(writer, index=False, sheet_name='Duct Entries', startrow=3)
    writer.close()
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='duct_entries.xlsx')

@app.route('/export_pdf/<int:project_id>')
def export_pdf(project_id):
    conn = sqlite3.connect('data.db')
    project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    entries = conn.execute("SELECT * FROM duct_entries WHERE project_id=?", (project_id,)).fetchall()
    conn.close()

    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=letter)
    width, height = letter
    y = height - 40
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(30, y, f"Project: {project[1]} | Enquiry: {project[2]} | Engineer: {project[4]}")
    y -= 20
    pdf.setFont("Helvetica", 9)
    for e in entries:
        text = f"{e[2]} | {e[3]} | W:{e[4]} H:{e[5]} L:{e[8]} Qty:{e[9]} Area:{e[13]:.2f} Gauge:{e[12]}"
        if y < 40: pdf.showPage(); y = height - 40
        pdf.drawString(30, y, text)
        y -= 14
    pdf.save()
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="duct_entries.pdf")

if __name__ == '__main__':
    app.run(debug=True)
