from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from components.smart_diagnostics.implementations.lesion_segmenter import LesionSegmenter
from components.smart_diagnostics.implementations.vit_classifier import ViTClassifier
from components.smart_diagnostics.implementations.yolo_detector import YOLODetector
from components.smart_diagnostics.model_errors import ModelUnavailable
from components.smart_diagnostics.pipeline.llm_reasoner import generate_report_result, _build_user_prompt
from .conftest import FakeDetector, FakeClassifier


def test_photo_orientation_is_normalized_before_crop_coordinates():
    import io
    from components.smart_diagnostics.image_service import open_image_from_bytes
    image = Image.new('RGB',(60,30))
    exif = Image.Exif(); exif[274] = 6
    buffer = io.BytesIO(); image.save(buffer,format='JPEG',exif=exif)
    normalized = open_image_from_bytes(buffer.getvalue())
    assert normalized.size == (30,60)
    assert normalized.mode == 'RGB'


def segmenter(output, **kwargs):
    adapter = LesionSegmenter('unused.keras', image_size=8, **kwargs)
    adapter.model = SimpleNamespace(predict=lambda *a, **k: output, output_names=['mask_output', 'class_output'])
    return adapter


@pytest.mark.parametrize('bad', [np.zeros((1,8,8,2)), np.full((1,8,8,1), np.nan),
    np.full((1,8,8,1), np.inf), np.full((1,8,8,1), 1.1), np.zeros((8,8)), {'wrong': np.zeros((1,8,8,1))}])
def test_invalid_masks_never_become_measured_zero(bad):
    image, result = segmenter(bad).predict_with_metrics(Image.new('RGB',(32,64)))
    assert image is None and result['status'] == 'failed'
    assert result['lesion_coverage_pct'] is None and result['cluster_count'] is None


def test_float_precision_and_named_output_selection():
    mask = np.full((1,8,8,1), .5001, dtype=np.float32)
    adapter = segmenter([mask, np.ones((1,4))])
    _, result = adapter.predict_with_metrics(Image.new('RGB', (32,64)))
    assert result['status'] == 'completed_with_regions'
    assert result['lesion_coverage_pct'] == 100 and result['lesion_pixels'] == 2048
    assert result['mean_intensity'] == pytest.approx(.5001)


def test_region_filter_has_eight_connectivity_and_removes_small_noise():
    mask = np.zeros((1,8,8,1), dtype=np.float32)
    mask[0,1:4,1:4,0] = 1
    mask[0,4,4,0] = 1  # diagonal belongs to the same component
    mask[0,7,7,0] = 1  # independent noise
    _, result = segmenter(mask,min_region_fraction=.1).predict_with_metrics(Image.new('RGB',(8,8)))
    assert result['cluster_count'] == 1 and result['lesion_pixels'] == 10
    assert result['connectivity'] == 8


def test_measured_empty_mask_is_distinct_from_missing_weights(tmp_path):
    _, empty = segmenter(np.zeros((1,8,8,1))).predict_with_metrics(Image.new('RGB',(8,8)))
    _, missing = LesionSegmenter(str(tmp_path/'missing.keras')).predict_with_metrics(Image.new('RGB',(8,8)))
    assert empty['status'] == 'completed_no_regions' and empty['lesion_coverage_pct'] == 0
    assert missing['status'] == 'unavailable' and missing['lesion_coverage_pct'] is None
    with pytest.raises(ModelUnavailable):
        ViTClassifier(str(tmp_path/'missing.pt'))._ensure_loaded()
    with pytest.raises(ModelUnavailable):
        YOLODetector(str(tmp_path/'missing.pt'))._resolve_model_path()


def test_incompatible_vit_never_sets_loaded_model(tmp_path):
    checkpoint = tmp_path/'invalid.pt'
    checkpoint.write_bytes(b'invalid weights')
    model = SimpleNamespace(heads=SimpleNamespace(head=SimpleNamespace(in_features=2)),
                            load_state_dict=lambda value: None)
    classifier = ViTClassifier(str(checkpoint))
    with patch('torchvision.models.vit_b_16',return_value=model), patch('torch.load', side_effect=ValueError('bad checkpoint')):
        with pytest.raises(ModelUnavailable): classifier._ensure_loaded()
    assert not classifier.is_loaded and classifier.load_state == 'unavailable'


def test_reasoning_fallback_preserves_original_assessment_and_zero_score():
    baseline = dict(grade='Mild', score=0, composite_score=0, lesion_coverage_pct=None,
                    cluster_count=None, needs_review=True, confidence_level='Low')
    vision = dict(upstream_severity=baseline, detections=[dict(vit_predicted_class='lumpy_skin',
        vit_predicted_display='Lumpy Skin Disease', segmentation_status='unavailable')])
    with patch('openai.OpenAI',side_effect=ConnectionError('offline')):
        outcome = generate_report_result(vision)
    assert outcome.status == 'fallback'
    assert outcome.severity_assessment.score == outcome.severity_assessment.composite_score == 0
    assert outcome.severity_assessment.needs_review and outcome.severity_assessment.lesion_coverage_pct is None
    assert 'unavailable / not measured' in _build_user_prompt(vision['detections'], {})


