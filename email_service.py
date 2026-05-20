"""
Email Service Module for JobPortal Interview Scheduling System.
Uses Python built-in smtplib + email.mime — no extra pip packages required.
SMTP credentials loaded from .env via os.getenv().
"""

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# SMTP Configuration from environment variables
MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
MAIL_SENDER_NAME = os.getenv('MAIL_SENDER_NAME', 'JobPortal Recruitment')


def _send_email(recipient_email, subject, html_body, ics_content=None):
    """
    Internal helper: sends an HTML email via SMTP with optional .ics attachment.
    Returns (True, None) on success, (False, error_message) on failure.
    """
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        print("[EMAIL] SMTP credentials not configured in .env — skipping email send.")
        return False, "SMTP credentials not configured"

    try:
        msg = MIMEMultipart('mixed')
        msg['From'] = f"{MAIL_SENDER_NAME} <{MAIL_USERNAME}>"
        msg['To'] = recipient_email
        msg['Subject'] = subject

        # Attach HTML body
        html_part = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(html_part)

        # Attach .ics calendar file if provided
        if ics_content:
            ics_part = MIMEBase('text', 'calendar', method='REQUEST')
            ics_part.set_payload(ics_content.encode('utf-8'))
            encoders.encode_base64(ics_part)
            ics_part.add_header('Content-Disposition', 'attachment', filename='interview.ics')
            msg.attach(ics_part)

        # Connect and send
        server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.sendmail(MAIL_USERNAME, recipient_email, msg.as_string())
        server.quit()

        print(f"[EMAIL] Successfully sent email to {recipient_email}: {subject}")
        return True, None

    except Exception as e:
        error_msg = str(e)
        print(f"[EMAIL] Failed to send email to {recipient_email}: {error_msg}")
        return False, error_msg


