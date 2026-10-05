# Deep-learning models

FalconHeat includes an executable DeepLabV3 inference module in `src/eo_deep_learning.py`.

By default, torchvision downloads its official pretrained DeepLabV3 weights on first use.
Those default weights are generic semantic-segmentation weights and are **not a validated
Earth-observation land-cover model**.

For the final EO version, place/document the chosen EO-trained checkpoint here (or provide
a reproducible download script if licensing/size prevents committing it), record its source,
training dataset, licence, classes and evaluation metrics, and update the loader accordingly.
