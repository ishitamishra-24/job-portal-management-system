import pymysql

def get_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="root",
        database="jobportal",
        cursorclass=pymysql.cursors.DictCursor
    )

def setup_database():
    try:
        db = get_connection()
        cursor = db.cursor()
        
        print("Connected to database successfully. Creating tables...")
        
        # Create users table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            role ENUM('candidate', 'recruiter') NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create jobs table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            recruiter_id INT NOT NULL,
            title VARCHAR(200) NOT NULL,
            job_type VARCHAR(50) NOT NULL,
            location VARCHAR(100) NOT NULL,
            salary_min INT,
            salary_max INT,
            description TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (recruiter_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)

        # Create applications table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            job_id INT NOT NULL,
            candidate_id INT NOT NULL,
            status VARCHAR(50) DEFAULT 'Under Review',
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
            FOREIGN KEY (candidate_id) REFERENCES users(id) ON DELETE CASCADE
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
        
        db.commit()
        print("Database tables created successfully!")
        
    except pymysql.MySQLError as e:
        print(f"Error connecting to MySQL: {e}")
    finally:
        if 'db' in locals() and db.open:
            cursor.close()
            db.close()

if __name__ == '__main__':
    setup_database()