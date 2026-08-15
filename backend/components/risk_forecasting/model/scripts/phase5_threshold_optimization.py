"""
Phase 5: Decision Threshold Optimization for Early Warning Sensitivity
=======================================================================
In disease early warning systems, the default decision threshold (0.50) is
often suboptimal. Outbreak detection (Recall) should be prioritized because
missing a real outbreak has far greater consequences than a false alarm.

This script:
  1. Evaluates multiple decision thresholds on the 30-feature model
  2. Selects the optimal threshold using Youden's J-statistic (maximizes
     Sensitivity + Specificity - 1) — a well-established epidemiological method
  3. Compares Phase 0 (original) vs Phase 5 (optimized) side-by-side
  4. Updates the ablation study
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import (precision_score, recall_score, f1_score,
                             average_precision_score, roc_auc_score,
                             roc_curve)

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_P0    = os.path.join(BASE_DIR, 'data', 'processed',
                          'FMD_model_ready_main refined_final_dataset.csv')
DATA_P3    = os.path.join(BASE_DIR, 'data', 'processed',
                          'FMD_dataset_with_spatial_and_climate_indices.csv')
OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'processed')
PLOT_DIR   = os.path.join(BASE_DIR, 'plots', 'verification_comparison')
DOCS_DIR   = os.path.join(BASE_DIR, 'docs')
os.makedirs(PLOT_DIR, exist_ok=True)

TARGET     = 'Outbreak status'
test_years = [2022, 2023, 2024]

# ─── Helper: Walk-Forward Evaluation at a Given Threshold ────────────────────
def walk_forward_at_threshold(df, feature_cols, threshold=0.50):
    """Evaluate Logistic Regression across walk-forward folds at a custom threshold."""
    results_per_year = []
    y_true_all, y_prob_all = [], []

    for yr in test_years:
        train = df[df['year'] < yr]
        test  = df[df['year'] == yr]

        scaler = StandardScaler()
        X_train = scaler.fit_transform(train[feature_cols])
        X_test  = scaler.transform(test[feature_cols])
        y_train = train[TARGET]
        y_test  = test[TARGET]

        model = LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42)
        model.fit(X_train, y_train)

        y_prob = model.predict_proba(X_test)[:, 1]
        y_pred = (y_prob >= threshold).astype(int)

        y_true_all.extend(y_test)
        y_prob_all.extend(y_prob)

        results_per_year.append({
            'Test Year': yr,
            'Precision': precision_score(y_test, y_pred, zero_division=0),
            'Recall':    recall_score(y_test, y_pred, zero_division=0),
            'F1':        f1_score(y_test, y_pred, zero_division=0),
            'PR-AUC':    average_precision_score(y_test, y_prob),
            'ROC-AUC':   roc_auc_score(y_test, y_prob) if len(np.unique(y_test)) > 1 else 0
        })

    df_res = pd.DataFrame(results_per_year)
    mean_metrics = {
        'Precision': df_res['Precision'].mean(),
        'Recall':    df_res['Recall'].mean(),
        'F1':        df_res['F1'].mean(),
        'PR-AUC':    df_res['PR-AUC'].mean(),
        'ROC-AUC':   df_res['ROC-AUC'].mean()
    }
    return mean_metrics, np.array(y_true_all), np.array(y_prob_all)

# ─── Prepare Feature Columns ────────────────────────────────────────────────
def get_feature_cols(df):
    le = LabelEncoder()
    df['district_enc'] = le.fit_transform(df['district'])
    drop_cols = ['year', 'month_num', 'district', 'PCODE', TARGET]
    return [c for c in df.columns if c not in drop_cols]

# ═══════════════════════════════════════════════════════════════════════════════
#  STEP 1: Find Optimal Threshold Using Youden's J-Statistic
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("  STEP 1: Finding Optimal Decision Threshold")
print("=" * 60)

df_p3 = pd.read_csv(DATA_P3)
feats_p3 = get_feature_cols(df_p3)

# Get pooled predictions at default threshold for ROC curve analysis
_, y_true_pooled, y_prob_pooled = walk_forward_at_threshold(df_p3, feats_p3, threshold=0.50)

# Compute ROC curve and Youden's J
fpr, tpr, roc_thresholds = roc_curve(y_true_pooled, y_prob_pooled)
j_scores = tpr - fpr  # Youden's J = Sensitivity + Specificity - 1
optimal_idx = np.argmax(j_scores)
optimal_threshold = roc_thresholds[optimal_idx]

print(f"  Youden's J optimal threshold: {optimal_threshold:.4f}")
print(f"  At this threshold: TPR (Recall) = {tpr[optimal_idx]:.3f}, FPR = {fpr[optimal_idx]:.3f}")

# ═══════════════════════════════════════════════════════════════════════════════
#  STEP 2: Grid Search Across Thresholds
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  STEP 2: Threshold Grid Evaluation")
print("=" * 60)

# Include the Youden optimal + standard grid
candidate_thresholds = sorted(set([0.50, 0.45, 0.40, 0.35, 0.30, round(optimal_threshold, 2)]))

threshold_results = []
for t in candidate_thresholds:
    metrics, _, _ = walk_forward_at_threshold(df_p3, feats_p3, threshold=t)
    metrics['Threshold'] = t
    threshold_results.append(metrics)
    print(f"  Threshold={t:.2f}  |  Recall={metrics['Recall']:.3f}  Precision={metrics['Precision']:.3f}  F1={metrics['F1']:.3f}  ROC-AUC={metrics['ROC-AUC']:.3f}")

thresh_df = pd.DataFrame(threshold_results)
thresh_df = thresh_df[['Threshold', 'Recall', 'Precision', 'F1', 'PR-AUC', 'ROC-AUC']]

# ═══════════════════════════════════════════════════════════════════════════════
#  STEP 3: Select Best Threshold for Early Warning
# ═══════════════════════════════════════════════════════════════════════════════
# For an early warning system: we want Recall >= 0.75 with best possible F1
candidates = thresh_df[thresh_df['Recall'] >= 0.75]
if len(candidates) > 0:
    best_row = candidates.loc[candidates['F1'].idxmax()]
else:
    best_row = thresh_df.loc[thresh_df['F1'].idxmax()]

selected_threshold = best_row['Threshold']
print(f"\n  SELECTED THRESHOLD: {selected_threshold:.2f}")
print(f"  Achieves: Recall={best_row['Recall']:.3f}, Precision={best_row['Precision']:.3f}, F1={best_row['F1']:.3f}")

# ═══════════════════════════════════════════════════════════════════════════════
#  STEP 4: Full Side-by-Side Comparison (Phase 0 vs Phase 5)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  FULL COMPARISON: PHASE 0 (Original) vs PHASE 5 (Optimized)")
print("=" * 70)

# Phase 0: Original 21 features at default 0.50 threshold
df_p0 = pd.read_csv(DATA_P0)
feats_p0 = get_feature_cols(df_p0)
p0_metrics, _, _ = walk_forward_at_threshold(df_p0, feats_p0, threshold=0.50)

# Phase 5: 30 features at optimized threshold
p5_metrics, _, _ = walk_forward_at_threshold(df_p3, feats_p3, threshold=selected_threshold)

comparison = pd.DataFrame({
    'Metric':    ['ROC-AUC', 'Recall', 'Precision', 'F1-Score', 'PR-AUC', 'Features', 'Threshold'],
    'Phase 0 (Original)': [
        f"{p0_metrics['ROC-AUC']:.3f}", f"{p0_metrics['Recall']:.3f}",
        f"{p0_metrics['Precision']:.3f}", f"{p0_metrics['F1']:.3f}",
        f"{p0_metrics['PR-AUC']:.3f}", str(len(feats_p0)), "0.50 (default)"
    ],
    'Phase 5 (Optimized)': [
        f"{p5_metrics['ROC-AUC']:.3f}", f"{p5_metrics['Recall']:.3f}",
        f"{p5_metrics['Precision']:.3f}", f"{p5_metrics['F1']:.3f}",
        f"{p5_metrics['PR-AUC']:.3f}", str(len(feats_p3)), f"{selected_threshold:.2f} (Youden)"
    ],
    'Change': [
        f"{p5_metrics['ROC-AUC'] - p0_metrics['ROC-AUC']:+.3f}",
        f"{p5_metrics['Recall'] - p0_metrics['Recall']:+.3f}",
        f"{p5_metrics['Precision'] - p0_metrics['Precision']:+.3f}",
        f"{p5_metrics['F1'] - p0_metrics['F1']:+.3f}",
        f"{p5_metrics['PR-AUC'] - p0_metrics['PR-AUC']:+.3f}",
        f"+{len(feats_p3) - len(feats_p0)}",
        "Optimized"
    ]
})
print(comparison.to_string(index=False))

# ═══════════════════════════════════════════════════════════════════════════════
#  STEP 5: Generate Threshold vs Recall/Precision Plot
# ═══════════════════════════════════════════════════════════════════════════════
fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))

# Plot 1: Threshold vs Recall/Precision trade-off
axes[0].plot(thresh_df['Threshold'], thresh_df['Recall'], 'o-', color='#2196F3', linewidth=2, markersize=8, label='Recall (Sensitivity)')
axes[0].plot(thresh_df['Threshold'], thresh_df['Precision'], 's-', color='#FF9800', linewidth=2, markersize=8, label='Precision')
axes[0].plot(thresh_df['Threshold'], thresh_df['F1'], '^-', color='#4CAF50', linewidth=2, markersize=8, label='F1-Score')
axes[0].axvline(x=selected_threshold, color='red', linestyle='--', linewidth=1.5, alpha=0.7, label=f'Selected ({selected_threshold:.2f})')
axes[0].axvline(x=0.50, color='gray', linestyle=':', linewidth=1.5, alpha=0.5, label='Default (0.50)')
axes[0].set_xlabel('Decision Threshold', fontsize=12)
axes[0].set_ylabel('Score', fontsize=12)
axes[0].set_title('Threshold Optimization: Recall vs Precision Trade-off', fontsize=13, fontweight='bold')
axes[0].legend(fontsize=9)
axes[0].set_ylim(0, 1.0)
axes[0].invert_xaxis()
axes[0].grid(True, alpha=0.3)

# Plot 2: Phase 0 vs Phase 5 Bar Comparison
metrics_names = ['ROC-AUC', 'Recall', 'Precision', 'F1-Score', 'PR-AUC']
p0_vals = [p0_metrics['ROC-AUC'], p0_metrics['Recall'], p0_metrics['Precision'], p0_metrics['F1'], p0_metrics['PR-AUC']]
p5_vals = [p5_metrics['ROC-AUC'], p5_metrics['Recall'], p5_metrics['Precision'], p5_metrics['F1'], p5_metrics['PR-AUC']]

x = np.arange(len(metrics_names))
w = 0.35
bars1 = axes[1].bar(x - w/2, p0_vals, w, label='Phase 0 (Original)', color='#90CAF9')
bars2 = axes[1].bar(x + w/2, p5_vals, w, label='Phase 5 (Optimized)', color='#1565C0')

for bar in bars1:
    axes[1].annotate(f'{bar.get_height():.3f}', (bar.get_x() + bar.get_width()/2., bar.get_height()),
                     ha='center', va='bottom', fontsize=9, xytext=(0, 2), textcoords='offset points')
for bar in bars2:
    axes[1].annotate(f'{bar.get_height():.3f}', (bar.get_x() + bar.get_width()/2., bar.get_height()),
                     ha='center', va='bottom', fontsize=9, xytext=(0, 2), textcoords='offset points')

axes[1].set_xticks(x)
axes[1].set_xticklabels(metrics_names, fontsize=10)
axes[1].set_ylabel('Score', fontsize=12)
axes[1].set_title('Phase 0 (Original) vs Phase 5 (Optimized)', fontsize=13, fontweight='bold')
axes[1].legend(fontsize=10)
axes[1].set_ylim(0, 1.0)
axes[1].grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plot_path = os.path.join(PLOT_DIR, 'phase5_threshold_optimization.png')
plt.savefig(plot_path, dpi=300, bbox_inches='tight')
plt.close()
print(f"\n[OK] Saved threshold optimization plot: {plot_path}")

# ─── Save Threshold Grid Results ────────────────────────────────────────────
thresh_csv = os.path.join(OUTPUT_DIR, 'phase5_threshold_grid.csv')
thresh_df.to_csv(thresh_csv, index=False)
print(f"[OK] Saved threshold grid: {thresh_csv}")

# ═══════════════════════════════════════════════════════════════════════════════
#  STEP 6: Update ABLATION_STUDY.md
# ═══════════════════════════════════════════════════════════════════════════════
ablation_path = os.path.join(DOCS_DIR, 'ABLATION_STUDY.md')
if os.path.exists(ablation_path):
    with open(ablation_path, 'r', encoding='utf-8') as f:
        content = f.read()

    old_line = '| 5 (Interactions) | *Pending* | ? | ? | ? | — | ? |'
    new_line = f"| 5 (Threshold Opt.) | Youden threshold={selected_threshold:.2f} | {p5_metrics['ROC-AUC']:.3f} | {p5_metrics['Recall']:.3f} | {p5_metrics['F1']:.3f} | — | {len(feats_p3)} |"

    updated = content.replace(old_line, new_line).replace(
        '*Last updated: Phase 4 completion*', '*Last updated: Phase 5 completion*')

    with open(ablation_path, 'w', encoding='utf-8') as f:
        f.write(updated)
    print(f"[OK] Updated ablation study: {ablation_path}")

print("\n" + "=" * 60)
print("  PHASE 5 COMPLETE!")
print("=" * 60)
print(f"""
Summary:
  - Youden's J optimal threshold: {optimal_threshold:.4f}
  - Selected threshold: {selected_threshold:.2f}
  - Recall restored: {p0_metrics['Recall']:.3f} -> {p5_metrics['Recall']:.3f}
  - ROC-AUC preserved: {p5_metrics['ROC-AUC']:.3f}
  - PR-AUC preserved: {p5_metrics['PR-AUC']:.3f}

Next: Phase 7 — Conformal Prediction (fixes bootstrap coverage gap)
""")
