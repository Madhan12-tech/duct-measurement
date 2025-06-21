from flask import Flask, render_template, request, redirect, jsonify, send_file
from flask_mysqldb import MySQL
import math
import io
import csv
import xlsxwriter
from xhtml2pdf import pisa

app = Flask(__name__)
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'MAD123@mad'
app.config['MYSQL_DB'] = 'measurement_db'
mysql = MySQL(app)

def calculate_area(data):
    w1 = float(data.get('w1') or 0)
    h1 = float(data.get('h1') or 0)
    w2 = float(data.get('w2') or 0)
    h2 = float(data.get('h2') or 0)
    length_or_radius = float(data.get('length_or_radius') or 0)
    quantity = int(data.get('quantity') or 0)
    degree_or_offset = float(data.get('offset_deg') or 0)
    factor = float(data.get('factor') or 1.5)
    dtype = data.get('duct_type')

    area = 0
    if dtype == 'elb':
        area = (2 * (w1 / 1000 + h1 / 1000)) * (h1 / 1000) / 2 + (length_or_radius / 1000) * (math.pi * (degree_or_offset / 180)) * quantity * factor
    elif dtype == 'vanes':
        area = w1 / 1000 * (2 * math.pi * (w1 / 1000) / 2) / 4 * quantity
    elif dtype == 'shoe':
        area = (w1 / 1000 + h1 / 1000) * 2 * (length_or_radius / 1000) * quantity * factor
    elif dtype == 'offset':
        area = (w1 / 1000 + h1 / 1000 + w2 / 1000 + h2 / 1000) * (length_or_radius / 1000 + degree_or_offset / 1000) * quantity * factor
    elif dtype == 'dm':
        area = (w1 / 1000 + h1 / 1000) * quantity
    elif dtype == 'red':
        area = (w1 / 1000 + w2 / 1000 + h2 / 1000) * (length_or_radius / 1000) * quantity * factor
    elif dtype == 'st':
        area = 2 * (w1 / 1000 + h1 / 1000) * (length_or_radius / 1000) * quantity

    return round(area, 3)

def calculate_gauge(w1, h1):
    max_dim = max(w1, h1)
    if max_dim <= 751:
        return '24g'
    elif max_dim <= 1201:
        return '22g'
    elif max_dim <= 1800:
        return '20g'
    else:
        return '18g'

def calculate_accessories(gauge, qty, w1, w2, h1, h2, dtype):
    nuts_bolts = qty * 4
    gasket = ((w1 + w2 + h1 + h2) / 1000) * qty
    cleat_map = {
        '24g': qty * 4,
        '22g': qty * 8,
        '20g': qty * 10,
        '18g': qty * 12,
    }
    cleat = cleat_map.get(gauge, 0)
    corner_pieces = 0 if dtype == 'dm' else 8
    return nuts_bolts, cleat, gasket, corner_pieces

@app.route('/')
def index():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM projects")
    projects = cur.fetchall()
    cur.close()
    return render_template('project_list.html', projects=projects)

@app.route('/project', methods=['POST'])
def add_project():
    data = request.form
    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO projects (project_name, enquiry_no, company_name, gst_no, office_contact, site_contact, site_engineer, location, floors, units)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        data['project_name'], data['enquiry_no'], data['company_name'], data['gst_no'],
        data['office_contact'], data['site_contact'], data['site_engineer'],
        data['location'], data['floors'], data['units']
    ))
    mysql.connection.commit()
    project_id = cur.lastrowid
    cur.close()
    return redirect(f'/project/{project_id}')

