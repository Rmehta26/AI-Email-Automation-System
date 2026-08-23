import os
import json
import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, classification_report

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(CURRENT_DIR, "dataset.csv")
MODEL_PATH = os.path.join(CURRENT_DIR, "model.pkl")
VECTORIZER_PATH = os.path.join(CURRENT_DIR, "vectorizer.pkl")
METRICS_PATH = os.path.join(CURRENT_DIR, "model_metrics.json")

def load_data():
    if os.path.exists(DATASET_PATH):
        df = pd.read_csv(DATASET_PATH)
        print(f"Loaded {len(df)} samples from {DATASET_PATH}")
        return df["text"].tolist(), df["label"].tolist()
    else:
        raise FileNotFoundError(f"Dataset not found at {DATASET_PATH}")

def train_and_save():
    print("=" * 60)
    print("Training ML Spam Classifier Pipeline (TF-IDF + Naive Bayes)...")
    print("=" * 60)

    X, y = load_data()
    
    # Train-test split (80% train, 20% test)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    # Initialize TF-IDF Vectorizer with unigrams & bigrams
    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True,
        max_features=5000
    )

    # Transform training data
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    # Train Multinomial Naive Bayes classifier
    classifier = MultinomialNB(alpha=0.1)
    classifier.fit(X_train_vec, y_train)

    # Evaluate on test set
    y_pred = classifier.predict(X_test_vec)
    
    accuracy = float(accuracy_score(y_test, y_pred))
    precision = float(precision_score(y_test, y_pred, pos_label="spam", zero_division=0))
    recall = float(recall_score(y_test, y_pred, pos_label="spam", zero_division=0))
    f1 = float(f1_score(y_test, y_pred, pos_label="spam", zero_division=0))
    cm = confusion_matrix(y_test, y_pred).tolist()

    print(f"\nModel Performance Metrics:")
    print(f"  • Accuracy:  {accuracy * 100:.2f}%")
    print(f"  • Precision: {precision * 100:.2f}%")
    print(f"  • Recall:    {recall * 100:.2f}%")
    print(f"  • F1-Score:  {f1 * 100:.2f}%")
    print("\nClassification Report:\n", classification_report(y_test, y_pred))

    # Refit on full dataset for maximum deployment accuracy
    X_full_vec = vectorizer.fit_transform(X)
    classifier.fit(X_full_vec, y)

    # Save artifacts
    os.makedirs(CURRENT_DIR, exist_ok=True)
    joblib.dump(vectorizer, VECTORIZER_PATH)
    joblib.dump(classifier, MODEL_PATH)

    metrics = {
        "model_type": "MultinomialNB + TF-IDF (1-2 ngrams)",
        "total_samples": len(X),
        "spam_samples": sum(1 for label in y if label == "spam"),
        "ham_samples": sum(1 for label in y if label == "ham"),
        "vocabulary_size": len(vectorizer.vocabulary_),
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "confusion_matrix": cm,
        "trained_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=4)

    print(f"Artifacts successfully saved:")
    print(f"  -> Model:      {MODEL_PATH}")
    print(f"  -> Vectorizer: {VECTORIZER_PATH}")
    print(f"  -> Metrics:    {METRICS_PATH}")
    print("=" * 60)
    return metrics

if __name__ == "__main__":
    train_and_save()
