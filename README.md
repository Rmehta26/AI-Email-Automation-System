# 🤖 AI Email Automation System

An AI-powered email automation system that connects to Gmail, detects spam using Machine Learning, analyzes emails using Google Gemini, generates smart replies, extracts action items, and displays results through a Streamlit dashboard.

## ✨ Features

* 📧 Gmail IMAP integration
* 🛡️ Spam detection using TF-IDF + Multinomial Naive Bayes
* 🧠 AI email categorization using Google Gemini
* ⚡ Urgency and sentiment analysis
* 📌 Action-item and deadline extraction
* ✍️ AI-powered smart reply generation
* 💾 SQLite database
* 📊 Streamlit dashboard
* 🔄 Mock mode for testing

## 🛠️ Tech Stack

**Python | FastAPI | Streamlit | Scikit-learn | Google Gemini API | Gmail IMAP/SMTP | SQLite**

## 📊 ML Performance

| Metric    | Score |
| --------- | ----: |
| Accuracy  |   95% |
| Precision |  100% |
| Recall    |   90% |
| F1 Score  | 94.7% |

## 🏗️ Architecture

```text
Gmail Inbox
     ↓
IMAP Email Processor
     ↓
FastAPI Backend
     ↓
 ┌─────────────┬─────────────┐
 │             │             │
 ML          Gemini        SQLite
Spam AI      Analysis      Database
 │             │             │
 └─────────────┴─────────────┘
               ↓
      Streamlit Dashboard
```

## 📁 Project Structure

```text
AI-Email-Automation-System/
│
├── backend/
│   ├── main.py
│   ├── database.py
│   └── auto_processor.py
│
├── frontend/
│   └── app.py
│
├── model/
│   ├── dataset.csv
│   ├── model.pkl
│   ├── vectorizer.pkl
│   ├── model_metrics.json
│   └── train.py
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## ⚙️ Setup

```bash
git clone https://github.com/Rmehta26/AI-Email-Automation-System.git
cd AI-Email-Automation-System
pip install -r requirements.txt
```

Create a `.env` file using `.env.example` and add your Gemini API key and Gmail App Password.

> ⚠️ Never commit your `.env` file or expose your API keys and email credentials.

## ▶️ Run

**FastAPI Backend**

```bash
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

**Email Processor**

```bash
python backend/auto_processor.py
```

**Streamlit Dashboard**

```bash
streamlit run frontend/app.py
```

## 👩‍💻 Author

**Rashmi Mehta**
B.Tech Computer Science Engineering

GitHub: [https://github.com/Rmehta26](https://github.com/Rmehta26)
