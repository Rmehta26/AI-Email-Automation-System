import os
import sys
import json
import requests
import pandas as pd
import streamlit as st

# Ensure project root is accessible
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from backend.database import (
        init_db, get_emails, get_analytics_stats,
        update_email_status, delete_email, insert_email
    )
except ImportError:
    from database import (
        init_db, get_emails, get_analytics_stats,
        update_email_status, delete_email, insert_email
    )

API_URL = os.environ.get("API_URL", "http://localhost:8000")
METRICS_PATH = os.path.join(BASE_DIR, "model", "model_metrics.json")
DATASET_PATH = os.path.join(BASE_DIR, "model", "dataset.csv")

# Set Page Config
st.set_page_config(
    page_title="AI Email Automation & Intelligence",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling
st.markdown("""
<style>
    .metric-card {
        background-color: #1E222D;
        border: 1px solid #2E3440;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
    }
    .badge-spam {
        background-color: #EF4444;
        color: white;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .badge-ham {
        background-color: #10B981;
        color: white;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .badge-category {
        background-color: #3B82F6;
        color: white;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
    }
    .badge-urgency-high {
        background-color: #F59E0B;
        color: black;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# App Title & Header
st.title("📧 AI Email Automation System")
st.caption("Intelligent Spam Filtering, Categorization, Action Extraction, and Smart Reply Drafting")

# Initialize database
init_db()

# Sidebar Information
with st.sidebar:
    st.header("⚡ System Control")
    backend_online = False
    try:
        health_resp = requests.get(f"{API_URL}/health", timeout=2)
        if health_resp.status_code == 200:
            backend_online = True
            st.success("🟢 Backend API: Online")
            hdata = health_resp.json()
            if hdata.get("gemini_connected"):
                st.info("🤖 Gemini AI: Connected")
            else:
                st.warning("⚠️ Gemini AI: Rule-based fallback")
        else:
            st.error("🔴 Backend API: Error")
    except:
        st.error("🔴 Backend API: Offline (Run FastAPI)")

    st.markdown("---")
    st.subheader("🛠️ Quick Stats")
    stats = get_analytics_stats()
    st.write(f"**Total Processed:** {stats['total_emails']}")
    st.write(f"**Spam Blocked:** {stats['spam_count']} ({stats['spam_percentage']}%)")
    st.write(f"**Drafts Created:** {stats['replies_count']}")

    st.markdown("---")
    st.markdown("""
    **Architecture:**
    - **Classifier:** TF-IDF + MultinomialNB (95% Acc)
    - **LLM:** Google Gemini 1.5/2.0
    - **Inbox Engine:** IMAP4 / Mock Loop
    - **Storage:** SQLite Database
    """)

# Tabs Layout
tab1, tab2, tab3 = st.tabs([
    "📊 Real-Time Live Inbox",
    "🧪 Manual Email Studio",
    "⚙️ Model Health & Settings"
])

# ==================== TAB 1: LIVE INBOX ====================
with tab1:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Emails", stats["total_emails"])
    with col2:
        st.metric("Spam Blocked", f"{stats['spam_count']} ({stats['spam_percentage']}%)")
    with col3:
        st.metric("Legitimate Emails", stats["ham_count"])
    with col4:
        st.metric("Replies Drafted", stats["replies_count"])

    st.markdown("---")

    # Visual Charts
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        if stats["categories"]:
            cat_df = pd.DataFrame(
                list(stats["categories"].items()),
                columns=["Category", "Count"]
            ).set_index("Category")
            st.subheader("📂 Category Breakdown")
            st.bar_chart(cat_df, height=220)
        else:
            st.info("No categorical data available yet.")

    with col_chart2:
        if stats["urgencies"]:
            urg_df = pd.DataFrame(
                list(stats["urgencies"].items()),
                columns=["Urgency", "Count"]
            ).set_index("Urgency")
            st.subheader("⚡ Urgency Levels (Legitimate)")
            st.bar_chart(urg_df, height=220)
        else:
            st.info("No urgency data available yet.")

    st.markdown("---")
    
    # Filter & Search Controls
    st.subheader("📬 Live Feed & Action Center")
    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([2, 2, 3, 1])
    
    with filter_col1:
        filter_spam = st.selectbox("Spam Filter", ["All", "Legitimate Only", "Spam Only"])
    with filter_col2:
        filter_cat = st.selectbox("Category Filter", ["All", "Work", "Personal", "Finance", "Support", "Promotions", "Spam"])
    with filter_col3:
        search_kw = st.text_input("🔍 Search Subject / Sender", placeholder="Type keyword...")
    with filter_col4:
        st.write("")
        st.write("")
        if st.button("🔄 Refresh"):
            st.rerun()

    # Query DB with filters
    is_spam_val = True if filter_spam == "Spam Only" else (False if filter_spam == "Legitimate Only" else None)
    cat_val = filter_cat if filter_cat != "All" else None
    
    emails = get_emails(limit=50, is_spam=is_spam_val, category=cat_val, search=search_kw)

    if not emails:
        st.info("No emails found matching the filter criteria. Start the background processor: `python backend/auto_processor.py`")
    else:
        for em in emails:
            e_id = em["id"]
            is_spam = em["is_spam"]
            status = em["status"]
            category = em["category"]
            urgency = em["urgency"]
            sentiment = em["sentiment"]
            
            icon = "🚨" if is_spam else "📧"
            header_title = f"{icon} #{e_id} | {em['subject']} — From: {em['sender']} ({em['created_at']})"
            
            with st.expander(header_title, expanded=(not is_spam and status == "Drafted")):
                bcol1, bcol2, bcol3, bcol4 = st.columns(4)
                with bcol1:
                    if is_spam:
                        st.error(f"🚨 **SPAM** (Conf: {em['spam_confidence']*100:.1f}%)")
                    else:
                        st.success(f"✅ **HAM / SAFE** (Conf: {em['spam_confidence']*100:.1f}%)")
                with bcol2:
                    st.info(f"📂 **Category:** {category}")
                with bcol3:
                    st.warning(f"⚡ **Urgency:** {urgency}")
                with bcol4:
                    st.write(f"🏷️ **Status:** `{status}`")

                st.markdown("**Original Email Body:**")
                st.text_area("Body", em["body"], height=100, key=f"body_{e_id}", disabled=True)

                # Show Action Items if any
                action_items = em.get("action_items", [])
                if action_items:
                    st.markdown("**📌 Detected Action Items & Deadlines:**")
                    for item in action_items:
                        st.markdown(f"- ⏳ `{item}`")

                # Show Reply & Approval
                if not is_spam:
                    st.markdown("**🤖 AI Drafted Smart Reply:**")
                    reply_edit = st.text_area(
                        "Edit Reply Before Sending:",
                        em.get("reply", ""),
                        height=120,
                        key=f"rep_{e_id}"
                    )
                    
                    act_col1, act_col2, act_col3 = st.columns([2, 2, 4])
                    with act_col1:
                        if st.button("✅ Approve & Mark Sent", key=f"app_{e_id}"):
                            update_email_status(e_id, "Sent", reply_edit)
                            st.success(f"Email #{e_id} marked as Sent!")
                            st.rerun()
                    with act_col2:
                        if st.button("💾 Save Draft Edits", key=f"save_{e_id}"):
                            update_email_status(e_id, "Drafted", reply_edit)
                            st.success("Draft updated!")
                            st.rerun()
                    with act_col3:
                        if st.button("🗑️ Delete Record", key=f"del_{e_id}"):
                            delete_email(e_id)
                            st.rerun()
                else:
                    if st.button("🗑️ Delete Spam Record", key=f"del_spam_{e_id}"):
                        delete_email(e_id)
                        st.rerun()

# ==================== TAB 2: MANUAL TESTER ====================
with tab2:
    st.header("🧪 Manual Email Testing Studio")
    st.write("Test incoming emails against the ML spam detector, multi-dimensional categorization, and custom-toned smart reply generator.")

    # Preset templates for convenience
    templates = {
        "Custom": {"sender": "", "subject": "", "body": ""},
        "🚨 Phishing Attempt": {
            "sender": "security-support@apple-id-verify.com",
            "subject": "URGENT: Your Apple ID is Locked",
            "body": "Dear customer, your Apple ID was locked for suspicious login attempts. Verify your credit card and password immediately at http://appleid-confirm-secure.com to avoid permanent account deletion."
        },
        "💼 Work Meeting Request": {
            "sender": "david.ross@acmecorp.com",
            "subject": "Sync regarding Q4 Product Architecture",
            "body": "Hi Alex,\n\nCould we schedule a 30-minute sync this Wednesday at 3:00 PM to finalize the system design document and assign development tickets?\n\nPlease let me know if this time works for you."
        },
        "💰 Invoice / Billing": {
            "sender": "billing@cloudservices.io",
            "subject": "Monthly Service Invoice #INV-8891",
            "body": "Dear Client,\n\nYour monthly cloud hosting invoice of $129.00 for October has been generated. Please review the attached invoice breakdown and submit payment by Nov 5."
        },
        "🎁 Promotional Offer": {
            "sender": "newsletter@traveldeals.com",
            "subject": "FLASH SALE: 70% Off Flight Tickets to Paris!",
            "body": "Exclusive weekend discount! Book your holiday packages today with code HOLIDAY70 and save big on flights and 5-star hotel bookings. Offer valid for 48 hours only."
        }
    }

    selected_template = st.selectbox("⚡ Quick Load Demo Template:", list(templates.keys()))
    t_data = templates[selected_template]

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        in_sender = st.text_input("Sender Email", value=t_data["sender"], placeholder="sender@example.com")
    with col_s2:
        in_subject = st.text_input("Email Subject", value=t_data["subject"], placeholder="Meeting sync / Discount / Invoice")

    in_body = st.text_area("Email Content", value=t_data["body"], height=160, placeholder="Paste or type email text here...")

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        in_tone = st.selectbox(
            "Desired Reply Tone:",
            ["Professional", "Casual", "Concise", "Polite Decline", "Follow-up / Meeting Confirmation"]
        )
    with col_t2:
        in_custom_instructions = st.text_input("Custom Reply Instructions (Optional):", placeholder="e.g. Mention that I will be available after 4 PM")

    if st.button("🚀 Analyze Email & Generate Smart Reply", type="primary", use_container_width=True):
        if not in_body.strip():
            st.warning("Please enter email text to analyze.")
        else:
            with st.spinner("Running AI analysis pipeline..."):
                # 1. Spam Prediction
                try:
                    p_resp = requests.post(
                        f"{API_URL}/predict",
                        json={"text": in_body, "subject": in_subject, "sender": in_sender},
                        timeout=5
                    )
                    p_data = p_resp.json() if p_resp.status_code == 200 else {}
                except Exception as e:
                    p_data = {"is_spam": False, "confidence": 0.5, "indicators": []}

                # 2. Categorization
                try:
                    c_resp = requests.post(
                        f"{API_URL}/categorize",
                        json={"text": in_body, "subject": in_subject},
                        timeout=5
                    )
                    c_data = c_resp.json() if c_resp.status_code == 200 else {}
                except Exception as e:
                    c_data = {"category": "Personal", "urgency": "Medium", "sentiment": "Neutral", "summary": ""}

                # 3. Action extraction
                try:
                    a_resp = requests.post(
                        f"{API_URL}/extract-actions",
                        json={"text": in_body},
                        timeout=5
                    )
                    a_data = a_resp.json() if a_resp.status_code == 200 else {}
                except Exception as e:
                    a_data = {"action_items": [], "deadlines": [], "meeting_requested": False}

                # 4. Reply generation
                try:
                    r_resp = requests.post(
                        f"{API_URL}/reply",
                        json={
                            "text": in_body,
                            "sender": in_sender,
                            "subject": in_subject,
                            "tone": in_tone,
                            "custom_instructions": in_custom_instructions
                        },
                        timeout=8
                    )
                    r_data = r_resp.json() if r_resp.status_code == 200 else {}
                except Exception as e:
                    r_data = {"reply": "Thank you for your email. I will follow up shortly."}

                st.markdown("---")
                st.subheader("🎯 Pipeline Analysis Results")

                res_col1, res_col2, res_col3, res_col4 = st.columns(4)
                is_sp = p_data.get("is_spam", False)
                conf = p_data.get("confidence", 0.0)
                
                with res_col1:
                    if is_sp:
                        st.error(f"🚨 **SPAM DETECTED**\nConfidence: {conf*100:.1f}%")
                    else:
                        st.success(f"✅ **LEGITIMATE (HAM)**\nConfidence: {conf*100:.1f}%")
                with res_col2:
                    st.info(f"📂 **Category:** {c_data.get('category', 'Personal')}")
                with res_col3:
                    st.warning(f"⚡ **Urgency:** {c_data.get('urgency', 'Medium')}")
                with res_col4:
                    st.write(f"🎭 **Sentiment:** {c_data.get('sentiment', 'Neutral')}")

                # Show Trigger Indicators
                indicators = p_data.get("indicators", [])
                if indicators:
                    st.markdown(f"**Spam Trigger Keywords Detected:** `{'`, `'.join(indicators)}`")

                # Show Action Items
                actions = a_data.get("action_items", [])
                deadlines = a_data.get("deadlines", [])
                if actions or deadlines:
                    st.markdown("**📌 Extracted Tasks & Deadlines:**")
                    for a in actions:
                        st.markdown(f"- Task: `{a}`")
                    for d in deadlines:
                        st.markdown(f"- Deadline: `{d}`")

                # Smart Reply
                st.markdown("### 🤖 Context-Aware Smart Reply")
                reply_text = r_data.get("reply", "")
                st.text_area("Generated Reply:", value=reply_text, height=140)

                if st.button("📥 Save This Analysis to Inbox History"):
                    insert_email({
                        "sender": in_sender or "manual-test@user.com",
                        "subject": in_subject or "Manual Test",
                        "body": in_body,
                        "is_spam": is_sp,
                        "spam_confidence": conf,
                        "category": c_data.get("category", "Personal"),
                        "urgency": c_data.get("urgency", "Medium"),
                        "sentiment": c_data.get("sentiment", "Neutral"),
                        "action_items": actions,
                        "reply": reply_text,
                        "status": "Drafted" if not is_sp else "Moved to Spam",
                        "source": "manual"
                    })
                    st.success("Saved to database successfully!")
                    st.rerun()

# ==================== TAB 3: MODEL HEALTH & SETTINGS ====================
with tab3:
    st.header("⚙️ Model Health, Evaluation & System Configuration")
    
    col_m1, col_m2 = st.columns(2)

    with col_m1:
        st.subheader("📈 ML Model Evaluation Metrics")
        if os.path.exists(METRICS_PATH):
            with open(METRICS_PATH, "r") as f:
                metrics_data = json.load(f)
            
            st.write(f"**Algorithm:** `{metrics_data.get('model_type')}`")
            st.write(f"**Vocabulary Size:** `{metrics_data.get('vocabulary_size')} tokens`")
            st.write(f"**Total Samples:** `{metrics_data.get('total_samples')}` ({metrics_data.get('spam_samples')} Spam, {metrics_data.get('ham_samples')} Ham)")
            st.write(f"**Last Trained:** `{metrics_data.get('trained_at')}`")
            
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            m_col1.metric("Accuracy", f"{metrics_data.get('accuracy', 0)*100:.1f}%")
            m_col2.metric("Precision", f"{metrics_data.get('precision', 0)*100:.1f}%")
            m_col3.metric("Recall", f"{metrics_data.get('recall', 0)*100:.1f}%")
            m_col4.metric("F1-Score", f"{metrics_data.get('f1_score', 0)*100:.1f}%")

            # Show Confusion Matrix
            cm = metrics_data.get("confusion_matrix")
            if cm:
                st.markdown("**Confusion Matrix (Test Set):**")
                cm_df = pd.DataFrame(
                    cm,
                    columns=["Pred Ham", "Pred Spam"],
                    index=["Actual Ham", "Actual Spam"]
                )
                st.dataframe(cm_df)
        else:
            st.warning("No model metrics file found. Please train model.")

        if st.button("🔄 Retrain ML Model Now"):
            with st.spinner("Retraining model on dataset.csv..."):
                try:
                    r_resp = requests.post(f"{API_URL}/retrain", timeout=30)
                    if r_resp.status_code == 200:
                        st.success("Model retrained successfully!")
                        st.rerun()
                    else:
                        st.error(f"Retrain error: {r_resp.text}")
                except Exception as e:
                    st.error(f"Failed to connect to backend: {e}")

    with col_m2:
        st.subheader("🔌 IMAP / SMTP Configuration Guide")
        st.markdown("""
        To connect a live Gmail/Outlook account:
        1. Open `.env` in the root folder.
        2. Add your credentials:
        ```env
        GEMINI_API_KEY=your_gemini_api_key
        IMAP_SERVER=imap.gmail.com
        IMAP_PORT=993
        IMAP_USER=your_email@gmail.com
        IMAP_PASS=your_16_digit_app_password
        ```
        > **Note:** For Gmail, generate an **App Password** under Google Account -> Security -> 2-Step Verification -> App Passwords.
        
        If no IMAP credentials are provided, the system automatically runs in **Smart Mock Mode** to simulate realistic incoming traffic for demos.
        """)

        st.subheader("📁 Training Dataset Preview")
        if os.path.exists(DATASET_PATH):
            df = pd.read_csv(DATASET_PATH)
            st.write(f"Total Rows: {len(df)}")
            st.dataframe(df.head(10), height=200)
