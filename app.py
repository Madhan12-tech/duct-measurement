from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime

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
    return redirect(url_for('home'))

@app.route('/home')
def home():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM projects ORDER BY id DESC LIMIT 1")
    project = cursor.fetchone()

    cursor.execute("SELECT * FROM duct_entries ORDER BY id DESC")
    entries = cursor.fetchall()

    # Totals
    total_qty = sum(entry[8] for entry in entries)
    total_area = sum(entry[11] for entry in entries)
    total_bolts = sum(entry[12] for entry in entries)
    total_cleat = sum(entry[13] for entry in entries)
    total_gasket = sum(entry[14] for entry in entries)
    total_corner = sum(entry[15] for entry in entries)
    area_24g = sum(entry[11] for entry in entries if entry[10] == '24g')
    area_22g = sum(entry[11] for entry in entries if entry[10] == '22g')
    area_20g = sum(entry[11] for entry in entries if entry[10] == '20g')
    area_18g = sum(entry[11] for entry in entries if entry[10] == '18g')

    conn.close()
    return render_template(
        'duct_entry.html',
        project=project,
        entries=entries,
        total_qty=total_qty,
        total_area=total_area,
        total_bolts=total_bolts,
        total_cleat=total_cleat,
        total_gasket=total_gasket,
        total_corner=total_corner,
        area_24g=area_24g,
        area_22g=area_22g,
        area_20g=area_20g,
        area_18g=area_18g
    )

@app.route('/add_duct', methods=['POST'])
def add_duct():
    form = request.form
    id_ = form.get('id')
    duct_no = form['duct_no']
    duct_type = form['duct_type']
    width1 = float(form['width1'])
    height1 = float(form['height1'])
    width2 = float(form['width2'] or 0)
    height2 = float(form['height2'] or 0)
    length_or_radius = float(form['length_or_radius'])
    quantity = int(form['quantity'])
    degree_or_offset = float(form['degree_or_offset'] or 0)

    size_sum = width1 + height1
    if size_sum <= 750:
        gauge = '24g'
    elif size_sum <= 1200:
        gauge = '22g'
    elif size_sum <= 1800:
        gauge = '20g'
    else:
        gauge = '18g'

    if duct_type == 'ST':
        area = 2 * (width1 / 1000 + height1 / 1000) * (length_or_radius / 1000) * quantity
    elif duct_type == 'RED':
        area = (width1 / 1000 + height1 / 1000 + width2 / 1000 + height2 / 1000) * (length_or_radius / 1000) * quantity * 1.5
    elif duct_type == 'DUM':
        area = (width1 / 1000 * height1 / 1000) * quantity
    elif duct_type == 'OFFSET':
        area = (width1 / 1000 + height1 / 1000 + width2 / 1000 + height2 / 1000) * ((length_or_radius + degree_or_offset) / 1000) * quantity * 1.5
    elif duct_type == 'SHOE':
        area = (width1 / 1000 + height1 / 1000) * 2 * (length_or_radius / 1000) * quantity * 1.5
    elif duct_type == 'VANES':
        area = (width1 / 1000) * (2 * 3.14 * (width1 / 1000) / 2) / 4 * quantity
    elif duct_type == 'ELB':
        area = 2 * (width1 / 1000 + height1 / 1000) * ((height1 / 1000) / 2 + (length_or_radius / 1000) * (3.14 * (degree_or_offset / 180))) * quantity * 1.5
    else:
        area = 0

    if gauge == '24g': cleat = quantity * 4
    elif gauge == '22g': cleat = quantity * 8
    elif gauge == '20g': cleat = quantity * 10
    elif gauge == '18g': cleat = quantity * 12
    else: cleat = 0

    nuts_bolts = quantity * 4
    gasket = (width1 + height1 + width2 + height2) / 1000 * quantity
    corner_pieces = 0 if duct_type == 'DUM' else quantity * 8

    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()

    if id_:
        cursor.execute('''
            UPDATE duct_entries SET duct_no=?, duct_type=?, width1=?, height1=?, width2=?, height2=?,
            length_or_radius=?, quantity=?, degree_or_offset=?, gauge=?, area=?, nuts_bolts=?, cleat=?,
            gasket=?, corner_pieces=?, timestamp=? WHERE id=?
        ''', (duct_no, duct_type, width1, height1, width2, height2, length_or_radius, quantity, degree_or_offset,
              gauge, area, nuts_bolts, cleat, gasket, corner_pieces, datetime.now(), id_))
        flash('Duct entry updated!')
    else:
        cursor.execute('''
            INSERT INTO duct_entries (
                duct_no, duct_type, width1, height1, width2, height2, length_or_radius, quantity,
                degree_or_offset, gauge, area, nuts_bolts, cleat, gasket, corner_pieces, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (duct_no, duct_type, width1, height1, width2, height2, length_or_radius, quantity, degree_or_offset,
              gauge, area, nuts_bolts, cleat, gasket, corner_pieces, datetime.now()))
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
    return render_template('duct_entry.html', edit_entry=entry, project=project, entries=entries)

@app.route('/delete/<int:id>')
def delete_duct(id):
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM duct_entries WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash('Duct entry deleted!')
    return redirect(url_for('home'))

@app.route('/submit_all', methods=['POST'])
def submit_all():
    flash('All duct entries submitted successfully!')
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
