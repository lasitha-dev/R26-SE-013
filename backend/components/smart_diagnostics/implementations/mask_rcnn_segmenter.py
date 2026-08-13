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
        self.is_loaded = False
        try:
            self._load_model()
        except Exception as e:
            logger.error("Failed to load Mask R-CNN model from %s: %s", model_path, e)

    def _load_model(self):
        import tensorflow as tf
        logger.info("Loading Mask R-CNN model from %s ...", self.model_path)
        self.model = tf.keras.models.load_model(self.model_path, compile=False)
        self.is_loaded = True
        logger.info("Mask R-CNN model loaded successfully.")

    def predict(self, image: Image.Image) -> Image.Image:
        """Run inference and overlay the predicted symptom mask on the image.

        Returns a PIL Image with a semi-transparent red overlay where
        symptoms were detected.
        """
        if not self.is_loaded or self.model is None:
            logger.warning("Mask R-CNN model not loaded, returning original image.")
            return image

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
            # Depending on Keras version / save format, preds is either:
            #   - a dict  {'class_output': ..., 'mask_output': ...}
            #   - a list  [class_output, mask_output]
            if isinstance(preds, dict):
                mask = preds["mask_output"][0]  # (224, 224, 1)
            elif isinstance(preds, (list, tuple)):
                # mask_output is the second output based on the build order
                mask = preds[1][0]  # (224, 224, 1)
            else:
                # Single output fallback
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

            # Threshold to binary mask
            binary_mask = mask_array > 127

            # Create RGBA overlay (red, 50% opacity where symptoms detected)
            overlay = np.zeros((orig_h, orig_w, 4), dtype=np.uint8)
            overlay[binary_mask] = [255, 0, 0, 128]

            overlay_image = Image.fromarray(overlay, mode="RGBA")
            annotated = Image.alpha_composite(
                original_image.convert("RGBA"), overlay_image
            )
            return annotated.convert("RGB")

        except Exception as e:
            logger.error("Error during Mask R-CNN prediction: %s", e)
            return original_image
