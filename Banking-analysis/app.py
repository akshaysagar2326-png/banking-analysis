import os
import pandas as pd
import sqlite3
import re
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'fintech_rupee_2026'

# --- FIXED PATH LOGIC ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

# Ensure the directory exists immediately on startup
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, email TEXT, phone TEXT, password TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- Helper Functions ---
def normalize_columns(df):
    df.columns = [re.sub(r'\s+', '_', col.strip().lower()) for col in df.columns]
    return df

def find_columns(df):
    cols = df.columns
    mapping = {}
    for col in cols:
        if 'loan' in col: mapping['loan'] = col
        if 'deposit' in col: mapping['deposit'] = col
        if 'balance' in col or 'acc' in col: mapping['balance'] = col
        if 'date' in col: mapping['date'] = col
    return mapping

# --- Routes ---
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = request.form
        hashed_pw = generate_password_hash(user['password'], method='pbkdf2:sha256')
        try:
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("INSERT INTO users (username, email, phone, password) VALUES (?,?,?,?)",
                      (user['username'], user['email'], user['phone'], hashed_pw))
            conn.commit()
            conn.close()
            flash("Registration Successful!", "success")
            return redirect(url_for('login'))
        except:
            flash("Registration failed.", "danger")
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email = ?", (request.form['email'],))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user[4], request.form['password']):
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('dashboard'))
        flash("Invalid Credentials", "danger")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'])

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    # TRIPLE CHECK: Create folder right before saving to prevent FileNotFoundError
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
        
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        file.save(filepath)
        session['filepath'] = filepath
        session.modified = True
        return jsonify({'message': 'Uploaded', 'filename': filename})
    except Exception as e:
        return jsonify({'error': f"Save failed: {str(e)}"}), 500

@app.route('/analyze', methods=['POST'])
def analyze():
    path = session.get('filepath')
    if not path or not os.path.exists(path):
        return jsonify({'error': 'File not found on server. Please upload again.'}), 400
    
    try:
        df = pd.read_csv(path)
        df = normalize_columns(df)
        m = find_columns(df)
        
        required = ['loan', 'deposit', 'balance', 'date']
        if not all(k in m for k in required):
            return jsonify({'error': 'CSV missing required columns (Loan, Deposit, Balance, Date)'}), 400

        df[m['date']] = pd.to_datetime(df[m['date']], errors='coerce')
        df = df.dropna(subset=[m['date']])

        start, end = request.json.get('start_date'), request.json.get('end_date')
        if start and end:
            df = df[(df[m['date']] >= start) & (df[m['date']] <= end)]
        
        if df.empty: return jsonify({'error': 'No data in this date range'}), 400

        return jsonify({
            'metrics': {
                'total_loans': float(df[m['loan']].sum()),
                'total_deposits': float(df[m['deposit']].sum()),
                'avg_balance': float(df[m['balance']].mean())
            },
            'segments': [
                len(df[df[m['balance']] < 50000]),
                len(df[(df[m['balance']] >= 50000) & (df[m['balance']] <= 150000)]),
                len(df[df[m['balance']] > 150000])
            ]
        })
    except Exception as e:
        return jsonify({'error': f'Analysis Error: {str(e)}'}), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)