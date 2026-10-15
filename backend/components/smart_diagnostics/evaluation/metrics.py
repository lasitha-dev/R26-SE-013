"""Metrics with explicit misses, empty-mask conventions and group uncertainty."""
import numpy as np
from .audit import CLASSES


def iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x2-x1) * max(0, y2-y1)
    union = max(0, a[2]-a[0])*max(0, a[3]-a[1]) + max(0, b[2]-b[0])*max(0, b[3]-b[1]) - intersection
    return intersection / union if union else 0.0


def classification(targets, predictions, probabilities=None):
    if not targets:
        return dict(n=0, accuracy=None, macro_f1=None, per_class={})
    confusion = np.zeros((4, 5), dtype=int)  # Last column: missed/unavailable/wrong ROI.
    for target, prediction in zip(targets, predictions, strict=True):
        confusion[CLASSES.index(target), CLASSES.index(prediction) if prediction in CLASSES else 4] += 1
    per_class = {}
    for i, name in enumerate(CLASSES):
        tp = int(confusion[i, i]); support = int(confusion[i].sum()); predicted = int(confusion[:, i].sum())
        precision = tp / predicted if predicted else 0.0
        recall = tp / support if support else None
        f1 = 2 * tp / (support + predicted) if support + predicted else None
        per_class[name] = dict(support=support, precision=precision if predicted else None, recall=recall, f1=f1)
    # Missing target classes are not assigned a fabricated zero or perfect F1.
    f1s = [p["f1"] for p in per_class.values() if p["support"]]
    result = dict(n=len(targets), accuracy=float(np.trace(confusion[:, :4]) / len(targets)),
                  macro_f1=float(np.mean(f1s)), all_classes_supported=all(p["support"] for p in per_class.values()),
                  confusion_rows=CLASSES, confusion_columns=CLASSES+["miss_or_wrong_roi"],
                  confusion_matrix=confusion.tolist(), per_class=per_class)
    if probabilities is not None and len(probabilities):
        p = np.asarray(probabilities, dtype=float)
        if p.shape != (len(targets), 4) or not np.isfinite(p).all() or np.any(p < 0) or np.any(p > 1) or not np.allclose(p.sum(axis=1), 1, atol=1e-5):
            raise ValueError("Invalid class probabilities")
        y = np.array([CLASSES.index(t) for t in targets])
        correct = p.argmax(axis=1) == y
        confidence = p.max(axis=1)
        ece = 0.0
        for lo, hi in zip(np.linspace(0, 1, 11)[:-1], np.linspace(0, 1, 11)[1:]):
            selected = (confidence >= lo) & ((confidence < hi) if hi < 1 else (confidence <= hi))
            if selected.any():
                ece += selected.mean() * abs(correct[selected].mean() - confidence[selected].mean())
        result.update(brier=float(((p-np.eye(4)[y])**2).sum(axis=1).mean()),
                      negative_log_likelihood=float(-np.log(np.maximum(p[np.arange(len(y)), y], 1e-12)).mean()),
                      ece_10_equal_width_bins=float(ece))
    return result


def selective_curve(targets, probabilities, thresholds=(0, .6, .7, .8, .9, .95), margins=(0, .15)):
    p = np.asarray(probabilities)
    if not len(p):
        return []
    classification(targets, [CLASSES[i] for i in p.argmax(axis=1)], p)
    sorted_p = np.sort(p, axis=1)
    curve = []
    for threshold in thresholds:
        for margin in margins:
            accepted = (p.max(axis=1) >= threshold) & (sorted_p[:, -1]-sorted_p[:, -2] >= margin)
            ids = np.flatnonzero(accepted)
            curve.append(dict(confidence_threshold=threshold, margin=margin, accepted=len(ids),
                coverage=len(ids)/len(p),
                metrics=classification([targets[i] for i in ids], [CLASSES[p[i].argmax()] for i in ids])))
    return curve


def detection(rows, predictions, confidence=.25, minimum_iou=.5):
    tp = fp = total_gt = selected_hits = positive_images = 0
    for row, prediction in zip(rows, predictions, strict=True):
        gt = row["boxes"] or []
        total_gt += len(gt)
        detections = sorted([d for d in prediction.get("detections", []) if d["confidence"] >= confidence], key=lambda d: -d["confidence"])
        if gt:
            positive_images += 1
            selected_hits += bool(detections and max(iou(detections[0]["bbox"], b["bbox"]) for b in gt) >= minimum_iou)
        matched = set()
        for det in detections:
            options = [(iou(det["bbox"], b["bbox"]), i) for i, b in enumerate(gt)
                       if i not in matched and b["disease"] == det["class_name"]]
            score, index = max(options, default=(0, -1))
            if score >= minimum_iou:
                matched.add(index); tp += 1
            else:
                fp += 1
    return dict(confidence_threshold=confidence, iou_threshold=minimum_iou, images=len(rows),
                positive_images=positive_images, ground_truth_boxes=total_gt, true_positive=tp, false_positive=fp,
                precision=tp/(tp+fp) if tp+fp else None, recall=tp/total_gt if total_gt else None,
                selected_roi_recall=selected_hits/positive_images if positive_images else None,
                selected_roi_semantics="IoU with any annotated region, class agnostic; not proof of lesion or selected-animal relevance")


def binary_metrics(target, predicted):
    target, predicted = np.asarray(target, dtype=bool), np.asarray(predicted, dtype=bool)
    if target.shape != predicted.shape or target.ndim != 2:
        raise ValueError("Pixel masks must have matching two-dimensional shapes; never resize ground truth silently.")
    tp = int((target & predicted).sum()); fp = int((~target & predicted).sum()); fn = int((target & ~predicted).sum())
    positive = int(target.sum())
    return dict(tp=tp, fp=fp, fn=fn, target_pixels=positive, pixels=target.size,
                dice=2*tp/(2*tp+fp+fn) if positive else None,
                iou=tp/(tp+fp+fn) if positive else None,
                precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/positive if positive else None,
                negative_false_positive_fraction=fp/target.size if not positive else None)


def group_bootstrap(rows, statistic, repetitions=300, seed=13013):
    """Groups are conservative photo-lineage bundles unless animal IDs are supplied."""
    groups = {}
    for row in rows:
        groups.setdefault(row["group_id"], []).append(row)
    keys = list(groups)
    if len(keys) < 2:
        return dict(lower=None, upper=None, groups=len(keys), repetitions=0)
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(repetitions):
        sample = [r for i in rng.integers(0, len(keys), len(keys)) for r in groups[keys[i]]]
        values.append(statistic(sample))
    return dict(lower=float(np.quantile(values, .025)), upper=float(np.quantile(values, .975)),
                groups=len(keys), repetitions=repetitions, seed=seed,
                interpretation="photo-lineage bootstrap; not verified animal/farm uncertainty")
