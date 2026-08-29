"""
Firth's Implementation Synthetic Sanity Check
===============================================
Tests the custom FirthLogisticRegression solver on a linearly separable binary 
dataset where standard MLE estimates explode to infinity.

Confirms Firth's Jeffreys prior penalty produces finite, properly shrunk coefficients.
"""

import sys
import os
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from audit_firth_math import WeightedFirthLogisticRegression
from sklearn.linear_model import LogisticRegression

print("=== FIRTH PENALIZED LIKELIHOOD SYNTHETIC SEPARATION SANITY CHECK ===")

# Create a small linearly separable dataset (N=30, 2 features)
np.random.seed(42)
X_sep = np.array([
    [-2.5, -2.1], [-2.0, -1.8], [-1.5, -2.2], [-1.2, -1.5], [-1.0, -1.0],
    [-0.8, -1.2], [-0.5, -0.9], [-0.4, -0.3], [-0.2, -0.6], [-0.1, -0.2],
    [0.1, 0.2], [0.2, 0.6], [0.4, 0.3], [0.5, 0.9], [0.8, 1.2],
    [1.0, 1.0], [1.2, 1.5], [1.5, 2.2], [2.0, 1.8], [2.5, 2.1],
    [-2.2, -2.0], [-1.8, -1.9], [-1.4, -1.6], [-1.1, -1.3], [-0.9, -0.7],
    [0.9, 0.7], [1.1, 1.3], [1.4, 1.6], [1.8, 1.9], [2.2, 2.0]
])

# Perfect linear separator at x1 + x2 = 0
y_sep = (X_sep[:, 0] + X_sep[:, 1] > 0).astype(int)

print(f"Separable Dataset: N={len(y_sep)} samples (Class 0: {np.sum(y_sep==0)}, Class 1: {np.sum(y_sep==1)})")

# 1. Standard Unregularized Logistic Regression (MLE)
lr_mle = LogisticRegression(penalty=None, solver='lbfgs', max_iter=1000, random_state=42)
lr_mle.fit(X_sep, y_sep)
coef_mle = lr_mle.coef_[0]
intercept_mle = lr_mle.intercept_[0]

# 2. Custom Firth Penalized Logistic Regression
firth = WeightedFirthLogisticRegression(max_iter=100, tol=1e-5)
firth.fit(X_sep, y_sep)
coef_firth = firth.coef_
intercept_firth = firth.intercept_

print("\n=== COEFFICIENT COMPARISON ON SEPARABLE DATA ===")
print(f"Unregularized MLE Intercept: {intercept_mle:10.4f} | Coefficients: [{coef_mle[0]:10.4f}, {coef_mle[1]:10.4f}]")
print(f"Custom Firth Intercept:       {intercept_firth:10.4f} | Coefficients: [{coef_firth[0]:10.4f}, {coef_firth[1]:10.4f}]")

# Check Shrinkage
mag_mle   = np.linalg.norm(coef_mle)
mag_firth = np.linalg.norm(coef_firth)

print(f"\nMLE Coefficient Vector Magnitude:   {mag_mle:.4f}")
print(f"Firth Coefficient Vector Magnitude: {mag_firth:.4f}")
print(f"Finite & Properly Shrunk? {mag_firth < mag_mle and np.isfinite(mag_firth)}")
