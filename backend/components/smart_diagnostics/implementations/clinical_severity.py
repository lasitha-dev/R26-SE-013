"""Versioned clinical checklists; no grades are inferred from image confidence.

FMD uses conservative profile matching adapted from Ausvet 2023, Appendix E.
It is field triage, not a validated universal clinical severity scale. Mastitis
uses the IDF clinical-sign hierarchy described by Krebs et al. 2023.
"""
from __future__ import annotations

import re
from typing import Any

from ..schemas import ClinicalObservations, SeverityMetrics

FMD_REFERENCE = {"title": "Ausvet 2023: Animal Health and Welfare Manual, Appendix E, p.40",
    "url": "https://www.ausvet.com.au/wp-content/uploads/2023/05/Animal-Health-and-Welfare-Manual-English-compressed-1.pdf#page=46"}
MASTITIS_REFERENCE = {"title": "Krebs et al. 2023: Severity of Clinical Mastitis and Bacterial Shedding (IDF grading)",
    "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC10537990/"}
GRADES = {1: "Mild", 2: "Moderate", 3: "Severe"}


def clinical_disease_key(name: str | None) -> str | None:
    key = re.sub(r"[^a-z]", "", (name or "").lower())
    if key in ("fmd", "footandmouth", "footandmouthdisease"):
        return "foot_and_mouth"
    return "mastitis" if key == "mastitis" else None


