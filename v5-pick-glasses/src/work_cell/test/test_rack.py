import math

import numpy as np
import pytest
from work_cell.rack.layout import (
    ARM_TILT_ACCURACY_DEG,
    SLOT_COUNT,
    SLOT_SPACING,
    Slot,
    fill_order,
    needs_empty_neighbour,
    slots_consumed,
    slots_from_marker,
    tilt_budget_deg,
    usable_slots,
)

# ----------------------------------------------------------- the tilt budget


def test_a_short_glass_has_a_comfortable_tilt_budget():
    # 80 mm across in 100 mm slots leaves 10 mm a side; at 90 mm tall that is
    # atan(10/90).
    assert tilt_budget_deg(0.080, 0.090) == pytest.approx(6.34, abs=0.05)


def test_the_same_glass_made_taller_has_much_less_room():
    assert tilt_budget_deg(0.080, 0.175) == pytest.approx(3.27, abs=0.05)


def test_a_wide_tall_glass_has_almost_none():
    # This is the case the whole rule exists for.
    assert tilt_budget_deg(0.090, 0.175) == pytest.approx(1.64, abs=0.05)


def test_leaving_a_gap_turns_an_impossible_budget_into_an_easy_one():
    tight = tilt_budget_deg(0.090, 0.175, spacing=SLOT_SPACING)
    roomy = tilt_budget_deg(0.090, 0.175, spacing=2 * SLOT_SPACING)
    assert tight < 2.0
    assert roomy == pytest.approx(17.44, abs=0.1)


def test_a_glass_wider_than_the_slot_spacing_has_no_budget_at_all():
    assert tilt_budget_deg(0.110, 0.150) == 0.0


def test_a_glass_with_no_height_is_refused_rather_than_dividing_by_zero():
    with pytest.raises(ValueError):
        tilt_budget_deg(0.080, 0.0)


# --------------------------------------------------- needing an empty neighbour


def test_a_small_glass_does_not_need_a_gap():
    assert not needs_empty_neighbour(0.070, 0.090)


def test_a_wide_tall_glass_does():
    assert needs_empty_neighbour(0.090, 0.175)


def test_the_decision_agrees_with_the_budget_it_is_based_on():
    for width in (0.060, 0.075, 0.085, 0.095):
        for height in (0.060, 0.120, 0.200):
            expected = tilt_budget_deg(width, height) < ARM_TILT_ACCURACY_DEG
            assert needs_empty_neighbour(width, height) is expected


# --------------------------------------------------------------- the slots


def test_six_slots_are_placed_evenly_about_the_marker():
    slots = slots_from_marker(np.array([0.5, 0.3, 0.77]), marker_yaw=0.0)
    assert len(slots) == SLOT_COUNT
    gaps = [float(np.linalg.norm(b.centre - a.centre)) for a, b in zip(slots, slots[1:], strict=False)]
    assert gaps == pytest.approx([SLOT_SPACING] * (SLOT_COUNT - 1))


def test_the_slots_move_when_the_rack_does():
    # Nothing about a slot position may be a constant in the code.
    here = slots_from_marker(np.array([0.5, 0.3, 0.77]), marker_yaw=0.0)
    there = slots_from_marker(np.array([0.7, 0.1, 0.77]), marker_yaw=0.0)
    assert not np.allclose(here[0].centre, there[0].centre)


def test_turning_the_rack_turns_the_row_of_slots():
    straight = slots_from_marker(np.zeros(3), marker_yaw=0.0)
    turned = slots_from_marker(np.zeros(3), marker_yaw=math.pi / 2)
    # The row runs along y when square on, and along x when turned a quarter.
    assert abs(straight[0].centre[1]) > abs(straight[0].centre[0])
    assert abs(turned[0].centre[0]) > abs(turned[0].centre[1])


# ------------------------------------------------------------ choosing one


def test_a_glass_needing_a_gap_can_only_use_a_slot_with_free_neighbours():
    free = [Slot(i, np.zeros(3)) for i in (0, 1, 2, 5)]
    usable = usable_slots(free, needs_gap=True)
    # Slot 5's neighbour, 4, is taken, so 5 is out. Slot 0's neighbour, -1,
    # does not exist, so 0 is allowed.
    assert {slot.index for slot in usable} == {0, 1}


def test_a_glass_not_needing_a_gap_can_use_any_free_slot():
    free = [Slot(i, np.zeros(3)) for i in (0, 1, 2, 5)]
    assert len(usable_slots(free, needs_gap=False)) == 4


def test_placing_a_wide_glass_uses_up_its_neighbours_too():
    assert slots_consumed(Slot(3, np.zeros(3)), needs_gap=True) == {2, 3, 4}
    assert slots_consumed(Slot(3, np.zeros(3)), needs_gap=False) == {3}


def test_a_slot_at_the_end_only_consumes_slots_that_exist():
    assert slots_consumed(Slot(0, np.zeros(3)), needs_gap=True) == {0, 1}
    assert slots_consumed(Slot(5, np.zeros(3)), needs_gap=True) == {4, 5}


def test_slots_are_filled_from_the_far_end_first():
    # So that a glass already standing is never between the arm and the next
    # slot it has to reach.
    slots = [Slot(i, np.array([0.5, 0.1 * i, 0.77])) for i in range(3)]
    order = fill_order(slots, reach_from=np.zeros(3))
    assert [slot.index for slot in order] == [2, 1, 0]
