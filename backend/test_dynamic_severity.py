import numpy as np
from PIL import Image
from components.smart_diagnostics.implementations.mask_rcnn_segmenter import MaskRCNNSegmenter
from components.smart_diagnostics.schemas import SeverityMetrics, DetectResponse, ReasoningResponse
from components.smart_diagnostics.pipeline.llm_reasoner import (
    create_clinical_fallback_severity,
    parse_llm_severity_assessment,
)


def test_mask_rcnn_severity_metrics_calculation():
    segmenter = MaskRCNNSegmenter(model_path="dummy_path.h5")
    
    # Test default metrics when model not loaded
    dummy_img = Image.new("RGB", (224, 224), color=(255, 255, 255))
    annotated, metrics = segmenter.predict_with_metrics(dummy_img)
    
    assert "lesion_coverage_pct" in metrics
    assert "cluster_count" in metrics
    assert "lesion_pixels" in metrics
    assert "mean_intensity" in metrics
    print("MaskRCNNSegmenter predict_with_metrics interface verified.")


def test_clinical_fallback_severity_generation():
    # Simulate acute Lumpy Skin Disease multi-modal telemetry
    vision_results = {
        "detections": [
            {
                "vit_predicted_class": "lumpy_skin",
                "vit_predicted_display": "Lumpy Skin Disease",
                "vit_confidence_pct": 94.5,
                "lesion_coverage_pct": 14.5,
                "cluster_count": 8,
            }
        ]
    }
    sev = create_clinical_fallback_severity(vision_results)
    
    assert sev.grade == "Severe"
    assert sev.stage == "Acute Eruptive / Advanced"
    assert sev.prognosis == "Guarded"
    assert "Lumpy Skin Disease" in sev.description
    assert sev.lesion_coverage_pct == 14.5
    assert sev.cluster_count == 8
    print(f"Clinical fallback severity verified: {sev.grade} - {sev.description}")


def test_healthy_baseline_severity():
    vision_results = {
        "detections": [
            {
                "vit_predicted_class": "cattle",
                "vit_predicted_display": "Cattle (Healthy)",
                "vit_confidence_pct": 98.2,
                "lesion_coverage_pct": 0.0,
                "cluster_count": 0,
            }
        ]
    }
    sev = create_clinical_fallback_severity(vision_results)
    assert sev.grade == "Healthy Baseline"
    assert sev.prognosis == "Excellent"
    assert sev.lesion_coverage_pct == 0.0
    print("Healthy baseline severity verified.")


def test_llm_severity_metadata_parsing():
    raw_llm_output = (
        "[SEVERITY_META: Grade=Severe | Stage=Acute Coalescent Phase | Prognosis=Guarded | "
        "Description=Extensive multifocal cutaneous eruptions covering 15.2% surface area with systemic viral dissemination risk.]\n\n"
        "## 1. Clinical Severity Assessment & Pathological Stage\nThe animal demonstrates extensive nodular coalescent lesions...\n\n"
        "## 2. Primary Diagnostic Assessment & Certainty Level\nHigh certainty for Lumpy Skin Disease."
    )
    vision_results = {
        "detections": [
            {
                "vit_predicted_class": "lumpy_skin",
                "vit_predicted_display": "Lumpy Skin Disease",
                "vit_confidence_pct": 95.0,
                "lesion_coverage_pct": 15.2,
                "cluster_count": 9,
            }
        ]
    }
    cleaned_report, sev = parse_llm_severity_assessment(raw_llm_output, vision_results)

    assert sev.grade == "Severe"
    assert sev.stage == "Acute Coalescent Phase"
    assert sev.prognosis == "Guarded"
    assert "Extensive multifocal cutaneous eruptions" in sev.description
    assert "[SEVERITY_META:" not in cleaned_report
    assert "## 1. Clinical Severity Assessment & Pathological Stage" in cleaned_report
    print("LLM severity metadata extraction and clean report parsing verified.")


def test_markdown_severity_metadata_parsing():
    # Exactly matching user's LLM output from screenshot
    raw_llm_output = (
        "### SEVERITY META: Grade=Mild | Stage=Early Acute | Prognosis=Guarded | "
        "Description=Minimal lesions detected, no clinical signs of severe disease yet\n\n"
        "## 1. Clinical Severity Assessment & Pathological Stage\n"
        "The image shows minimal lesion coverage and nodular cluster counts consistent with early acute manifestations of Foot and Mouth Disease (FMD).\n\n"
        "## 2. Primary Diagnostic Assessment & Certainty Level\nHigh certainty.\n\n"
        "## 3. Pathological & Morphological Rationale\nVesicular erosion morphology detected on the coronary border and interdigital cleft."
    )
    vision_results = {
        "detections": [
            {
                "vit_predicted_class": "foot_and_mouth",
                "vit_predicted_display": "Foot and Mouth Disease",
                "vit_confidence_pct": 92.0,
                "lesion_coverage_pct": 2.1,
                "cluster_count": 1,
                "spatial_correlation": "Localized at Distal Locomotor & Coronary Cleft",
            }
        ]
    }
    cleaned_report, sev = parse_llm_severity_assessment(raw_llm_output, vision_results)

    assert sev.grade == "Mild"
    assert sev.stage == "Early Acute"
    assert sev.prognosis == "Guarded"
    assert "Minimal lesions detected" in sev.description
    assert sev.diagnostic_rationale is not None
    assert "Vesicular erosion morphology" in sev.diagnostic_rationale
    assert "Distal Locomotor" in sev.spatial_correlation
    assert "### SEVERITY META" not in cleaned_report
    assert cleaned_report.startswith("## 1. Clinical Severity Assessment & Pathological Stage")
    print("Markdown format `### SEVERITY META` extraction and report cleaning verified.")


if __name__ == "__main__":
    test_mask_rcnn_severity_metrics_calculation()
    test_clinical_fallback_severity_generation()
    test_healthy_baseline_severity()
    test_llm_severity_metadata_parsing()
    test_markdown_severity_metadata_parsing()
    print("All dynamic LLM severity reasoning tests passed successfully!")
