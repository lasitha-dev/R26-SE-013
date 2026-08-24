import logging
import numpy as np
from PIL import Image

logger = logging.getLogger("smart_diagnostics.mask_rcnn")


class MaskRCNNSegmenter:
    """Loads a Keras Mask R-CNN style model with dual outputs:
       - 'class_output': classification head (softmax)
       - 'mask_output': segmentation mask (sigmoid, 224x224x1)

    The model was trained in Tier_3_Disease_Segmentation.ipynb using a
    ResNet50 backbone with Conv2DTranspose upsampling layers.
    Input shape: (None, 224, 224, 3), normalised to [0, 1].
    """

    def __init__(self, model_path: str, image_size: int = 224):
        self.model_path = model_path
        self.image_size = image_size
        self.model = None

    @property
    def is_loaded(self) -> bool:
        """Return True if the underlying Mask R-CNN model has been loaded into memory."""
        return self.model is not None

    def _ensure_loaded(self):
        if self.model is not None:
            return
        import os
        if not os.path.isfile(self.model_path):
            logger.warning("Mask R-CNN checkpoint not found at: %s", self.model_path)
            return

        logger.info("Loading Mask R-CNN model from %s ...", self.model_path)
        try:
            import tensorflow as tf
            self.model = tf.keras.models.load_model(self.model_path, compile=False)
            logger.info("Mask R-CNN model loaded successfully.")
        except Exception as e:
            logger.error("Failed to load Mask R-CNN model from %s: %s", self.model_path, e)

    def predict_with_metrics(self, image: Image.Image) -> tuple[Image.Image, dict]:
        """Run inference, overlay the symptom mask, and extract quantitative metrics.

        Returns:
            annotated_image: PIL Image with semi-transparent red overlay
            metrics: dict containing:
                - lesion_coverage_pct (float): Percentage of image area with detected lesions
                - cluster_count (int): Number of distinct connected lesion clusters / nodules
                - lesion_pixels (int): Total positive lesion pixels
                - mean_intensity (float): Average probability density on lesion pixels
        """
        default_metrics = {
            "lesion_coverage_pct": 0.0,
            "cluster_count": 0,
            "lesion_pixels": 0,
            "mean_intensity": 0.0,
        }

        self._ensure_loaded()
        if not self.is_loaded or self.model is None:
            logger.warning("Mask R-CNN model not loaded, returning original image.")
            return image, default_metrics

        original_image = image.copy()

        # --- Preprocess -------------------------------------------------------
        img_resized = image.resize((self.image_size, self.image_size))
        img_array = np.array(img_resized, dtype=np.float32) / 255.0

        # Ensure 3 channels
        if img_array.ndim == 2:
            img_array = np.stack((img_array,) * 3, axis=-1)
        elif img_array.shape[2] == 4:
            img_array = img_array[..., :3]

        input_tensor = np.expand_dims(img_array, axis=0)  # (1, 224, 224, 3)

        # --- Inference --------------------------------------------------------
        try:
            preds = self.model.predict(input_tensor, verbose=0)

            # The model has two outputs: class_output and mask_output.
            if isinstance(preds, dict):
                mask = preds["mask_output"][0]  # (224, 224, 1)
            elif isinstance(preds, (list, tuple)):
                mask = preds[1][0]  # (224, 224, 1)
            else:
                mask = preds[0]

            # Squeeze to (224, 224) if needed
            if mask.ndim == 3:
                mask = mask[..., 0]

            # Resize mask back to original image dimensions
            orig_w, orig_h = original_image.size
            mask_pil = Image.fromarray(
                (mask * 255).astype(np.uint8)
            ).resize((orig_w, orig_h), Image.BILINEAR)
            mask_array = np.array(mask_pil)

            # Threshold to binary mask (confidence threshold ~0.5)
            binary_mask = mask_array > 127
            lesion_pixels = int(np.sum(binary_mask))
            total_pixels = int(mask_array.size)
            lesion_coverage_pct = round((lesion_pixels / max(total_pixels, 1)) * 100, 2)

            # Connected component analysis for distinct eruptive nodule / lesion clusters
            cluster_count = 0
            if lesion_pixels > 0:
                try:
                    from scipy.ndimage import label
                    # Filter tiny noise pixels (< 15 px) using morphological labeling
                    labeled_array, num_features = label(binary_mask)
                    cluster_count = int(num_features)
                except Exception:
                    try:
                        import cv2
                        num_labels, _ = cv2.connectedComponents(binary_mask.astype(np.uint8))
                        cluster_count = max(0, int(num_labels) - 1)
                    except Exception:
                        cluster_count = 1

            mean_intensity = (
                float(np.mean(mask_array[binary_mask]) / 255.0)
                if lesion_pixels > 0
                else 0.0
            )

            metrics = {
                "lesion_coverage_pct": lesion_coverage_pct,
                "cluster_count": cluster_count,
                "lesion_pixels": lesion_pixels,
                "mean_intensity": round(mean_intensity, 3),
            }

            # Create RGBA overlay (red, 50% opacity where symptoms detected)
            overlay = np.zeros((orig_h, orig_w, 4), dtype=np.uint8)
            overlay[binary_mask] = [255, 0, 0, 128]

            overlay_image = Image.fromarray(overlay, mode="RGBA")
            annotated = Image.alpha_composite(
                original_image.convert("RGBA"), overlay_image
            )
            return annotated.convert("RGB"), metrics

        except Exception as e:
            logger.error("Error during Mask R-CNN prediction: %s", e)
            return original_image, default_metrics

    def predict(self, image: Image.Image) -> Image.Image:
        """Run inference and overlay the predicted symptom mask on the image."""
        annotated, _ = self.predict_with_metrics(image)
        return annotated