@app.route('/project/<int:project_id>')
def view_project(project_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
    project = cur.fetchone()

    cur.execute("SELECT * FROM ducts WHERE project_id = %s", (project_id,))
    ducts = cur.fetchall()

    totals = {
        'quantity': 0, 'area': 0.0, '24g': 0.0, '22g': 0.0, '20g': 0.0, '18g': 0.0,
        'nuts': 0, 'cleat': 0, 'gasket': 0.0, 'corner': 0
    }
    for d in ducts:
        totals['quantity'] += d[10]
        totals['area'] += d[13]
        totals['24g'] += d[14]
        totals['22g'] += d[15]
        totals['20g'] += d[16]
        totals['18g'] += d[17]
        totals['nuts'] += d[18]
        totals['cleat'] += d[19]
        totals['gasket'] += d[20]
        totals['corner'] += d[21]

    cur.close()
    return render_template('duct_entry.html', project=project, ducts=ducts, totals=totals)

@app.route('/duct', methods=['POST'])
def add_or_update_duct():
    data = request.get_json()
    duct_id = data.get('duct_id')
    project_id = int(data['project_id'])
    w1 = float(data.get('w1') or 0)
    h1 = float(data.get('h1') or 0)

    gauge = calculate_gauge(w1, h1)
    area = calculate_area(data)
    nuts_bolts, cleat, gasket, corner_pieces = calculate_accessories(
        gauge, int(data['quantity']), w1, float(data.get('w2') or 0),
        h1, float(data.get('h2') or 0), data['duct_type'])

    g_values = {
        '24g': area if gauge == '24g' else 0,
        '22g': area if gauge == '22g' else 0,
        '20g': area if gauge == '20g' else 0,
        '18g': area if gauge == '18g' else 0,
    }

    cur = mysql.connection.cursor()
    if duct_id:
        cur.execute("""
            UPDATE ducts SET duct_no=%s, duct_type=%s, w1=%s, h1=%s, w2=%s, h2=%s,
            length=%s, radius=%s, quantity=%s, offset_deg=%s, gauge=%s, area=%s,
            g24=%s, g22=%s, g20=%s, g18=%s, nuts_bolts=%s, cleat=%s, gasket=%s, corner_pieces=%s
            WHERE id=%s
        """, (
            data['duct_no'], data['duct_type'], w1, h1,
            float(data.get('w2') or 0), float(data.get('h2') or 0),
            float(data.get('length_or_radius') or 0), float(data.get('length_or_radius') or 0),
            int(data['quantity']), float(data.get('offset_deg') or 0),
            gauge, area, g_values['24g'], g_values['22g'], g_values['20g'], g_values['18g'],
            nuts_bolts, cleat, gasket, corner_pieces, int(duct_id)
        ))
    else:
        cur.execute("""
            INSERT INTO ducts (project_id, duct_no, duct_type, w1, h1, w2, h2, length, radius,
            quantity, offset_deg, gauge, area, g24, g22, g20, g18, nuts_bolts, cleat, gasket, corner_pieces)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            project_id, data['duct_no'], data['duct_type'], w1, h1, float(data.get('w2') or 0), float(data.get('h2') or 0),
            float(data.get('length_or_radius') or 0), float(data.get('length_or_radius') or 0),
            int(data['quantity']), float(data.get('offset_deg') or 0), gauge, area,
            g_values['24g'], g_values['22g'], g_values['20g'], g_values['18g'],
            nuts_bolts, cleat, gasket, corner_pieces
        ))
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': 'Duct entry saved successfully'})

@app.route('/duct/<int:duct_id>/edit')
def edit_duct(duct_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM ducts WHERE id = %s", (duct_id,))
    duct = cur.fetchone()
    cur.close()
    keys = ['id', 'project_id', 'duct_no', 'duct_type', 'w1', 'h1', 'w2', 'h2',
            'length_or_radius', 'length_or_radius', 'quantity', 'offset_deg']
    return jsonify(dict(zip(keys, duct[:12])))

@app.route('/duct/<int:duct_id>/delete')
def delete_duct(duct_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM ducts WHERE id = %s", (duct_id,))
    mysql.connection.commit()
    cur.close()
    return redirect(request.referrer or '/')

@app.route('/export_excel/<int:project_id>')
def export_excel(project_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
    project = cur.fetchone()

    cur.execute("SELECT * FROM ducts WHERE project_id = %s", (project_id,))
    ducts = cur.fetchall()
    cur.close()

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet("Duct Data")
    bold = workbook.add_format({'bold': True})

    worksheet.write('A1', 'Project Details', bold)
    worksheet.write_row('A2', ['Project Name', 'Enquiry No', 'Company', 'GST No', 'Office Contact',
                               'Site Contact', 'Engineer', 'Location', 'Floors', 'Units'], bold)
    worksheet.write_row('A3', list(project[1:]))

    start_row = 5
    headers = ['Duct No', 'Type', 'W1', 'H1', 'W2', 'H2', 'Length', 'Radius', 'Qty',
               'Deg', 'Gauge', 'Area', '24g', '22g', '20g', '18g',
               'Nuts', 'Cleat', 'Gasket', 'Corner']
    worksheet.write_row(start_row, 0, headers, bold)

    for i, duct in enumerate(ducts):
        worksheet.write_row(start_row + 1 + i, 0, duct[2:22])

    workbook.close()
    output.seek(0)

    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='duct_export.xlsx')

@app.route('/export_pdf/<int:project_id>')
def export_pdf(project_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
    project = cur.fetchone()

    cur.execute("SELECT * FROM ducts WHERE project_id = %s", (project_id,))
    ducts = cur.fetchall()
    cur.close()

    html = render_template('pdf_template.html', project=project, ducts=ducts)
    result = io.BytesIO()
    pisa.CreatePDF(html.encode('utf-8'), dest=result)
    result.seek(0)

    return send_file(result, mimetype='application/pdf',
                     as_attachment=True, download_name='duct_export.pdf')

@app.route('/submit/<int:project_id>', methods=['POST'])
def submit_project(project_id):
    return f"Project {project_id} submitted!"

if __name__ == '__main__':
    app.run(debug=True)
