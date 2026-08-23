import os
import sys
import json
import time
import email
import imaplib
import smtplib
import random
import datetime
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict, Any
import requests

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from backend.database import init_db, insert_email, log_event, get_analytics_stats
except ImportError:
    from database import init_db, insert_email, log_event, get_analytics_stats

# Ensure database is initialized
init_db()

API_URL = os.environ.get("API_URL", "http://localhost:8000")
ENV_PATH = os.path.join(BASE_DIR, ".env")
LEGACY_LOG_FILE = os.path.join(BASE_DIR, "automation_logs.json")

# Load environment variables
def load_env():
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")

load_env()

# Realistic simulation emails for mock mode
SIMULATED_EMAILS = [
    {
        "sender": "sarah.jenkins@techcorp.io",
        "subject": "Sprint Review & Demo Agenda for Thursday",
        "body": "Hi team,\n\nPlease find the agenda for our upcoming Sprint Review on Thursday at 2:00 PM EST. We will demo the new user authentication module and review open bug tickets.\n\nLet me know if you have items to add."
    },
    {
        "sender": "security-alert@verify-paypal-service.com",
        "subject": "URGENT: Your Account Has Been Suspended",
        "body": "Dear valued customer,\n\nWe detected suspicious activity on your account. Your account access has been limited. Please click the link below immediately to verify your identity and restore access: http://bit.ly/secure-paypal-login\n\nFailure to verify within 24 hours will lead to permanent termination."
    },
    {
        "sender": "alex.m@clientdomain.com",
        "subject": "Feedback on Q3 Project Proposal",
        "body": "Hi Kevin,\n\nI went through the proposal you sent over. Overall looks very solid! Could we schedule a quick 20-minute call tomorrow at 11 AM to discuss the pricing breakdown and implementation timeline?\n\nThanks,\nAlex"
    },
    {
        "sender": "support@cloudhosting.net",
        "subject": "Scheduled Maintenance Notification for Sunday",
        "body": "Dear Customer,\n\nThis is an advance notice that scheduled server maintenance will take place this Sunday from 02:00 UTC to 04:00 UTC. Brief downtime of up to 10 minutes may occur. No action is required on your part."
    },
    {
        "sender": "exclusive-deals@rolex-outlet-discount.net",
        "subject": "LIMITED TIME: 90% Off Luxury Watches & Gift Cards",
        "body": "Congratulations! You have been selected for our VIP flash sale. Get 90% discount on all luxury watches and claim a free $500 gift card today only! Click here to shop now."
    },
    {
        "sender": "hr-department@acmecorp.com",
        "subject": "Action Required: Complete Annual Benefits Enrollment",
        "body": "Hi everyone,\n\nFriendly reminder that the open enrollment period for 2026 benefits closes this Friday at 5:00 PM. Please make sure to submit your selections in the HR portal before the deadline."
    },
    {
        "sender": "priya.sharma@investments.org",
        "subject": "Invoice #8942 - Consulting Services",
        "body": "Good afternoon,\n\nPlease find attached invoice #8942 for consulting services rendered in August. Kindly confirm receipt and process payment before the due date on Sept 15.\n\nBest regards,\nPriya"
    }
]

def clean_header(header_value: str) -> str:
    """Decode encoded email header string."""
    if not header_value:
        return ""
    decoded_parts = decode_header(header_value)
    result = []
    for text, encoding in decoded_parts:
        if isinstance(text, bytes):
            try:
                result.append(text.decode(encoding or "utf-8", errors="ignore"))
            except:
                result.append(text.decode("latin1", errors="ignore"))
        else:
            result.append(str(text))
    return "".join(result)

