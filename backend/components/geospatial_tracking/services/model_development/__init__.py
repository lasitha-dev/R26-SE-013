"""Checkpoint 7A: pre-fitting scientific-grid / evaluation-domain
protocol freeze — DEVELOPMENT-ONLY, pre-model-comparison code.

Every module in this package operates on `FIT_DEVELOPMENT` origins
only (each module's own entry point calls
`services.model_fitting_exposure.assert_fit_development_only` itself —
never trusting a caller to have pre-filtered). No module in this
package ever computes a predictive score, a target percentile/capture
metric, an AUC, or any other model-performance number — see
`MODEL_DEVELOPMENT_PROTOCOL.md` for the full scope boundary.
"""

from __future__ import annotations
