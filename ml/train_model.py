"""
Smart Sewage Monitoring System — ML Model Training & Evaluation
===============================================================
Trains and evaluates anomaly detection models on sewage sensor data.
Implements the threshold-based and ML-based approaches described in
the IEEE paper.

Parameters monitored:
  pH, Temperature, Turbidity, COD, BOD, TDS, Ammonia Concentration

Authors: T. Vijayakumar et al.
Institution: Dr. N.G.P. Institute of Technology, Coimbatore
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import SelectKBest, chi2
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report, ConfusionMatrixDisplay
)
from sklearn.pipeline import Pipeline
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# 1. SYNTHETIC DATASET GENERATION
#    (Replace with real sensor CSV data in production)
# ─────────────────────────────────────────────────────────────────────────────

def generate_sewage_dataset(n_samples: int = 1000, random_state: int = 42) -> pd.DataFrame:
    """
    Generate a realistic synthetic sewage sensor dataset.
    Label = 0 → Safe condition
    Label = 1 → Hazardous / requires intervention
    """
    rng = np.random.default_rng(random_state)

    # Safe samples (~70%)
    n_safe = int(n_samples * 0.70)
    safe = pd.DataFrame({
        "pH":          rng.uniform(6.5, 8.5,  n_safe),
        "Temperature": rng.uniform(20.0, 30.0, n_safe),
        "Turbidity":   rng.uniform(1.0, 5.0,   n_safe),
        "COD":         rng.uniform(50, 150,    n_safe),
        "BOD":         rng.uniform(10, 30,     n_safe),
        "TDS":         rng.uniform(300, 600,   n_safe),
        "Ammonia":     rng.uniform(0.1, 1.0,   n_safe),
        "Label": 0,
    })

    # Hazardous samples (~30%)
    n_hazard = n_samples - n_safe
    ph_low  = rng.uniform(0.0, 6.0,  n_hazard // 2)
    ph_high = rng.uniform(9.0, 14.0, n_hazard - n_hazard // 2)
    ph_hazard = np.concatenate([ph_low, ph_high])
    hazard = pd.DataFrame({
        "pH":          ph_hazard,
        "Temperature": rng.uniform(35.0, 55.0, n_hazard),
        "Turbidity":   rng.uniform(10.0, 50.0, n_hazard),
        "COD":         rng.uniform(300, 800,   n_hazard),
        "BOD":         rng.uniform(80, 250,    n_hazard),
        "TDS":         rng.uniform(900, 2000,  n_hazard),
        "Ammonia":     rng.uniform(5.0, 20.0,  n_hazard),
        "Label": 1,
    })

    df = pd.concat([safe, hazard], ignore_index=True).sample(
        frac=1, random_state=random_state).reset_index(drop=True)

    # Inject ~5% missing values
    for col in df.columns[:-1]:
        mask = rng.random(len(df)) < 0.05
        df.loc[mask, col] = np.nan

    return df


# ─────────────────────────────────────────────────────────────────────────────
# 2. PREPROCESSING PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def build_preprocessing_pipeline(k_features: int = 5) -> Pipeline:
    """
    Returns a sklearn Pipeline:
      1. Mean imputation for missing values
      2. Z-score standardization
      3. Chi-square feature selection (top-k features)
    """
    return Pipeline([
        ("imputer",   SimpleImputer(strategy="mean")),
        ("scaler",    StandardScaler()),
        # Note: chi2 requires non-negative features; use SelectKBest after scaling
        # For non-negative requirement we use f_classif instead post-scaling
    ])


# ─────────────────────────────────────────────────────────────────────────────
# 3. THRESHOLD-BASED ANOMALY DETECTION
# ─────────────────────────────────────────────────────────────────────────────

THRESHOLDS = {
    "pH":          (6.5, 8.5),    # (min_safe, max_safe)
    "Temperature": (None, 35.0),  # max only
    "Turbidity":   (None, 5.0),
    "COD":         (None, 150.0),
    "BOD":         (None, 30.0),
    "TDS":         (None, 600.0),
    "Ammonia":     (None, 1.0),
}


def threshold_predict(df: pd.DataFrame) -> np.ndarray:
    """
    Rule-based anomaly detection using predefined safe thresholds.
    Returns array of 0 (safe) or 1 (hazardous).
    """
    anomaly = np.zeros(len(df), dtype=int)
    for col, (lo, hi) in THRESHOLDS.items():
        if col not in df.columns:
            continue
        if lo is not None:
            anomaly |= (df[col] < lo).astype(int).values
        if hi is not None:
            anomaly |= (df[col] > hi).astype(int).values
    return anomaly


# ─────────────────────────────────────────────────────────────────────────────
# 4. ML MODEL DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

MODELS = {
    "Random Forest":         RandomForestClassifier(n_estimators=100, random_state=42),
    "Gradient Boosting":     GradientBoostingClassifier(n_estimators=100, random_state=42),
    "Support Vector Machine": SVC(kernel="rbf", probability=True, random_state=42),
    "Logistic Regression":   LogisticRegression(max_iter=1000, random_state=42),
}


# ─────────────────────────────────────────────────────────────────────────────
# 5. EVALUATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_model(name: str, model, X_test, y_test) -> dict:
    y_pred = model.predict(X_test)
    metrics = {
        "Model":     name,
        "Accuracy":  round(accuracy_score(y_test, y_pred), 4),
        "Precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "Recall":    round(recall_score(y_test, y_pred, zero_division=0), 4),
        "F1-Score":  round(f1_score(y_test, y_pred, zero_division=0), 4),
    }
    print(f"\n{'='*50}")
    print(f"  {name}")
    print(f"{'='*50}")
    print(classification_report(y_test, y_pred,
                                target_names=["Safe", "Hazardous"]))
    return metrics


def plot_confusion_matrix(model, X_test, y_test, title: str):
    fig, ax = plt.subplots(figsize=(5, 4))
    ConfusionMatrixDisplay.from_estimator(
        model, X_test, y_test,
        display_labels=["Safe", "Hazardous"],
        cmap="Blues", ax=ax
    )
    ax.set_title(title)
    plt.tight_layout()
    plt.savefig(f"confusion_matrix_{title.replace(' ', '_')}.png", dpi=150)
    plt.close()
    print(f"  → Saved confusion matrix: confusion_matrix_{title.replace(' ', '_')}.png")


def plot_model_comparison(results: list):
    df_res = pd.DataFrame(results).set_index("Model")
    df_res.plot(kind="bar", figsize=(10, 5), colormap="Set2", edgecolor="black")
    plt.title("Model Performance Comparison — Smart Sewage Monitoring System")
    plt.ylabel("Score")
    plt.ylim(0.8, 1.02)
    plt.xticks(rotation=30, ha="right")
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig("model_comparison.png", dpi=150)
    plt.close()
    print("\n  → Saved: model_comparison.png")


def plot_sensor_distributions(df: pd.DataFrame):
    features = [c for c in df.columns if c != "Label"]
    fig, axes = plt.subplots(2, 4, figsize=(16, 8))
    axes = axes.flatten()
    for i, feat in enumerate(features):
        for label, color, lbl in [(0, "steelblue", "Safe"), (1, "crimson", "Hazardous")]:
            axes[i].hist(df.loc[df["Label"] == label, feat].dropna(),
                         bins=25, alpha=0.6, color=color, label=lbl)
        axes[i].set_title(feat)
        axes[i].legend(fontsize=8)
    for j in range(len(features), len(axes)):
        axes[j].set_visible(False)
    fig.suptitle("Sensor Parameter Distributions by Condition", fontsize=14)
    plt.tight_layout()
    plt.savefig("sensor_distributions.png", dpi=150)
    plt.close()
    print("  → Saved: sensor_distributions.png")


def cross_validation_table(models: dict, X_train, y_train) -> pd.DataFrame:
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    rows = []
    for name, model in models.items():
        scores = cross_val_score(model, X_train, y_train, cv=cv, scoring="accuracy")
        rows.append({
            "Model":   name,
            "CV Mean": round(scores.mean(), 4),
            "CV Std":  round(scores.std(), 4),
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# 6. MAIN PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*60)
    print("  Smart Sewage Monitoring System — ML Pipeline")
    print("="*60)

    # ── 6.1 Load / Generate Data ──────────────────────────────────
    print("\n[1] Generating dataset...")
    df = generate_sewage_dataset(n_samples=1000)
    print(f"    Shape: {df.shape} | Hazardous rate: {df['Label'].mean():.1%}")

    # ── 6.2 EDA Plot ──────────────────────────────────────────────
    print("\n[2] Plotting sensor distributions...")
    plot_sensor_distributions(df)

    # ── 6.3 Preprocessing ─────────────────────────────────────────
    print("\n[3] Preprocessing...")
    X = df.drop("Label", axis=1)
    y = df["Label"]

    imputer = SimpleImputer(strategy="mean")
    scaler  = StandardScaler()

    X_imputed = imputer.fit_transform(X)
    X_scaled  = scaler.fit_transform(X_imputed)

    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42, stratify=y)
    print(f"    Train: {X_train.shape[0]} | Test: {X_test.shape[0]}")

    # ── 6.4 Threshold-Based Baseline ──────────────────────────────
    print("\n[4] Threshold-based detection (baseline)...")
    y_thresh = threshold_predict(df.drop("Label", axis=1))
    thresh_acc  = accuracy_score(y, y_thresh)
    thresh_prec = precision_score(y, y_thresh, zero_division=0)
    thresh_rec  = recall_score(y, y_thresh, zero_division=0)
    thresh_f1   = f1_score(y, y_thresh, zero_division=0)
    print(f"    Accuracy: {thresh_acc:.4f} | Precision: {thresh_prec:.4f} | "
          f"Recall: {thresh_rec:.4f} | F1: {thresh_f1:.4f}")

    # ── 6.5 Cross-Validation ──────────────────────────────────────
    print("\n[5] Cross-validation (5-fold)...")
    cv_df = cross_validation_table(MODELS, X_train, y_train)
    print(cv_df.to_string(index=False))

    # ── 6.6 Train & Evaluate All Models ───────────────────────────
    print("\n[6] Training and evaluating models...")
    all_results = [{
        "Model":     "Threshold-Based",
        "Accuracy":  round(thresh_acc, 4),
        "Precision": round(thresh_prec, 4),
        "Recall":    round(thresh_rec, 4),
        "F1-Score":  round(thresh_f1, 4),
    }]

    trained_models = {}
    for name, model in MODELS.items():
        model.fit(X_train, y_train)
        trained_models[name] = model
        metrics = evaluate_model(name, model, X_test, y_test)
        all_results.append(metrics)
        plot_confusion_matrix(model, X_test, y_test, name)

    # ── 6.7 Summary Table ─────────────────────────────────────────
    print("\n[7] Summary:")
    results_df = pd.DataFrame(all_results)
    print(results_df.to_string(index=False))
    results_df.to_csv("model_results.csv", index=False)
    print("\n  → Saved: model_results.csv")

    # ── 6.8 Comparison Plot ───────────────────────────────────────
    print("\n[8] Plotting model comparison...")
    plot_model_comparison(all_results)

    # ── 6.9 Feature Importance (Random Forest) ────────────────────
    rf_model = trained_models["Random Forest"]
    importances = pd.Series(rf_model.feature_importances_, index=X.columns)
    importances.sort_values().plot(kind="barh", figsize=(7, 5), color="teal")
    plt.title("Feature Importance — Random Forest")
    plt.xlabel("Importance Score")
    plt.tight_layout()
    plt.savefig("feature_importance.png", dpi=150)
    plt.close()
    print("  → Saved: feature_importance.png")

    print("\n✅ Pipeline complete.\n")


if __name__ == "__main__":
    main()
