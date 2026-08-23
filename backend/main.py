import os
import re
import json
import joblib
import datetime
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai

# Relative imports or direct imports
try:
    from backend.database import (
        init_db, insert_email, get_emails, get_email_by_id,
        update_email_status, delete_email, get_analytics_stats, log_event
    )
except ImportError:
    from database import (
        init_db, insert_email, get_emails, get_email_by_id,
        update_email_status, delete_email, get_analytics_stats, log_event
    )

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "model", "model.pkl")
VECTORIZER_PATH = os.path.join(BASE_DIR, "model", "vectorizer.pkl")
METRICS_PATH = os.path.join(BASE_DIR, "model", "model_metrics.json")
ENV_PATH = os.path.join(BASE_DIR, ".env")

# Initialize database
init_db()

# Initialize FastAPI
app = FastAPI(
    title="AI Email Automation & Intelligence API",
    description="High-performance email classification, smart reply generation, and inbox automation pipeline.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load ML Models
classifier = None
vectorizer = None

def load_ml_models():
    global classifier, vectorizer
    if os.path.exists(MODEL_PATH) and os.path.exists(VECTORIZER_PATH):
        try:
            classifier = joblib.load(MODEL_PATH)
            vectorizer = joblib.load(VECTORIZER_PATH)
            print("ML models loaded successfully.")
            return True
        except Exception as e:
            print(f"Error loading models: {e}")
            return False
    else:
        print("Warning: Model files not found. Run model/train.py to train.")
        return False

load_ml_models()

# Load Gemini API Key
if os.path.exists(ENV_PATH):
    with open(ENV_PATH, "r") as f:
        for line in f:
            if line.strip().startswith("GEMINI_API_KEY="):
                key = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                os.environ["GEMINI_API_KEY"] = key

gemini_key = os.environ.get("GEMINI_API_KEY")
llm_model = None

def get_genai_model():
    global llm_model
    if not gemini_key:
        return None
    try:
        genai.configure(api_key=gemini_key)
        for model_name in ["gemini-3.6-flash", "gemini-3.0-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-pro"]:
            try:
                m = genai.GenerativeModel(model_name)
                # Test with quick dry-run
                return m
            except:
                continue
        # Fallback to standard gemini-pro
        return genai.GenerativeModel("gemini-pro")
    except Exception as e:
        print(f"GenAI setup notice: {e}")
    return None

llm_model = get_genai_model()

# ==================== PYDANTIC SCHEMAS ====================

class EmailPredictRequest(BaseModel):
    text: str = Field(..., description="Email body text to analyze")
    sender: Optional[str] = "unknown@example.com"
    subject: Optional[str] = ""

class EmailPredictResponse(BaseModel):
    is_spam: bool
    confidence: float
    spam_score: float
    indicators: List[str]

class ReplyRequest(BaseModel):
    text: str
    sender: Optional[str] = "sender"
    subject: Optional[str] = ""
    tone: Optional[str] = "Professional"
    custom_instructions: Optional[str] = ""

class ReplyResponse(BaseModel):
    reply: str
    tone: str

class CategorizeRequest(BaseModel):
    text: str
    subject: Optional[str] = ""

class CategorizeResponse(BaseModel):
    category: str
    urgency: str
    sentiment: str
    summary: str

class ActionItemsRequest(BaseModel):
    text: str

class ActionItemsResponse(BaseModel):
    action_items: List[str]
    deadlines: List[str]
    meeting_requested: bool

class UpdateEmailRequest(BaseModel):
    status: Optional[str] = None
    reply: Optional[str] = None

# ==================== HELPER LOGIC ====================

SPAM_KEYWORDS = [
    "winner", "gift card", "claim", "prize", "suspended", "urgent",
    "verify", "password", "crypto", "bitcoin", "inherit", "inheritance",
    "rolex", "singles", "discount", "free", "limited time", "click here",
    "bank account", "compromised", "warranty", "lottery", "unclaimed"
]

def extract_indicators(text: str) -> List[str]:
    text_lower = text.lower()
    return [kw for kw in SPAM_KEYWORDS if kw in text_lower]

def fallback_categorize(text: str, subject: str = "") -> Dict[str, str]:
    content = f"{subject} {text}".lower()
    
    # Category rule matching
    if any(k in content for k in ["sale", "discount", "offer", "promo", "deal", "coupon", "off"]):
        category = "Promotions"
    elif any(k in content for k in ["invoice", "payment", "receipt", "billing", "statement", "tax", "fee"]):
        category = "Finance"
    elif any(k in content for k in ["meeting", "agenda", "sprint", "project", "review", "pr", "deploy", "team", "client"]):
        category = "Work"
    elif any(k in content for k in ["ticket", "support", "help", "issue", "bug", "error", "assist"]):
        category = "Support"
    else:
        category = "Personal"

    # Urgency rule matching
    if any(k in content for k in ["urgent", "asap", "emergency", "immediately", "deadline", "today"]):
        urgency = "High"
    elif any(k in content for k in ["tomorrow", "soon", "this week", "review"]):
        urgency = "Medium"
    else:
        urgency = "Low"

    # Sentiment rule matching
    if any(k in content for k in ["unhappy", "angry", "broken", "terrible", "issue", "complaint", "fail"]):
        sentiment = "Negative"
    elif any(k in content for k in ["thank", "great", "kudos", "congratulations", "awesome", "good"]):
        sentiment = "Positive"
    else:
        sentiment = "Neutral"

    return {
        "category": category,
        "urgency": urgency,
        "sentiment": sentiment,
        "summary": text[:120] + "..." if len(text) > 120 else text
    }

def fallback_reply(text: str, tone: str = "Professional") -> str:
    if "meeting" in text.lower():
        if tone.lower() == "casual":
            return "Hey! Thanks for reaching out. The proposed time works for me, see you then!"
        elif tone.lower() == "polite decline":
            return "Hi, thank you for the invitation. Unfortunately, I have a scheduling conflict and won't be able to make it at that time."
        elif tone.lower() == "concise":
            return "Confirmed. Will join at the scheduled time."
        else:
            return "Dear Sender,\n\nThank you for scheduling this. I confirm that I will attend as planned.\n\nBest regards,\nAutomated Assistant"
    elif "invoice" in text.lower() or "receipt" in text.lower():
        return "Dear Sender,\n\nThank you for providing the invoice details. I have forwarded this to our accounts department for processing.\n\nBest regards,\nAutomated Assistant"
    else:
        if tone.lower() == "casual":
            return "Hey there! Got your email, thanks for reaching out. I'll check into this and get back to you shortly."
        elif tone.lower() == "concise":
            return "Received and noted. Will follow up soon."
        elif tone.lower() == "polite decline":
            return "Thank you for thinking of us. Unfortunately, we are unable to accommodate this request at this time."
        else:
            return "Dear Sender,\n\nThank you for getting in touch. I have received your message and will review the details thoroughly before following up.\n\nBest regards,\nAutomated Assistant"

# ==================== ENDPOINTS ====================

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "model_loaded": classifier is not None,
        "gemini_connected": llm_model is not None,
        "database": "SQLite (email_assistant.db)"
    }

