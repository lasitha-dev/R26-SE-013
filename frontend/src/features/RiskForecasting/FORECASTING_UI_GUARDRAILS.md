# Risk Forecasting UI Architectural and Access Guardrails

This document establishes the scientific, operational, and presentation guardrails for the **Seasonal Risk Forecasting** frontend module (`component/disease-forecasting` branch).

> [!IMPORTANT]
> **Scope & Authority Note:**
> This document governs the Risk Forecasting UI contracts within `frontend/src/features/RiskForecasting/`. Cross-component integration rules, shared navigation reconciliation, and global design system alignments require separate team approval upon main-branch integration. This document does not claim to alter or bind other feature branches without explicit integration consent.

---

## 1. Scientific & Epidemiological Guardrails

1. **District-Level Predictions Only:** Outbreak probabilities are computed strictly at the administrative district level (25 Sri Lankan districts).
2. **No Farm-Level Risk Percentages:** Never calculate, estimate, or display farm-level probability percentages. Farm location mapping must remain geographical placement within a district boundary.
3. **Forecast vs. Diagnosis:** A seasonal risk forecast is a statistical prediction of outbreak likelihood based on climatological and historical features—it is **not** active disease detection or clinical diagnosis.
4. **Forecasting-Content CTA Prohibition:** Do not embed forecasting-content Call-to-Action buttons (e.g. *"Report Symptoms"*, *"Open AI Diagnosis"*, *"Diagnose This Forecast"*) linking risk forecasting results to the `ai-smart-diagnosis` module. The modules serve distinct epidemiological functions. (Note: Global app navigation items outside forecasting content are governed separately by team reconciliation).
5. **Stage 1 Occurrence vs. Stage 2 Output:** Stage 1 predicts outbreak occurrence likelihood. Stage 2 provides the backend-returned severity/suppressor output when evaluated. The UI must use `stage2.severity_predicted`, `stage2.evaluated`, `stage2.model_name`, `stage2.notes`, and `action_required` according to the backend response. It must not create its own severity-code mapping.
6. **Model Independence & Evaluation Status:**
   - FMD Stage 1 and Stage 2 remain distinct.
   - LSD Stage 1 outbreak probability and LSD Stage 2 quiet-period suppressor remain distinct.
   - The UI must not imply that LSD Stage 2 is validated for active-wave severity discrimination.
   - When Stage 1 is below threshold, Stage 2 evaluation is explicitly bypassed (`stage2.evaluated = false`). The UI must display `"Stage 2 model bypassed (Stage 1 prob < 0.40)"` and must never display active severity warnings when bypassed.
7. **Mandatory LSD Scientific Disclaimer:** The LSD prediction response includes a mandatory backend-provided disclaimer. The UI must display `response.disclaimer` verbatim in authorized views where LSD Stage 2 technical output is shown. The frontend must not replace, shorten, or reinterpret that scientific disclaimer.
8. **Uncertainty Quantification (UQ) Role-Based Presentation:** UQ data fields (`uncertainty.status`, `uncertainty.reliability`, `uncertainty.prediction_set`, `uncertainty.empirical_coverage_pct`, `uncertainty.notes`) must be presented according to role context:
   - **FARMER:** No technical UQ panel. Simple data-confidence or fallback wording only when necessary.
   - **VETERINARY_OFFICER:** Concise operational uncertainty summary. Clearly disclose unreliable or unavailable uncertainty.
   - **DAPH_OFFICIAL (with `viewDataQuality` / `viewModelTransparency` capability):** Complete technical UQ fields may be displayed.
9. **Log-Odds Decomposition:** For linear models, feature contributions are expressed in linear log-odds units ($\beta_i \cdot x_i$). Log-odds must **never** be converted into percentage feature importances.

---

## 2. Presentation & Fail-Closed Access Guardrails

10. **Frontend Presentation Gating Only:** Frontend access checks (`ViewerContext`) control presentation and view visibility only. Real authorization and district-scoping must be enforced by the backend API once shared authentication is integrated.
11. **Fail-Closed Defaulting:** Any missing, invalid, or unauthenticated `ViewerContext` must fail closed (deny access, hide sensitive views, and return empty authorization sets).
12. **Role/Scope Compatibility Matrix:** Viewer contexts must satisfy strict role-to-scope compatibility (`FARMER` $\rightarrow$ `FARM` only; `VETERINARY_OFFICER` $\rightarrow$ `DISTRICT` / `PROVINCE`; `DAPH_OFFICIAL` $\rightarrow$ `DISTRICT` / `PROVINCE` / `NATIONAL`). Incompatible combinations fail closed.
13. **No Default Scope Escalation:** A missing or invalid `scopeLevel` must **never** default to `NATIONAL` authorization or automatically grant access to all 25 districts.
14. **No Runtime Mock Operational Data:** The application must never generate fake prediction values, fake district risk tiers, or fake farm-level telemetry. API error states must be displayed transparently.
15. **Canonical Role & Scope Names:** Use only canonical constants (`FARMER`, `VETERINARY_OFFICER`, `DAPH_OFFICIAL`, and `FARM`, `DISTRICT`, `PROVINCE`, `NATIONAL`). Non-canonical aliases (e.g. `VET`, `ADMIN`) must fail closed.
16. **Explicit Capabilities:** Permissions (`viewDataQuality`, `viewModelTransparency`, `manageAlerts`, `recordResponse`, `viewReports`) require strict boolean `true`. Roles alone do not grant technical capability access.
17. **Shared Data Integration:** Historical surveillance logs and disease records require future backend verification. Unverified diagnostic outputs must not feed historical surveillance models.
18. **Stitch Reference Mockups:** Mockup assets under `frontend/public/design/` are visual design references only (`REFERENCE ONLY`).
19. **Shared UI File Reconciliation:** `AppShell`, `SideNavBar`, and `TopHeader` under `shared_components/` are duplicated across feature branches and require future team reconciliation.
20. **Deferred Screen Classification:** Deferred screens (`DEFER` state) must be clearly documented as pending future development and must not be presented to users as fully implemented features.