def generate_ics(interview_data):
    """
    Generate an .ics calendar file string from interview data dictionary.
    Uses manual RFC 5545 format — no external icalendar package needed.
    """
    # Parse date and times
    interview_date = interview_data.get('interview_date')  # 'YYYY-MM-DD'
    start_time = interview_data.get('start_time')  # 'HH:MM'
    end_time = interview_data.get('end_time')  # 'HH:MM'

    if isinstance(interview_date, str):
        date_obj = datetime.strptime(interview_date, '%Y-%m-%d')
    else:
        date_obj = interview_date

    if isinstance(start_time, str):
        start_dt = datetime.combine(date_obj.date() if isinstance(date_obj, datetime) else date_obj,
                                     datetime.strptime(start_time, '%H:%M').time())
    elif hasattr(start_time, 'seconds') or hasattr(start_time, 'total_seconds'):
        # timedelta from MySQL TIME field
        total_secs = int(start_time.total_seconds()) if hasattr(start_time, 'total_seconds') else int(start_time.seconds)
        hours, remainder = divmod(total_secs, 3600)
        minutes, _ = divmod(remainder, 60)
        start_dt = datetime.combine(date_obj.date() if isinstance(date_obj, datetime) else date_obj,
                                     datetime.strptime(f"{hours:02d}:{minutes:02d}", '%H:%M').time())
    else:
        start_dt = datetime.combine(date_obj.date() if isinstance(date_obj, datetime) else date_obj,
                                     start_time)

    if isinstance(end_time, str):
        end_dt = datetime.combine(date_obj.date() if isinstance(date_obj, datetime) else date_obj,
                                   datetime.strptime(end_time, '%H:%M').time())
    elif hasattr(end_time, 'seconds') or hasattr(end_time, 'total_seconds'):
        total_secs = int(end_time.total_seconds()) if hasattr(end_time, 'total_seconds') else int(end_time.seconds)
        hours, remainder = divmod(total_secs, 3600)
        minutes, _ = divmod(remainder, 60)
        end_dt = datetime.combine(date_obj.date() if isinstance(date_obj, datetime) else date_obj,
                                   datetime.strptime(f"{hours:02d}:{minutes:02d}", '%H:%M').time())
    else:
        end_dt = datetime.combine(date_obj.date() if isinstance(date_obj, datetime) else date_obj,
                                   end_time)

    now = datetime.utcnow()
    uid = f"interview-{interview_data.get('interview_id', 0)}@jobportal.com"

    location = interview_data.get('meeting_link') or interview_data.get('office_address') or 'TBD'
    description = interview_data.get('instructions') or 'Interview scheduled via JobPortal'

    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//JobPortal//Interview//EN
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VEVENT
UID:{uid}
DTSTART:{start_dt.strftime('%Y%m%dT%H%M%S')}
DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}
DTSTAMP:{now.strftime('%Y%m%dT%H%M%SZ')}
SUMMARY:{interview_data.get('interview_title', 'Interview')}
DESCRIPTION:{description}
LOCATION:{location}
ORGANIZER;CN={interview_data.get('interviewer_name', 'Recruiter')}:mailto:{interview_data.get('interviewer_email', '')}
STATUS:CONFIRMED
BEGIN:VALARM
TRIGGER:-PT30M
ACTION:DISPLAY
DESCRIPTION:Interview in 30 minutes
END:VALARM
END:VEVENT
END:VCALENDAR"""
    return ics


def send_interview_invite(candidate_name, candidate_email, interview_data, job_title, company_name):
    """Send a professional HTML interview invitation email with .ics attachment."""
    
    interview_type = interview_data.get('interview_type', 'Online')
    interview_round = interview_data.get('interview_round', 'HR')
    
    # Format date
    raw_date = interview_data.get('interview_date')
    if isinstance(raw_date, str):
        formatted_date = datetime.strptime(raw_date, '%Y-%m-%d').strftime('%B %d, %Y')
    else:
        formatted_date = raw_date.strftime('%B %d, %Y') if raw_date else 'TBD'
    
    # Format times
    def format_time(t):
        if isinstance(t, str):
            return datetime.strptime(t, '%H:%M').strftime('%I:%M %p')
        elif hasattr(t, 'total_seconds'):
            total = int(t.total_seconds())
            h, m = divmod(total, 3600)
            m = m // 60
            return datetime.strptime(f"{h:02d}:{m:02d}", '%H:%M').strftime('%I:%M %p')
        elif hasattr(t, 'strftime'):
            return t.strftime('%I:%M %p')
        return str(t)
    
    start_time = format_time(interview_data.get('start_time', ''))
    end_time = format_time(interview_data.get('end_time', ''))
    
    # Location info
    if interview_type == 'Online':
        location_html = f'<a href="{interview_data.get("meeting_link", "#")}" style="color:#3b82f6;text-decoration:none;font-weight:600;">🔗 Join Meeting Link</a>'
    elif interview_type == 'Offline':
        location_html = f'📍 {interview_data.get("office_address", "Office address to be shared")}'
    else:
        location_html = f'📞 You will receive a call at the scheduled time'
    
    instructions = interview_data.get('instructions', '')
    required_docs = interview_data.get('required_documents', '')
    
    subject = f"Interview Scheduled — {job_title} ({interview_round} Round)"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin:0;padding:0;background:#f4f6f9;font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;">
        <div style="max-width:600px;margin:30px auto;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,0.08);">
            
            <!-- Header -->
            <div style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%);padding:40px 30px;text-align:center;">
                <h1 style="color:#ffffff;margin:0 0 8px 0;font-size:22px;">📅 Interview Scheduled</h1>
                <p style="color:#94a3b8;margin:0;font-size:14px;">{company_name} • {job_title}</p>
            </div>
            
            <!-- Body -->
            <div style="padding:30px;">
                <p style="font-size:16px;color:#334155;margin-bottom:20px;">
                    Dear <strong>{candidate_name}</strong>,
                </p>
                <p style="font-size:14px;color:#475569;line-height:1.7;margin-bottom:24px;">
                    We are pleased to inform you that your <strong>{interview_round} Round</strong> interview for the 
                    <strong>{job_title}</strong> position has been scheduled. Please find the details below:
                </p>
                
                <!-- Interview Details Card -->
                <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:24px;margin-bottom:24px;">
                    <h3 style="color:#0f172a;margin:0 0 16px 0;font-size:16px;border-bottom:2px solid #3b82f6;padding-bottom:8px;">
                        {interview_data.get('interview_title', 'Interview Session')}
                    </h3>
                    <table style="width:100%;border-collapse:collapse;font-size:14px;color:#475569;">
                        <tr>
                            <td style="padding:8px 0;font-weight:600;width:140px;vertical-align:top;">📅 Date</td>
                            <td style="padding:8px 0;">{formatted_date}</td>
                        </tr>
                        <tr>
                            <td style="padding:8px 0;font-weight:600;vertical-align:top;">⏰ Time</td>
                            <td style="padding:8px 0;">{start_time} — {end_time} ({interview_data.get('timezone', 'IST')})</td>
                        </tr>
                        <tr>
                            <td style="padding:8px 0;font-weight:600;vertical-align:top;">🎯 Round</td>
                            <td style="padding:8px 0;"><span style="background:#dbeafe;color:#1d4ed8;padding:3px 12px;border-radius:20px;font-size:13px;font-weight:600;">{interview_round}</span></td>
                        </tr>
                        <tr>
                            <td style="padding:8px 0;font-weight:600;vertical-align:top;">💻 Mode</td>
                            <td style="padding:8px 0;">{interview_type}</td>
                        </tr>
                        <tr>
                            <td style="padding:8px 0;font-weight:600;vertical-align:top;">📍 Location</td>
                            <td style="padding:8px 0;">{location_html}</td>
                        </tr>
                    </table>
                </div>
                
                {"<div style='background:#fffbeb;border:1px solid #fbbf24;border-radius:10px;padding:16px;margin-bottom:20px;'><p style=\"margin:0;font-size:13px;color:#92400e;\"><strong>📋 Instructions:</strong><br>" + instructions + "</p></div>" if instructions else ""}
                
                {"<div style='background:#f0fdf4;border:1px solid #86efac;border-radius:10px;padding:16px;margin-bottom:20px;'><p style=\"margin:0;font-size:13px;color:#166534;\"><strong>📄 Required Documents:</strong><br>" + required_docs + "</p></div>" if required_docs else ""}
                
                <!-- Interviewer Contact -->
                <div style="background:#f1f5f9;border-radius:10px;padding:16px;margin-bottom:24px;">
                    <p style="margin:0 0 6px 0;font-size:13px;font-weight:700;color:#334155;">Interviewer Contact</p>
                    <p style="margin:0;font-size:13px;color:#64748b;">
                        👤 {interview_data.get('interviewer_name', 'Recruiter')} &nbsp;|&nbsp; 
                        ✉️ {interview_data.get('interviewer_email', '')}
                        {(" &nbsp;|&nbsp; 📞 " + interview_data.get('contact_phone')) if interview_data.get('contact_phone') else ''}
                    </p>
                </div>
                
                <p style="font-size:13px;color:#94a3b8;text-align:center;margin-top:30px;">
                    Please log in to your <strong>JobPortal Dashboard</strong> for the latest updates.
                </p>
            </div>
            
            <!-- Footer -->
            <div style="background:#f8fafc;padding:20px 30px;text-align:center;border-top:1px solid #e2e8f0;">
                <p style="margin:0;font-size:12px;color:#94a3b8;">© 2026 JobPortal. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Generate .ics calendar attachment
    ics_content = generate_ics(interview_data)
    
    success, error = _send_email(candidate_email, subject, html_body, ics_content)
    return success, error, subject


def send_offer_email(candidate_name, candidate_email, job_title, company_name, recruiter_name):
    """Send a professional congratulations/offer email."""
    
    subject = f"🎉 Congratulations! You Have Been Selected — {job_title}"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin:0;padding:0;background:#f4f6f9;font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;">
        <div style="max-width:600px;margin:30px auto;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,0.08);">
            
            <!-- Header -->
            <div style="background:linear-gradient(135deg,#065f46 0%,#047857 50%,#10b981 100%);padding:45px 30px;text-align:center;">
                <div style="font-size:48px;margin-bottom:12px;">🏆</div>
                <h1 style="color:#ffffff;margin:0 0 8px 0;font-size:24px;">Congratulations!</h1>
                <p style="color:#a7f3d0;margin:0;font-size:14px;">You've been selected for the position</p>
            </div>
            
            <!-- Body -->
            <div style="padding:30px;">
                <p style="font-size:16px;color:#334155;margin-bottom:20px;">
                    Dear <strong>{candidate_name}</strong>,
                </p>
                <p style="font-size:14px;color:#475569;line-height:1.8;margin-bottom:24px;">
                    We are thrilled to inform you that after careful evaluation of your candidacy, 
                    you have been <strong style="color:#059669;">selected</strong> for the 
                    <strong>{job_title}</strong> position at <strong>{company_name}</strong>.
                </p>
                
                <div style="background:linear-gradient(135deg,#f0fdf4,#ecfdf5);border:2px solid #86efac;border-radius:12px;padding:24px;margin-bottom:24px;text-align:center;">
                    <h3 style="color:#065f46;margin:0 0 8px 0;font-size:18px;">🎯 Your New Role</h3>
                    <p style="color:#047857;font-size:20px;font-weight:700;margin:0;">{job_title}</p>
                    <p style="color:#6b7280;font-size:13px;margin:8px 0 0 0;">at {company_name}</p>
                </div>
                
                <div style="background:#f8fafc;border-radius:10px;padding:20px;margin-bottom:24px;">
                    <h4 style="color:#0f172a;margin:0 0 12px 0;font-size:15px;">📋 Next Steps</h4>
                    <ol style="margin:0;padding-left:20px;color:#475569;font-size:14px;line-height:2;">
                        <li>Our HR team will contact you with the formal offer letter</li>
                        <li>Complete any pending document verification</li>
                        <li>Confirm your joining date with the recruitment team</li>
                    </ol>
                </div>
                
                <div style="background:#f1f5f9;border-radius:10px;padding:16px;">
                    <p style="margin:0;font-size:13px;color:#334155;">
                        <strong>Recruitment Contact:</strong> {recruiter_name} &nbsp;|&nbsp;
                        Reply to this email for any queries.
                    </p>
                </div>
            </div>
            
            <!-- Footer -->
            <div style="background:#f8fafc;padding:20px 30px;text-align:center;border-top:1px solid #e2e8f0;">
                <p style="margin:0;font-size:12px;color:#94a3b8;">© 2026 JobPortal. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    success, error = _send_email(candidate_email, subject, html_body)
    return success, error, subject


def send_rejection_email(candidate_name, candidate_email, job_title, company_name):
    """Send a polite, professional rejection email."""
    
    subject = f"Update on Your Application — {job_title}"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin:0;padding:0;background:#f4f6f9;font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;">
        <div style="max-width:600px;margin:30px auto;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,0.08);">
            
            <!-- Header -->
            <div style="background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);padding:40px 30px;text-align:center;">
                <h1 style="color:#ffffff;margin:0 0 8px 0;font-size:20px;">Application Status Update</h1>
                <p style="color:#94a3b8;margin:0;font-size:14px;">{company_name} • {job_title}</p>
            </div>
            
            <!-- Body -->
            <div style="padding:30px;">
                <p style="font-size:16px;color:#334155;margin-bottom:20px;">
                    Dear <strong>{candidate_name}</strong>,
                </p>
                <p style="font-size:14px;color:#475569;line-height:1.8;margin-bottom:20px;">
                    Thank you for your interest in the <strong>{job_title}</strong> position at 
                    <strong>{company_name}</strong> and for investing your time in the application process.
                </p>
                <p style="font-size:14px;color:#475569;line-height:1.8;margin-bottom:24px;">
                    After careful consideration, we regret to inform you that we have decided to move forward 
                    with other candidates whose qualifications more closely align with the current requirements 
                    of this role.
                </p>
                
                <div style="background:#fefce8;border:1px solid #fde68a;border-radius:10px;padding:20px;margin-bottom:24px;">
                    <p style="margin:0;font-size:14px;color:#92400e;line-height:1.7;">
                        💡 <strong>Don't give up!</strong> This decision does not reflect your overall abilities. 
                        We encourage you to apply for future openings that match your skill set. 
                        Your profile will remain in our database for future opportunities.
                    </p>
                </div>
                
                <p style="font-size:14px;color:#475569;line-height:1.8;">
                    We sincerely wish you the very best in your career journey and future endeavors.
                </p>
                
                <p style="font-size:14px;color:#334155;margin-top:24px;">
                    Warm regards,<br>
                    <strong>{company_name} Recruitment Team</strong>
                </p>
            </div>
            
            <!-- Footer -->
            <div style="background:#f8fafc;padding:20px 30px;text-align:center;border-top:1px solid #e2e8f0;">
                <p style="margin:0;font-size:12px;color:#94a3b8;">© 2026 JobPortal. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    success, error = _send_email(candidate_email, subject, html_body)
    return success, error, subject


def log_email(cursor, recipient_email, recipient_name, email_type, subject, 
              application_id=None, interview_id=None, status='sent', error_message=None):
    """Log an email send attempt to the email_logs database table."""
    try:
        cursor.execute("""
            INSERT INTO email_logs (recipient_email, recipient_name, email_type, subject, 
                                     application_id, interview_id, status, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (recipient_email, recipient_name, email_type, subject,
              application_id, interview_id, status, error_message))
    except Exception as e:
        print(f"[EMAIL LOG] Failed to log email: {e}")
