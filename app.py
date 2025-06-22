from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'secretkey'

def init_db():
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    # Projects table
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
    # Duct entries table
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

def calculate_area(width, height, length, factor):
    return round(((2 * (width + height)) * length * factor) / 144, 2)

def calculate_accessories(area):
    return round(area * 0.25, 2)

@app.route('/duct-entry')
def duct_entry():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM duct_entries ORDER BY id DESC")
    entries = cursor.fetchall()
    conn.close()
    return render_template('duct_entry.html', entries=entries)

@app.route('/add_duct', methods=['POST'])
def add_duct():
    form = request.form
    duct_no = form['duct_no']
    duct_type = form['duct_type']
    width = float(form['width'])
    height = float(form['height'])
    length_or_radius = float(form['length_or_radius'])
    quantity = int(form['quantity'])
    gauge = form['gauge']
    factor = float(form['factor']) if form['factor'] else 1.0

    area = calculate_area(width, height, length_or_radius, factor)
    accessories = calculate_accessories(area)

    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO duct_entries 
        (duct_no, duct_type, width, height, length_or_radius, quantity, gauge, factor, area, accessories, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (duct_no, duct_type, width, height, length_or_radius, quantity, gauge, factor, area, accessories, datetime.now()))
    conn.commit()
    conn.close()

    flash('Duct entry added successfully!')
    return redirect(url_for('duct_entry'))
