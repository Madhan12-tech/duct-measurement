from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import sqlite3
from datetime import datetime
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = 'secretkey'

def init_db():
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS duct_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            duct_no TEXT,
            duct_type TEXT,
            width1 REAL,
            height1 REAL,
            width2 REAL,
            height2 REAL,
            length_or_radius REAL,
            quantity INTEGER,
            degree_or_offset REAL,
            gauge TEXT,
            area REAL,
            nuts_bolts INTEGER,
            cleat INTEGER,
            gasket REAL,
            corner_pieces INTEGER,
            factor REAL,
            timestamp DATETIME
        )
    ''')
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
        form['project_name'],
        form['enquiry_no'],
        form['office_no'],
        form['site_engineer'],
        form['site_contact'],
        form['location'],
        datetime.now()
    ))
    conn.commit()
    conn.close()
    flash('Project saved successfully!')
    return redirect(url_for('home'))

@app.route('/home')
def home():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects ORDER BY id DESC LIMIT 1")
    project = cursor.fetchone()
    cursor.execute("SELECT * FROM duct_entries ORDER BY id DESC")
    entries = cursor.fetchall()
    conn.close()

    def total(col): return sum(e[col] for e in entries)
    def area_g(g): return sum(e[11] for e in entries if e[10] == g)

    return render_template('duct_entry.html',
        project=project,
        entries=entries,
        total_qty=total(8),
        total_area=total(11),
        total_bolts=total(12),
        total_cleat=total(13),
        total_gasket=total(14),
        total_corner=total(15),
        area_24g=area_g('24g'),
        area_22g=area_g('22g'),
        area_20g=area_g('20g'),
        area_18g=area_g('18g')
    )

@app.route('/add_duct', methods=['POST'])
def add_duct():
    form = request.form
    id_ = form.get('id')
    duct_type = form['duct_type']
    factor = float(form.get('factor') or 1.5)

    width1 = float(form['width1'])
    height1 = float(form['height1'])
    width2 = float(form['width2'] or 0)
    height2 = float(form['height2'] or 0)
    length = float(form['length_or_radius'])
    qty = int(form['quantity'])
    offset = float(form['degree_or_offset'] or 0)

    size_sum = width1 + height1
    gauge = '24g' if size_sum <= 750 else '22g' if size_sum <= 1200 else '20g' if size_sum <= 1800 else '18g'

    if duct_type == 'ST':
        area = 2 * (width1 + height1) / 1000 * (length / 1000) * qty
    elif duct_type == 'RED':
        area = (width1 + height1 + width2 + height2) / 1000 * (length / 1000) * qty * factor
    elif duct_type == 'DUM':
        area = (width1 * height1) / 1_000_000 * qty
    elif duct_type == 'OFFSET':
        area = (width1 + height1 + width2 + height2) / 1000 * ((length + offset) / 1000) * qty * factor
    elif duct_type == 'SHOE':
        area = (width1 + height1) * 2 / 1000 * (length / 1000) * qty * factor
    elif duct_type == 'VANES':
        area = width1 / 1000 * (2 * 3.14 * (width1 / 1000) / 2) / 4 * qty
    elif duct_type == 'ELB':
        area = 2 * (width1 + height1) / 1000 * ((height1 / 2 / 1000) + (length / 1000) * (3.14 * (offset / 180))) * qty * factor
    else:
        area = 0

    cleat = qty * (4 if gauge == '24g' else 8 if gauge == '22g' else 10 if gauge == '20g' else 12)
    nuts = qty * 4
    gasket = (width1 + height1 + width2 + height2) / 1000 * qty
    corners = 0 if duct_type == 'DUM' else qty * 8

    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()

    if id_:
        cursor.execute('''
            UPDATE duct_entries SET duct_no=?, duct_type=?, width1=?, height1=?, width2=?, height2=?,
            length_or_radius=?, quantity=?, degree_or_offset=?, gauge=?, area=?, nuts_bolts=?, cleat=?,
            gasket=?, corner_pieces=?, factor=?, timestamp=? WHERE id=?
        ''', (
            form['duct_no'], duct_type, width1, height1, width2, height2,
            length, qty, offset, gauge, area, nuts, cleat,
            gasket, corners, factor, datetime.now(), id_
        ))
        flash('Duct entry updated!')
    else:
        cursor.execute('''
            INSERT INTO duct_entries (
                duct_no, duct_type, width1, height1, width2, height2,
                length_or_radius, quantity, degree_or_offset, gauge, area,
                nuts_bolts, cleat, gasket, corner_pieces, factor, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            form['duct_no'], duct_type, width1, height1, width2, height2,
            length, qty, offset, gauge, area, nuts, cleat, gasket, corners, factor, datetime.now()
        ))
        flash('Duct entry added!')

    conn.commit()
    conn.close()
    return redirect(url_for('home'))

@app.route('/edit/<int:id>')
def edit_duct(id):
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM duct_entries WHERE id=?", (id,))
    entry = cursor.fetchone()
    cursor.execute("SELECT * FROM projects ORDER BY id DESC LIMIT 1")
    project = cursor.fetchone()
    cursor.execute("SELECT * FROM duct_entries ORDER BY id DESC")
    entries = cursor.fetchall()
    conn.close()

    def total(col): return sum(e[col] for e in entries)
    def area_g(g): return sum(e[11] for e in entries if e[10] == g)

    return render_template('duct_entry.html',
        edit_entry=entry,
        project=project,
        entries=entries,
        total_qty=total(8),
        total_area=total(11),
        total_bolts=total(12),
        total_cleat=total(13),
        total_gasket=total(14),
        total_corner=total(15),
        area_24g=area_g('24g'),
        area_22g=area_g('22g'),
        area_20g=area_g('20g'),
        area_18g=area_g('18g')
    )

@app.route('/delete/<int:id>')
def delete_duct(id):
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM duct_entries WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash('Entry deleted.')
    return redirect(url_for('home'))

@app.route('/export_excel')
def export_excel():
    conn = sqlite3.connect('data.db')
    df = pd.read_sql_query("SELECT * FROM duct_entries", conn)
    conn.close()
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')
    df.to_excel(writer, index=False, sheet_name='Duct Entries')
    writer.close()
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='duct_entries.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/export_pdf')
def export_pdf():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM duct_entries")
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
        line = ", ".join(str(i) for i in row[:11])
        if y < 40:
            pdf.showPage()
            y = height - 40
        pdf.drawString(30, y, line)
        y -= 15
    pdf.save()
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='duct_entries.pdf', mimetype='application/pdf')

if __name__ == '__main__':
    app.run(debug=True)
