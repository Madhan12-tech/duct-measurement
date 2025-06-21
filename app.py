from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import sqlite3
from datetime import datetime
from io import BytesIO
import xlsxwriter
from fpdf import FPDF
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'
DB_NAME = "Duct_Measurement.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS project (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT,
            enquiry_no TEXT,
            office_no TEXT,
            site_engineer TEXT,
            site_contact TEXT,
            location TEXT
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS duct_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            duct_type TEXT,
            width REAL,
            height REAL,
            length_radius REAL,
            quantity INTEGER,
            gauge TEXT,
            factor REAL,
            area REAL,
            accessories REAL,
            duct_number TEXT,
            timestamp TEXT
        )
    ''')

    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('base.html')

@app.route('/save_project', methods=['POST'])
def save_project():
    data = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO project (project_name, enquiry_no, office_no, site_engineer, site_contact, location)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        data['project_name'], data['enquiry_no'], data['office_no'],
        data['site_engineer'], data['site_contact'], data['location']
    ))
    conn.commit()
    project_id = cur.lastrowid
    conn.close()
    return redirect(url_for('duct_entry', project_id=project_id))

@app.route('/duct_entry/<int:project_id>', methods=['GET', 'POST'])
def duct_entry(project_id):
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        form = request.form
        duct_type = form['duct_type']
        width = float(form['width'])
        height = float(form['height'])
        length_radius = float(form['length_radius'])
        quantity = int(form['quantity'])
        gauge = form['gauge']
        factor = float(form['factor']) if form['factor'] else 1.5
        duct_number = form['duct_number']
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        area = (2 * (width + height) * length_radius * factor) / 144
        accessories = quantity * 5  # Placeholder

        cur.execute('''
            INSERT INTO duct_entries (project_id, duct_type, width, height, length_radius,
            quantity, gauge, factor, area, accessories, duct_number, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            project_id, duct_type, width, height, length_radius, quantity,
            gauge, factor, area, accessories, duct_number, timestamp
        ))
        conn.commit()
        flash('Duct entry added successfully!')

    cur.execute('SELECT * FROM project WHERE id = ?', (project_id,))
    project = cur.fetchone()

    cur.execute('SELECT * FROM duct_entries WHERE project_id = ?', (project_id,))
    entries = cur.fetchall()

    totals = {'quantity': 0, 'area': 0, 'accessories': 0}
    for row in entries:
        totals['quantity'] += row['quantity']
        totals['area'] += row['area']
        totals['accessories'] += row['accessories']

    conn.close()
    return render_template('duct_entry.html', project=project, entries=entries, totals=totals)

@app.route('/export_excel/<int:project_id>')
def export_excel(project_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute('SELECT * FROM project WHERE id = ?', (project_id,))
    project = cur.fetchone()

    cur.execute('SELECT * FROM duct_entries WHERE project_id = ?', (project_id,))
    entries = cur.fetchall()

    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet()

    worksheet.write_row(0, 0, [
        'Duct No', 'Type', 'Width', 'Height', 'Length/Radius',
        'Quantity', 'Gauge', 'Factor', 'Area', 'Accessories', 'Timestamp'
    ])

    for idx, row in enumerate(entries, start=1):
        worksheet.write_row(idx, 0, [
            row['duct_number'], row['duct_type'], row['width'], row['height'],
            row['length_radius'], row['quantity'], row['gauge'],
            row['factor'], row['area'], row['accessories'], row['timestamp']
        ])

    workbook.close()
    output.seek(0)
    filename = f"Duct_Entries_Project_{project_id}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True)

@app.route('/export_pdf/<int:project_id>')
def export_pdf(project_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute('SELECT * FROM project WHERE id = ?', (project_id,))
    project = cur.fetchone()

    cur.execute('SELECT * FROM duct_entries WHERE project_id = ?', (project_id,))
    entries = cur.fetchall()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Duct Measurement Report", ln=1, align='C')

    for key in ['project_name', 'enquiry_no', 'office_no', 'site_engineer', 'site_contact', 'location']:
        pdf.cell(200, 10, txt=f"{key.replace('_', ' ').title()}: {project[key]}", ln=1)

    pdf.ln(5)
    pdf.set_font("Arial", size=10)
    for row in entries:
        line = f"Duct No: {row['duct_number']} | Type: {row['duct_type']} | Qty: {row['quantity']} | Area: {row['area']:.2f}"
        pdf.cell(200, 8, txt=line, ln=1)

    output = BytesIO()
    pdf.output(output)
    output.seek(0)
    filename = f"Duct_Entries_Project_{project_id}.pdf"
    return send_file(output, download_name=filename, as_attachment=True)

@app.route('/submit/<int:project_id>', methods=['POST'])
def submit(project_id):
    flash("Project submitted successfully!")
    return redirect(url_for('duct_entry', project_id=project_id))

