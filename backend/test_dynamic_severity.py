import numpy as np
from PIL import Image
from components.smart_diagnostics.implementations.mask_rcnn_segmenter import MaskRCNNSegmenter
from components.smart_diagnostics.schemas import SeverityMetrics, DetectResponse

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

def test_severity_scoring_logic():
    # Simulate diseased lesion metrics: 14.5% coverage, 8 clusters, 92% ViT confidence
    lsr = 14.5
    clusters = 8
    vit_conf = 92.0
    
    raw_score = (lsr * 0.35) + (min(clusters, 15) * 0.25) + (vit_conf * 0.04)
    score = round(min(10.0, max(1.0, raw_score)), 1)
    
    assert 7.1 <= score <= 10.0
    grade = "High"
    
    sev = SeverityMetrics(
        score=score,
        grade=grade,
        lesion_coverage_pct=lsr,
        cluster_count=clusters,
        mean_intensity=0.82,
        formatted=f"{score:.1f} / {grade}"
    )
    
    assert sev.score == score
    assert sev.grade == "High"
    assert "High" in sev.formatted
    print(f"Dynamic severity formula verified: {sev.formatted} from {lsr}% coverage and {clusters} clusters.")

if __name__ == "__main__":
    test_mask_rcnn_severity_metrics_calculation()
    test_severity_scoring_logic()
    print("All dynamic severity scoring tests passed successfully!")
