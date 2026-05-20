from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, jsonify, make_response
import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

from datetime import timedelta, datetime
import uuid
from email_service import send_interview_invite, send_offer_email, send_rejection_email, generate_ics, log_email

# Session stability config
app.config['SECRET_KEY'] = 'super_secret_key_for_session_management'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

@app.before_request
def make_session_permanent():
    session.permanent = True
    print(f"[DEBUG] session content: {dict(session)}")

# Directory for uploads (e.g., resumes, profile pictures)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Target folder for permanent resume storage
RESUME_UPLOAD_FOLDER = os.path.join('static', 'uploads', 'resumes')
os.makedirs(RESUME_UPLOAD_FOLDER, exist_ok=True)
app.config['RESUME_UPLOAD_FOLDER'] = RESUME_UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    """Helper function to create and return a MySQL database connection."""
    db = pymysql.connect(
        host="localhost",
        user="root",
        password="root",
        database="jobportal",
        cursorclass=pymysql.cursors.DictCursor
    )
    return db

# -------------------------------------------------------------
# ROUTES
# -------------------------------------------------------------

@app.route('/')
def home():
    """Home page with hero section, search, dynamic stats, and featured jobs."""
    db = get_db_connection()
    cursor = db.cursor()
    
    # READ: Fetch latest 6 jobs
    cursor.execute("""
        SELECT jobs.*, companies.company_name 
        FROM jobs 
        LEFT JOIN companies ON jobs.company_id = companies.company_id
        ORDER BY jobs.job_id DESC LIMIT 6
    """)
    featured_jobs = cursor.fetchall()
    
    # READ: Dynamic counts from MySQL for dashboard statistics
    cursor.execute("SELECT COUNT(*) as total FROM jobs")
    jobs_count = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM companies")
    companies_count = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM users WHERE role = 'candidate'")
    candidates_count = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM applications WHERE status = 'Offered'")
    hired_count = cursor.fetchone()['total']
    
    cursor.close()
    db.close()
    
    return render_template(
        'index.html', 
        featured_jobs=featured_jobs,
        jobs_count=jobs_count,
        companies_count=companies_count,
        candidates_count=candidates_count,
        hired_count=hired_count
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login route handling both GET (form) and POST (auth)."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            db = get_db_connection()
            cursor = db.cursor()
            
            # READ: Verify user credentials
            cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
            user = cursor.fetchone()
            
            cursor.close()
            db.close()
        except Exception as e:
            print(f"Database error during login: {e}")
            flash('Database connection failed. Please try again later.', 'danger')
            return redirect(url_for('login'))
        
        if user:
            session.permanent = True
            session['user_id'] = user['user_id']
            session['role'] = user['role']
            session['name'] = user['fullname']
            
            # Ensure candidate_profiles record exists if role is candidate
            if user['role'] == 'candidate':
                try:
                    db_check = get_db_connection()
                    cursor_check = db_check.cursor()
                    cursor_check.execute("SELECT profile_id FROM candidate_profiles WHERE user_id = %s", (user['user_id'],))
                    if not cursor_check.fetchone():
                        cursor_check.execute("""
                            INSERT INTO candidate_profiles (user_id, full_name)
                            VALUES (%s, %s)
                        """, (user['user_id'], user['fullname']))
                        db_check.commit()
                        print(f"[DEBUG] Default candidate profile created for logged in user {user['user_id']}")
                    cursor_check.close()
                    db_check.close()
                except Exception as e:
                    print(f"[ERROR] Ensuring candidate profile during login: {e}")
                    
            flash('Login successful!', 'success')
            
            if user['role'] == 'candidate':
                return redirect(url_for('candidate_dashboard'))
            else:
                return redirect(url_for('recruiter_dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration route."""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        try:
            db = get_db_connection()
            cursor = db.cursor()
            
            # READ: Check if email already exists
            cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                flash('Email already registered! Please log in.', 'danger')
                cursor.close()
                db.close()
                return redirect(url_for('register'))
                
            # CREATE: Insert new user into database
            cursor.execute("""
                INSERT INTO users (fullname, email, password, role) 
                VALUES (%s, %s, %s, %s)
            """, (name, email, password, role))
            db.commit()
            
            new_user_id = cursor.lastrowid
            
            # If candidate, create profile
            if role == 'candidate':
                cursor.execute("""
                    INSERT INTO candidate_profiles (user_id, full_name)
                    VALUES (%s, %s)
                """, (new_user_id, name))
                db.commit()
            
            cursor.close()
            db.close()
            
            session.permanent = True
            session['user_id'] = new_user_id
            session['name'] = name
            session['role'] = role
            
            flash('Registration successful! Welcome!', 'success')
            if role == 'recruiter':
                return redirect(url_for('recruiter_dashboard'))
            else:
                return redirect(url_for('candidate_dashboard'))
        except Exception as e:
            print(f"Registration error: {e}")
            flash('An error occurred during registration. Please try again.', 'danger')
        
    return render_template('register.html')

@app.route('/logout')
def logout():
    """Clear session and logout."""
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('home'))

@app.route('/jobs', methods=['GET'])
def jobs():
    """Jobs listing page with search and filter capabilities."""
    search_query = request.args.get('search', '')
    location_filter = request.args.get('location', '')
    job_types = request.args.getlist('job_type')
    
    db = get_db_connection()
    cursor = db.cursor()
    
    # READ: Fetch all active jobs with dynamic filtering
    query = """
        SELECT jobs.*, companies.company_name 
        FROM jobs 
        LEFT JOIN companies ON jobs.company_id = companies.company_id 
        WHERE 1=1
    """
    params = []
    
    if search_query:
        query += " AND (jobs.title LIKE %s OR jobs.skills_required LIKE %s)"
        params.extend(['%' + search_query + '%', '%' + search_query + '%'])
    if location_filter:
        query += " AND jobs.location LIKE %s"
        params.append('%' + location_filter + '%')
    if job_types:
        format_strings = ','.join(['%s'] * len(job_types))
        query += f" AND jobs.job_type IN ({format_strings})"
        params.extend(job_types)
        
    query += " ORDER BY jobs.job_id DESC"
    
    cursor.execute(query, tuple(params))
    jobs_list = cursor.fetchall()
    
    cursor.close()
    db.close()
    
    return render_template('jobs.html', jobs=jobs_list)

@app.route('/job/<int:job_id>')
def job_details(job_id):
    """Detailed view for a specific job with Candidate-specific Skill Matcher calculations."""
    db = get_db_connection()
    cursor = db.cursor()
    
    # READ: Fetch details of the specific job
    cursor.execute("""
        SELECT jobs.*, companies.company_name 
        FROM jobs 
        JOIN companies ON jobs.company_id = companies.company_id 
        WHERE jobs.job_id = %s
    """, (job_id,))
    job = cursor.fetchone()
    
    if not job:
        flash('Job not found.', 'danger')
        cursor.close()
        db.close()
        return redirect(url_for('jobs'))
        
    # READ: Fetch similar jobs based on job type
    cursor.execute("""
        SELECT jobs.*, companies.company_name 
        FROM jobs 
        JOIN companies ON jobs.company_id = companies.company_id 
        WHERE jobs.job_type = %s AND jobs.job_id != %s 
        LIMIT 3
    """, (job['job_type'], job_id))
    similar_jobs = cursor.fetchall()
    
    # Intelligent Skill Matching: Calculate candidate-specific match
    match_data = None
    if 'user_id' in session and session.get('role') == 'candidate':
        cursor.execute("SELECT skills FROM candidate_profiles WHERE user_id = %s", (session['user_id'],))
        user_skills_row = cursor.fetchone()
        
        user_skills_str = user_skills_row['skills'] if user_skills_row and user_skills_row['skills'] else ""
        job_skills_str = job['skills_required'] or ""
        
        import re
        def get_words(text):
            return [w.strip().lower() for w in text.split(',') if w.strip()] if ',' in text else list(set(re.findall(r'\b[a-zA-Z0-9+#.-]+\b', text.lower())))
            
        user_skills = get_words(user_skills_str)
        job_skills = get_words(job_skills_str)
        
        matched_skills = []
        missing_skills = []
        
        if job_skills:
            for js in job_skills:
                # Substring check to cover variations
                if any(js in us or us in js for us in user_skills):
                    matched_skills.append(js)
                else:
                    missing_skills.append(js)
            match_pct = int((len(matched_skills) / len(job_skills)) * 100)
        else:
            match_pct = 100
            
        match_data = {
            'pct': match_pct,
            'matched': matched_skills,
            'missing': missing_skills,
            'has_skills': bool(user_skills_str)
        }
    
    # Fetch candidate resume status if logged in
    candidate_resume = None
    if 'user_id' in session and session.get('role') == 'candidate':
        cursor.execute("SELECT resume_path AS resume FROM candidate_profiles WHERE user_id = %s", (session['user_id'],))
        row = cursor.fetchone()
        if row:
            candidate_resume = row['resume']

    cursor.close()
    db.close()
    
    return render_template('job_details.html', job=job, similar_jobs=similar_jobs, match_data=match_data, candidate_resume=candidate_resume)

@app.route('/apply/<int:job_id>', methods=['POST'])
def apply_job(job_id):
    """Candidate applies for a job."""
    if 'user_id' not in session or session.get('role') != 'candidate':
        flash('Please log in as a candidate to apply.', 'warning')
        return redirect(url_for('login'))
        
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Check if already applied
        cursor.execute("SELECT application_id FROM applications WHERE job_id=%s AND user_id=%s", (job_id, session['user_id']))
        if cursor.fetchone():
            flash('You have already applied for this job!', 'info')
        else:
            # CREATE: Insert job application
            cursor.execute("INSERT INTO applications (job_id, user_id, status) VALUES (%s, %s, 'New')", (job_id, session['user_id']))
            db.commit()
            flash('Application submitted successfully!', 'success')
            
    except Exception as e:
        print(f"Error applying for job: {e}")
        flash('An error occurred while applying. Please try again.', 'danger')
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()
    return redirect(url_for('job_details', job_id=job_id))

@app.route('/save_job/<int:job_id>', methods=['POST'])
def save_job(job_id):
    """Candidate saves a job for later."""
    if 'user_id' not in session or session.get('role') != 'candidate':
        flash('Please log in as a candidate to save jobs.', 'warning')
        return redirect(url_for('login'))
        
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Check if already saved
        cursor.execute("SELECT saved_id FROM saved_jobs WHERE job_id=%s AND user_id=%s", (job_id, session['user_id']))
        if cursor.fetchone():
            flash('Job is already saved!', 'info')
        else:
            cursor.execute("INSERT INTO saved_jobs (job_id, user_id) VALUES (%s, %s)", (job_id, session['user_id']))
            db.commit()
            flash('Job saved successfully!', 'success')
            
    except Exception as e:
        print(f"Error saving job: {e}")
        flash('An error occurred while saving the job.', 'danger')
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()
    return redirect(url_for('job_details', job_id=job_id))

@app.route('/candidate/dashboard')
def candidate_dashboard():
    """Dashboard for candidates to view applied jobs, profile info, and status updates."""
    if 'user_id' not in session or session.get('role') != 'candidate':
        flash('Please log in as a candidate to access this page.', 'warning')
        return redirect(url_for('login'))
        
    db = get_db_connection()
    cursor = db.cursor()
    
    # READ: Fetch jobs applied by this candidate
    cursor.execute("""
        SELECT applications.*, jobs.title, companies.company_name 
        FROM applications 
        JOIN jobs ON applications.job_id = jobs.job_id 
        JOIN companies ON jobs.company_id = companies.company_id
        WHERE applications.user_id = %s
        ORDER BY applications.applied_at DESC
    """, (session['user_id'],))
    applied_jobs = cursor.fetchall()
    
    # READ: Get total applied count
    cursor.execute("SELECT COUNT(*) as total FROM applications WHERE user_id = %s", (session['user_id'],))
    total_applied = cursor.fetchone()['total']

    # READ: Fetch detailed candidate profile fields from candidate_profiles table
    cursor.execute("""
        SELECT cp.*, u.email, cp.full_name AS fullname, cp.resume_path AS resume, cp.github_url AS github_link, cp.linkedin_url AS linkedin_link 
        FROM candidate_profiles cp
        JOIN users u ON cp.user_id = u.user_id
        WHERE cp.user_id = %s
    """, (session['user_id'],))
    candidate = cursor.fetchone()
    
    # If no profile exists, create one dynamically to prevent errors
    if not candidate:
        cursor.execute("SELECT fullname FROM users WHERE user_id = %s", (session['user_id'],))
        user_row = cursor.fetchone()
        fullname = user_row['fullname'] if user_row else "Candidate"
        cursor.execute("""
            INSERT INTO candidate_profiles (user_id, full_name)
            VALUES (%s, %s)
        """, (session['user_id'], fullname))
        db.commit()
        
        cursor.execute("""
            SELECT cp.*, u.email, cp.full_name AS fullname, cp.resume_path AS resume, cp.github_url AS github_link, cp.linkedin_url AS linkedin_link 
            FROM candidate_profiles cp
            JOIN users u ON cp.user_id = u.user_id
            WHERE cp.user_id = %s
        """, (session['user_id'],))
        candidate = cursor.fetchone()
    
    # Find matching jobs based on skills/resume keywords
    recommended_jobs = []
    if candidate:
        candidate_skills = candidate['skills'] or ""
        import re
        skills_list = [s.strip().lower() for s in candidate_skills.split(',') if s.strip()]
        if not skills_list and candidate['resume']:
            # Parse keywords from resume filename (removing generic terms)
            skills_list = [w.lower() for w in re.findall(r'[a-zA-Z0-9+#.-]+', candidate['resume']) if w.lower() not in ['resume', 'user', 'pdf', 'docx', 'doc', 'txt']]
            
        if skills_list:
            query = """
                SELECT jobs.*, companies.company_name 
                FROM jobs 
                JOIN companies ON jobs.company_id = companies.company_id
                WHERE 
            """
            or_clauses = []
            params = []
            for skill in skills_list:
                or_clauses.append("jobs.skills_required LIKE %s OR jobs.title LIKE %s")
                params.extend([f"%{skill}%", f"%{skill}%"])
            query += " (" + " OR ".join(or_clauses) + ") "
            query += """
                AND jobs.job_id NOT IN (
                    SELECT job_id FROM applications WHERE user_id = %s
                )
                ORDER BY jobs.job_id DESC LIMIT 5
            """
            params.append(session['user_id'])
            try:
                cursor.execute(query, tuple(params))
                recommended_jobs = cursor.fetchall()
            except Exception as e:
                print(f"Error querying recommended jobs: {e}")
    
    # Fetch upcoming interviews for this candidate
    upcoming_interviews = []
    try:
        cursor.execute("""
            SELECT i.*, j.title AS job_title, c.company_name,
                   COALESCE(cp2.full_name, u2.fullname) AS interviewer_display_name
            FROM interviews i
            JOIN jobs j ON i.job_id = j.job_id
            LEFT JOIN companies c ON j.company_id = c.company_id
            LEFT JOIN users u2 ON i.recruiter_id = u2.user_id
            LEFT JOIN candidate_profiles cp2 ON u2.user_id = cp2.user_id
            WHERE i.candidate_id = %s AND i.status = 'Scheduled' AND i.interview_date >= CURDATE()
            ORDER BY i.interview_date ASC, i.start_time ASC
        """, (session['user_id'],))
        upcoming_interviews = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching interviews: {e}")

    # Fetch proposed interview slots
    proposed_slots = []
    try:
        cursor.execute("""
            SELECT s.*, j.title AS job_title, c.company_name
            FROM interview_slots s
            JOIN applications a ON s.application_id = a.application_id
            JOIN jobs j ON a.job_id = j.job_id
            LEFT JOIN companies c ON j.company_id = c.company_id
            WHERE a.user_id = %s AND s.status = 'Pending'
            ORDER BY s.interview_time ASC
        """, (session['user_id'],))
        proposed_slots = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching proposed slots: {e}")

    cursor.close()
    db.close()
    
    return render_template(
        'candidate_dashboard.html', 
        applied_jobs=applied_jobs, 
        total_applied=total_applied,
        candidate=candidate,
        recommended_jobs=recommended_jobs,
        upcoming_interviews=upcoming_interviews,
        proposed_slots=proposed_slots
    )

@app.route('/upload_resume', methods=['POST'])
def upload_resume():
    """Candidate uploads resume file and saves location details inside DB."""
    if 'user_id' not in session or session.get('role') != 'candidate':
        flash('Please log in as a candidate to upload resume.', 'warning')
        return redirect(url_for('login'))
        
    print(f"[DEBUG] upload_resume session: {dict(session)}")
        
    if 'resume' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('candidate_dashboard'))
        
    file = request.files['resume']
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('candidate_dashboard'))
        
    if file and allowed_file(file.filename):
        import time
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        unique_name = f"resume_{session['user_id']}_{uuid.uuid4().hex}_{int(time.time())}.{file_ext}"
        
        file_path = os.path.join(app.config['RESUME_UPLOAD_FOLDER'], unique_name)
        file.save(file_path)
        print(f"[DEBUG] Saved resume file permanently to: {file_path}")
        
        try:
            db = get_db_connection()
            cursor = db.cursor()
            
            # Ensure candidate_profiles record exists
            cursor.execute("SELECT profile_id FROM candidate_profiles WHERE user_id = %s", (session['user_id'],))
            if not cursor.fetchone():
                cursor.execute("SELECT fullname FROM users WHERE user_id = %s", (session['user_id'],))
                user_row = cursor.fetchone()
                fullname = user_row['fullname'] if user_row else "Candidate"
                cursor.execute("""
                    INSERT INTO candidate_profiles (user_id, full_name, resume_path, resume_filename)
                    VALUES (%s, %s, %s, %s)
                """, (session['user_id'], fullname, unique_name, unique_name))
            else:
                cursor.execute("""
                    UPDATE candidate_profiles 
                    SET resume_path = %s, resume_filename = %s 
                    WHERE user_id = %s
                """, (unique_name, unique_name, session['user_id']))
                
            db.commit()
            print(f"[DEBUG] SQL UPDATE for resume_path completed. Set to: {unique_name} for user {session['user_id']}")
            flash('Resume uploaded successfully!', 'success')
        except Exception as e:
            print(f"[ERROR] Database error during resume upload: {e}")
            db.rollback()
            flash('Resume saved locally but database transaction failed.', 'warning')
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'db' in locals() and db.open:
                db.close()
    else:
        flash('Allowed file types: pdf, doc, docx.', 'danger')
                
    return redirect(url_for('candidate_dashboard'))

