"""
RenalAI Grad-CAM visual-explainability module.

HONESTY NOTE (same principle as imaging_service.py): there is no trained kidney
imaging model anywhere in this project. Grad-CAM needs a convolutional network
with learned weights to differentiate through -- since no renal CT/MRI/USG
classifier exists, this module uses a general-purpose ImageNet-pretrained
ResNet-18 as the backbone.

That means:
  - The Grad-CAM *algorithm* below is real and mathematically correct: it hooks
    the last convolutional block, backpropagates the top predicted class's
    score, and builds a gradient-weighted activation map exactly as in the
    Selvaraju et al. (2017) paper.
  - What it *visualises* is what a generic vision network (trained on cats,
    cars, everyday objects) attends to in the pixels -- not a kidney-disease
    finding. It must never be presented to a user as a diagnostic heatmap.

This is wired up as an honest architecture demonstration: upload -> backbone
forward/backward pass -> real CAM -> overlay. Swapping in a properly trained
and validated renal-imaging CNN later only requires pointing `_get_model()`
at that model's last conv layer; everything else already works.
"""
import io
import base64
import logging

import numpy as np
from PIL import Image

logger = logging.getLogger("renalai.gradcam")

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

_MODEL = None


class GradCAMUnavailableError(Exception):
    pass


def gradcam_is_configured() -> bool:
    try:
        import torch  # noqa: F401
        import torchvision  # noqa: F401
        return True
    except ImportError:
        return False


def _get_model():
    """Loads the ImageNet-pretrained ResNet-18 once and reuses it for every request."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    import torch  # noqa: F401 (import guarded by caller)
    import torchvision

    weights = torchvision.models.ResNet18_Weights.IMAGENET1K_V1
    model = torchvision.models.resnet18(weights=weights)
    model.eval()
    _MODEL = model
    logger.info("Grad-CAM backbone loaded: ImageNet-pretrained ResNet-18 (general vision, not kidney-specific).")
    return model


def _jet_colormap(gray: np.ndarray) -> np.ndarray:
    """gray: float array in [0,1], HxW. Returns HxWx3 uint8 heatmap. No cv2/matplotlib dependency."""
    g = np.clip(gray, 0.0, 1.0)
    r = np.clip(1.5 - np.abs(4 * g - 3), 0, 1)
    gch = np.clip(1.5 - np.abs(4 * g - 2), 0, 1)
    b = np.clip(1.5 - np.abs(4 * g - 1), 0, 1)
    rgb = np.stack([r, gch, b], axis=-1)
    return (rgb * 255).astype(np.uint8)


def generate_gradcam(content: bytes) -> dict:
    """
    Returns a dict describing the Grad-CAM result. Never raises for expected
    failure modes (missing torch, bad image) -- always returns a structured
    'available: False' state instead, so the imaging pipeline stays non-fatal.
    """
    if not gradcam_is_configured():
        return {
            "available": False,
            "overlay_base64": None,
            "note": (
                "Grad-CAM requires torch and torchvision, which are not installed in "
                "this environment. Run `pip install -r backend/requirements.txt` "
                "(they're listed there) to enable this feature."
            ),
        }

    try:
        import torch
        import torch.nn.functional as F
    except ImportError as e:  # pragma: no cover - defensive, matches check above
        return {"available": False, "overlay_base64": None, "note": f"torch import failed: {e}"}

    try:
        model = _get_model()

        img = Image.open(io.BytesIO(content)).convert("RGB")
        orig = img.copy()
        resized = img.resize((224, 224))
        arr = np.asarray(resized, dtype=np.float32) / 255.0
        arr = (arr - IMAGENET_MEAN) / IMAGENET_STD
        tensor = torch.from_numpy(arr.transpose(2, 0, 1)).unsqueeze(0).float()
        tensor.requires_grad_(True)

        activations: dict = {}
        gradients: dict = {}

        def fwd_hook(_module, _inp, out):
            activations["value"] = out

        def bwd_hook(_module, _grad_in, grad_out):
            gradients["value"] = grad_out[0]

        target_layer = model.layer4[-1]
        h1 = target_layer.register_forward_hook(fwd_hook)
        h2 = target_layer.register_full_backward_hook(bwd_hook)

        try:
            model.zero_grad()
            logits = model(tensor)
            probs = F.softmax(logits, dim=1)
            top_idx = int(torch.argmax(logits, dim=1).item())
            top_prob = float(probs[0, top_idx].item())
            logits[0, top_idx].backward()

            act = activations["value"][0].detach().numpy()   # C, H, W
            grad = gradients["value"][0].detach().numpy()    # C, H, W
            weights = grad.mean(axis=(1, 2))                  # C
            cam = np.maximum(np.tensordot(weights, act, axes=([0], [0])), 0)  # H, W
            cam = cam / cam.max() if cam.max() > 0 else cam
        finally:
            h1.remove()
            h2.remove()

        cam_img = Image.fromarray((cam * 255).astype(np.uint8)).resize(orig.size, resample=Image.BILINEAR)
        cam_resized = np.asarray(cam_img, dtype=np.float32) / 255.0
        heatmap_rgb = _jet_colormap(cam_resized)

        orig_arr = np.asarray(orig, dtype=np.float32)
        overlay = (0.55 * orig_arr + 0.45 * heatmap_rgb).clip(0, 255).astype(np.uint8)

        buf = io.BytesIO()
        Image.fromarray(overlay).save(buf, format="PNG")
        overlay_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        return {
            "available": True,
            "overlay_base64": overlay_b64,
            "backbone": "ResNet-18 (ImageNet-pretrained -- general vision, not kidney-specific)",
            "backbone_top_class_index": top_idx,
            "backbone_confidence": round(top_prob, 4),
            "note": (
                "Real Grad-CAM (gradient-weighted class activation mapping) computed against "
                "a general-purpose ImageNet backbone. No trained kidney-imaging model exists "
                "in this project, so the highlighted regions reflect generic visual features, "
                "not a renal finding. Architecture demo only -- never a diagnosis."
            ),
        }
    except Exception as e:
        logger.exception("Grad-CAM generation failed")
        return {"available": False, "overlay_base64": None, "note": f"Grad-CAM generation failed: {e}"}
