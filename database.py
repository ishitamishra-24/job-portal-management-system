import pymysql

def get_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="root",
        database="jobportal",
        cursorclass=pymysql.cursors.DictCursor
    )

def create_index_if_not_exists(cursor, table, index_name, columns):
    try:
        cursor.execute(f"SHOW INDEX FROM {table} WHERE Key_name = %s", (index_name,))
        if not cursor.fetchone():
            cursor.execute(f"CREATE INDEX {index_name} ON {table}({columns})")
            print(f"Index {index_name} created on {table} for columns ({columns}).")
        else:
            print(f"Index {index_name} already exists on table {table}.")
    except Exception as e:
        print(f"Warning: Could not create index {index_name}: {e}")

def setup_database():
    try:
        # 1. Connect to MySQL server without database to create it if missing
        conn = pymysql.connect(
            host="localhost",
            user="root",
            password="root",
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS jobportal")
        conn.commit()
        cursor.close()
        conn.close()

        # 2. Connect to jobportal database for setup
        db = get_connection()
        cursor = db.cursor()
        
        print("Connected to database jobportal successfully. Setting up tables...")
        
        # Create users table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INT AUTO_INCREMENT PRIMARY KEY,
            fullname VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(100) NOT NULL,
            role ENUM('candidate', 'recruiter') NOT NULL,
            skills TEXT,
            phone VARCHAR(20) DEFAULT NULL,
            resume VARCHAR(255) DEFAULT NULL
        )
        """)
        print("Table 'users' setup completed.")
        
        # Create companies table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            company_id INT AUTO_INCREMENT PRIMARY KEY,
            company_name VARCHAR(100) NOT NULL,
            location VARCHAR(100),
            description TEXT
        )
        """)
        print("Table 'companies' setup completed.")

        # Create jobs table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id INT AUTO_INCREMENT PRIMARY KEY,
            recruiter_id INT,
            company_id INT,
            title VARCHAR(100) NOT NULL,
            skills_required TEXT,
            location VARCHAR(100),
            salary VARCHAR(50),
            job_type VARCHAR(50),
            posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (recruiter_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE SET NULL
        )
        """)
        print("Table 'jobs' setup completed.")

        # Create applications table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            application_id INT AUTO_INCREMENT PRIMARY KEY,
            job_id INT NOT NULL,
            user_id INT NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'New',
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        """)
        print("Table 'applications' setup completed.")

        # Create saved_jobs table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS saved_jobs (
            saved_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            job_id INT,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
        )
        """)

        # Create contact_messages table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS contact_messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100) NOT NULL,
            subject VARCHAR(150),
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Create application_history table for trigger logs
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS application_history (
            history_id INT AUTO_INCREMENT PRIMARY KEY,
            application_id INT,
            old_status VARCHAR(50),
            new_status VARCHAR(50),
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (application_id) REFERENCES applications(application_id) ON DELETE CASCADE
        )
        """)
        
        # Create candidate_profiles table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS candidate_profiles (
            profile_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT UNIQUE NOT NULL,
            full_name VARCHAR(100) NOT NULL,
            phone VARCHAR(20) DEFAULT NULL,
            skills TEXT,
            github_url VARCHAR(255) DEFAULT NULL,
            linkedin_url VARCHAR(255) DEFAULT NULL,
            portfolio_url VARCHAR(255) DEFAULT NULL,
            resume_path VARCHAR(255) DEFAULT NULL,
            resume_filename VARCHAR(255) DEFAULT NULL,
            headline VARCHAR(255) DEFAULT NULL,
            summary TEXT DEFAULT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        """)
        print("Table 'candidate_profiles' setup completed.")

        # Create interview_slots table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS interview_slots (
            slot_id INT AUTO_INCREMENT PRIMARY KEY,
            application_id INT NOT NULL,
            interview_time DATETIME NOT NULL,
            duration_minutes INT NOT NULL DEFAULT 30,
            location_details VARCHAR(255) DEFAULT NULL,
            status ENUM('Pending', 'Accepted', 'Declined') DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (application_id) REFERENCES applications(application_id) ON DELETE CASCADE
        )
        """)
        print("Table 'interview_slots' setup completed.")

        # Create work_experience table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS work_experience (
            experience_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            company_name VARCHAR(100) NOT NULL,
            job_title VARCHAR(100) NOT NULL,
            start_date DATE DEFAULT NULL,
            end_date DATE DEFAULT NULL,
            description TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        """)
        print("Table 'work_experience' setup completed.")

        # Create education table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS education (
            education_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            institution VARCHAR(100) NOT NULL,
            degree VARCHAR(100) NOT NULL,
            field_of_study VARCHAR(100) DEFAULT NULL,
            start_date DATE DEFAULT NULL,
            end_date DATE DEFAULT NULL,
            grade VARCHAR(20) DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        """)
        print("Table 'education' setup completed.")

        # Create job_alerts table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS job_alerts (
            alert_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            keyword VARCHAR(100) DEFAULT NULL,
            location VARCHAR(100) DEFAULT NULL,
            job_type VARCHAR(50) DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        """)
        print("Table 'job_alerts' setup completed.")

        # Create interviews table for interview scheduling system
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS interviews (
            interview_id INT AUTO_INCREMENT PRIMARY KEY,
            application_id INT NOT NULL,
            candidate_id INT NOT NULL,
            job_id INT NOT NULL,
            recruiter_id INT NOT NULL,
            interview_title VARCHAR(200) NOT NULL,
            interview_type ENUM('Online', 'Offline', 'Phone') NOT NULL,
            interview_round ENUM('HR', 'Technical', 'Final') NOT NULL,
            interview_date DATE NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            timezone VARCHAR(50) DEFAULT 'IST',
            meeting_link VARCHAR(500) DEFAULT NULL,
            office_address TEXT DEFAULT NULL,
            instructions TEXT DEFAULT NULL,
            required_documents TEXT DEFAULT NULL,
            contact_phone VARCHAR(20) DEFAULT NULL,
            interviewer_name VARCHAR(100) NOT NULL,
            interviewer_email VARCHAR(100) NOT NULL,
            status ENUM('Scheduled', 'Completed', 'Cancelled', 'Rescheduled') DEFAULT 'Scheduled',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (application_id) REFERENCES applications(application_id) ON DELETE CASCADE,
            FOREIGN KEY (candidate_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
            FOREIGN KEY (recruiter_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        """)
        print("Table 'interviews' setup completed.")

        # Create email_logs table for notification tracking
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_logs (
            log_id INT AUTO_INCREMENT PRIMARY KEY,
            recipient_email VARCHAR(100) NOT NULL,
            recipient_name VARCHAR(100),
            email_type ENUM('interview_invite', 'offer_letter', 'rejection', 'reschedule', 'cancellation') NOT NULL,
            subject VARCHAR(255) NOT NULL,
            application_id INT DEFAULT NULL,
            interview_id INT DEFAULT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status ENUM('sent', 'failed') DEFAULT 'sent',
            error_message TEXT DEFAULT NULL,
            FOREIGN KEY (application_id) REFERENCES applications(application_id) ON DELETE SET NULL
        )
        """)
        print("Table 'email_logs' setup completed.")
        
        # Migrate existing candidates from users to candidate_profiles if they don't have one
        cursor.execute("SELECT user_id, fullname, phone, skills, resume, github_link, linkedin_link FROM users WHERE role = 'candidate'")
        existing_candidates = cursor.fetchall()
        for cand in existing_candidates:
            cursor.execute("SELECT profile_id FROM candidate_profiles WHERE user_id = %s", (cand['user_id'],))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO candidate_profiles (user_id, full_name, phone, skills, resume_path, github_url, linkedin_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (cand['user_id'], cand['fullname'], cand['phone'], cand['skills'], cand['resume'], cand['github_link'], cand['linkedin_link']))
                print(f"Migrated user {cand['user_id']} to candidate_profiles.")
        
        # 3. SCHEMA MIGRATIONS (Checking and altering tables dynamically)
        db.commit()

        # Add github_link & linkedin_link columns to users table
        cursor.execute("SHOW COLUMNS FROM users LIKE 'github_link'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE users ADD COLUMN github_link VARCHAR(255) DEFAULT NULL")
            print("Added github_link column to users.")

        cursor.execute("SHOW COLUMNS FROM users LIKE 'linkedin_link'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE users ADD COLUMN linkedin_link VARCHAR(255) DEFAULT NULL")
            print("Added linkedin_link column to users.")

        # Add resume column to users table if missing
        cursor.execute("SHOW COLUMNS FROM users LIKE 'resume'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE users ADD COLUMN resume VARCHAR(255) DEFAULT NULL")
            print("Added resume column to users.")

        # Add posted_at column to jobs table if missing
        cursor.execute("SHOW COLUMNS FROM jobs LIKE 'posted_at'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE jobs ADD COLUMN posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
            print("Added posted_at column to jobs.")

        # Migrate missing candidate_profiles columns dynamically
        cursor.execute("SHOW COLUMNS FROM candidate_profiles LIKE 'headline'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE candidate_profiles ADD COLUMN headline VARCHAR(255) DEFAULT NULL")
            print("Added headline column to candidate_profiles.")

        cursor.execute("SHOW COLUMNS FROM candidate_profiles LIKE 'summary'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE candidate_profiles ADD COLUMN summary TEXT DEFAULT NULL")
            print("Added summary column to candidate_profiles.")

        cursor.execute("SHOW COLUMNS FROM candidate_profiles LIKE 'portfolio_url'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE candidate_profiles ADD COLUMN portfolio_url VARCHAR(255) DEFAULT NULL")
            print("Added portfolio_url column to candidate_profiles.")

        cursor.execute("SHOW COLUMNS FROM candidate_profiles LIKE 'resume_filename'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE candidate_profiles ADD COLUMN resume_filename VARCHAR(255) DEFAULT NULL")
            print("Added resume_filename column to candidate_profiles.")

        cursor.execute("SHOW COLUMNS FROM candidate_profiles LIKE 'updated_at'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE candidate_profiles ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
            print("Added updated_at column to candidate_profiles.")

        # 3.1. Modify status column to VARCHAR first to allow temporary invalid ENUM values
        cursor.execute("ALTER TABLE applications MODIFY COLUMN status VARCHAR(50)")
        db.commit()

        # Update application status values from old system ('Applied', 'Selected') to new system
        cursor.execute("UPDATE applications SET status = 'New' WHERE status = 'Applied'")
        cursor.execute("UPDATE applications SET status = 'Offered' WHERE status = 'Selected'")
        db.commit()

        # Alter applications status column to use the new ENUM values safely
        cursor.execute("""
            ALTER TABLE applications MODIFY COLUMN status 
            ENUM('New', 'Reviewed', 'Interviewing', 'Offered', 'Rejected') DEFAULT 'New'
        """)
        print("Updated applications status column schema to ENUM('New', 'Reviewed', 'Interviewing', 'Offered', 'Rejected').")

        # Migrate and alter interview_slots columns to match expected schema exactly
        cursor.execute("ALTER TABLE interview_slots MODIFY COLUMN status VARCHAR(50)")
        db.commit()
        cursor.execute("UPDATE interview_slots SET status = 'Pending' WHERE status = 'suggested' OR status IS NULL")
        cursor.execute("UPDATE interview_slots SET status = 'Accepted' WHERE status = 'accepted'")
        cursor.execute("UPDATE interview_slots SET status = 'Declined' WHERE status = 'declined'")
        db.commit()
        cursor.execute("""
            ALTER TABLE interview_slots 
            MODIFY COLUMN status ENUM('Pending', 'Accepted', 'Declined') DEFAULT 'Pending',
            MODIFY COLUMN duration_minutes INT NOT NULL DEFAULT 30,
            MODIFY COLUMN location_details VARCHAR(255) DEFAULT NULL
        """)
        print("Updated interview_slots column schemas successfully.")

        # 4. VIEW SETUP: Create job analytics view
        cursor.execute("""
            CREATE OR REPLACE VIEW job_analytics AS
            SELECT 
                j.job_id,
                j.title,
                j.recruiter_id,
                j.posted_at,
                c.company_name,
                COUNT(a.application_id) as total_applications,
                SUM(CASE WHEN a.status = 'New' THEN 1 ELSE 0 END) as total_new,
                SUM(CASE WHEN a.status = 'Reviewed' THEN 1 ELSE 0 END) as total_reviewed,
                SUM(CASE WHEN a.status = 'Interviewing' THEN 1 ELSE 0 END) as total_interviewing,
                SUM(CASE WHEN a.status = 'Offered' THEN 1 ELSE 0 END) as total_offers,
                SUM(CASE WHEN a.status = 'Rejected' THEN 1 ELSE 0 END) as total_rejections
            FROM jobs j
            LEFT JOIN companies c ON j.company_id = c.company_id
            LEFT JOIN applications a ON j.job_id = a.job_id
            GROUP BY j.job_id, j.title, j.recruiter_id, j.posted_at, c.company_name
        """)
        print("VIEW 'job_analytics' created/replaced successfully.")

        # 5. TRIGGER SETUP: Log status changes in application_history
        cursor.execute("DROP TRIGGER IF EXISTS after_application_status_update")
        cursor.execute("""
            CREATE TRIGGER after_application_status_update
            AFTER UPDATE ON applications
            FOR EACH ROW
            BEGIN
                IF OLD.status <> NEW.status THEN
                    INSERT INTO application_history (application_id, old_status, new_status)
                    VALUES (NEW.application_id, OLD.status, NEW.status);
                END IF;
            END;
        """)
        print("TRIGGER 'after_application_status_update' created/replaced successfully.")

        # 6. INDEX SETUP: Create indexes for database query optimization
        create_index_if_not_exists(cursor, "jobs", "idx_jobs_title", "title")
        create_index_if_not_exists(cursor, "jobs", "idx_jobs_recruiter", "recruiter_id")
        create_index_if_not_exists(cursor, "applications", "idx_applications_user", "user_id")
        create_index_if_not_exists(cursor, "applications", "idx_applications_job", "job_id")
        create_index_if_not_exists(cursor, "applications", "idx_applications_status", "status")

        # Indexes for interview scheduling system
        create_index_if_not_exists(cursor, "interviews", "idx_interviews_application", "application_id")
        create_index_if_not_exists(cursor, "interviews", "idx_interviews_candidate", "candidate_id")
        create_index_if_not_exists(cursor, "interviews", "idx_interviews_date", "interview_date")
        create_index_if_not_exists(cursor, "interviews", "idx_interviews_status", "status")
        create_index_if_not_exists(cursor, "email_logs", "idx_email_logs_recipient", "recipient_email")
        create_index_if_not_exists(cursor, "email_logs", "idx_email_logs_type", "email_type")

        db.commit()
        print("All database tables, view, trigger, and indexes created successfully!")
        
    except pymysql.MySQLError as e:
        print(f"Error setting up MySQL database: {e}")
    finally:
        if 'db' in locals() and db.open:
            cursor.close()
            db.close()

if __name__ == '__main__':
    setup_database()