@app.route('/candidate/update_profile', methods=['POST'])
def candidate_update_profile():
    """Update candidate profile details (skills, links, name) inside DB."""
    if 'user_id' not in session or session.get('role') != 'candidate':
        flash('Please log in as a candidate to perform this action.', 'warning')
        return redirect(url_for('login'))
        
    print(f"[DEBUG] candidate_update_profile session: {dict(session)}")
    
    fullname = request.form.get('fullname', '').strip()
    phone = request.form.get('phone', '').strip() or None
    skills = request.form.get('skills', '').strip() or None
    github_link = request.form.get('github_link', '').strip() or None
    linkedin_link = request.form.get('linkedin_link', '').strip() or None
    headline = request.form.get('headline', '').strip() or None
    portfolio_url = request.form.get('portfolio_url', '').strip() or None
    summary = request.form.get('summary', '').strip() or None
    
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Check if profile already exists
        cursor.execute("SELECT profile_id FROM candidate_profiles WHERE user_id = %s", (session['user_id'],))
        profile_row = cursor.fetchone()
        
        if profile_row:
            # UPDATE
            cursor.execute("""
                UPDATE candidate_profiles 
                SET full_name = %s, phone = %s, skills = %s, github_url = %s, linkedin_url = %s, headline = %s, portfolio_url = %s, summary = %s
                WHERE user_id = %s
            """, (fullname, phone, skills, github_link, linkedin_link, headline, portfolio_url, summary, session['user_id']))
            print(f"[DEBUG] SQL UPDATE executed for user {session['user_id']}")
        else:
            # INSERT fallback
            cursor.execute("""
                INSERT INTO candidate_profiles (user_id, full_name, phone, skills, github_url, linkedin_url, headline, portfolio_url, summary)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (session['user_id'], fullname, phone, skills, github_link, linkedin_link, headline, portfolio_url, summary))
            print(f"[DEBUG] SQL INSERT executed for user {session['user_id']}")
            
        # Also sync fullname back to users table
        cursor.execute("UPDATE users SET fullname = %s WHERE user_id = %s", (fullname, session['user_id']))
        
        db.commit()
        print(f"[DEBUG] Database transaction committed successfully.")
        
        session['name'] = fullname  # Synchronize current session display name
        flash('Profile updated successfully!', 'success')
    except Exception as e:
        print(f"[ERROR] Database error during profile updates: {e}")
        db.rollback()
        flash('An error occurred. Please try again.', 'danger')
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals() and db.open:
            db.close()
            
    return redirect(url_for('candidate_dashboard'))

@app.route('/recruiter/dashboard')
def recruiter_dashboard():
    """Dashboard for recruiters using the job_analytics VIEW to load posting metrics."""
    if 'user_id' not in session or session.get('role') != 'recruiter':
        flash('Please log in as a recruiter to access this page.', 'warning')
        return redirect(url_for('login'))
        
    db = get_db_connection()
    cursor = db.cursor()
    
    # READ: Fetch jobs posted by this recruiter using the database VIEW 'job_analytics'
    cursor.execute("""
        SELECT *, total_applications AS app_count 
        FROM job_analytics 
        WHERE recruiter_id = %s
        ORDER BY job_id DESC
    """, (session['user_id'],))
    posted_jobs = cursor.fetchall()
    
    total_jobs = len(posted_jobs)
    
    # READ: Total applicants for their jobs
    cursor.execute("""
        SELECT COUNT(applications.application_id) as total_applicants 
        FROM applications 
        JOIN jobs ON applications.job_id = jobs.job_id 
        WHERE jobs.recruiter_id = %s
    """, (session['user_id'],))
    result = cursor.fetchone()
    total_applicants = result['total_applicants'] if result else 0
    
    cursor.close()
    db.close()
    
    return render_template('recruiter_dashboard.html', posted_jobs=posted_jobs, total_jobs=total_jobs, total_applicants=total_applicants)

@app.route('/recruiter/applicants/<int:job_id>')
def view_applicants(job_id):
    """View and manage all candidates who applied for a specific job."""
    if 'user_id' not in session or session.get('role') != 'recruiter':
        flash('Please log in as a recruiter to view applicants.', 'warning')
        return redirect(url_for('login'))
        
    db = get_db_connection()
    cursor = db.cursor()
    
    # Confirm recruiter owns this job
    cursor.execute("SELECT * FROM jobs WHERE job_id = %s AND recruiter_id = %s", (job_id, session['user_id']))
    job = cursor.fetchone()
    
    if not job:
        flash('Job posting not found or unauthorized access.', 'danger')
        cursor.close()
        db.close()
        return redirect(url_for('recruiter_dashboard'))
        
    # READ: Fetch applicants with complete profiles
    cursor.execute("""
        SELECT a.application_id, a.status, a.applied_at, 
               u.user_id, cp.full_name AS fullname, u.email, cp.phone, 
               cp.skills AS candidate_skills, cp.resume_path AS resume, 
               cp.github_url AS github_link, cp.linkedin_url AS linkedin_link,
               cp.headline, cp.summary, cp.portfolio_url, cp.resume_filename
        FROM applications a
        JOIN users u ON a.user_id = u.user_id
        LEFT JOIN candidate_profiles cp ON u.user_id = cp.user_id
        WHERE a.job_id = %s
        ORDER BY a.applied_at DESC
    """, (job_id,))
    applicants = cursor.fetchall()
    
    # Extract clean keyword elements for matching calculations
    job_skills_req = [s.strip().lower() for s in job['skills_required'].split(',') if s.strip()] if job['skills_required'] else []
    if not job_skills_req and job['skills_required']:
        import re
        job_skills_req = list(set(re.findall(r'\b[a-zA-Z0-9+#.-]+\b', job['skills_required'].lower())))
        
    for app in applicants:
        app_skills_str = app['candidate_skills'] or ""
        import re
        cand_skills = [s.strip().lower() for s in app_skills_str.split(',') if s.strip()]
        if not cand_skills and app_skills_str:
            cand_skills = list(set(re.findall(r'\b[a-zA-Z0-9+#.-]+\b', app_skills_str.lower())))
            
        matched = []
        missing = []
        
        for js in job_skills_req:
            if any(js in cs or cs in js for cs in cand_skills):
                matched.append(js)
            else:
                missing.append(js)
                
        match_pct = int((len(matched) / len(job_skills_req)) * 100) if job_skills_req else 100
        app['match_pct'] = match_pct
        app['matched_skills'] = matched
        app['missing_skills'] = missing
        
        # READ: Fetch updates log history from the 'application_history' database table
        cursor.execute("""
            SELECT old_status, new_status, changed_at 
            FROM application_history 
            WHERE application_id = %s
            ORDER BY changed_at ASC
        """, (app['application_id'],))
        app['history'] = cursor.fetchall()
        
        # Fetch interview schedules for this application
        cursor.execute("""
            SELECT interview_id, interview_title, interview_type, interview_round,
                   interview_date, start_time, end_time, timezone, meeting_link,
                   interviewer_name, status
            FROM interviews
            WHERE application_id = %s
            ORDER BY interview_date DESC
        """, (app['application_id'],))
        app['interviews'] = cursor.fetchall()
        
    cursor.close()
    db.close()
    
    return render_template('applicants.html', job=job, applicants=applicants)

@app.route('/recruiter/update_status/<int:application_id>', methods=['POST'])
def update_application_status(application_id):
    """AJAX endpoint that updates application status (triggers the MySQL logger).
    Also auto-sends offer/rejection emails and signals schedule modal for Interviewing."""
    if 'user_id' not in session or session.get('role') != 'recruiter':
        return jsonify({"success": False, "message": "Unauthorized access"}), 403
        
    new_status = request.json.get('status')
    if new_status not in ['New', 'Reviewed', 'Interviewing', 'Offered', 'Rejected']:
        return jsonify({"success": False, "message": "Invalid status value"}), 400
        
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Verify job ownership and fetch candidate + job info for email
        cursor.execute("""
            SELECT a.application_id, a.user_id AS candidate_id, a.job_id,
                   j.recruiter_id, j.title AS job_title,
                   c.company_name,
                   u.email AS candidate_email,
                   COALESCE(cp.full_name, u.fullname) AS candidate_name
            FROM applications a
            JOIN jobs j ON a.job_id = j.job_id
            LEFT JOIN companies c ON j.company_id = c.company_id
            JOIN users u ON a.user_id = u.user_id
            LEFT JOIN candidate_profiles cp ON u.user_id = cp.user_id
            WHERE a.application_id = %s
        """, (application_id,))
        app_info = cursor.fetchone()
        
        if not app_info or app_info['recruiter_id'] != session['user_id']:
            cursor.close()
            db.close()
            return jsonify({"success": False, "message": "Unauthorized ownership check"}), 403
            
        # TRANSACTION: Update DB record. This fires the MySQL trigger to record status history.
        cursor.execute("UPDATE applications SET status = %s WHERE application_id = %s", (new_status, application_id))
        db.commit()
        
        response_data = {"success": True, "message": f"Status updated to {new_status}."}
        
        # AUTO-EMAIL: Send emails based on status change
        if new_status == 'Offered':
            success, error, subject = send_offer_email(
                app_info['candidate_name'], app_info['candidate_email'],
                app_info['job_title'], app_info['company_name'] or 'Our Company',
                session.get('name', 'Recruiter')
            )
            log_email(cursor, app_info['candidate_email'], app_info['candidate_name'],
                     'offer_letter', subject, application_id, None,
                     'sent' if success else 'failed', error)
            db.commit()
            response_data['email_sent'] = success
            response_data['email_type'] = 'offer_letter'
            
        elif new_status == 'Rejected':
            success, error, subject = send_rejection_email(
                app_info['candidate_name'], app_info['candidate_email'],
                app_info['job_title'], app_info['company_name'] or 'Our Company'
            )
            log_email(cursor, app_info['candidate_email'], app_info['candidate_name'],
                     'rejection', subject, application_id, None,
                     'sent' if success else 'failed', error)
            db.commit()
            response_data['email_sent'] = success
            response_data['email_type'] = 'rejection'
            
        elif new_status == 'Interviewing':
            # Signal frontend to open the Schedule Interview modal
            response_data['show_schedule_modal'] = True
            response_data['candidate_name'] = app_info['candidate_name']
            response_data['candidate_email'] = app_info['candidate_email']
            response_data['job_title'] = app_info['job_title']
            response_data['candidate_id'] = app_info['candidate_id']
            response_data['job_id'] = app_info['job_id']
        
        return jsonify(response_data)
    except Exception as e:
        print(f"Error executing database updates: {e}")
        db.rollback()
        return jsonify({"success": False, "message": "Database transaction failed"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals() and db.open:
            db.close()

# -----------------------------------------------------------------
# INTERVIEW SCHEDULING & EMAIL COMMUNICATION ROUTES
# -----------------------------------------------------------------

@app.route('/recruiter/schedule_interview/<int:application_id>', methods=['POST'])
def schedule_interview(application_id):
    """Schedule an interview for a candidate. Saves to DB and sends email invite."""
    if 'user_id' not in session or session.get('role') != 'recruiter':
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        db = get_db_connection()
        cursor = db.cursor()

        # Verify ownership
        cursor.execute("""
            SELECT a.user_id AS candidate_id, a.job_id, j.recruiter_id, j.title AS job_title,
                   c.company_name, u.email AS candidate_email,
                   COALESCE(cp.full_name, u.fullname) AS candidate_name
            FROM applications a
            JOIN jobs j ON a.job_id = j.job_id
            LEFT JOIN companies c ON j.company_id = c.company_id
            JOIN users u ON a.user_id = u.user_id
            LEFT JOIN candidate_profiles cp ON u.user_id = cp.user_id
            WHERE a.application_id = %s
        """, (application_id,))
        app_info = cursor.fetchone()

        if not app_info or app_info['recruiter_id'] != session['user_id']:
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        # Collect form data from JSON body
        data = request.json
        interview_title = data.get('interview_title', f"Interview for {app_info['job_title']}")
        interview_type = data.get('interview_type', 'Online')
        interview_round = data.get('interview_round', 'HR')
        interview_date = data.get('interview_date')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        timezone = data.get('timezone', 'IST')
        meeting_link = data.get('meeting_link', '')
        office_address = data.get('office_address', '')
        instructions = data.get('instructions', '')
        required_documents = data.get('required_documents', '')
        contact_phone = data.get('contact_phone', '')
        interviewer_name = data.get('interviewer_name', session.get('name', ''))
        interviewer_email = data.get('interviewer_email', '')

        if not interview_date or not start_time or not end_time:
            return jsonify({"success": False, "message": "Date and time are required"}), 400

        # INSERT interview record
        cursor.execute("""
            INSERT INTO interviews (application_id, candidate_id, job_id, recruiter_id,
                interview_title, interview_type, interview_round, interview_date,
                start_time, end_time, timezone, meeting_link, office_address,
                instructions, required_documents, contact_phone,
                interviewer_name, interviewer_email, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Scheduled')
        """, (application_id, app_info['candidate_id'], app_info['job_id'], session['user_id'],
              interview_title, interview_type, interview_round, interview_date,
              start_time, end_time, timezone, meeting_link, office_address,
              instructions, required_documents, contact_phone,
              interviewer_name, interviewer_email))
        db.commit()
        interview_id = cursor.lastrowid

        # Send interview invitation email
        interview_data = {
            'interview_id': interview_id,
            'interview_title': interview_title,
            'interview_type': interview_type,
            'interview_round': interview_round,
            'interview_date': interview_date,
            'start_time': start_time,
            'end_time': end_time,
            'timezone': timezone,
            'meeting_link': meeting_link,
            'office_address': office_address,
            'instructions': instructions,
            'required_documents': required_documents,
            'contact_phone': contact_phone,
            'interviewer_name': interviewer_name,
            'interviewer_email': interviewer_email
        }

        email_success, email_error, subject = send_interview_invite(
            app_info['candidate_name'], app_info['candidate_email'],
            interview_data, app_info['job_title'],
            app_info['company_name'] or 'Our Company'
        )

        log_email(cursor, app_info['candidate_email'], app_info['candidate_name'],
                 'interview_invite', subject, application_id, interview_id,
                 'sent' if email_success else 'failed', email_error)
        db.commit()

        return jsonify({
            "success": True,
            "message": "Interview scheduled successfully!",
            "interview_id": interview_id,
            "email_sent": email_success
        })

    except Exception as e:
        print(f"[ERROR] Schedule interview: {e}")
        if 'db' in locals():
            db.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals() and db.open:
            db.close()


@app.route('/recruiter/cancel_interview/<int:interview_id>', methods=['POST'])
def cancel_interview(interview_id):
    """Cancel a scheduled interview and notify candidate."""
    if 'user_id' not in session or session.get('role') != 'recruiter':
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("""
            SELECT i.*, j.title AS job_title, c.company_name,
                   u.email AS candidate_email,
                   COALESCE(cp.full_name, u.fullname) AS candidate_name
            FROM interviews i
            JOIN jobs j ON i.job_id = j.job_id
            LEFT JOIN companies c ON j.company_id = c.company_id
            JOIN users u ON i.candidate_id = u.user_id
            LEFT JOIN candidate_profiles cp ON u.user_id = cp.user_id
            WHERE i.interview_id = %s AND i.recruiter_id = %s
        """, (interview_id, session['user_id']))
        interview = cursor.fetchone()

        if not interview:
            return jsonify({"success": False, "message": "Interview not found"}), 404

        cursor.execute("UPDATE interviews SET status = 'Cancelled' WHERE interview_id = %s", (interview_id,))
        db.commit()

        return jsonify({"success": True, "message": "Interview cancelled."})

    except Exception as e:
        print(f"[ERROR] Cancel interview: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals() and db.open:
            db.close()


@app.route('/recruiter/send_offer/<int:application_id>', methods=['POST'])
def send_offer_route(application_id):
    """Manually send offer email for an application."""
    if 'user_id' not in session or session.get('role') != 'recruiter':
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("""
            SELECT a.application_id, j.title AS job_title, c.company_name,
                   u.email AS candidate_email,
                   COALESCE(cp.full_name, u.fullname) AS candidate_name,
                   j.recruiter_id
            FROM applications a
            JOIN jobs j ON a.job_id = j.job_id
            LEFT JOIN companies c ON j.company_id = c.company_id
            JOIN users u ON a.user_id = u.user_id
            LEFT JOIN candidate_profiles cp ON u.user_id = cp.user_id
            WHERE a.application_id = %s
        """, (application_id,))
        info = cursor.fetchone()

        if not info or info['recruiter_id'] != session['user_id']:
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        # Update status to Offered
        cursor.execute("UPDATE applications SET status = 'Offered' WHERE application_id = %s", (application_id,))
        db.commit()

        success, error, subject = send_offer_email(
            info['candidate_name'], info['candidate_email'],
            info['job_title'], info['company_name'] or 'Our Company',
            session.get('name', 'Recruiter')
        )
        log_email(cursor, info['candidate_email'], info['candidate_name'],
                 'offer_letter', subject, application_id, None,
                 'sent' if success else 'failed', error)
        db.commit()

        return jsonify({"success": True, "message": "Offer email sent!", "email_sent": success})

    except Exception as e:
        print(f"[ERROR] Send offer: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals() and db.open:
            db.close()


@app.route('/recruiter/send_rejection/<int:application_id>', methods=['POST'])
def send_rejection_route(application_id):
    """Manually send rejection email for an application."""
    if 'user_id' not in session or session.get('role') != 'recruiter':
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("""
            SELECT a.application_id, j.title AS job_title, c.company_name,
                   u.email AS candidate_email,
                   COALESCE(cp.full_name, u.fullname) AS candidate_name,
                   j.recruiter_id
            FROM applications a
            JOIN jobs j ON a.job_id = j.job_id
            LEFT JOIN companies c ON j.company_id = c.company_id
            JOIN users u ON a.user_id = u.user_id
            LEFT JOIN candidate_profiles cp ON u.user_id = cp.user_id
            WHERE a.application_id = %s
        """, (application_id,))
        info = cursor.fetchone()

        if not info or info['recruiter_id'] != session['user_id']:
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        # Update status to Rejected
        cursor.execute("UPDATE applications SET status = 'Rejected' WHERE application_id = %s", (application_id,))
        db.commit()

        success, error, subject = send_rejection_email(
            info['candidate_name'], info['candidate_email'],
            info['job_title'], info['company_name'] or 'Our Company'
        )
        log_email(cursor, info['candidate_email'], info['candidate_name'],
                 'rejection', subject, application_id, None,
                 'sent' if success else 'failed', error)
        db.commit()

        return jsonify({"success": True, "message": "Rejection email sent.", "email_sent": success})

    except Exception as e:
        print(f"[ERROR] Send rejection: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals() and db.open:
            db.close()


@app.route('/recruiter/interviews')
def recruiter_interviews():
    """Recruiter interview management dashboard — upcoming and past interviews."""
    if 'user_id' not in session or session.get('role') != 'recruiter':
        flash('Please log in as a recruiter.', 'warning')
        return redirect(url_for('login'))

    db = get_db_connection()
    cursor = db.cursor()

    # Upcoming interviews
    cursor.execute("""
        SELECT i.*, j.title AS job_title, c.company_name,
               COALESCE(cp.full_name, u.fullname) AS candidate_name, u.email AS candidate_email
        FROM interviews i
        JOIN jobs j ON i.job_id = j.job_id
        LEFT JOIN companies c ON j.company_id = c.company_id
        JOIN users u ON i.candidate_id = u.user_id
        LEFT JOIN candidate_profiles cp ON u.user_id = cp.user_id
        WHERE i.recruiter_id = %s AND i.status = 'Scheduled' AND i.interview_date >= CURDATE()
        ORDER BY i.interview_date ASC, i.start_time ASC
    """, (session['user_id'],))
    upcoming = cursor.fetchall()

    # Past interviews
    cursor.execute("""
        SELECT i.*, j.title AS job_title, c.company_name,
               COALESCE(cp.full_name, u.fullname) AS candidate_name, u.email AS candidate_email
        FROM interviews i
        JOIN jobs j ON i.job_id = j.job_id
        LEFT JOIN companies c ON j.company_id = c.company_id
        JOIN users u ON i.candidate_id = u.user_id
        LEFT JOIN candidate_profiles cp ON u.user_id = cp.user_id
        WHERE i.recruiter_id = %s AND (i.status != 'Scheduled' OR i.interview_date < CURDATE())
        ORDER BY i.interview_date DESC
        LIMIT 20
    """, (session['user_id'],))
    past = cursor.fetchall()

    # Stats
    cursor.execute("SELECT COUNT(*) as total FROM interviews WHERE recruiter_id = %s AND status = 'Scheduled' AND interview_date >= CURDATE()", (session['user_id'],))
    total_upcoming = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM interviews WHERE recruiter_id = %s AND status = 'Completed'", (session['user_id'],))
    total_completed = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM interviews WHERE recruiter_id = %s AND status = 'Cancelled'", (session['user_id'],))
    total_cancelled = cursor.fetchone()['total']

    cursor.close()
    db.close()

    return render_template('recruiter_interviews.html',
                         upcoming=upcoming, past=past,
                         total_upcoming=total_upcoming, total_completed=total_completed,
                         total_cancelled=total_cancelled)


@app.route('/interview/calendar/<int:interview_id>')
def download_ics(interview_id):
    """Download .ics calendar file for an interview."""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("""
        SELECT i.*, j.title AS job_title
        FROM interviews i
        JOIN jobs j ON i.job_id = j.job_id
        WHERE i.interview_id = %s AND (i.candidate_id = %s OR i.recruiter_id = %s)
    """, (interview_id, session['user_id'], session['user_id']))
    interview = cursor.fetchone()

    cursor.close()
    db.close()

    if not interview:
        flash('Interview not found.', 'danger')
        return redirect(url_for('home'))

    ics_content = generate_ics(interview)

    response = make_response(ics_content)
    response.headers['Content-Type'] = 'text/calendar; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=interview_{interview_id}.ics'
    return response


# -----------------------------------------------------------------
# INTERVIEW SLOTS SUGGESTION & RESPONSE ROUTES
# -----------------------------------------------------------------

@app.route('/recruiter/slots/<int:application_id>', methods=['GET'])
def get_recruiter_slots(application_id):
    """Fetch suggested interview slots for a specific application."""
    if 'user_id' not in session or session.get('role') != 'recruiter':
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        db = get_db_connection()
        cursor = db.cursor()

        # Verify recruiter ownership of this application via job posting
        cursor.execute("""
            SELECT j.recruiter_id 
            FROM applications a 
            JOIN jobs j ON a.job_id = j.job_id 
            WHERE a.application_id = %s
        """, (application_id,))
        job_info = cursor.fetchone()

        if not job_info or job_info['recruiter_id'] != session['user_id']:
            return jsonify({"success": False, "message": "Unauthorized ownership check"}), 403

        # Fetch slots
        cursor.execute("""
            SELECT slot_id, interview_time, duration_minutes, location_details, status, created_at 
            FROM interview_slots 
            WHERE application_id = %s 
            ORDER BY interview_time ASC
        """, (application_id,))
        slots = cursor.fetchall()

        # Format datetime for JSON representation
        for s in slots:
            if s['interview_time']:
                s['interview_time_str'] = s['interview_time'].strftime('%Y-%m-%d %H:%M')

        return jsonify({"success": True, "slots": slots})

    except Exception as e:
        print(f"[ERROR] Fetch slots: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals() and db.open:
            db.close()


@app.route('/recruiter/suggest_slot/<int:application_id>', methods=['POST'])
def suggest_slot(application_id):
    """Recruiter adds a new proposed interview slot suggestion."""
    if 'user_id' not in session or session.get('role') != 'recruiter':
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        db = get_db_connection()
        cursor = db.cursor()

        # Verify recruiter ownership of this application via job posting
        cursor.execute("""
            SELECT j.recruiter_id 
            FROM applications a 
            JOIN jobs j ON a.job_id = j.job_id 
            WHERE a.application_id = %s
        """, (application_id,))
        job_info = cursor.fetchone()

        if not job_info or job_info['recruiter_id'] != session['user_id']:
            return jsonify({"success": False, "message": "Unauthorized ownership check"}), 403

        data = request.json
        interview_time_str = data.get('interview_time')
        duration_minutes = int(data.get('duration_minutes', 30))
        location_details = data.get('location_details', '')

        if not interview_time_str:
            return jsonify({"success": False, "message": "Interview slot time is required"}), 400

        # Insert proposed slot
        cursor.execute("""
            INSERT INTO interview_slots (application_id, interview_time, duration_minutes, location_details, status)
            VALUES (%s, %s, %s, %s, 'Pending')
        """, (application_id, interview_time_str, duration_minutes, location_details))
        db.commit()

        return jsonify({"success": True, "message": "Interview slot suggested successfully!"})

    except Exception as e:
        print(f"[ERROR] Suggest slot: {e}")
        if 'db' in locals():
            db.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals() and db.open:
            db.close()


@app.route('/recruiter/delete_slot/<int:slot_id>', methods=['POST'])
def delete_slot(slot_id):
    """Recruiter deletes a proposed interview slot suggestion."""
    if 'user_id' not in session or session.get('role') != 'recruiter':
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        db = get_db_connection()
        cursor = db.cursor()

        # Verify recruiter ownership of this slot
        cursor.execute("""
            SELECT j.recruiter_id 
            FROM interview_slots s
            JOIN applications a ON s.application_id = a.application_id
            JOIN jobs j ON a.job_id = j.job_id
            WHERE s.slot_id = %s
        """, (slot_id,))
        slot_info = cursor.fetchone()

        if not slot_info or slot_info['recruiter_id'] != session['user_id']:
            return jsonify({"success": False, "message": "Unauthorized ownership check"}), 403

        # Delete slot
        cursor.execute("DELETE FROM interview_slots WHERE slot_id = %s", (slot_id,))
        db.commit()

        return jsonify({"success": True, "message": "Proposed slot deleted successfully!"})

    except Exception as e:
        print(f"[ERROR] Delete slot: {e}")
        if 'db' in locals():
            db.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals() and db.open:
            db.close()


@app.route('/candidate/accept_slot/<int:slot_id>', methods=['POST'])
def accept_slot(slot_id):
    """Candidate accepts a suggested interview slot."""
    if 'user_id' not in session or session.get('role') != 'candidate':
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        db = get_db_connection()
        cursor = db.cursor()

        # Fetch proposed slot details and verify ownership
        cursor.execute("""
            SELECT s.*, a.user_id AS candidate_id, a.job_id, a.application_id, j.recruiter_id, j.title AS job_title,
                   c.company_name, u.email AS candidate_email, u2.email AS recruiter_email,
                   COALESCE(cp.full_name, u.fullname) AS candidate_name, u2.fullname AS recruiter_name
            FROM interview_slots s
            JOIN applications a ON s.application_id = a.application_id
            JOIN jobs j ON a.job_id = j.job_id
            LEFT JOIN companies c ON j.company_id = c.company_id
            JOIN users u ON a.user_id = u.user_id
            LEFT JOIN candidate_profiles cp ON u.user_id = cp.user_id
            JOIN users u2 ON j.recruiter_id = u2.user_id
            WHERE s.slot_id = %s
        """, (slot_id,))
        slot = cursor.fetchone()

        if not slot or slot['candidate_id'] != session['user_id']:
            return jsonify({"success": False, "message": "Proposed slot not found or unauthorized access"}), 403

        if slot['status'] != 'Pending':
            return jsonify({"success": False, "message": "This slot has already been processed"}), 400

        # TRANSACTION: Update slot status to Accepted
        cursor.execute("UPDATE interview_slots SET status = 'Accepted' WHERE slot_id = %s", (slot_id,))

        # Update other Pending slots for the same application to Declined
        cursor.execute("""
            UPDATE interview_slots 
            SET status = 'Declined' 
            WHERE application_id = %s AND slot_id != %s AND status = 'Pending'
        """, (slot['application_id'], slot_id))

        # Update application status to Interviewing
        cursor.execute("UPDATE applications SET status = 'Interviewing' WHERE application_id = %s", (slot['application_id'],))

        # Extract date and time from DATETIME
        dt = slot['interview_time']
        interview_date = dt.strftime('%Y-%m-%d')
        start_time = dt.strftime('%H:%M')
        
        # Calculate end time using duration_minutes
        end_dt = dt + timedelta(minutes=slot['duration_minutes'])
        end_time = end_dt.strftime('%H:%M')

        # Insert scheduled interview record
        cursor.execute("""
            INSERT INTO interviews (application_id, candidate_id, job_id, recruiter_id,
                interview_title, interview_type, interview_round, interview_date,
                start_time, end_time, timezone, meeting_link, office_address,
                instructions, contact_phone, interviewer_name, interviewer_email, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'IST', %s, %s, %s, %s, %s, %s, 'Scheduled')
        """, (slot['application_id'], slot['candidate_id'], slot['job_id'], slot['recruiter_id'],
              f"Interview for {slot['job_title']}", 'Online' if 'meet' in slot['location_details'].lower() or 'zoom' in slot['location_details'].lower() or 'teams' in slot['location_details'].lower() else 'Offline',
              'Technical', interview_date, start_time, end_time,
              slot['location_details'] if 'http' in slot['location_details'] else None,
              None if 'http' in slot['location_details'] else slot['location_details'],
              'Please join using the meeting link at the scheduled time.',
              None, slot['recruiter_name'], slot['recruiter_email']))
              
        interview_id = cursor.lastrowid
        db.commit()

        # Send interview invitation email
        interview_data = {
            'interview_id': interview_id,
            'interview_title': f"Interview for {slot['job_title']}",
            'interview_type': 'Online' if 'meet' in slot['location_details'].lower() or 'zoom' in slot['location_details'].lower() or 'teams' in slot['location_details'].lower() else 'Offline',
            'interview_round': 'Technical',
            'interview_date': interview_date,
            'start_time': start_time,
            'end_time': end_time,
            'timezone': 'IST',
            'meeting_link': slot['location_details'] if 'http' in slot['location_details'] else '',
            'office_address': '' if 'http' in slot['location_details'] else slot['location_details'],
            'instructions': 'Please join using the meeting link at the scheduled time.',
            'interviewer_name': slot['recruiter_name'],
            'interviewer_email': slot['recruiter_email']
        }

        email_success, email_error, email_subject = send_interview_invite(
            slot['candidate_name'], slot['candidate_email'],
            interview_data, slot['job_title'],
            slot['company_name'] or 'Our Company'
        )

        log_email(cursor, slot['candidate_email'], slot['candidate_name'],
                 'interview_invite', email_subject, slot['application_id'], interview_id,
                 'sent' if email_success else 'failed', email_error)
        db.commit()

        return jsonify({"success": True, "message": "Interview slot accepted and booked successfully!", "email_sent": email_success})

    except Exception as e:
        print(f"[ERROR] Accept slot: {e}")
        if 'db' in locals():
            db.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals() and db.open:
            db.close()


@app.route('/candidate/decline_slot/<int:slot_id>', methods=['POST'])
def decline_slot(slot_id):
    """Candidate declines a suggested interview slot."""
    if 'user_id' not in session or session.get('role') != 'candidate':
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        db = get_db_connection()
        cursor = db.cursor()

        # Fetch proposed slot details and verify ownership
        cursor.execute("""
            SELECT s.*, a.user_id AS candidate_id
            FROM interview_slots s
            JOIN applications a ON s.application_id = a.application_id
            WHERE s.slot_id = %s
        """, (slot_id,))
        slot = cursor.fetchone()

        if not slot or slot['candidate_id'] != session['user_id']:
            return jsonify({"success": False, "message": "Proposed slot not found or unauthorized access"}), 403

        if slot['status'] != 'Pending':
            return jsonify({"success": False, "message": "This slot has already been processed"}), 400

        # Update slot status to Declined
        cursor.execute("UPDATE interview_slots SET status = 'Declined' WHERE slot_id = %s", (slot_id,))
        db.commit()

        return jsonify({"success": True, "message": "Proposed slot declined successfully."})

    except Exception as e:
        print(f"[ERROR] Decline slot: {e}")
        if 'db' in locals():
            db.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals() and db.open:
            db.close()


# -----------------------------------------------------------------
# END INTERVIEW ROUTES
# -----------------------------------------------------------------

@app.route('/uploads/<path:filename>')
def download_resume(filename):
    """Securely serve uploaded resumes for download."""
    if os.path.exists(os.path.join(app.config['RESUME_UPLOAD_FOLDER'], filename)):
        return send_from_directory(app.config['RESUME_UPLOAD_FOLDER'], filename, as_attachment=True)
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/post_job', methods=['POST'])
def post_job():
    """Recruiter posts a new job."""
    if 'user_id' not in session or session.get('role') != 'recruiter':
        flash('Please log in as a recruiter to post jobs.', 'warning')
        return redirect(url_for('login'))
        
    title = request.form.get('title')
    job_type = request.form.get('job_type')
    location = request.form.get('location')
    salary_min = request.form.get('salary_min', '')
    salary_max = request.form.get('salary_max', '')
    description = request.form.get('description')
    
    if not title or not job_type or not location or not description:
        flash('Please fill out all required fields.', 'danger')
        return redirect(url_for('recruiter_dashboard'))
    
    salary = ""
    if salary_min and salary_max:
        salary = f"${salary_min} - ${salary_max}"
    elif salary_min:
        salary = f"${salary_min}+"
    elif salary_max:
        salary = f"Up to ${salary_max}"
        
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Ensure at least one company exists
        cursor.execute("SELECT company_id FROM companies LIMIT 1")
        company = cursor.fetchone()
        
        if company:
            company_id = company['company_id']
        else:
            # Create a default company if none exists to avoid foreign key errors
            cursor.execute("""
                INSERT INTO companies (company_name, location, description) 
                VALUES ('Default Company', 'Headquarters', 'Default company description.')
            """)
            db.commit()
            company_id = cursor.lastrowid
            
        # CREATE: Insert new job posting
        cursor.execute("""
            INSERT INTO jobs (recruiter_id, company_id, title, job_type, location, salary, skills_required) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (session['user_id'], company_id, title, job_type, location, salary, description))
        db.commit()
        
        flash('Job posted successfully!', 'success')
    except Exception as e:
        print(f"Database error while posting job: {e}")
        if 'db' in locals() and db.open:
            db.rollback()
        flash(f'An error occurred while posting the job: {e}', 'danger')
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals() and db.open:
            db.close()
            
    return redirect(url_for('recruiter_dashboard'))

@app.route('/delete_job/<int:job_id>', methods=['POST'])
def delete_job(job_id):
    """DELETE: Recruiter removes a job posting."""
    if 'user_id' not in session or session.get('role') != 'recruiter':
        return redirect(url_for('login'))
        
    db = get_db_connection()
    cursor = db.cursor()
    
    # DELETE: Delete the job (applications are CASCADE deleted by MySQL constraints)
    cursor.execute("DELETE FROM jobs WHERE job_id=%s AND recruiter_id=%s", (job_id, session['user_id']))
    db.commit()
    
    cursor.close()
    db.close()
    
    flash('Job deleted successfully!', 'success')
    return redirect(url_for('recruiter_dashboard'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)