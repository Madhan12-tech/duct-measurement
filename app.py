from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os
from datetime import datetime

app = Flask(_name_)
app.secret_key = 'secretkey'

# ✅ Create DB and table if not exist
def init_db():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute('''
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

# ✅ Home page route
@app.route('/')
def home():
    return render_template('home.html')

# ✅ Save project POST route with error handling
@app.route('/save_project', methods=['POST'])
def save_project():
    try:
        project_name = request.form['project_name']
        enquiry_no = request.form['enquiry_no']
        office_no = request.form['office_no']
        site_engineer = request.form['site_engineer']
        site_contact = request.form['site_contact']
        location = request.form['location']
        timestamp = datetime.now()

        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO projects (project_name, enquiry_no, office_no, site_engineer, site_contact, location, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (project_name, enquiry_no, office_no, site_engineer, site_contact, location, timestamp))
        conn.commit()
        conn.close()

        flash('Project saved successfully!')
        return redirect(url_for('duct_entry'))

    except Exception as e:
        return f"<h3 style='color:red;'>Internal Error:</h3><p>{e}</p>"

# ✅ Duct entry page
@app.route('/duct-entry')
def duct_entry():
    return render_template('duct_entry.html')

# ✅ Only run init_db and app locally
if _name_ == '_main_':
    init_db()
    app.run(debug=True)
