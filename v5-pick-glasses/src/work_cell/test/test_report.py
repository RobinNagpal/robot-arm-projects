"""The run report, on drawn pictures. No ROS, no simulator."""

import numpy as np
from work_cell.report import Report, annotate, with_marks, with_mask


def test_the_caption_goes_above_the_picture_not_over_it():
    picture = np.zeros((40, 200, 3), dtype=np.uint8)
    out = annotate(picture, "reaching for the glass")
    assert out.shape[1] == 200
    assert out.shape[0] > 40
    # The picture itself is untouched, at the bottom.
    assert (out[-40:] == 0).all()


def test_a_long_caption_wraps_instead_of_running_off():
    short = annotate(np.zeros((30, 160, 3), dtype=np.uint8), "hello")
    long = annotate(np.zeros((30, 160, 3), dtype=np.uint8), "hello " * 40)
    assert long.shape[0] > short.shape[0]


def test_it_is_written_as_it_happens(tmp_path):
    """A run that dies half way still has to leave everything up to then."""
    report = Report(tmp_path / "run", "A run")
    report.step("Looking for the rack")
    report.say("about to take a picture")
    assert "about to take a picture" in (tmp_path / "run" / "report.md").read_text()


def test_a_picture_lands_in_images_and_the_markdown_points_at_it(tmp_path):
    report = Report(tmp_path / "run", "A run")
    report.picture(np.zeros((20, 60, 3), dtype=np.uint8), "looking at the table", then="found one")

    text = (tmp_path / "run" / "report.md").read_text()
    assert "looking at the table" in text
    assert "found one" in text

    written = list((tmp_path / "run" / "images").glob("*.png"))
    assert len(written) == 1
    assert "images/" + written[0].name in text


def test_pictures_are_numbered_in_the_order_they_were_taken(tmp_path):
    report = Report(tmp_path / "run", "A run")
    for which in ("first", "second", "third"):
        report.picture(np.zeros((10, 40, 3), dtype=np.uint8), which)
    names = sorted(p.name for p in (tmp_path / "run" / "images").glob("*.png"))
    assert [n.split("-")[0] for n in names] == ["01", "02", "03"]


def test_a_mask_and_a_float_depth_picture_can_both_be_saved(tmp_path):
    """Whatever the arm was looking at, not only 8 bit colour."""
    report = Report(tmp_path / "run", "A run")
    mask = np.zeros((20, 30), dtype=bool)
    mask[5:15, 10:20] = True
    report.picture(mask, "what it thinks is glass")
    report.picture(np.full((20, 30), 0.42), "how far away everything is")
    assert len(list((tmp_path / "run" / "images").glob("*.png"))) == 2


def test_the_outline_is_drawn_where_the_glass_was_found():
    rgb = np.zeros((40, 40, 3), dtype=np.uint8)
    mask = np.zeros((40, 40), dtype=bool)
    mask[10:30, 10:30] = True
    assert with_mask(rgb, mask).any()


def test_a_mark_is_drawn_where_it_was_told_to():
    rgb = np.zeros((40, 40, 3), dtype=np.uint8)
    assert with_marks(rgb, [(20.0, 20.0, "here")]).any()


def test_two_runs_in_the_same_minute_do_not_share_a_folder(tmp_path):
    """Down to the second, because runs come a few minutes apart at most and
    a run that overwrote the one before it would be worth nothing."""
    import re

    from work_cell.report import run_folder

    folder = run_folder(tmp_path)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}", folder.name), folder.name


def test_an_earlier_run_is_left_alone(tmp_path):
    from work_cell.report import run_folder

    older = run_folder(tmp_path)
    Report(older, "The first run").say("something worth keeping")

    run_folder(tmp_path)
    assert "something worth keeping" in (older / "report.md").read_text()
