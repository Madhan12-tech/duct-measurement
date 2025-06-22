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
            degree_or_offset TEXT,
            gauge TEXT,
            area REAL,
            nuts_bolts INTEGER,
            cleat INTEGER,
            gasket REAL,
            corner_pieces INTEGER,
            timestamp DATETIME
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def determine_gauge(width, height):
    perimeter = width + height
    if perimeter <= 750:
        return "24g"
    elif perimeter <= 1200:
        return "22g"
    elif perimeter <= 1800:
        return "20g"
    else:
        return "18g"

def calculate_area(duct_type, w1, h1, w2, h2, l, qty, offset, deg):
    if duct_type == 'ST':
        return round(2 * (w1/1000 + h1/1000) * (l/1000) * qty, 2)
    elif duct_type == 'RED':
        return round((w1/1000 + h1/1000 + w2/1000 + h2/1000) * (l/1000) * qty * 1.5, 2)
    elif duct_type == 'DUM':
        return round((w1/1000 * h1/1000) * qty, 2)
    elif duct_type == 'OFFSET':
        return round((w1/1000 + h1/1000 + w2/1000 + h2/1000) * ((l + offset)/1000) * qty * 1.5, 2)
    elif duct_type == 'SHOE':
        return round((w1/1000 + h1/1000) * 2 * (l/1000) * qty * 1.5, 2)
    elif duct_type == 'VANES':
        return round((w1/1000) * (2 * 3.14 * (w1/1000) / 2) / 4 * qty, 2)
    elif duct_type == 'ELB':
        return round((2 * (w1/1000 + h1/1000)) * ((h1/1000)/2 + (l/1000) * (3.14 * (float(deg or 0)/180)) * qty * 1.5), 2)
    return 0

def calculate_cleat(gauge, qty):
    return {
        '24g': qty * 4,
        '22g': qty * 8,
        '20g': qty * 10,
        '18g': qty * 12
    }.get(gauge, 0)

def calculate_gasket(w1, h1, w2, h2, qty):
    return round((w1 + h1 + (w2 or 0) + (h2 or 0)) / 1000 * qty, 2)

def calculate_corner_pieces(duct_type, qty):
    return 0 if duct_type == 'DUM' else qty * 8

@app.route('/')
def home():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects ORDER BY id DESC LIMIT 1")
    project = cursor.fetchone()
    conn.close()
    return render_template('duct_entry.html', project=project, entries=[], edit_entry=None)

@app.route('/add_duct', methods=['POST'])
def add_duct():
    form = request.form
    id = form.get('id')
    duct_no = form['duct_no']
    duct_type = form['duct_type']
    width1 = float(form['width1'])
    height1 = float(form['height1'])
    width2 = float(form['width2'] or 0)
    height2 = float(form['height2'] or 0)
    length_or_radius = float(form['length_or_radius'])
    quantity = int(form['quantity'])
    degree_or_offset = form['degree_or_offset']

    gauge = determine_gauge(width1, height1)
    area = calculate_area(duct_type, width1, height1, width2, height2, length_or_radius, quantity, float(degree_or_offset or 0), degree_or_offset)
    nuts_bolts = quantity * 4
    cleat = calculate_cleat(gauge, quantity)
    gasket = calculate_gasket(width1, height1, width2, height2, quantity)
    corner_pieces = calculate_corner_pieces(duct_type, quantity)

    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    if id:
        cursor.execute('''
            UPDATE duct_entries SET duct_no=?, duct_type=?, width1=?, height1=?, width2=?, height2=?,
            length_or_radius=?, quantity=?, degree_or_offset=?, gauge=?, area=?, nuts_bolts=?, cleat=?,
            gasket=?, corner_pieces=?, timestamp=? WHERE id=?
        ''', (duct_no, duct_type, width1, height1, width2, height2, length_or_radius, quantity,
              degree_or_offset, gauge, area, nuts_bolts, cleat, gasket, corner_pieces, datetime.now(), id))
        flash('Duct entry updated!')
    else:
        cursor.execute('''
            INSERT INTO duct_entries (duct_no, duct_type, width1, height1, width2, height2, length_or_radius,
            quantity, degree_or_offset, gauge, area, nuts_bolts, cleat, gasket, corner_pieces, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (duct_no, duct_type, width1, height1, width2, height2, length_or_radius, quantity,
              degree_or_offset, gauge, area, nuts_bolts, cleat, gasket, corner_pieces, datetime.now()))
        flash('Duct entry added!')

    conn.commit()
    conn.close()
    return redirect(url_for('home'))

@app.route('/edit/<int:id>')
def edit_duct(id):
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects ORDER BY id DESC LIMIT 1")
    project = cursor.fetchone()
    cursor.execute("SELECT * FROM duct_entries ORDER BY id DESC")
    entries = cursor.fetchall()
    cursor.execute("SELECT * FROM duct_entries WHERE id=?", (id,))
    edit_entry = cursor.fetchone()
    conn.close()
    return render_template('duct_entry.html', project=project, entries=entries, edit_entry=edit_entry)

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
    flash(f"All duct entries submitted successfully at {datetime.now().strftime('%H:%M:%S')}")
    return redirect(url_for('home'))
