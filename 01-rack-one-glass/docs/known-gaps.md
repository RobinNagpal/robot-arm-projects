# Known gaps

Things that are known not to work yet. Short on purpose: each entry says what
fails, why, and the numbers that show it.

## Most glass sizes cannot be held

Checked on 23 September 2026, after the shortest straight glasses and the
smallest wine glasses were dropped to fit the taller rack pegs. 200 random
glasses of each kind, across the full size range in `glasses/shapes.py`, were
given to the real classifier and grip rules. Each used its exact shape, with no
camera error, so this is the best case.

| Kind | Classified right | Grip found | Heights that got a grip |
|---|---|---|---|
| Straight | 200 / 200 | 85 / 200 | 125–170 mm only |
| Tapered | 190 / 200 | 45 / 200 | 180–200 mm only |
| Stemmed | 200 / 200 | 70 / 200 | 180–230 mm only |
| Short-stemmed | 200 / 200 | 0 / 200 | none |

Steps 1 to 3 mostly work: 5% of tapered glasses are called straight. The gap is
step 4, which only chooses a height and always comes in level from the side.
Two limits then cancel each other out:

- **No grip below 50 mm.** The tool comes in level, so it lies beside the glass
  rather than above it, and the widest thing on it hangs 44.5 mm below the
  tool's axis. That is the FT 300-S force sensor, which is 89 mm across; the
  gripper's own body is narrower at 75 mm. Below 50 mm the sensor hits the
  table. See `LOWEST_GRIP` in `arm/dimensions.py`.
- **No grip above half the glass's height**, so the fingers end up above the
  rack after the turn.

So any glass under about 112 mm tall cannot be held. For a tapered glass the
search stops at 35% of the height, which pushes the limit to about 160 mm.

Stemmed glasses have their own fault. The rule takes the single narrowest
point on the stem, often near its foot at about 40 mm, and refuses the glass if
that point is under 50 mm. It does this even when most of the stem is higher
up. A short-stemmed glass's whole stem is under 50 mm, so none can be held.

Possible fixes: approach short glasses at an angle or from above; hold
stemmed glasses on the part of the stem above the limit; and add a test that
fails when grip coverage per kind drops.

## The pads are taller than any rule guarantees wall for

Found on 12 October 2026, when the invented gripper was replaced by a real
Robotiq 2F-85.

A grip needs a run of upright wall for the pads to sit flat on, and each kind
of glass says how much it needs: 12 mm for a straight or tapered glass, 10 for
a stemmed one, 8 for a short-stemmed one. Those figures were chosen against a
pad 14 mm tall. **The 2F-85's pad is 22 mm tall.** So the pads now stand taller
than the wall they are promised, and their top and bottom edges can land on
wall that has already started to curve away.

Nothing is known to fail because of it yet, and that is exactly why it is here
rather than fixed. Raising the figures to match the pad would refuse a great
many glasses, and there is nothing to raise them *to*: what settles it is how
much slope a silicone pad of this size really takes up before it stops holding,
which is a measurement to make on a bench with a real pad and a real glass. The
same mistake has already been made once in this project, by guessing force caps
instead of measuring them, and the entry below is about what that cost.

`test_dimensions.py` states the situation as an assertion rather than hiding
it, so whoever measures the pad has a test to come back to.

## How hard to squeeze is set by the gripper, not by the glass

Found on the same day, and it is the clearest thing a real gripper changed.

This project works out how hard to hold each glass from its weight and the
friction of the pad, and the answers come out in single newtons: about 3 N for
a wine glass, a little more for a tumbler. **A Robotiq 2F-85 cannot be set
below 20 N.** That is not a recommended minimum or a reliable minimum; it is
the bottom of the adjustable range the gripper exposes. So every glass in this
cell is held several times harder than the sums ask for, and the sums no longer
decide anything about the squeeze.

The force caps had to be rewritten because of it. They used to be 6 N for a
thin wall, 12 for a normal one and 20 for a thick one, and against those the
gripper's own minimum broke the rating of every thin and normal glass, so the
arm would have refused nearly every glass on the table. They are now written
against the gripper's floor: the floor itself for a thin wall, half again for a
normal one, twice for a thick one. The *ordering* is the part there was ever a
reason for, and it is kept. The level is now at least a real number rather than
a guess, but it is a real number about the gripper and not about glass.

What this needs is the one measurement nobody here has made: what force
actually breaks the wall or the stem of a real drinking glass. Until then,
`glasses/force.py` reports how many times harder the gripper squeezed than the
sums wanted, so the size of the gap shows up in every run's own output instead
of being buried.
