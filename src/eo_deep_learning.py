"""
FalconHeat AI — Earth Observation Deep Learning module

Purpose
-------
Semantic segmentation of RGB Earth-observation imagery with a DeepLabV3
convolutional neural network. The function accepts a local image, runs
inference, returns a segmentation mask and summary percentages.

Important
---------
The default torchvision DeepLabV3 weights are generic pretrained semantic-
segmentation weights, NOT an EO land-cover model. Therefore their classes
must not be presented as validated vegetation/building/road EO classes.
For a scientifically valid FalconHeat submission, replace MODEL_WEIGHTS with
a land-cover model trained/fine-tuned on an appropriate EO dataset and update
CLASS_NAMES / mapping accordingly.

This module is deliberately separated from the transparent heat-risk engine:
DL extracts image information; the risk engine combines validated indicators.
"""
from pathlib import Path
import numpy as np

CLASS_NAMES = [
    "background","aeroplane","bicycle","bird","boat","bottle","bus","car","cat",
    "chair","cow","diningtable","dog","horse","motorbike","person","pottedplant",
    "sheep","sofa","train","tvmonitor"
]

def deep_learning_available():
    try:
        import torch  # noqa
        import torchvision  # noqa
        from PIL import Image  # noqa
        return True
    except Exception:
        return False

def segment_image(image_path, output_mask=None):
    """Run pretrained DeepLabV3 inference on a local RGB image."""
    try:
        import torch
        from PIL import Image
        from torchvision.models.segmentation import (
            deeplabv3_resnet50, DeepLabV3_ResNet50_Weights
        )
    except ImportError as e:
        raise RuntimeError(
            "Deep-learning extras are not installed. "
            "Install with: pip install -r requirements-dl.txt"
        ) from e

    image = Image.open(image_path).convert("RGB")
    weights = DeepLabV3_ResNet50_Weights.DEFAULT
    model = deeplabv3_resnet50(weights=weights)
    model.eval()

    preprocess = weights.transforms()
    batch = preprocess(image).unsqueeze(0)

    with torch.inference_mode():
        logits = model(batch)["out"][0]
    mask = logits.argmax(0).byte().cpu().numpy()

    values, counts = np.unique(mask, return_counts=True)
    total = counts.sum()
    summary = {
        CLASS_NAMES[int(v)] if int(v) < len(CLASS_NAMES) else f"class_{int(v)}":
        round(float(c / total * 100), 2)
        for v, c in zip(values, counts)
    }

    if output_mask is not None:
        out = Path(output_mask)
        out.parent.mkdir(parents=True, exist_ok=True)
        # deterministic visualization palette
        palette = np.array([
            [20,30,28],[66,135,245],[230,180,40],[160,210,80],[70,150,200],
            [200,90,90],[220,130,60],[180,180,180],[180,100,170],[110,160,130],
            [190,150,90],[150,100,70],[200,120,140],[110,180,90],[90,110,170],
            [235,190,150],[70,190,100],[160,160,90],[140,100,130],[100,130,180],
            [200,200,120]
        ], dtype=np.uint8)
        rgb = palette[mask % len(palette)]
        Image.fromarray(rgb).save(out)

    return mask, summary
