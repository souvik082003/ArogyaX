"""
ArogyaX — Hospital Management System
Backend: MongoDB Atlas (PyMongo) + Google Gemini AI + Flask-Bcrypt
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from flask_mail import Mail, Message
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from bson.objectid import ObjectId
import random, string, os, csv, io
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from dotenv import load_dotenv
load_dotenv(override=True)
from io import BytesIO
from functools import wraps
from datetime import datetime

# ── ML + AI imports ──────────────────────────────────────────
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split

# TensorFlow (optional — graceful fallback if not installed)
try:
    from tensorflow.keras.preprocessing import image as keras_image
    import tensorflow as tf
    TF_AVAILABLE = True
except Exception:
    TF_AVAILABLE = False

# Google Gemini AI (new SDK)
try:
    from google import genai as google_genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except Exception:
    GEMINI_AVAILABLE = False

# PDF generation
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

# ── Load environment ───────────────────────────────────────────
load_dotenv()

# ── Flask app ──────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'manipal-sevak-default-secret-2024')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'profile_photos')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# ── Flask-Bcrypt ───────────────────────────────────────────────
bcrypt = Bcrypt(app)

# ── Mail ───────────────────────────────────────────────────────
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 465))
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')
mail = Mail(app)

# ── MongoDB Atlas ──────────────────────────────────────────────
MONGO_URI = os.getenv('MONGO_URI', '')
mongo_client = None
db = None
users_col = None
appointments_col = None

def connect_mongo():
    global mongo_client, db, users_col, appointments_col
    try:
        import certifi
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, tlsCAFile=certifi.where())
        mongo_client.server_info()  # triggers connection test
        db = mongo_client['manipal_sevak']
        users_col = db['users']
        appointments_col = db['appointments']
        # Create unique index on username
        users_col.create_index('username', unique=True)
        print("✅ MongoDB Atlas connected successfully.")
    except Exception as e:
        print(f"⚠️  MongoDB connection failed: {e}")
        print("   Running in NO-DB mode (demo only). Fill MONGO_URI in .env to enable.")

connect_mongo()

# ── Gemini AI ──────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
gemini_client = None
gemini_model = None

if GEMINI_AVAILABLE and GEMINI_API_KEY and not GEMINI_API_KEY.startswith('AIzaSyYOUR'):
    try:
        import certifi
        gemini_client = google_genai.Client(api_key=GEMINI_API_KEY)
        gemini_model = 'gemini-2.5-flash'
        print("✅ Gemini AI connected successfully.")
    except Exception as e:
        print(f"⚠️  Gemini AI init failed: {e}")
else:
    print("ℹ️  Gemini AI not configured. Add GEMINI_API_KEY to .env")

# ── ML Disease Prediction Model ────────────────────────────────
try:
    data = pd.read_csv(os.path.join("static", "Data", "Training.csv"))
    df = pd.DataFrame(data)
    cols = df.columns[:-1]
    x = df[cols]
    y = df['prognosis']
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.33, random_state=42)
    dt = DecisionTreeClassifier()
    dt.fit(x_train, y_train)
    symptoms = df.columns.values[:-1]
    dictionary = dict(zip(symptoms, range(len(symptoms))))
    ML_MODEL_AVAILABLE = True
    print("✅ Disease prediction ML model loaded.")
except Exception as e:
    print(f"⚠️  ML model load failed: {e}")
    ML_MODEL_AVAILABLE = False
    symptoms = []
    dictionary = {}

with open('static/Data/Testing.csv', newline='') as f:
    reader = csv.reader(f)
    symptoms_list = next(reader)[:-1]

# ── Helpers ────────────────────────────────────────────────────

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_random_string(length=10):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))

def send_mail_safe(subject, recipient, body):
    try:
        msg = Message(subject, recipients=[recipient])
        msg.body = body
        mail.send(msg)
    except Exception as e:
        print(f"Mail error (non-fatal): {e}")

# ── Auth decorators ────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Access denied. Admin only.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

def doctor_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'doctor':
            flash('Access denied. Doctors only.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

# ── MongoDB user helpers ───────────────────────────────────────

def get_user_by_id(user_id):
    if users_col is None:
        return None
    try:
        return users_col.find_one({'_id': ObjectId(user_id)})
    except Exception:
        return None

def get_current_user():
    if 'user_id' not in session:
        return None
    return get_user_by_id(session['user_id'])

# ============================================================
# SEED DEMO DATA
# ============================================================

@app.route('/seed-demo')
def seed_demo():
    if users_col is None:
        flash('MongoDB not connected. Fill MONGO_URI in .env first.', 'error')
        return redirect(url_for('admin_login'))

    # Admin
    if not users_col.find_one({'username': 'admin'}):
        users_col.insert_one({
            'username': 'admin', 'email': 'admin@arogyax.com',
            'password': bcrypt.generate_password_hash('admin123').decode('utf-8'),
            'role': 'admin', 'phone': '+91 9000000001', 'is_active': True,
            'created_at': datetime.utcnow()
        })

    # Demo doctors
    doctors = [
        {'username': 'dr_anika', 'email': 'anika@arogyax.com', 'type_of_doctor': 'Cardiologist',
         'bio': 'Dr. Anika Sharma is a senior cardiologist with over 12 years of experience in diagnosing and treating complex heart conditions. She specializes in interventional cardiology and heart failure management.',
         'years_of_experience': 12, 'consultation_fee': 800,
         'availability': 'Mon, Wed, Fri — 10:00 AM to 5:00 PM', 'phone': '+91 9000000002'},
        {'username': 'dr_rahul', 'email': 'rahul@arogyax.com', 'type_of_doctor': 'Neurologist',
         'bio': 'Dr. Rahul Mehta is a leading neurologist specializing in epilepsy, stroke management, and neurodegenerative diseases. He has published 30+ research papers in leading medical journals.',
         'years_of_experience': 15, 'consultation_fee': 1000,
         'availability': 'Tue, Thu, Sat — 9:00 AM to 3:00 PM', 'phone': '+91 9000000003'},
        {'username': 'dr_priya', 'email': 'priya@arogyax.com', 'type_of_doctor': 'Ophthalmologist',
         'bio': 'Dr. Priya Nair is an expert ophthalmologist specializing in cataract surgery, retinal disorders, and LASIK procedures. She has performed over 5,000 successful eye surgeries.',
         'years_of_experience': 10, 'consultation_fee': 700,
         'availability': 'Mon to Fri — 11:00 AM to 6:00 PM', 'phone': '+91 9000000004'},
        {'username': 'dr_sandeep', 'email': 'sandeep@arogyax.com', 'type_of_doctor': 'Pulmonologist',
         'bio': 'Dr. Sandeep Kaur specializes in respiratory medicine and has extensive experience treating asthma, COPD, pneumonia, and lung cancer. He runs a dedicated pulmonary rehabilitation program.',
         'years_of_experience': 8, 'consultation_fee': 600,
         'availability': 'Mon, Tue, Thu — 12:00 PM to 7:00 PM', 'phone': '+91 9000000005'},
    ]
    for d in doctors:
        if not users_col.find_one({'username': d['username']}):
            d.update({
                'password': bcrypt.generate_password_hash('doctor123').decode('utf-8'),
                'role': 'doctor', 'profile_photo': None, 'is_active': True,
                'created_at': datetime.utcnow()
            })
            users_col.insert_one(d)

    # Demo patients
    patients = [
        {'username': 'john_patient', 'email': 'john@example.com', 'phone': '+91 9111111111'},
        {'username': 'priti_patient', 'email': 'priti@example.com', 'phone': '+91 9222222222'},
        {'username': 'aman_patient', 'email': 'aman@example.com', 'phone': '+91 9333333333'},
    ]
    patient_ids = {}
    for p in patients:
        existing = users_col.find_one({'username': p['username']})
        if not existing:
            result = users_col.insert_one({
                **p,
                'password': bcrypt.generate_password_hash('patient123').decode('utf-8'),
                'role': 'patient', 'is_active': True,
                'created_at': datetime.utcnow()
            })
            patient_ids[p['username']] = result.inserted_id
        else:
            patient_ids[p['username']] = existing['_id']

    # Demo appointments
    if appointments_col.count_documents({}) == 0:
        demo_appts = [
            {'name': 'John Doe', 'age': 35, 'blood_group': 'O+', 'time_slot': '10:00 AM - 11:00 AM',
             'phone_number': '+91 9111111111', 'email': 'john@example.com',
             'type_of_doctor': 'Cardiologist', 'status': 'Approved',
             'user_id': patient_ids.get('john_patient'), 'created_at': datetime.utcnow()},
            {'name': 'Priti Sharma', 'age': 28, 'blood_group': 'B+', 'time_slot': '11:00 AM - 12:00 PM',
             'phone_number': '+91 9222222222', 'email': 'priti@example.com',
             'type_of_doctor': 'Ophthalmologist', 'status': 'Pending',
             'user_id': patient_ids.get('priti_patient'), 'created_at': datetime.utcnow()},
            {'name': 'Aman Rao', 'age': 42, 'blood_group': 'A+', 'time_slot': '02:00 PM - 03:00 PM',
             'phone_number': '+91 9333333333', 'email': 'aman@example.com',
             'type_of_doctor': 'Neurologist', 'status': 'Prescribed',
             'user_id': patient_ids.get('aman_patient'), 'prescription_file': None,
             'created_at': datetime.utcnow()},
            {'name': 'John Doe', 'age': 35, 'blood_group': 'O+', 'time_slot': '03:00 PM - 04:00 PM',
             'phone_number': '+91 9111111111', 'email': 'john@example.com',
             'type_of_doctor': 'Pulmonologist', 'status': 'Pending',
             'user_id': patient_ids.get('john_patient'), 'created_at': datetime.utcnow()},
        ]
        appointments_col.insert_many(demo_appts)

    flash('✅ Demo data seeded! Login: admin/admin123 | Doctors: dr_anika/doctor123 | Patients: john_patient/patient123', 'success')
    return redirect(url_for('admin_login'))

# ============================================================
# ADMIN ROUTES
# ============================================================

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if users_col is None:
            flash('MongoDB not connected. Fill MONGO_URI in .env', 'error')
            return render_template('admin-login.html')
        user = users_col.find_one({'username': username, 'role': 'admin'})
        if user and bcrypt.check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        flash('Invalid admin credentials.', 'error')
    return render_template('admin-login.html')

@app.route('/admin-dashboard')
@admin_required
def admin_dashboard():
    admin_user = get_current_user()
    total_doctors = users_col.count_documents({'role': 'doctor'})
    total_patients = users_col.count_documents({'role': 'patient'})
    total_users = total_doctors + total_patients
    total_appointments = appointments_col.count_documents({})
    pending = appointments_col.count_documents({'status': 'Pending'})
    approved = appointments_col.count_documents({'status': 'Approved'})
    prescribed = appointments_col.count_documents({'status': 'Prescribed'})
    all_doctors = list(users_col.find({'role': 'doctor'}))
    all_patients = list(users_col.find({'role': 'patient'}))
    all_appointments = list(appointments_col.find().sort('_id', -1))
    # Convert ObjectId to string for templates
    for doc in all_doctors + all_patients:
        doc['_id'] = str(doc['_id'])
        doc['appointments_count'] = appointments_col.count_documents({'user_id': ObjectId(doc['_id'])})
    for appt in all_appointments:
        appt['_id'] = str(appt['_id'])
    return render_template('admin.html',
        admin_user=admin_user, total_users=total_users,
        total_doctors=total_doctors, total_patients=total_patients,
        total_appointments=total_appointments, pending=pending,
        approved=approved, prescribed=prescribed,
        all_doctors=all_doctors, all_patients=all_patients,
        all_appointments=all_appointments
    )

@app.route('/admin/delete-user/<user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    user = users_col.find_one({'_id': ObjectId(user_id)})
    appointments_col.delete_many({'user_id': ObjectId(user_id)})
    users_col.delete_one({'_id': ObjectId(user_id)})
    flash(f"User {user.get('username','?')} deleted.", 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/toggle-user/<user_id>', methods=['POST'])
@admin_required
def admin_toggle_user(user_id):
    user = users_col.find_one({'_id': ObjectId(user_id)})
    new_status = not user.get('is_active', True)
    users_col.update_one({'_id': ObjectId(user_id)}, {'$set': {'is_active': new_status}})
    flash(f"User {'activated' if new_status else 'deactivated'}.", 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

# ============================================================
# DOCTOR PROFILE EDIT
# ============================================================

@app.route('/doctor-profile-edit', methods=['GET', 'POST'])
@login_required
def doctor_profile_edit():
    user = get_current_user()
    if not user or user.get('role') != 'doctor':
        return redirect(url_for('index'))

    if request.method == 'POST':
        updates = {
            'bio': request.form.get('bio', ''),
            'years_of_experience': int(request.form.get('years_of_experience', 0) or 0),
            'consultation_fee': int(request.form.get('consultation_fee', 0) or 0),
            'availability': request.form.get('availability', ''),
            'phone': request.form.get('phone', ''),
            'email': request.form.get('email', user['email']),
        }
        if request.form.get('type_of_doctor'):
            updates['type_of_doctor'] = request.form.get('type_of_doctor')

        # Profile photo upload
        if 'profile_photo' in request.files:
            file = request.files['profile_photo']
            if file and file.filename and allowed_file(file.filename):
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                filename = secure_filename(f"doctor_{user['_id']}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                updates['profile_photo'] = f"uploads/profile_photos/{filename}"

        users_col.update_one({'_id': user['_id']}, {'$set': updates})
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('doctor_profile_edit'))

    # Re-fetch after possible update
    user = get_current_user()
    user_str = dict(user)
    user_str['_id'] = str(user['_id'])
    return render_template('doctor-profile-edit.html', user=user_str, doctor=user_str, username=user['username'])

# ============================================================
# DOCTORS DIRECTORY
# ============================================================

@app.route('/doctors')
def doctors_directory():
    username = None
    if 'user_id' in session:
        u = get_current_user()
        if u:
            username = u['username']
    specialization = request.args.get('specialization', '')
    query = {'role': 'doctor', 'is_active': True}
    if specialization:
        query['type_of_doctor'] = specialization
    doctors = list(users_col.find(query)) if users_col is not None else []
    for d in doctors:
        d['_id'] = str(d['_id'])
    specs_raw = users_col.distinct('type_of_doctor', {'role': 'doctor'}) if users_col is not None else []
    specializations = [s for s in specs_raw if s]
    return render_template('doctors.html', doctors=doctors, username=username,
                           specializations=specializations, current_specialization=specialization)

# ============================================================
# AUTH ROUTES
# ============================================================

@app.route('/', methods=['GET', 'POST'])
def index():
    username = None
    if 'user_id' in session:
        user = get_current_user()
        if user:
            username = user['username']
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            if user['role'] == 'doctor':
                appts = list(appointments_col.find({'type_of_doctor': user.get('type_of_doctor')}))
                for a in appts:
                    a['_id'] = str(a['_id'])
                user_str = dict(user)
                user_str['_id'] = str(user['_id'])
                return render_template('doctor-dashboard.html', username=username, appointments=appts, doctor=user_str)
            else:
                user_appts = list(appointments_col.find({'user_id': user['_id']}))
                for a in user_appts:
                    a['_id'] = str(a['_id'])
                return render_template('patient-dashboard.html', username=username, user_appointments=user_appts)
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if users_col is None:
            flash('MongoDB not connected. Fill MONGO_URI in .env', 'error')
            return render_template('login.html')
        user = users_col.find_one({'username': username})
        if user:
            if user.get('role') == 'admin':
                flash('Please use the Admin Login portal.', 'error')
                return redirect(url_for('admin_login'))
            # Support both hashed and legacy plain-text passwords
            try:
                pwd_ok = bcrypt.check_password_hash(user['password'], password)
            except Exception:
                pwd_ok = (user['password'] == password)  # legacy fallback
            if pwd_ok:
                session['user_id'] = str(user['_id'])
                session['role'] = user.get('role', 'patient')
                return redirect(url_for('index'))
        flash('Wrong username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/patient-register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        if users_col is None:
            flash('MongoDB not connected.', 'error')
            return render_template('patient-register.html')
        try:
            hashed = bcrypt.generate_password_hash(password).decode('utf-8')
            result = users_col.insert_one({
                'username': username, 'email': email, 'password': hashed,
                'role': 'patient', 'is_active': True, 'created_at': datetime.utcnow()
            })
            session['user_id'] = str(result.inserted_id)
            session['role'] = 'patient'
            return redirect(url_for('index'))
        except DuplicateKeyError:
            flash('Username already taken. Choose another.', 'error')
    return render_template('patient-register.html')

@app.route('/doctor-register', methods=['GET', 'POST'])
def doctor_register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        type_of_doctor = request.form['type_of_doctor']
        try:
            hashed = bcrypt.generate_password_hash(password).decode('utf-8')
            result = users_col.insert_one({
                'username': username, 'email': email, 'password': hashed,
                'role': 'doctor', 'type_of_doctor': type_of_doctor,
                'is_active': True, 'created_at': datetime.utcnow()
            })
            session['user_id'] = str(result.inserted_id)
            session['role'] = 'doctor'
            return redirect(url_for('index'))
        except DuplicateKeyError:
            flash('Username already taken. Choose another.', 'error')
    return render_template('doctor-register.html')

@app.route('/profile')
@login_required
def profile():
    user = get_current_user()
    username = user['username']
    email = user['email']
    user_appts = list(appointments_col.find({'user_id': user['_id']}))
    for a in user_appts:
        a['_id'] = str(a['_id'])
    return render_template('patient-profile.html', username=username, Email=email, user_appointments=user_appts)

# ============================================================
# APPOINTMENTS
# ============================================================

@app.route('/book-appointment', methods=['GET', 'POST'])
@login_required
def book_appointment():
    user = get_current_user()
    username = user['username']
    doctors = list(users_col.find({'role': 'doctor', 'is_active': True})) if users_col is not None else []
    for d in doctors:
        d['_id'] = str(d['_id'])

    if request.method == 'POST':
        appt_data = {
            'name': request.form['name'],
            'age': int(request.form['age']),
            'blood_group': request.form['blood_group'],
            'time_slot': request.form['time_slot'],
            'phone_number': request.form['phone_number'],
            'email': request.form['email'],
            'type_of_doctor': request.form['type_of_doctor'],
            'status': 'Pending',
            'user_id': user['_id'],
            'created_at': datetime.utcnow()
        }
        appointments_col.insert_one(appt_data)

        doctor_obj = users_col.find_one({'type_of_doctor': appt_data['type_of_doctor'], 'role': 'doctor'})
        if doctor_obj:
            send_mail_safe('New Appointment Request', doctor_obj['email'],
                f"Hello Dr. {doctor_obj['username']},\n\nNew appointment from {appt_data['name']}. Please log in to approve.")

        flash('Appointment booked successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('book-appointment.html', doctors=doctors, username=username)

@app.route('/approve-appointment/<appointment_id>')
@login_required
def approve_appointment(appointment_id):
    doctor = get_current_user()
    appt = appointments_col.find_one({'_id': ObjectId(appointment_id)})
    if appt and appt.get('type_of_doctor') == doctor.get('type_of_doctor'):
        appointments_col.update_one({'_id': ObjectId(appointment_id)}, {'$set': {'status': 'Approved'}})
        send_mail_safe('Appointment Approved', appt['email'],
            f"Hello {appt['name']},\n\nYour appointment with Dr. {doctor['username']} has been approved!")
    return redirect(url_for('index'))

@app.route('/doctor-patients')
@login_required
def doctor_patients():
    user = get_current_user()
    if user.get('role') != 'doctor':
        return redirect(url_for('index'))
    username = user['username']
    appts = list(appointments_col.find({'type_of_doctor': user.get('type_of_doctor')}))
    for a in appts:
        a['_id'] = str(a['_id'])
    user_str = dict(user)
    user_str['_id'] = str(user['_id'])
    return render_template('doctor-patients.html', doctor=user_str, appointments=appts, username=username, file_list=[])

@app.route('/prescribe-medicine/<appointment_id>', methods=['GET', 'POST'])
@login_required
def prescribe_medicine(appointment_id):
    doctor = get_current_user()
    appt = appointments_col.find_one({'_id': ObjectId(appointment_id)})
    available_medicines = [
        "Paracetamol 500mg", "Ibuprofen 400mg", "Amoxicillin 500mg",
        "Omeprazole 20mg", "Cetirizine 10mg", "Metformin 500mg",
        "Atorvastatin 10mg", "Amlodipine 5mg", "Azithromycin 500mg",
        "Vitamin D3 60000IU"
    ]
    if request.method == 'POST':
        selected_medicines = request.form.getlist('medicines[]')
        buffer = BytesIO()
        styles = getSampleStyleSheet()
        
        # Define styles
        title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=24, spaceAfter=6, textColor=colors.HexColor('#16a34a'), alignment=1)
        subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#6b7280'), alignment=1, spaceAfter=20)
        normal_style = styles['Normal']
        normal_style.fontSize = 11
        normal_style.leading = 14
        
        content = []
        
        # Header (Clinic Info)
        content.append(Paragraph("<b>ArogyaX Clinic</b>", title_style))
        content.append(Paragraph("123 Health Avenue, Medical District, Cityville • Ph: +91 800-123-4567<br/>Email: contact@arogyax.com • Web: www.arogyax.com", subtitle_style))
        content.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e5e7eb'), spaceBefore=0, spaceAfter=20))
        
        # Patient Details Table
        patient_data = [
            [Paragraph("<b>Patient Name:</b>", normal_style), Paragraph(appt['name'], normal_style), Paragraph("<b>Date:</b>", normal_style), Paragraph(datetime.utcnow().strftime('%d %b %Y'), normal_style)],
            [Paragraph("<b>Age:</b>", normal_style), Paragraph(str(appt['age']), normal_style), Paragraph("<b>Blood Group:</b>", normal_style), Paragraph(appt['blood_group'], normal_style)],
            [Paragraph("<b>Phone:</b>", normal_style), Paragraph(appt['phone_number'], normal_style), Paragraph("<b>Doctor:</b>", normal_style), Paragraph(f"Dr. {doctor['username']}", normal_style)]
        ]
        patient_table = Table(patient_data, colWidths=[100, 200, 80, 120])
        patient_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9fafb')),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
            ('INNERGRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
        ]))
        content.append(patient_table)
        content.append(Spacer(1, 25))
        
        # Rx Symbol & Medicines
        content.append(Paragraph("<b>Rx</b>", ParagraphStyle('Rx', fontName='Helvetica-Bold', fontSize=22, textColor=colors.HexColor('#16a34a'), spaceAfter=15)))
        
        # Medicines Table
        meds_data = [["Medicine Name", "Dosage / Instructions"]]
        for idx, m in enumerate(selected_medicines):
            meds_data.append([f"{idx+1}. {m}", "As directed by physician"])
            
        meds_table = Table(meds_data, colWidths=[250, 250])
        meds_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16a34a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('PADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')])
        ]))
        content.append(meds_table)
        content.append(Spacer(1, 40))
        
        # Footer / Signature
        signature_data = [
            ["", "_______________________"],
            ["", f"Dr. {doctor['username']}"],
            ["", f"{doctor.get('type_of_doctor', 'Physician')}"]
        ]
        sig_table = Table(signature_data, colWidths=[300, 200])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('FONTNAME', (1, 1), (1, 1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (1, 1), (1, -1), colors.HexColor('#374151')),
        ]))
        content.append(sig_table)
        
        # Generate PDF
        pdf = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        pdf.build(content)

        os.makedirs(os.path.join("static", "prescriptions"), exist_ok=True)
        pdf_filename = f"prescription_{appointment_id}.pdf"
        pdf_filepath = os.path.join("static", "prescriptions", pdf_filename)
        buffer.seek(0)
        with open(pdf_filepath, 'wb') as f:
            f.write(buffer.read())

        appointments_col.update_one({'_id': ObjectId(appointment_id)},
            {'$set': {'status': 'Prescribed', 'prescription_file': pdf_filepath}})
        return redirect(url_for('doctor_patients'))

    appt_str = dict(appt)
    appt_str['_id'] = str(appt['_id'])
    return render_template('prescribe-medicine.html', appointment=appt_str, available_medicines=available_medicines)

@app.route('/view-prescription/<appointment_id>')
@login_required
def view_prescription(appointment_id):
    doctor = get_current_user()
    appt = appointments_col.find_one({'_id': ObjectId(appointment_id)})
    if appt and appt.get('type_of_doctor') == doctor.get('type_of_doctor') and appt.get('status') == 'Prescribed':
        filepath = appt.get('prescription_file')
        if filepath and os.path.exists(filepath):
            return send_file(filepath, as_attachment=True)
        else:
            flash('Prescription file not found.', 'error')
    return redirect(url_for('doctor_patients'))

@app.route('/view-prescription-patient/<appointment_id>')
@login_required
def view_prescription_patient(appointment_id):
    user = get_current_user()
    appt = appointments_col.find_one({'_id': ObjectId(appointment_id)})
    if appt and str(appt.get('user_id')) == str(user['_id']) and appt.get('status') == 'Prescribed':
        filepath = appt.get('prescription_file')
        if filepath and os.path.exists(filepath):
            return send_file(filepath, as_attachment=True)
        else:
            flash('Prescription file not found.', 'error')
    return redirect(url_for('index'))

# ============================================================
# AI — DISEASE PREDICTION
# ============================================================

def predict_disease_ml(selected_symptoms):
    """Local ML model prediction."""
    user_input_label = [0] * 132
    for s in selected_symptoms:
        if s in dictionary:
            user_input_label[dictionary[s]] = 1
    user_input = np.array(user_input_label).reshape(1, -1)
    disease = dt.predict(user_input)[0]
    confidence = float(np.max(dt.predict_proba(user_input)) * 100)
    return disease, confidence

def get_gemini_disease_explanation(disease, symptoms_list):
    """Call Gemini AI for a plain-language medical explanation."""
    if not gemini_client:
        return None
    try:
        prompt = f"""You are a friendly medical assistant on ArogyaX health platform.
