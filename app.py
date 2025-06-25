from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import sqlite3
from datetime import datetime
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

app = Flask(__name__)
app.secret_key = 'secretkey'

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

    def total(index): return sum(float(e[index]) for e in entries if e[index] is not None)
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

    try:
        project_id = int(form['project_id'])
        duct_no = form['duct_no']
        duct_type = form['duct_type']
        factor = float(form.get('factor') or 1.0) if duct_type in ['RED', 'OFFSET', 'SHOE', 'ELB'] else 1.0

        width1 = float(form.get('width1') or 0)
        height1 = float(form.get('height1') or 0)
        width2 = float(form.get('width2') or 0)
        height2 = float(form.get('height2') or 0)
        length = float(form.get('length_or_radius') or 0)
        quantity = int(form.get('quantity') or 0)
        degree = float(form.get('degree_or_offset') or 0)

        if not duct_no or width1 == 0 or height1 == 0 or length == 0 or quantity == 0:
            flash("Please fill in all required fields.")
            return redirect(url_for('home', project_id=project_id))

    except Exception as e:
        flash(f"Invalid input: {e}")
        return redirect(url_for('home', project_id=form.get('project_id')))

    # Corrected gauge logic: check both width1 and height1 ranges
    if 0 <= width1 <= 751 and 0 <= height1 <= 751:
        gauge = '24g'
    elif 751 < width1 <= 1201 and 751 < height1 <= 1201:
        gauge = '22g'
    elif 1201 < width1 <= 1800 and 1201 < height1 <= 1800:
        gauge = '20g'
    elif width1 > 1800 and height1 > 1800:
        gauge = '18g'
    else:
        gauge = '18g'  # default fallback

    # Area logic
    if duct_type == 'ST':
        area = 2 * (width1 + height1) / 1000 * (length / 1000) * quantity
    elif duct_type == 'RED':
        area = (width1 + height1 + width2 + height2) / 1000 * (length / 1000) * quantity * factor
    elif duct_type == 'DUM':
        area = (width1 * height1) / 1_000_000 * quantity
    elif duct_type == 'OFFSET':
        area = (width1 + height1 + width2 + height2) / 1000 * ((length + degree) / 1000) * quantity * factor
    elif duct_type == 'SHOE':
        area = (width1 + height1) * 2 / 1000 * (length / 1000) * quantity * factor
    elif duct_type == 'VANES':
        area = width1 / 1000 * (2 * 3.14 * (width1 / 1000) / 4) * quantity
    elif duct_type == 'ELB':
        area = 2 * (width1 + height1) / 1000 * ((height1 / 2 / 1000) + (length / 1000) * (3.14 * (degree / 180))) * quantity * factor
    else:
        area = 0

    nuts_bolts = quantity * 4
    cleat = quantity * (4 if gauge == '24g' else 8 if gauge == '22g' else 10 if gauge == '20g' else 12)
    gasket = (width1 + height1 + width2 + height2) / 1000 * quantity
    corner = 0 if duct_type == 'DUM' else quantity * 8

    conn = sqlite3.connect('data.db')
    c = conn.cursor()

    if id_:
        c.execute('''
            UPDATE duct_entries SET project_id=?, duct_no=?, duct_type=?, width1=?, height1=?, width2=?, height2=?,
            length_or_radius=?, quantity=?, degree_or_offset=?, factor=?, gauge=?, area=?, nuts_bolts=?, cleat=?,
            gasket=?, corner_pieces=?, timestamp=? WHERE id=?
        ''', (project_id, duct_no, duct_type, width1, height1, width2, height2,
              length, quantity, degree, factor, gauge, area, nuts_bolts, cleat,
              gasket, corner, datetime.now(), id_))
        flash("Duct updated")
    else:
        c.execute('''
            INSERT INTO duct_entries (project_id, duct_no, duct_type, width1, height1, width2, height2,
            length_or_radius, quantity, degree_or_offset, factor, gauge, area, nuts_bolts, cleat,
            gasket, corner_pieces, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            project_id, duct_no, duct_type, width1, height1, width2, height2,
            length, quantity, degree, factor, gauge, area, nuts_bolts, cleat,
            gasket, corner, datetime.now()
        ))
        flash("Duct added")

    conn.commit()
    conn.close()
    return redirect(url_for('home', project_id=project_id))

@app.route('/edit/<int:id>')
def edit_duct(id):
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute("SELECT * FROM duct_entries WHERE id=?", (id,))
    entry = c.fetchone()
    if not entry:
        flash("Entry not found")
        return redirect(url_for('index'))
    project_id = entry[1]
    c.execute("SELECT * FROM projects WHERE id=?", (project_id,))
    project = c.fetchone()
    c.execute("SELECT * FROM duct_entries WHERE project_id=? ORDER BY id DESC", (project_id,))
    entries = c.fetchall()
    conn.close()

    def total(i): return sum(float(e[i]) for e in entries if e[i])
    def area_g(g): return sum(e[13] for e in entries if e[12] == g)

    return render_template('duct_entry.html', edit_entry=entry, project=project, entries=entries,
        project_id=project_id,
        total_qty=total(9),
        total_area=total(13),
        total_bolts=total(14),
        total_cleat=total(15),
        total_gasket=total(16),
        total_corner=total(17),
        area_24g=area_g('24g'),
        area_22g=area_g('22g'),
        area_20g=area_g('20g'),
        area_18g=area_g('18g')
    )

@app.route('/delete/<int:id>')
def delete_duct(id):
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute("SELECT project_id FROM duct_entries WHERE id=?", (id,))
    project_id = c.fetchone()[0]
    c.execute("DELETE FROM duct_entries WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Deleted successfully")
    return redirect(url_for('home', project_id=project_id))

@app.route('/export_excel/<int:project_id>')
def export_excel(project_id):
    import xlsxwriter

    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute("SELECT * FROM projects WHERE id=?", (project_id,))
    project = c.fetchone()
    c.execute("SELECT * FROM duct_entries WHERE project_id=?", (project_id,))
    entries = c.fetchall()
    conn.close()

    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet("Duct Entries")

    bold = workbook.add_format({'bold': True})
    center = workbook.add_format({'align': 'center'})
    total_format = workbook.add_format({'bold': True, 'bg_color': '#D9D9D9'})

    # Project Info
    worksheet.write('A1', 'Project Name', bold)
    worksheet.write('B1', project[1])
    worksheet.write('A2', 'Enquiry No', bold)
    worksheet.write('B2', project[2])
    worksheet.write('A3', 'Office No', bold)
    worksheet.write('B3', project[3])
    worksheet.write('A4', 'Site Engineer', bold)
    worksheet.write('B4', project[4])
    worksheet.write('A5', 'Contact', bold)
    worksheet.write('B5', project[5])
    worksheet.write('A6', 'Location', bold)
    worksheet.write('B6', project[6])

    # Table headers (row 8 = index 7)
    headers = [
        "Duct No", "Type", "W1", "H1", "W2", "H2", "Len/Rad", "Qty",
        "Deg/Off", "Factor", "Gauge", "Area", "Nuts", "Cleat", "Gasket", "Corner"
    ]
    for col, header in enumerate(headers):
        worksheet.write(7, col, header, bold)

    # Data rows
    total_qty = total_area = total_bolts = total_cleat = total_gasket = total_corner = 0
    row = 8
    for entry in entries:
        worksheet.write(row, 0, entry[2])   # Duct No
        worksheet.write(row, 1, entry[3])   # Type
        worksheet.write(row, 2, entry[4])   # W1
        worksheet.write(row, 3, entry[5])   # H1
        worksheet.write(row, 4, entry[6])   # W2
        worksheet.write(row, 5, entry[7])   # H2
        worksheet.write(row, 6, entry[8])   # Length/Radius
        worksheet.write(row, 7, entry[9])   # Qty
        worksheet.write(row, 8, entry[10])  # Degree/Offset
        worksheet.write(row, 9, entry[11])  # Factor
        worksheet.write(row,10, entry[12])  # Gauge
        worksheet.write(row,11, entry[13])  # Area
        worksheet.write(row,12, entry[14])  # Nuts
        worksheet.write(row,13, entry[15])  # Cleat
        worksheet.write(row,14, entry[16])  # Gasket
        worksheet.write(row,15, entry[17])  # Corner

        total_qty += entry[9]
        total_area += entry[13]
        total_bolts += entry[14]
        total_cleat += entry[15]
        total_gasket += entry[16]
        total_corner += entry[17]
        row += 1

    # Totals row
    worksheet.write(row, 6, 'Total', total_format)
    worksheet.write(row, 7, total_qty, total_format)
    worksheet.write(row,11, total_area, total_format)
    worksheet.write(row,12, total_bolts, total_format)
    worksheet.write(row,13, total_cleat, total_format)
    worksheet.write(row,14, total_gasket, total_format)
    worksheet.write(row,15, total_corner, total_format)

    # Auto column width
    for i in range(len(headers)):
        worksheet.set_column(i, i, 12)

    workbook.close()
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='duct_entries.xlsx')

@app.route('/submit_all/<int:project_id>', methods=['POST'])
def submit_all(project_id):
    flash("All duct entries submitted successfully!")
    return redirect(url_for('home', project_id=project_id))

@app.route('/export_pdf/<int:project_id>')
def export_pdf(project_id):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute("SELECT * FROM projects WHERE id=?", (project_id,))
    project = c.fetchone()
    c.execute("SELECT * FROM duct_entries WHERE project_id=?", (project_id,))
    entries = c.fetchall()
    conn.close()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)

    styles = getSampleStyleSheet()
    elements = []

    # Project & client info at top
    project_info = [
        f"Project Name: {project[1]}",
        f"Enquiry No: {project[2]}",
        f"Office No: {project[3]}",
        f"Site Engineer: {project[4]}",
        f"Contact: {project[5]}",
        f"Location: {project[6]}"
    ]
    for line in project_info:
        elements.append(Paragraph(line, styles['Normal']))
    elements.append(Spacer(1, 12))

    # Table headings
    table_data = [[
        "Duct No", "Type", "W1", "H1", "W2", "H2", "Len/Rad", "Qty",
        "Deg/Off", "Factor", "Gauge", "Area", "Nuts", "Cleat", "Gasket", "Corner"
    ]]

    # Data rows
    total_qty = total_area = total_bolts = total_cleat = total_gasket = total_corner = 0

    for entry in entries:
        table_data.append([
            entry[2], entry[3], entry[4], entry[5], entry[6], entry[7], entry[8], entry[9],
            entry[10], entry[11], entry[12], f"{entry[13]:.2f}", entry[14],
            entry[15], f"{entry[16]:.2f}", entry[17]
        ])
        total_qty += entry[9]
        total_area += entry[13]
        total_bolts += entry[14]
        total_cleat += entry[15]
        total_gasket += entry[16]
        total_corner += entry[17]

    # Totals row
    table_data.append([
        "", "", "", "", "", "", "Total", total_qty, "", "", "", f"{total_area:.2f}",
        total_bolts, total_cleat, f"{total_gasket:.2f}", total_corner
    ])

    # Build the table
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,-1), (-1,-1), colors.lightgrey),
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='duct_entries.pdf')


if __name__ == '__main__':
    app.run(debug=True)