@app.get("/model-info")
def get_model_metrics():
    if os.path.exists(METRICS_PATH):
        with open(METRICS_PATH, "r") as f:
            return json.load(f)
    return {"status": "Metrics not found. Please train model."}

@app.post("/retrain")
def retrain_model():
    try:
        from model.train import train_and_save
        metrics = train_and_save()
        load_ml_models()
        log_event("INFO", f"Model successfully retrained with {metrics.get('total_samples', 0)} samples.")
        return {"status": "success", "message": "Model retrained and reloaded successfully.", "metrics": metrics}
    except Exception as e:
        log_event("ERROR", f"Retrain failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/predict", response_model=EmailPredictResponse)
def predict_spam(request: EmailPredictRequest):
    if not classifier or not vectorizer:
        success = load_ml_models()
        if not success:
            raise HTTPException(status_code=503, detail="ML model is not loaded.")
    
    full_text = f"{request.subject} {request.text}".strip()
    X = vectorizer.transform([full_text])
    pred = classifier.predict(X)[0]
    probs = classifier.predict_proba(X)[0]
    
    # Probabilities mapping: ['ham', 'spam']
    classes = list(classifier.classes_)
    spam_idx = classes.index("spam") if "spam" in classes else 1
    spam_prob = float(probs[spam_idx])
    
    is_spam = (pred == "spam") or (spam_prob >= 0.5)
    confidence = spam_prob if is_spam else (1.0 - spam_prob)
    indicators = extract_indicators(full_text)

    return EmailPredictResponse(
        is_spam=is_spam,
        confidence=round(confidence, 4),
        spam_score=round(spam_prob, 4),
        indicators=indicators
    )

