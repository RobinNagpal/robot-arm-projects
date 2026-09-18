"""The settings YOLO is trained with. docs/yolo-classification/training.md gives the reason for each.

Plain values only, with no Ultralytics import, so the tests can check them
against the ranges the pictures were drawn from.
"""

from __future__ import annotations

# A segmentation model, because the arm needs each block's outline, not only a
# box. Size s: n loses the small blocks, m and up cost time for 7 plain shapes.
# The weights start from COCO, real photos, which is what gives a model trained
# on Gazebo pictures a chance on a real camera.
MODEL = "yolo26s-seg.pt"

TRAINING = {
    "imgsz": 640,  # the pictures are 640 x 480; smaller would shrink the far blocks further
    "epochs": 100,
    "patience": 20,  # stop once val has not improved for this many epochs
    "batch": 8,  # 16 GB is shared by CPU and GPU on the Mac; raise it on a bigger GPU
    "cache": False,  # in RAM the pictures alone would take about 5.5 GB
    "seed": 0,
}

AUGMENTATION = {
    # A mirrored or upside-down shape is still the same shape.
    "fliplr": 0.5,
    "flipud": 0.5,
    "degrees": 10.0,
    "translate": 0.1,
    "scale": 0.5,
    # Off. Shearing a square makes it look like a rhombus while it is still
    # labelled square, which wipes out the gap kept between the classes. The
    # camera angle in the pictures already squashes shapes the way a real one does.
    "shear": 0.0,
    "perspective": 0.0,
    # Off. The generator already draws every training hue, and any hue shift
    # would carry the edge of those hues into the band only test-unseen uses.
    "hsv_h": 0.0,
    "hsv_s": 0.7,
    "hsv_v": 0.4,
    "mosaic": 1.0,
    "close_mosaic": 10,
    "mixup": 0.0,
    "copy_paste": 0.0,
}

# What a real camera does that Gazebo does not: blur, noise, JPEG blocks.
# Probabilities per picture. Built into Albumentations transforms in train.py.
CAMERA_EFFECTS = {
    "blur": 0.1,
    "motion_blur": 0.1,
    "noise": 0.1,
    "jpeg": 0.1,
    "grey": 0.02,
    "contrast": 0.02,
}
