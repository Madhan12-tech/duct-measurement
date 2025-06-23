from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import sqlite3
from datetime import datetime
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import logging

app = Flask(__name__)
app.secret_key = 'secretkey'
logging.basicConfig(level=logging.DEBUG)

def init_db():
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT,
            enquiry_no TEXT,
            office_no TEXT,
            site_engineer TEXT,
            site_contact TEXT,
            location TEXT,
            timestamp DATETIME
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS duct_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            duct_no TEXT,
            duct_type TEXT,
            width1 REAL,
            height1 REAL,
            width2 REAL,
            height2 REAL,
            length_or_radius REAL,
            quantity INTEGER,
            degree_or_offset REAL,
            factor REAL DEFAULT 1.0,
            gauge TEXT,
            area REAL,
            nuts_bolts INTEGER,
            cleat INTEGER,
            gasket REAL,
            corner_pieces INTEGER,
            timestamp DATETIME
        )
    ''')
    # Safe add new columns
    try:
        c.execute("ALTER TABLE duct_entries ADD COLUMN factor REAL DEFAULT 1.0")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE duct_entries ADD COLUMN timestamp DATETIME")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects ORDER BY id DESC")
    projects = cursor.fetchall()
    conn.close()
    return render_template('home.html', projects=projects)

@app.route('/save_project', methods=['POST'])
def save_project():
    form = request.form
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO projects (project_name, enquiry_no, office_no, site_engineer, site_contact, location, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        form['project_name'], form['enquiry_no'], form['office_no'],
        form['site_engineer'], form['site_contact'], form['location'], datetime.now()
    ))
    conn.commit()
    project_id = c.lastrowid
    conn.close()
    return redirect(url_for('home', project_id=project_id))

@app.route('/home/<int:project_id>')
def home(project_id):
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE id=?", (project_id,))
    project = cursor.fetchone()
    cursor.execute("SELECT * FROM duct_entries WHERE project_id=? ORDER BY id DESC", (project_id,))
    entries = cursor.fetchall()
    conn.close()

    def total(column): return sum(e[column] for e in entries)
    def area_by_gauge(g): return sum(e[13] for e in entries if e[12] == g)

    return render_template('duct_entry.html',
        project=project,
        entries=entries,
        project_id=project_id,
        total_qty=total(9),
        total_area=total(13),
        total_bolts=total(14),
        total_cleat=total(15),
        total_gasket=total(16),
        total_corner=total(17),
        area_24g=area_by_gauge('24g'),
        area_22g=area_by_gauge('22g'),
        area_20g=area_by_gauge('20g'),
        area_18g=area_by_gauge('18g')
    )

@app.route('/add_duct', methods=['POST'])
def add_duct():
    form = request.form
    id_ = form.get('id')
    project_id = int(form.get('project_id'))
    duct_type = form['duct_type']
    factor = float(form.get('factor', 1.0)) if duct_type in ['RED', 'OFFSET', 'SHOE', 'ELB'] else 1.0

    width1 = float(form.get('width1', 0))
    height1 = float(form.get('height1', 0))
    width2 = float(form.get('width2') or 0)
    height2 = float(form.get('height2') or 0)
    length_or_radius = float(form.get('length_or_radius', 0))
    quantity = int(form.get('quantity', 1))
    degree_or_offset = float(form.get('degree_or_offset') or 0)

    max_size = max(width1, height1)
    if max_size <= 375:
        gauge = '24g'
    elif max_size <= 600:
        gauge = '22g'
    elif max_size <= 900:
        gauge = '20g'
    else:
        gauge = '18g'

    if duct_type == 'ST':
        area = 2 * (width1 + height1) / 1000 * (length_or_radius / 1000) * quantity
    elif duct_type == 'RED':
        area = (width1 + height1 + width2 + height2) / 1000 * (length_or_radius / 1000) * quantity * factor
    elif duct_type == 'DUM':
        area = (width1 * height1) / 1_000_000 * quantity
    elif duct_type == 'OFFSET':
        area = (width1 + height1 + width2 + height2) / 1000 * ((length_or_radius + degree_or_offset) / 1000) * quantity * factor
    elif duct_type == 'SHOE':
        area = (width1 + height1) * 2 / 1000 * (length_or_radius / 1000) * quantity * factor
    elif duct_type == 'VANES':
        area = width1 / 1000 * (2 * 3.14 * (width1 / 1000) / 2) / 4 * quantity
    elif duct_type == 'ELB':
        area = 2 * (width1 + height1) / 1000 * ((height1 / 2 / 1000) + (length_or_radius / 1000) * (3.14 * (degree_or_offset / 180))) * quantity * factor
    else:
        area = 0

    nuts_bolts = quantity * 4
    cleat = quantity * (4 if gauge == '24g' else 8 if gauge == '22g' else 10 if gauge == '20g' else 12)
    gasket = (width1 + height1 + width2 + height2) / 1000 * quantity
    corner_pieces = 0 if duct_type == 'DUM' else quantity * 8

    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()

    if id_:
        cursor.execute('''
            UPDATE duct_entries SET project_id=?, duct_no=?, duct_type=?, width1=?, height1=?, width2=?, height2=?,
            length_or_radius=?, quantity=?, degree_or_offset=?, factor=?, gauge=?, area=?, nuts_bolts=?, cleat=?,
            gasket=?, corner_pieces=?, timestamp=? WHERE id=?
        ''', (
            project_id, form['duct_no'], duct_type, width1, height1, width2, height2, length_or_radius,
            quantity, degree_or_offset, factor, gauge, area, nuts_bolts, cleat, gasket, corner_pieces, datetime.now(), id_
        ))
        flash('Duct entry updated!')
    else:
        cursor.execute('''
            INSERT INTO duct_entries (project_id, duct_no, duct_type, width1, height1, width2, height2, length_or_radius,
            quantity, degree_or_offset, factor, gauge, area, nuts_bolts, cleat, gasket, corner_pieces, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            project_id, form['duct_no'], duct_type, width1, height1, width2, height2, length_or_radius,
            quantity, degree_or_offset, factor, gauge, area, nuts_bolts, cleat, gasket, corner_pieces, datetime.now()
        ))
        flash('Duct entry added!')

    conn.commit()
    conn.close()
    return redirect(url_for('home', project_id=project_id))