@app.post("/categorize", response_model=CategorizeResponse)
def categorize_email(request: CategorizeRequest):
    content = f"Subject: {request.subject}\nBody:\n{request.text}"
    
    if llm_model:
        prompt = f"""You are an intelligent email triage assistant.
Analyze the following email and return a JSON object with exactly these keys:
- "category": Choose one of ["Work", "Personal", "Promotions", "Finance", "Support"]
- "urgency": Choose one of ["High", "Medium", "Low"]
- "sentiment": Choose one of ["Positive", "Neutral", "Negative"]
- "summary": A brief 1-sentence summary of the email.

Email:
{content}

Respond with ONLY the valid raw JSON object, without markdown formatting or code fences."""
        try:
            res = llm_model.generate_content(prompt)
            raw_text = res.text.strip()
            # Clean possible markdown fences
            raw_text = re.sub(r"^```json\s*", "", raw_text)
            raw_text = re.sub(r"^```\s*", "", raw_text)
            raw_text = re.sub(r"\s*```$", "", raw_text)
            parsed = json.loads(raw_text)
            return CategorizeResponse(
                category=parsed.get("category", "Personal"),
                urgency=parsed.get("urgency", "Medium"),
                sentiment=parsed.get("sentiment", "Neutral"),
                summary=parsed.get("summary", request.text[:100])
            )
        except Exception as e:
            print(f"Gemini categorize fallback: {e}")

    # Rule-based fallback
    fb = fallback_categorize(request.text, request.subject or "")
    return CategorizeResponse(**fb)

@app.post("/reply", response_model=ReplyResponse)
def generate_reply(request: ReplyRequest):
    tone = request.tone or "Professional"
    custom_inst = f"\nAdditional Instructions: {request.custom_instructions}" if request.custom_instructions else ""
    
    if llm_model:
        prompt = f"""You are an executive email assistant.
Draft a {tone.lower()} reply to the following incoming email.
Make sure the response is relevant, clear, and context-aware.
Tone desired: {tone}{custom_inst}

Sender: {request.sender}
Subject: {request.subject}
Email Content:
{request.text}

Write only the email reply body. Do not include meta explanations."""
        try:
            res = llm_model.generate_content(prompt)
            return ReplyResponse(reply=res.text.strip(), tone=tone)
        except Exception as e:
            print(f"Gemini reply error, using fallback: {e}")

    return ReplyResponse(
        reply=fallback_reply(request.text, tone),
        tone=tone
    )

@app.post("/extract-actions", response_model=ActionItemsResponse)
def extract_action_items(request: ActionItemsRequest):
    text = request.text
    if llm_model:
        prompt = f"""Extract action items, deadlines, and whether a meeting is requested from this email.
Return ONLY a valid JSON object with:
- "action_items": list of concise string tasks
- "deadlines": list of mentioned dates or times
- "meeting_requested": boolean (true/false)

Email:
{text}"""
        try:
            res = llm_model.generate_content(prompt)
            raw_text = res.text.strip()
            raw_text = re.sub(r"^```json\s*", "", raw_text)
            raw_text = re.sub(r"^```\s*", "", raw_text)
            raw_text = re.sub(r"\s*```$", "", raw_text)
            parsed = json.loads(raw_text)
            return ActionItemsResponse(
                action_items=parsed.get("action_items", []),
                deadlines=parsed.get("deadlines", []),
                meeting_requested=bool(parsed.get("meeting_requested", False))
            )
        except Exception as e:
            print(f"Action item extraction error: {e}")

    # Fallback extraction
    action_items = []
    deadlines = []
    meeting_requested = "meet" in text.lower() or "schedule" in text.lower()
    
    for sentence in re.split(r"[.!?\n]", text):
        s = sentence.strip()
        if any(w in s.lower() for w in ["please", "could you", "need to", "action", "review", "approve", "submit"]):
            if len(s) > 10:
                action_items.append(s)
        if any(w in s.lower() for w in ["by", "before", "due", "deadline", "at 1", "at 2", "at 3", "at 4", "at 5", "at 6", "at 7", "at 8", "at 9", "at 10", "at 11", "at 12", "am", "pm", "today", "tomorrow", "friday", "monday"]):
            deadlines.append(s)

    return ActionItemsResponse(
        action_items=action_items[:3],
        deadlines=deadlines[:2],
        meeting_requested=meeting_requested
    )

@app.get("/emails")
def list_emails(
    limit: int = Query(50, ge=1, le=200),
    is_spam: Optional[bool] = None,
    category: Optional[str] = None,
    search: Optional[str] = None
):
    return get_emails(limit=limit, is_spam=is_spam, category=category, search=search)

@app.get("/emails/{email_id}")
def get_single_email(email_id: int):
    email_data = get_email_by_id(email_id)
    if not email_data:
        raise HTTPException(status_code=404, detail="Email not found.")
    return email_data

@app.patch("/emails/{email_id}")
def patch_email(email_id: int, req: UpdateEmailRequest):
    success = update_email_status(email_id, req.status, req.reply)
    if not success:
        raise HTTPException(status_code=404, detail="Email not found.")
    return {"status": "success", "message": f"Email {email_id} updated."}

@app.delete("/emails/{email_id}")
def remove_email(email_id: int):
    success = delete_email(email_id)
    if not success:
        raise HTTPException(status_code=404, detail="Email not found.")
    return {"status": "success", "message": f"Email {email_id} deleted."}

@app.get("/stats")
def get_stats():
    return get_analytics_stats()
