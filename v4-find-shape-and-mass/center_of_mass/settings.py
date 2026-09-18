"""The settings the centre-of-mass model is trained with. docs/center-of-mass/training.md explains each.

Plain values only, with no Ultralytics import, so the tests can check them.
"""

from __future__ import annotations

# A pose model: for every block it gives a box, a class, and keypoints. Here
# one keypoint, the centre of mass. Size s: n is weaker at placing a point to
# the pixel, m and up are slow to train on a Mac for 250 pictures of simple
# scenes. The weights start from COCO people, so the backbone already knows
# edges, corners and shapes; the keypoint head is new, since COCO has 17
# keypoints and this has 1.
MODEL = "yolo26s-pose.pt"

TRAINING = {
    "imgsz": 640,  # the pictures are 640 x 480; smaller would lose pixels of accuracy
    "epochs": 150,  # few pictures, so each epoch is short and more of them are needed
    "patience": 40,  # stop once val has not improved for this many epochs
    "batch": 8,  # 16 GB is shared by CPU and GPU on the Mac; raise it on a bigger GPU
    "cache": "ram",  # 400 pictures take under 400 MB
    "seed": 0,
}

# How strict the keypoint loss and the pose score are about distance. The
# error counts as e = d² / (8 σ² × box area). With 0.05, a point 10 pixels
# off on a 70 × 70 pixel block gives e = 1, a clear penalty, and 2 pixels off
# almost none. Ultralytics' default for one keypoint is 1.0, which barely
# notices 10 pixels, so the model would never learn to be precise.
KEYPOINT_SIGMA = 0.05

AUGMENTATION = {
    # On. A mirrored block's centre of mass is the mirrored point, so the
    # label stays right.
    "fliplr": 0.5,
    "flipud": 0.5,
    # Off. Every block is already at a random turn. Turning, moving or
    # enlarging the whole picture would push blocks near the edge partly out
    # of it, and the label would still mark the centre of the whole block,
    # which the picture no longer shows.
    "degrees": 0.0,
    "translate": 0.0,
    "scale": 0.0,
    # Off. The camera never slants, so a slanted picture teaches nothing real.
    # Perspective also moves the true centre of mass away from where the
    # transformed point lands, so the label would be wrong.
    "shear": 0.0,
    "perspective": 0.0,
    # Off. Mosaic cuts pictures into tiles and crops blocks at the seams, the
    # same problem as moving the picture.
    "mosaic": 0.0,
    "close_mosaic": 0,
    "mixup": 0.0,
    "copy_paste": 0.0,
    # On. Colour says nothing about where the mass is.
    "hsv_h": 0.015,
    "hsv_s": 0.7,
    "hsv_v": 0.4,
}

# A predicted block and a true block are the same block if their boxes overlap
# at least this much (intersection over union).
MATCH_IOU = 0.5
# Predictions less sure than this are dropped before scoring.
CONFIDENCE = 0.25
