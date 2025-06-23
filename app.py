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
    return render_template('home.html')

@app.route('/home')
def home():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects ORDER BY id DESC LIMIT 1")
    project = cursor.fetchone()
    cursor.execute("SELECT * FROM duct_entries ORDER BY id DESC")
    entries = cursor.fetchall()
    conn.close()
    return render_template('duct_entry.html', project=project, entries=entries)

@app.route('/save_project', methods=['POST'])
def save_project():
    data = (
        request.form['project_name'],
        request.form['enquiry_no'],
        request.form['office_no'],
        request.form['site_engineer'],
        request.form['site_contact'],
        request.form['location'],
        datetime.now()
    )
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO projects (project_name, enquiry_no, office_no, site_engineer, site_contact, location, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', data)
    conn.commit()
    conn.close()
    flash('Project saved successfully!')
    return redirect(url_for('home'))

@app.route('/add_duct', methods=['POST'])
def add_duct():
    form = request.form
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

    cleat = {'24g': 4, '22g': 8, '20g': 10, '18g': 12}.get(gauge, 0) * quantity
    nuts_bolts = quantity * 4
    gasket = (width1 + height1 + width2 + height2) / 1000 * quantity
    corner_pieces = 0 if duct_type == 'DUM' else quantity * 8

    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO duct_entries (
            duct_no, duct_type, width1, height1, width2, height2, length_or_radius,
            quantity, degree_or_offset, gauge, area, nuts_bolts, cleat,
            gasket, corner_pieces, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        duct_no, duct_type, width1, height1, width2, height2, length_or_radius,
        quantity, degree_or_offset, gauge, area, nuts_bolts, cleat,
        gasket, corner_pieces, datetime.now()
    ))
    conn.commit()
    conn.close()
    flash('Duct entry added!')
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

if __name__ == "__main__":
    app.run(debug=True)
