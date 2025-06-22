from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import sqlite3
from datetime import datetime
import io
import xlsxwriter
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = 'secretkey'

# Ensure tables exist
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
            width REAL,
            height REAL,
            length_or_radius REAL,
            quantity INTEGER,
            gauge TEXT,
            factor REAL,
            area REAL,
            accessories REAL,
            timestamp DATETIME,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    return render_template('home.html')

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
    c = conn.cursor()
    c.execute("INSERT INTO projects (project_name, enquiry_no, office_no, site_engineer, site_contact, location, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)", data)
    conn.commit()
    project_id = c.lastrowid
    conn.close()
    return redirect(url_for('duct_entry', project_id=project_id))

@app.route('/duct_entry')
def duct_entry():
    project_id = request.args.get('project_id')
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute("SELECT * FROM projects WHERE id=?", (project_id,))
    project = c.fetchone()
    c.execute("SELECT * FROM duct_entries WHERE project_id=? ORDER BY id DESC", (project_id,))
    entries = c.fetchall()
    c.execute("SELECT SUM(quantity), SUM(area), SUM(accessories) FROM duct_entries WHERE project_id=?", (project_id,))
    total = c.fetchone()
    conn.close()
    total_data = {
        'total_qty': total[0] or 0,
        'total_area': round(total[1] or 0, 2),
        'total_acc': round(total[2] or 0, 2)
    }
    return render_template('duct_entry.html', project=project, entries=entries, total=total_data)

def calculate_area(width, height, length, factor):
    return round(((2 * (width + height)) * length * factor) / 144, 2)

def calculate_accessories(area):
    return round(area * 0.25, 2)

@app.route('/add_duct', methods=['POST'])
def add_duct():
    form = request.form
    id = form.get('id')
    project_id = request.args.get('project_id')
    duct_no = form['duct_no']
    duct_type = form['duct_type']
    width = float(form['width'])
    height = float(form['height'])
    length = float(form['length_or_radius'])
    quantity = int(form['quantity'])
    gauge = form['gauge']
    factor = float(form['factor']) if form['factor'] else 1.0
    area = calculate_area(width, height, length, factor)
    accessories = calculate_accessories(area)
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    if id:
        cursor.execute('''
            UPDATE duct_entries SET 
            duct_no=?, duct_type=?, width=?, height=?, length_or_radius=?, quantity=?, gauge=?, factor=?, area=?, accessories=?, timestamp=?
            WHERE id=?
        ''', (duct_no, duct_type, width, height, length, quantity, gauge, factor, area, accessories, datetime.now(), id))
        flash('Duct entry updated!')
    else:
        cursor.execute('''
            INSERT INTO duct_entries 
            (project_id, duct_no, duct_type, width, height, length_or_radius, quantity, gauge, factor, area, accessories, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (project_id, duct_no, duct_type, width, height, length, quantity, gauge, factor, area, accessories, datetime.now()))
        flash('Duct entry added!')
    conn.commit()
    conn.close()
    return redirect(url_for('duct_entry', project_id=project_id))

@app.route('/edit/<int:id>')
def edit_duct(id):
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute("SELECT * FROM duct_entries WHERE id=?", (id,))
    entry = c.fetchone()
    c.execute("SELECT * FROM projects WHERE id=?", (entry[1],))
    project = c.fetchone()
    c.execute("SELECT * FROM duct_entries WHERE project_id=? ORDER BY id DESC", (entry[1],))
    entries = c.fetchall()
    c.execute("SELECT SUM(quantity), SUM(area), SUM(accessories) FROM duct_entries WHERE project_id=?", (entry[1],))
    total = c.fetchone()
    conn.close()
    total_data = {
        'total_qty': total[0] or 0,
        'total_area': round(total[1] or 0, 2),
        'total_acc': round(total[2] or 0, 2)
    }
    return render_template('duct_entry.html', project=project, entries=entries, total=total_data, edit_entry=entry)

@app.route('/delete/<int:id>')
def delete_duct(id):
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute("SELECT project_id FROM duct_entries WHERE id=?", (id,))
    project_id = c.fetchone()[0]
    c.execute("DELETE FROM duct_entries WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash('Duct entry deleted!')
    return redirect(url_for('duct_entry', project_id=project_id))

@app.route('/submit_all', methods=['POST'])
def submit_all():
    project_id = request.args.get('project_id')
    flash(f"All duct entries submitted successfully at {datetime.now().strftime('%H:%M:%S')}")
    return redirect(url_for('duct_entry', project_id=project_id))
