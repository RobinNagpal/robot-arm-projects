# Known gaps

Things that are known not to work yet. Short on purpose: each entry says what
fails, why, and the numbers that show it.

## Most glass sizes cannot be held

Checked on 23 September 2026. 200 random glasses of each kind, across the full
size range in `glasses/shapes.py`, were given to the real classifier and grip
rules. Each used its exact shape, with no camera error, so this is the best case.

| Kind | Classified right | Grip found | Heights that got a grip |
|---|---|---|---|
| Straight | 200 / 200 | 74 / 200 | 125–170 mm only |
| Tapered | 190 / 200 | 45 / 200 | 180–200 mm only |
| Stemmed | 200 / 200 | 52 / 200 | 179–230 mm only |
| Short-stemmed | 200 / 200 | 0 / 200 | none |

Steps 1 to 3 mostly work: 5% of tapered glasses are called straight. The gap is
step 4, which only chooses a height and always comes in level from the side.
Two limits then cancel each other out:

- **No grip below 50 mm.** The gripper body is a 90 mm box beside the glass, so
  below this it hits the table. See `LOWEST_GRIP` in `arm/dimensions.py`.
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
