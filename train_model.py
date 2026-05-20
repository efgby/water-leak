import json
from datetime import datetime

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

from config import FEATURE_COLUMNS, METRICS_PATH, MODEL_PATH
from database import read_sql


def build_training_frame() -> pd.DataFrame:
    df = read_sql(
        """
        SELECT
            r.record_id,
            r.water_id,
            r.record_time,
            r.instant_usage,
            r.node_inflow,
            r.node_outflow,
            r.leakage_rate,
            r.pressure,
            r.is_leak,
            m.install_date
        FROM flow_record r
        JOIN water_meter m ON r.water_id = m.water_id
        """
    )

    if df.empty:
        raise RuntimeError("数据库中没有流量记录。请先运行 python generate_data.py")

    df["record_time"] = pd.to_datetime(df["record_time"])
    df["install_date"] = pd.to_datetime(df["install_date"])
    df["hour"] = df["record_time"].dt.hour
    df["day_of_week"] = df["record_time"].dt.dayofweek
    df["meter_age_days"] = (df["record_time"] - df["install_date"]).dt.days.clip(lower=0)

    return df


def main() -> None:
    df = build_training_frame()

    X = df[FEATURE_COLUMNS]
    y = df["is_leak"].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )

    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    metrics = {
        "train_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "num_samples": int(len(df)),
        "positive_ratio": float(y.mean()),
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "auc": float(roc_auc_score(y_test, y_prob)),
        "feature_columns": FEATURE_COLUMNS,
        "classification_report": classification_report(y_test, y_pred, zero_division=0),
    }

    joblib.dump(model, MODEL_PATH)

    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    print("MySQL 版模型训练完成")
    print(f"模型保存路径: {MODEL_PATH}")
    print(f"指标保存路径: {METRICS_PATH}")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
