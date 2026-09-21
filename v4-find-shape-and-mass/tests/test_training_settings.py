from synthetic.randomization import SEEN, UNSEEN
from training.settings import AUGMENTATION


def test_hue_augmentation_does_not_reach_the_unseen_hues():
    # Ultralytics shifts hue by up to hsv_h of the whole colour wheel, the
    # same unit the hue bands are in.
    shift = AUGMENTATION["hsv_h"]
    for low, high in SEEN.hue_bands:
        for unseen_low, unseen_high in UNSEEN.hue_bands:
            assert high + shift <= unseen_low or low - shift >= unseen_high


def test_no_augmentation_bends_one_class_into_another():
    # Shear and perspective turn a square's right angles into a rhombus's.
    assert AUGMENTATION["shear"] == 0
    assert AUGMENTATION["perspective"] == 0