@app.route('/edit/<int:id>')
def edit_duct(id):
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM duct_entries WHERE id=?", (id,))
    entry = cursor.fetchone()
    if not entry:
        flash("Entry not found!")
        return redirect(url_for('index'))
    project_id = entry[1]
    cursor.execute("SELECT * FROM projects WHERE id=?", (project_id,))
    project = cursor.fetchone()
    cursor.execute("SELECT * FROM duct_entries WHERE project_id=? ORDER BY id DESC", (project_id,))
    entries = cursor.fetchall()
    conn.close()
    return render_template('duct_entry.html', edit_entry=entry, project=project, entries=entries, project_id=project_id)

@app.route('/delete/<int:id>')
def delete_duct(id):
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT project_id FROM duct_entries WHERE id=?", (id,))
    result = cursor.fetchone()
    if not result:
        flash("Entry not found!")
        return redirect(url_for('index'))
    project_id = result[0]
    cursor.execute("DELETE FROM duct_entries WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Duct entry deleted!")
    return redirect(url_for('home', project_id=project_id))

@app.route('/export_excel/<int:project_id>')
def export_excel(project_id):
    conn = sqlite3.connect('data.db')
    df = pd.read_sql_query("SELECT * FROM duct_entries WHERE project_id=?", conn, params=(project_id,))
    conn.close()
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')
    df.to_excel(writer, index=False, sheet_name='Duct Entries')
    writer.close()
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='duct_entries.xlsx')

@app.route('/export_pdf/<int:project_id>')
def export_pdf(project_id):
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM duct_entries WHERE project_id=?", (project_id,))
    data = cursor.fetchall()
    conn.close()

    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=letter)
    width, height = letter
    y = height - 40
    pdf.setFont("Helvetica", 10)
    pdf.drawString(30, y, "Duct Entries Report")
    y -= 20

    for row in data:
        text = ", ".join(str(x) for x in row[1:12])
        if y < 40:
            pdf.showPage()
            y = height - 40
        pdf.drawString(30, y, text)
        y -= 15

    pdf.save()
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='duct_entries.pdf')

if __name__ == '__main__':
    app.run(debug=True)