def assess_clinical_severity(name: str, observations: ClinicalObservations | dict | None = None,
                             signals: dict[str, Any] | None = None) -> SeverityMetrics:
    disease = clinical_disease_key(name)
    if disease is None:
        raise ValueError("Clinical checklists support FMD and mastitis only.")
    obs = ClinicalObservations.model_validate(observations) if observations is not None else None
    if obs is not None and obs.disease != disease:
        raise ValueError("The clinical checklist does not match the predicted disease.")
    signals = signals or {}
    required = (("milk_abnormal", "udder_inflammation", "systemic_illness") if disease == "mastitis" else
                ("affected_feet", "mouth_lesion_cm", "appetite", "mentation", "heel_and_coronary_involved", "unable_to_stand"))
    # A checklist needs complete findings and vet confirmation before grading;
    # unknown signs are never filled in from the image model's confidence.
    missing = [field for field in required if obs is None or getattr(obs, field) is None]
    if obs is None or not obs.vet_confirmed:
        missing.insert(0, "vet_confirmed")
    evidence = []
    grade_number = None
    reason = "Clinical observations are incomplete or have not been confirmed by the reviewing veterinarian."
    if not missing and obs is not None:
        if disease == "mastitis":
            evidence = [f"Abnormal milk: {obs.milk_abnormal}.", f"Udder inflammation: {obs.udder_inflammation}.",
                        f"Systemic illness assessed in this clinical context: {obs.systemic_illness}."]
            if obs.milk_abnormal and obs.systemic_illness and not obs.udder_inflammation:
                reason = "Systemic illness with no reported udder inflammation does not match the complete reference profile; veterinary assessment is required."
            elif obs.milk_abnormal:
                grade_number = 3 if obs.systemic_illness else (2 if obs.udder_inflammation else 1)
                reason = "Reported findings match the IDF milk / udder / systemic clinical-sign hierarchy."
            else:
                reason = "The reported findings do not establish the clinical-mastitis profile required by this rubric; no healthy or low-severity grade is inferred."
        else:
            foot_band = 1 if obs.affected_feet <= 1 else (2 if obs.affected_feet <= 3 else 3)
            mouth_band = 1 if obs.mouth_lesion_cm < 2 else (2 if obs.mouth_lesion_cm <= 5 else 3)
            appetite_band = {"normal": 1, "reduced": 2, "none": 3}[obs.appetite]
            mentation_band = {"normal": 1, "slightly_dull": 2, "depressed": 3}[obs.mentation]
            bands = (foot_band, mouth_band, appetite_band, mentation_band)
            evidence = [f"Affected feet among four examined: {obs.affected_feet} ({GRADES[foot_band]} extent band).",
                        f"Largest measured oral lesion: {obs.mouth_lesion_cm:g} cm ({GRADES[mouth_band]} size band).",
                        f"Appetite: {obs.appetite}; mentation: {obs.mentation}.",
                        f"Heel and coronary involvement: {obs.heel_and_coronary_involved}; unable to stand: {obs.unable_to_stand}."]
            # The FMD adaptation requires all four bands to agree; mixed signs
            # remain unassessable instead of being averaged into a clinical grade.
            if len(set(bands)) == 1:
                candidate = bands[0]
                if obs.affected_feet == 0 and obs.mouth_lesion_cm == 0:
                    reason = "No observed foot or oral lesions establish an FMD triage profile; this is not a healthy-animal determination."
                elif candidate == 3 and not obs.heel_and_coronary_involved:
                    reason = "The severe reference profile includes heel/coronary involvement; findings do not fully match it."
                elif candidate < 3 and (obs.unable_to_stand or obs.heel_and_coronary_involved):
                    reason = "Reported welfare/foot findings do not support assigning the lower reference profile. Veterinary grading is required."
                else:
                    grade_number = candidate
                    reason = "Findings match the selected field-triage profile. Concordant-profile matching is a conservative project adaptation, not an externally validated clinical classifier."
            else:
                reason = "The lesion-size, affected-foot, appetite and mentation bands are mixed. The reference does not define a validated aggregation rule; veterinary grading is required."
    # Welfare concerns remain visible even when other findings are missing.
    if obs is not None and (obs.systemic_illness or obs.unable_to_stand):
        evidence.append("Reported systemic illness or inability to stand requires prompt in-person veterinary assessment, even if this checklist is incomplete.")
    grade = GRADES[grade_number] if grade_number is not None else "Unassessable"
    target = "clinical_mastitis_grade" if disease == "mastitis" else "fmd_field_triage_profile"
    rubric = "mastitis_idf_signs_v1" if disease == "mastitis" else "fmd_ausvet_concordant_profile_v1"
    description = reason + " Rule-based research decision support; accuracy in this application has not been clinically validated."
    return SeverityMetrics(score=float(grade_number) if grade_number is not None else None,
        composite_score=None, grade=grade, description=description, prognosis="Not assessed",
        diagnostic_rationale="Grades use reported clinical observations. Image classification confidence, attention, bounding-box area and mask coverage do not determine clinical grade.",
        formatted=f"{grade}{' FMD field triage' if disease == 'foot_and_mouth' else ''} (provisional)" if grade_number else "Unassessable - clinical review needed",
        source="clinical_rules", confidence_level="Not validated", needs_review=True,
        rubric_id=rubric, assessment_status="provisional" if grade_number else "unassessable",
        assessment_target=target, evidence=evidence, missing_observations=missing,
        references=[MASTITIS_REFERENCE if disease == "mastitis" else FMD_REFERENCE], clinical_observations=obs,
        visual_assessment=signals.get("visual_assessment"),
        lesion_coverage_pct=signals.get("lesion_coverage_pct"),
        cluster_count=signals.get("cluster_count"), mean_intensity=signals.get("mean_intensity"))


def clinical_report(name: str, assessment: SeverityMetrics) -> str:
    evidence = "\n".join(f"- {item}" for item in assessment.evidence) or "Clinical checklist findings have not been supplied."
    missing = ", ".join(assessment.missing_observations)
    return (f"## 1. Clinical Checklist Assessment\n\n{assessment.formatted}. {assessment.description}\n\n"
            + (f"Missing findings: {missing}.\n\n" if missing else "")
            + f"## 2. Diagnostic Assessment\n\nImage model prediction: {name}. The checklist does not confirm disease identity or estimate disease stage or prognosis.\n\n"
            + f"## 3. Recorded Evidence\n\n{evidence}\n\n{assessment.diagnostic_rationale}")
