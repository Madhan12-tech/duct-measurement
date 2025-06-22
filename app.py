from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'secretkey'

# Create SQLite DB if not exists
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

@app.route('/duct-entry')
def duct_entry():
    return render_template('duct_entry.html')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
