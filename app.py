from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import pymysql

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_session_management'  # Replace with a secure key in production

# Directory for uploads (e.g., resumes, profile pictures)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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
    """Home page with hero section, search, and featured jobs."""
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
    
    cursor.close()
    db.close()
    
    return render_template('index.html', featured_jobs=featured_jobs)

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
            session['user_id'] = user['user_id']
            session['role'] = user['role']
            session['name'] = user['fullname']
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
        except Exception as e:
            print(e)
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
        
        cursor.close()
        db.close()
        
        session['user_id'] = new_user_id
        session['name'] = name
        session['role'] = role
        
        flash('Registration successful! Welcome!', 'success')
        if role == 'recruiter':
            return redirect(url_for('recruiter_dashboard'))
        else:
            return redirect(url_for('candidate_dashboard'))
        
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
    """Detailed view for a specific job."""
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
    
    cursor.close()
    db.close()
    
    return render_template('job_details.html', job=job, similar_jobs=similar_jobs)

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
            cursor.execute("INSERT INTO applications (job_id, user_id) VALUES (%s, %s)", (job_id, session['user_id']))
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
    """Dashboard for candidates to view applied jobs and profile."""
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
    
    cursor.close()
    db.close()
    
    return render_template('candidate_dashboard.html', applied_jobs=applied_jobs, total_applied=total_applied)

@app.route('/upload_resume', methods=['POST'])
def upload_resume():
    if 'user_id' not in session or session.get('role') != 'candidate':
        flash('Please log in as a candidate to upload resume.', 'warning')
        return redirect(url_for('login'))
        
    if 'resume' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('candidate_dashboard'))
        
    file = request.files['resume']
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('candidate_dashboard'))
        
    if file:
        filename = f"resume_user_{session['user_id']}_{file.filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        # Here you would typically save the filename to the database (e.g., users table)
        # For now, we just save it locally and flash success
        flash('Resume uploaded successfully!', 'success')
        return redirect(url_for('candidate_dashboard'))
@app.route('/recruiter/dashboard')
def recruiter_dashboard():
    """Dashboard for recruiters to manage jobs and view applicants."""
    if 'user_id' not in session or session.get('role') != 'recruiter':
        flash('Please log in as a recruiter to access this page.', 'warning')
        return redirect(url_for('login'))
        
    db = get_db_connection()
    cursor = db.cursor()
    
    # READ: Fetch jobs posted by this recruiter
    cursor.execute("""
        SELECT jobs.*, COUNT(applications.application_id) as app_count 
        FROM jobs 
        LEFT JOIN applications ON jobs.job_id = applications.job_id
        WHERE jobs.recruiter_id = %s
        GROUP BY jobs.job_id
        ORDER BY jobs.job_id DESC
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
    
    # DELETE: Delete the job (applications might fail if no cascade, let's delete applications first)
    cursor.execute("DELETE FROM applications WHERE job_id=%s", (job_id,))
    cursor.execute("DELETE FROM saved_jobs WHERE job_id=%s", (job_id,))
    cursor.execute("DELETE FROM jobs WHERE job_id=%s AND recruiter_id=%s", (job_id, session['user_id']))
    db.commit()
    
    cursor.close()
    db.close()
    
    flash('Job deleted successfully!', 'success')
    return redirect(url_for('recruiter_dashboard'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)