def extract_body(msg: email.message.Message) -> str:
    """Extract plain text body from email message."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
                    break
            elif content_type == "text/html" and not body and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    html_str = payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
                    # Simple strip of HTML tags
                    import re
                    body = re.sub(r"<[^>]+>", " ", html_str)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode(msg.get_content_charset() or "utf-8", errors="ignore")
    return body.strip()

def fetch_imap_emails():
    """Fetch unread emails from IMAP inbox."""
    imap_server = os.environ.get("IMAP_SERVER", "imap.gmail.com")
    imap_port = int(os.environ.get("IMAP_PORT", 993))
    imap_user = os.environ.get("IMAP_USER")
    imap_pass = os.environ.get("IMAP_PASS")

    if not imap_user or not imap_pass:
        return None

    emails_fetched = []
    try:
        mail = imaplib.IMAP4_SSL(imap_server, imap_port)
        mail.login(imap_user, imap_pass)
        mail.select("INBOX")

        # Search for unseen emails
        status, messages = mail.search(None, "UNSEEN")
        if status != "OK" or not messages[0]:
            mail.logout()
            return []

        email_ids = messages[0].split()
        for e_id in email_ids[:5]:  # Fetch up to 5 at a time
            status, data = mail.fetch(e_id, "(RFC822)")
            if status != "OK":
                continue
            
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            sender = clean_header(msg.get("From", "Unknown"))
            subject = clean_header(msg.get("Subject", "No Subject"))
            body = extract_body(msg)

            if body:
                emails_fetched.append({
                    "sender": sender,
                    "subject": subject,
                    "body": body,
                    "source": "imap"
                })

        mail.logout()
        return emails_fetched

    except Exception as e:
        log_event("ERROR", f"IMAP connection failed: {str(e)}")
        print(f"[-] IMAP Error: {e}")
        return None

def sync_legacy_json(record: dict):
    """Maintain automation_logs.json for backwards compatibility."""
    logs = []
    if os.path.exists(LEGACY_LOG_FILE):
        try:
            with open(LEGACY_LOG_FILE, "r") as f:
                logs = json.load(f)
        except:
            logs = []
    
    logs.insert(0, record)
    logs = logs[:50]
    try:
        with open(LEGACY_LOG_FILE, "w") as f:
            json.dump(logs, f, indent=4)
    except:
        pass

def process_email_item(email_item: dict):
    sender = email_item.get("sender", "unknown@domain.com")
    subject = email_item.get("subject", "No Subject")
    body = email_item.get("body", "")
    source = email_item.get("source", "mock")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n[+] Processing email from: {sender} | Subject: '{subject}'")

    # Step 1: Predict Spam
    is_spam = False
    spam_conf = 0.0
    try:
        pred_resp = requests.post(
            f"{API_URL}/predict",
            json={"text": body, "subject": subject, "sender": sender},
            timeout=5
        )
        if pred_resp.status_code == 200:
            pdata = pred_resp.json()
            is_spam = pdata.get("is_spam", False)
            spam_conf = pdata.get("confidence", 0.0)
    except Exception as e:
        print(f"  [!] Predict API error, evaluating offline: {e}")
        from model.train import load_data
        # Simple fallback check
        is_spam = any(w in body.lower() for w in ["winner", "suspended", "gift card", "rolex", "click here", "90% off"])
        spam_conf = 0.85 if is_spam else 0.80

    if is_spam:
        print(f"  [!] SPAM DETECTED (Confidence: {spam_conf:.2f}). Moving to spam.")
        db_record = {
            "sender": sender,
            "subject": subject,
            "body": body,
            "is_spam": True,
            "spam_confidence": spam_conf,
            "category": "Spam",
            "urgency": "Low",
            "sentiment": "Negative",
            "action_items": [],
            "reply": "No reply generated (Flagged as Spam).",
            "status": "Moved to Spam",
            "source": source,
            "created_at": now_str
        }
        insert_email(db_record)
        log_event("WARNING", f"Spam blocked from {sender}: {subject}")
        sync_legacy_json({
            "timestamp": now_str,
            "email_snippet": body[:100],
            "full_body": body,
            "status": "Moved to Spam",
            "is_spam": True,
            "spam_confidence": spam_conf,
            "category": "Spam",
            "reply": "No reply generated (Spam)."
        })
        return

    # Step 2: Categorize & Urgency
    category = "Personal"
    urgency = "Medium"
    sentiment = "Neutral"
    try:
        cat_resp = requests.post(
            f"{API_URL}/categorize",
            json={"text": body, "subject": subject},
            timeout=2
        )
        if cat_resp.status_code == 200:
            cdata = cat_resp.json()
            category = cdata.get("category", "Personal")
            urgency = cdata.get("urgency", "Medium")
            sentiment = cdata.get("sentiment", "Neutral")
    except Exception as e:
        print(f"  [!] Categorize API error: {e}")

    print(f"  [->] Categorized as: {category} | Urgency: {urgency} | Sentiment: {sentiment}")

    # Step 3: Extract Action Items
    action_items = []
    try:
        act_resp = requests.post(
            f"{API_URL}/extract-actions",
            json={"text": body},
            timeout=2
        )
        if act_resp.status_code == 200:
            action_items = act_resp.json().get("action_items", [])
    except:
        pass

    # Step 4: Generate Smart Reply
    reply_text = ""
    try:
        rep_resp = requests.post(
            f"{API_URL}/reply",
            json={
                "text": body,
                "sender": sender,
                "subject": subject,
                "tone": "Professional"
            },
            timeout=2
        )
        if rep_resp.status_code == 200:
            reply_text = rep_resp.json().get("reply", "")
    except Exception as e:
        print(f"  [!] Reply API error: {e}")
        reply_text = "Thank you for your email. I have received it and will follow up shortly."

    print("  [->] Smart Reply drafted.")

    # Save to Database
    db_record = {
        "sender": sender,
        "subject": subject,
        "body": body,
        "is_spam": False,
        "spam_confidence": spam_conf,
        "category": category,
        "urgency": urgency,
        "sentiment": sentiment,
        "action_items": action_items,
        "reply": reply_text,
        "status": "Drafted",
        "source": source,
        "created_at": now_str
    }
    insert_email(db_record)
    log_event("INFO", f"Processed email from {sender} -> Category: {category}")

    sync_legacy_json({
        "timestamp": now_str,
        "email_snippet": body[:100],
        "full_body": body,
        "status": "Replied (Drafted)",
        "is_spam": False,
        "spam_confidence": spam_conf,
        "category": category,
        "reply": reply_text
    })

def run_worker_loop(interval_seconds: int = 10, max_iterations: Optional[int] = None):
    print("=" * 60)
    print(">>> AI Email Automated Inbox Processor Started")
    print(f"Backend API URL: {API_URL}")
    print(f"Database: SQLite (email_assistant.db)")
    print("=" * 60)

    iteration = 0
    while True:
        try:
            iteration += 1
            load_env()
            
            # Check real IMAP first
            imap_emails = fetch_imap_emails()
            
            if imap_emails is not None:
                if imap_emails:
                    print(f"\n[+] Found {len(imap_emails)} unread emails via IMAP.")
                    for em in imap_emails:
                        process_email_item(em)
                else:
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] IMAP checked - no new unread emails.")
            else:
                # Simulation Mock Mode
                if random.random() > 0.35:  # 65% chance of simulated email arriving
                    sim_email = random.choice(SIMULATED_EMAILS).copy()
                    sim_email["source"] = "mock"
                    process_email_item(sim_email)
                else:
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Inbox idle. Waiting for incoming emails...")

            if max_iterations and iteration >= max_iterations:
                print(f"[+] Reached maximum test iterations ({max_iterations}). Stopping worker.")
                break

            time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print("\n[!] Shutting down automation worker.")
            break
        except Exception as e:
            print(f"[-] Worker loop error: {e}")
            log_event("ERROR", f"Worker loop error: {str(e)}")
            time.sleep(interval_seconds)

if __name__ == "__main__":
    run_worker_loop()