def test_no_analysis_never_produces_a_healthy_assessment():
    outcome = generate_report_result({'detections':[]})
    assert outcome.status == 'unavailable' and outcome.severity_assessment is None


def test_failed_segmenter_keeps_classification_but_reports_unknown_measurements(create_app, dummy_rgb_image_bytes, mock_yolo_single_detection):
    broken = SimpleNamespace(predict_with_metrics=lambda image: (_ for _ in ()).throw(RuntimeError('failed')))
    client = TestClient(create_app(detector=FakeDetector(mock_yolo_single_detection),
        classifier=FakeClassifier(dict(name='Lumpy Skin Disease',confidence=90,all_probabilities={})), segmenter=broken))
    result = client.post('/api/detect',files={'image':('cow.jpg',dummy_rgb_image_bytes,'image/jpeg')}).json()
    assert result['disease']['name'] == 'Lumpy Skin Disease'
    assert result['segmentation']['status'] == 'failed' and result['symptoms_image'] is None
    assert result['severity']['lesion_coverage_pct'] is None
    assert 'segmentation_failed' in result['review']['reasons']
    assert 'Body site is unknown' in result['spatial_correlation']


def test_api_preserves_supplied_measurements_through_unavailable_reasoning(client):
    body = dict(cattle_detected=True,detections=[],disease=dict(name='Lumpy Skin Disease',confidence=90,all_probabilities={}),
        best_detection=dict(bbox=[0,0,100,100],confidence=.9,bbox_normalized=dict(x1=0,y1=0,x2=1,y2=1)),
        severity=dict(grade='Moderate',score=.42,composite_score=.42,lesion_coverage_pct=12.25,cluster_count=3,needs_review=True),
        segmentation=dict(status='completed_with_regions',lesion_coverage_pct=12.25,cluster_count=3))
    with patch('openai.OpenAI',side_effect=ConnectionError('offline')):
        result = client.post('/api/reason',json=body).json()
    assert result['status'] == 'fallback'
    assert result['severity_assessment']['lesion_coverage_pct'] == 12.25
    assert result['severity_assessment']['grade'] == 'Moderate' and result['severity_assessment']['needs_review']


@pytest.mark.parametrize('disease', ['Lumpy Skin Disease', 'Mastitis', 'Foot and Mouth Disease'])
def test_three_model_evidence_and_thresholds_survive_api_and_explanation(
        disease, create_app, dummy_rgb_image_bytes, mock_yolo_single_detection):
    mask = SimpleNamespace(predict_with_metrics=lambda image: (image, dict(
        status='completed_with_regions', lesion_coverage_pct=35, cluster_count=3,
        contract_status='verified')))
    client = TestClient(create_app(detector=FakeDetector(mock_yolo_single_detection),
        classifier=FakeClassifier(dict(name=disease, confidence=90,
            all_probabilities={disease: 90}, top2_margin=80)), segmenter=mask))
    response = client.post('/api/detect', files={'image': ('cow.jpg', dummy_rgb_image_bytes, 'image/jpeg')})
    assert response.status_code == 200
    payload = response.json()
    visual = payload['severity']['visual_assessment']
    assert visual['grade'] == 'Severe' and visual['coverage_pct'] == 35
    assert visual['thresholds_pct'] == dict(moderate_min_pct=10, severe_min_pct=30)
    assert visual['evidence']['yolo_confidence'] == payload['best_detection']['confidence']
    assert visual['evidence']['vit_confidence_pct'] == payload['disease']['confidence']
    assert 'visual_thresholds_unvalidated' in payload['review']['reasons']
    if disease != 'Lumpy Skin Disease':
        assert payload['severity']['grade'] == 'Unassessable'
    with patch('openai.OpenAI', side_effect=ConnectionError('offline')):
        explained = client.post('/api/reason', json=payload)
    assert explained.status_code == 200
    assert explained.json()['severity_assessment']['visual_assessment'] == visual


def test_high_mask_coverage_cannot_bypass_low_classifier_confidence(
        create_app, dummy_rgb_image_bytes, mock_yolo_single_detection):
    mask = SimpleNamespace(predict_with_metrics=lambda image: (image, dict(
        status='completed_with_regions', lesion_coverage_pct=90, cluster_count=9)))
    client = TestClient(create_app(detector=FakeDetector(mock_yolo_single_detection),
        classifier=FakeClassifier(dict(name='Lumpy Skin Disease', confidence=55,
            all_probabilities={}, top2_margin=5)), segmenter=mask))
    payload = client.post('/api/detect', files={'image': ('cow.jpg', dummy_rgb_image_bytes, 'image/jpeg')}).json()
    assert payload['severity']['grade'] == 'Unassessable'
    assert payload['severity']['score'] is None
    assert payload['severity']['visual_assessment']['coverage_pct'] == 90
    assert 'classifier_confidence_missing_or_low' in payload['review']['reasons']
