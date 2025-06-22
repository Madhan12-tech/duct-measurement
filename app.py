from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import sqlite3
from datetime import datetime
import io
import xlsxwriter
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = 'secretkey'

def init_db():
    conn = sqlite3.connect('data.db')
    c = conn.cursor()

    # Create project table
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

    # Create duct entries table
    c.execute('''
        CREATE TABLE IF NOT EXISTS duct_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            timestamp DATETIME
        )
    ''')

    conn.commit()
    conn.close()

init_db()

def calculate_area(width, height, length, factor):
    return round(((2 * (width + height)) * length * factor) / 144, 2)

def calculate_accessories(area):
    return round(area * 0.25, 2)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/save_project', methods=['POST'])
def save_project():
    form = request.form
    data = (
        form['project_name'],
        form['enquiry_no'],
        form['office_no'],
        form['site_engineer'],
        form['site_contact'],
        form['location'],
        datetime.now()
    )
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO projects
        (project_name, enquiry_no, office_no, site_engineer, site_contact, location, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', data)
    conn.commit()
    conn.close()
    flash('Project saved successfully!')
    return redirect(url_for('duct_entry'))

@app.route('/duct_entry')
def duct_entry():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM duct_entries ORDER BY id DESC")
    entries = cursor.fetchall()

    cursor.execute("SELECT SUM(quantity), SUM(area), SUM(accessories) FROM duct_entries")
    total = cursor.fetchone()
    total_data = {
        'total_qty': total[0] or 0,
        'total_area': round(total[1] or 0, 2),
        'total_acc': round(total[2] or 0, 2)
    }

    cursor.execute("SELECT * FROM projects ORDER BY id DESC LIMIT 1")
    project = cursor.fetchone()

    conn.close()
    return render_template('duct_entry.html', entries=entries, total=total_data, project=project)

@app.route('/add_duct', methods=['POST'])
def add_duct():
    form = request.form
    id = form.get('id')
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
            (duct_no, duct_type, width, height, length_or_radius, quantity, gauge, factor, area, accessories, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (duct_no, duct_type, width, height, length, quantity, gauge, factor, area, accessories, datetime.now()))
        flash('Duct entry added!')
    conn.commit()
    conn.close()
    return redirect(url_for('duct_entry'))

@app.route('/edit/<int:id>')
def edit_duct(id):
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute("SELECT * FROM duct_entries WHERE id=?", (id,))
    entry = c.fetchone()

    c.execute("SELECT * FROM duct_entries ORDER BY id DESC")
    entries = c.fetchall()

    c.execute("SELECT SUM(quantity), SUM(area), SUM(accessories) FROM duct_entries")
    total = c.fetchone()
    total_data = {
        'total_qty': total[0] or 0,
        'total_area': round(total[1] or 0, 2),
        'total_acc': round(total[2] or 0, 2)
    }

    c.execute("SELECT * FROM projects ORDER BY id DESC LIMIT 1")
    project = c.fetchone()

    conn.close()
    return render_template("duct_entry.html", edit_entry=entry, entries=entries, total=total_data, project=project)

@app.route('/delete/<int:id>')
def delete_duct(id):
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute("DELETE FROM duct_entries WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash('Duct entry deleted!')
    return redirect(url_for('duct_entry'))

@app.route('/export_excel')
def export_excel():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM duct_entries")
    data = cursor.fetchall()

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet()

    headers = ['ID', 'Duct No', 'Type', 'Width', 'Height', 'Length', 'Qty', 'Gauge', 'Factor', 'Area', 'Accessories']
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)

    for row_num, row in enumerate(data, 1):
        for col_num in range(11):
            worksheet.write(row_num, col_num, row[col_num])

    workbook.close()
    output.seek(0)
    return send_file(output, download_name="duct_entries.xlsx", as_attachment=True)

@app.route('/export_pdf')
def export_pdf():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM duct_entries")
    data = cursor.fetchall()

    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    pdf.setFont("Helvetica", 10)
    y = 800

    pdf.drawString(30, y, "Duct Entries Report")
    y -= 20
    for entry in data:
        text = f"{entry[0]} | {entry[1]} | {entry[2]} | {entry[3]}x{entry[4]} | L:{entry[5]} | Qty:{entry[6]} | G:{entry[7]} | A:{entry[9]} | Acc:{entry[10]}"
        pdf.drawString(30, y, text)
        y -= 15
        if y < 50:
            pdf.showPage()
            y = 800

    pdf.save()
    output.seek(0)
    return send_file(output, download_name="duct_entries.pdf", as_attachment=True)

@app.route('/submit_all', methods=['POST'])
def submit_all():
    flash(f"All duct entries submitted successfully at {datetime.now().strftime('%H:%M:%S')}")
    return redirect(url_for('duct_entry'))

if __name__ == '__main__':
    app.run(debug=True)
