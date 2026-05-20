"""Quick test to verify session persistence when navigating from dashboard to jobs."""
import requests

BASE = "http://127.0.0.1:5000"
s = requests.Session()

# Login as candidate
r = s.post(f"{BASE}/login", data={"email": "candidate@test.com", "password": "password"}, allow_redirects=False)
print(f"1. POST /login => {r.status_code} Location={r.headers.get('Location','(none)')}")

# Follow redirect to dashboard
r2 = s.get(f"{BASE}/candidate/dashboard")
print(f"2. GET /candidate/dashboard => {r2.status_code}")
has_logout_dashboard = "Logout" in r2.text
print(f"   Dashboard shows 'Logout' button: {has_logout_dashboard}")

# Navigate to /jobs (this is what happens when candidate clicks 'Find Jobs')
r3 = s.get(f"{BASE}/jobs")
print(f"3. GET /jobs => {r3.status_code}")
has_logout_jobs = "Logout" in r3.text
has_dashboard_btn = "Dashboard" in r3.text and "btn-outline-custom" in r3.text
has_login_btn = 'Login</a>' in r3.text and 'Register</a>' in r3.text
print(f"   Jobs page shows 'Logout' button: {has_logout_jobs}")
print(f"   Jobs page shows 'Dashboard' button: {has_dashboard_btn}")
print(f"   Jobs page shows Login/Register (public state): {has_login_btn}")

if has_logout_jobs and has_dashboard_btn:
    print("\n✅ Session IS preserved - candidate is authenticated on /jobs page")
else:
    print("\n❌ Session LOST - candidate sees public /jobs page without auth")
