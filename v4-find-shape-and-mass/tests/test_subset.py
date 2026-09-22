from pathlib import Path

from training.subset import counts, pick, write_subset

SIZES = {"train": 6000, "val": 1000, "test": 1000, "test-unseen": 1000}


def test_every_split_is_cut_by_the_same_fraction():
    assert counts(SIZES, 250) == {"train": 250, "val": 42, "test": 42, "test-unseen": 42}
    assert counts(SIZES, 6000) == SIZES


def test_a_tiny_subset_still_keeps_a_picture_of_each_split():
    assert min(counts(SIZES, 1).values()) == 1


def test_the_same_seed_picks_the_same_pictures():
    pictures = [Path(f"{i:06d}.jpg") for i in range(1000)]
    first = pick(pictures, 42, seed=0, split="val")
    assert first == pick(pictures, 42, seed=0, split="val")
    assert first != pick(pictures, 42, seed=1, split="val")
    assert len(set(first)) == 42


def test_the_lists_point_at_pictures_that_have_labels(tmp_path):
    data = tmp_path / "shapes"
    for split in ("train", "val", "test", "test-unseen"):
        (data / "images" / split).mkdir(parents=True)
        for i in range(12 if split == "train" else 4):
            (data / "images" / split / f"{i:06d}.jpg").touch()

    kept = write_subset(data, tmp_path / "run" / "data", 6)
    assert kept == {"train": 6, "val": 2, "test": 2, "test-unseen": 2}
    listed = (tmp_path / "run" / "data" / "test-unseen.txt").read_text().split()
    assert all(Path(p).exists() and "/images/test-unseen/" in p for p in listed)
    assert "test: test-unseen.txt" in (tmp_path / "run" / "data" / "data-unseen.yaml").read_text()