A patient has symptoms: {', '.join(symptoms_list)}.
Our AI system predicted the disease: {disease}.

Please provide:
1. A brief plain-language explanation of {disease} (2-3 sentences)
2. 3-4 important home care tips
3. A clear recommendation to consult a doctor

Keep it simple, warm, and non-alarming. Format with clear headings."""
        response = gemini_client.models.generate_content(
            model=gemini_model,
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"Gemini error: {e}")
        return None

@app.route('/disease_predict', methods=['GET', 'POST'])
@login_required
def disease_predict():
    user = get_current_user()
    username = user['username'] if user else 'Guest'
    role = user.get('role', 'patient') if user else 'patient'
    user_str = dict(user) if user else {}
    if user_str and '_id' in user_str:
        user_str['_id'] = str(user_str['_id'])
    chart_data = {}
    gemini_explanation = None
    disease = None
    confidence_score = None

    if request.method == 'POST' and ML_MODEL_AVAILABLE:
        selected_symptoms = []
        for s in ['Symptom1', 'Symptom2', 'Symptom3', 'Symptom4', 'Symptom5']:
            val = request.form.get(s, '')
            if val and val not in selected_symptoms:
                selected_symptoms.append(val)
        if selected_symptoms:
            disease, confidence_score = predict_disease_ml(selected_symptoms)
            chart_data = {'disease': disease, 'confidence_score': confidence_score}
            # Gemini AI explanation
            gemini_explanation = get_gemini_disease_explanation(disease, selected_symptoms)

    return render_template('disease_predict.html',
        symptoms=symptoms_list, disease=disease, chart_data=chart_data,
        confidence_score=confidence_score, username=username,
        gemini_explanation=gemini_explanation,
        gemini_enabled=gemini_client is not None)

# ============================================================
# AI — SCAN ANALYSIS (Vision API)
# ============================================================

def analyze_scan_with_gemini(image_path, scan_type):
    """Use Gemini Vision to analyze an uploaded medical scan."""
    if not gemini_client:
        return None
    try:
        import PIL.Image
        img = PIL.Image.open(image_path)
        prompts = {
            'brain': "This is a brain MRI scan uploaded to ArogyaX health platform. Analyze this image for educational purposes only. Describe what you observe in simple terms a patient could understand. Note any patterns that could be relevant. Always end with a clear disclaimer that this is not a medical diagnosis and the patient must consult a neurologist.",
            'lung': "This is a chest X-ray uploaded to ArogyaX health platform. Analyze this image for educational purposes only. Describe what you observe — lung fields, bone structure, any notable patterns. Always end with a clear disclaimer that this is not a medical diagnosis and the patient must consult a pulmonologist.",
            'cataract': "This is an eye image uploaded to ArogyaX health platform. Analyze this image for educational purposes only. Describe what you observe about the eye — clarity, any cloudiness, pupil appearance. Always end with a clear disclaimer that this is not a medical diagnosis and the patient must consult an ophthalmologist.",
        }
        prompt = prompts.get(scan_type, "Analyze this medical image for educational purposes. Always end with a disclaimer.")
        response = gemini_client.models.generate_content(
            model=gemini_model,
            contents=[prompt, img]
        )
        return response.text
    except Exception as e:
        print(f"Gemini vision error: {e}")
        return None

@app.route('/braintumor', methods=['GET', 'POST'])
@login_required
def braintumor():
    user = get_current_user()
    username = user['username'] if user else 'Guest'
    role = user.get('role', 'patient') if user else 'patient'
    user_str = dict(user) if user else {}
    if user_str and '_id' in user_str:
        user_str['_id'] = str(user_str['_id'])
    gemini_result = None
    if request.method == 'POST' and 'scan_image' in request.files:
        file = request.files['scan_image']
        if file and allowed_file(file.filename):
            os.makedirs('/tmp/manipal_scans', exist_ok=True)
            filepath = f'/tmp/manipal_scans/{secure_filename(file.filename)}'
            file.save(filepath)
            gemini_result = analyze_scan_with_gemini(filepath, 'brain')
    return render_template('brain-tumor.html', username=username,
                           gemini_result=gemini_result, gemini_enabled=gemini_client is not None)

@app.route('/lung', methods=['GET', 'POST'])
@login_required
def lung():
    user = get_current_user()
    username = user['username'] if user else 'Guest'
    role = user.get('role', 'patient') if user else 'patient'
    user_str = dict(user) if user else {}
    if user_str and '_id' in user_str:
        user_str['_id'] = str(user_str['_id'])
    gemini_result = None
    if request.method == 'POST' and 'scan_image' in request.files:
        file = request.files['scan_image']
        if file and allowed_file(file.filename):
            os.makedirs('/tmp/manipal_scans', exist_ok=True)
            filepath = f'/tmp/manipal_scans/{secure_filename(file.filename)}'
            file.save(filepath)
            gemini_result = analyze_scan_with_gemini(filepath, 'lung')
    return render_template('lung.html', username=username, role=role, user=user_str,
                           gemini_result=gemini_result, gemini_enabled=gemini_client is not None)

@app.route('/cataract', methods=['GET', 'POST'])
@login_required
def cataract():
    user = get_current_user()
    username = user['username'] if user else 'Guest'
    role = user.get('role', 'patient') if user else 'patient'
    user_str = dict(user) if user else {}
    if user_str and '_id' in user_str:
        user_str['_id'] = str(user_str['_id'])
    gemini_result = None
    if request.method == 'POST' and 'scan_image' in request.files:
        file = request.files['scan_image']
        if file and allowed_file(file.filename):
            os.makedirs('/tmp/manipal_scans', exist_ok=True)
            filepath = f'/tmp/manipal_scans/{secure_filename(file.filename)}'
            file.save(filepath)
            gemini_result = analyze_scan_with_gemini(filepath, 'cataract')
    return render_template('cataract.html', username=username, role=role, user=user_str,
                           gemini_result=gemini_result, gemini_enabled=gemini_client is not None)

# ============================================================
# OTHER PAGES
# ============================================================

@app.route('/policy')
def policy():
    return render_template('privacy-policy.html')

@app.route('/videocall')
@login_required
def videocall():
    user = get_current_user()
    return render_template('videocall.html', username=user['username'])

@app.route('/admin')
def admin():
    return redirect(url_for('admin_login'))

@app.route('/Transforming_Healthcare')
def Transforming_Healthcare():
    username = get_current_user()['username'] if 'user_id' in session else None
    return render_template('blog_Transforming Healthcare.html', username=username)

@app.route('/Holistic_Health')
def Holistic_Health():
    username = get_current_user()['username'] if 'user_id' in session else None
    return render_template('blog_Holistic Health.html', username=username)

@app.route('/Nourishing_Body')
def Nourishing_Body():
    username = get_current_user()['username'] if 'user_id' in session else None
    return render_template('blog_Nourishing_Body.html', username=username)

@app.route('/Importance_of_Games')
def Importance_of_Games():
    username = get_current_user()['username'] if 'user_id' in session else None
    return render_template('blog_Importance_of_Games.html', username=username)

# ── API health check ───────────────────────────────────────────
@app.route('/api/health')
def health_check():
    return jsonify({
        'status': 'ok',
        'mongodb': 'connected' if db is not None else 'disconnected',
        'gemini_ai': 'connected' if gemini_client is not None else 'not configured',
        'ml_model': 'loaded' if ML_MODEL_AVAILABLE else 'unavailable',
    })


# ============================================================
# MEDICAL RECORDS VAULT
# ============================================================

@app.route('/vault', methods=['GET', 'POST'])
@login_required
def vault():
    user = get_current_user()
    if not user or user.get('role') != 'patient':
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        if 'record_file' in request.files:
            file = request.files['record_file']
            record_title = request.form.get('title', 'Untitled Record')
            if file and allowed_file(file.filename):
                os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'vault'), exist_ok=True)
                filename = secure_filename(f"vault_{user['_id']}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'vault', filename)
                file.save(filepath)
                
                record_entry = {
                    'title': record_title,
                    'filename': filename,
                    'filepath': f"uploads/profile_photos/vault/{filename}",
                    'uploaded_at': datetime.utcnow()
                }
                users_col.update_one({'_id': user['_id']}, {'$push': {'records': record_entry}})
                flash('Record uploaded successfully to your vault!', 'success')
                return redirect(url_for('vault'))
                
    user = get_current_user() # re-fetch
    user_str = dict(user)
    user_str['_id'] = str(user['_id'])
    
    return render_template('vault.html', user=user_str, username=user['username'], role='patient')

@app.route('/view-records/<patient_id>')
@login_required
def view_records(patient_id):
    doctor = get_current_user()
    if not doctor or doctor.get('role') != 'doctor':
        return redirect(url_for('index'))
        
    patient = get_user_by_id(patient_id)
    if not patient:
        flash('Patient not found.', 'error')
        return redirect(url_for('doctor_patients'))
        
    patient_str = dict(patient)
    patient_str['_id'] = str(patient['_id'])
    
    doctor_str = dict(doctor)
    doctor_str['_id'] = str(doctor['_id'])
    
    return render_template('doctor-view-records.html', patient=patient_str, doctor=doctor_str, username=doctor['username'], role='doctor', user=doctor_str)

# ── Run ────────────────────────────────────────────────────────
if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join("static", "prescriptions"), exist_ok=True)
    app.run(debug=True, port=5001)
