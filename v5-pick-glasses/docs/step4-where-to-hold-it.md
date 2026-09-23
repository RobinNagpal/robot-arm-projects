# Step 4 — where to hold it

Everything so far has been about looking. This is the step where looking turns
into a decision the arm has to live with, and it is the heart of the project.
The arm knows the shape and it knows the kind. It now has to choose a height to
grip at, and a distance to open the fingers to.

Both numbers come out of the measurement taken seconds earlier. Neither is
looked up anywhere. That is the claim of the
[problem statement](../problem-statement.md) made concrete. "Hold the narrowest
part below the bowl" is a sentence about wine glasses in general. The 9 mm it
turns into is about this wine glass only.

A grip has to satisfy three things at once, and any of them can fail. The pads
need a wall they will not slide on. They need enough of it to sit on. And the
grip has to be low enough that the glass can still be turned over afterwards
without putting the fingers into the rack. A rule that returns an answer
satisfying two of the three is worse than a rule that refuses.

Code: `glasses/rules.py`, `glasses/profile.py`, `glasses/spec.py`.

What follows, in order:

- the step in pseudocode, and the libraries it uses
- what makes a grip point good
- the three rules, and the shapes they read
- why the finger opening is never looked up
- the five ways an answer gets rejected
- why all of this beats a table of measurements
- the two things that went wrong when an arm first tried one of these grips
- where the method can still fail
- where the other ways of making this decision are compared

## The step in pseudocode

Each line says who does the work: **ours** means code in this repo, and a named
library means the work is not ours.

```text
look up what this kind of glass asks for          ours: glasses/spec.py
    which rule to apply                           Kind.grip_rule
    which band of height to search in             Kind.band_for()
    how far apart the fingers may end up          min/max_opening_m
    how much wall a pad needs                     min_band_height_m

raise the bottom of that band to LOWEST_GRIP      ours: glasses/rules.py
                                                  _apply_rule(). Before the search,
                                                  not after it.

run the rule on the measured profile              ours: rules.py
    straight glass: lowest upright band           _lowest_vertical_section()
    stemmed glass: narrowest below widest         _narrowest_below_widest()
    tapered glass: least sloping band             _flattest_in_band()
                                                  each asks profile.py:
                                                  vertical_bands(), waist_at(),
                                                  flattest_band()

height = the middle of the band it chose          ours: rules.py find_grip()
opening = the measured width at that height       ours: profile.py width_at()
check the answer five ways                        ours: rules.py _check(). Any
                                                  failure raises NoGrip with its
                                                  reason, and the glass is left
                                                  standing.

choose which way round to hold it                 ours: task.py
                                                  _approach_directions() and
                                                  arm/motion.py grasp_options()
    can the arm reach the hover pose?             MoveIt 2: inverse kinematics
    can the wrist still turn 180 degrees?         ours: motion.py
                                                  can_rotate_tool()
take the first the arm can reach and turn         asked now, because finding out
                                                  with the glass held leaves nothing
                                                  to do but put it back. Step 6
                                                  explains why the wrist limits it.

look down the fingers and shift sideways          ours: task.py
                                                  _centre_on_what_is_there(), by no
                                                  more than GRASP_NUDGE_LIMIT
```

### What each library gives this step

| Piece | Ours or a library | What it does here |
| --- | --- | --- |
| `glasses/rules.py` | ours | the three rules, and the five checks that can reject their answers |
| `glasses/profile.py` | ours | the shape questions the rules are built from: upright bands, the waist, the flattest run |
| `glasses/spec.py` | ours | what each kind asks for — its rule, its search band, its limits |
| `arm/dimensions.py` | ours | the gripper's own numbers: how wide it opens, how low its body may go, how far the aim may be nudged |
| [NumPy](https://numpy.org/) | library | slopes, medians and runs over the profile arrays |
| [MoveIt 2](https://moveit.picknik.ai/main/index.html) | library | says whether the chosen grasp pose can actually be reached, and plans the approach to it |
| [ros2_control](https://control.ros.org/jazzy/index.html) | library | opens the fingers to the width the rule asked for |

No grasp-planning library appears in that list, and that is the point of the
step. [`step4-approaches.md`](step4-approaches.md) is largely about the
libraries that are *not* here — [Contact-GraspNet](https://github.com/NVlabs/contact_graspnet),
[GraspNet-1Billion](https://graspnet.net/), [trimesh](https://trimesh.org/) —
and why a measured profile makes them unnecessary rather than unavailable.

## What makes a grip point good

Three things, and every rule in the project is an attempt to satisfy all three
at once.

**The wall must be upright enough.** Flat pads on a sloping wall slide. The
steeper the slope, the more of the grip force turns into a push down the wall
instead of into it. `VERTICAL_TOLERANCE` is 6 degrees, and the number comes
from the pads: a 12 mm silicone pad conforms by about 1.2 mm across its height,
and `atan(1.2/12)` is 5.7 degrees.

It started at 2 degrees, which is what you pick if you are thinking about
geometry rather than about rubber. It refused every short mould-tapered tumbler
in the test family, because a wall that leans 3 degrees is not vertical and 2
degrees says so. Six is a fact about the hardware; two was an opinion.

**There must be enough of it.** A pad needs a band of wall at least as tall as
the pad to sit on. That is `min_band_height_m`, and it is 8–12 mm depending on
the kind.

**It must be low.** After the turn, the end that was at the bottom is at the
top. Hold a glass halfway up and, once it is upside down, the fingers are level
with the rack pegs. Every search band in `spec.py` stops at or below half the
glass's height, and `_check()` enforces it as well, because a rule that finds
something high up has found the wrong thing.

## Three rules

![One rule per kind](../images/grip-per-kind.png)

| Rule | Used by | What it looks for |
| --- | --- | --- |
| `lowest_vertical_section` | straight glass | the lowest band of wall within 6° of upright, at least a pad tall |
| `flattest_in_band` | tapered glass | the least-sloping band in the search window |
| `narrowest_below_widest` | stemmed, short-stemmed | the waist below the widest point |

`flattest_in_band` exists because a cone has no upright wall anywhere. Asking
for one returns nothing, so the tapered rule asks a different question: of all
the places a pad could sit, which is closest to upright? On a conical tumbler
that is near the base, where the wall has had least distance to spread.

`narrowest_below_widest` is the one that reads like a sentence about glassware,
and it is true of every stemmed glass ever made. The widest point of a wine
glass is its rim or the belly of its bowl; below that the glass necks down to
the stem before flaring out again into the foot. The narrowest point in
between is the stem, wherever it happens to be on this particular glass.

## Finding the waist was harder than it sounds

`waist_at()` originally returned the first index of the narrowest run of
widths. On a glass with a long parallel stem that is a plateau, many rows wide,
and the first row of that plateau is at the bottom — right where the stem
starts flaring into the foot. The arm would have gripped the flare, which is
sloping, wider, and exactly where a stem is weakest.

It now returns the **middle of the longest narrowest run**, which on a parallel
stem is the middle of the stem.

A second bug in the same area is worth recording because it only appeared once
in forty glasses. The generator drew the foot diameter independently of the bowl diameter. So
occasionally the foot came out wider than the bowl. That makes the *base* the
widest point of the glass. `waist_at()` is then searching a slice below the
base, and it crashes on an empty array. Real glasses do not have
feet wider than their bowls, and the generator now draws the foot as a fraction
of the bowl.

Neither of those would have been found with one test glass. Both were found by
running the rules over a family of forty.

## The opening is read off, never looked up

Once the rule has returned a height, the finger opening is the width the camera
measured **at that height**:

```python
opening = profile.width_at(height)
```

That single line is the whole reason this project can handle a glass nobody
measured. There is no lookup, no average stem diameter, no per-kind default.
The camera saw 9.2 mm at 30.8 mm up, so the fingers go to 9.2 mm.

Change the glass and both numbers change, with nothing to edit.

## Five ways an answer is rejected

A rule can return a number that is arithmetically correct and a bad idea. A
"waist" found in a mask artefact. A stem on a glass far too wide for the
gripper. `_check()` catches five cases, each one much cheaper to catch here
than with the arm already moving:

1. **The opening is outside what this kind should ever need.** A stem 60 mm
   across is not a stem; the rule found something else.
2. **The opening is wider than the gripper opens at all** (95 mm).
3. **The band is shorter than the pads need.**
4. **The grip is more than halfway up the glass**, which after the turn puts
   the fingers among the rack pegs.
5. **The grip is too low for the gripper's own body to clear the table**,
   which is the next section, and which was added only after an arm tried it.

Each raises `NoGrip` with the reason written out, and that reason is what ends
up in the run report next to the glass that was left standing.

The fifth is worth its own section, because unlike the other four it is not
about the glass at all.

## Why this beats a table of measurements

![Eight wine glasses, and where the rule holds each one](../images/why-rules-not-sizes.png)

The left panel is eight wine glasses the project generated. They are all called
the same thing and no two are alike: heights from 131 to 230 mm, bowls of
different depths, stems of different lengths and thicknesses. The red mark on
each is where `narrowest_below_widest` decided to hold it.

The right panel is the same information as a table of measurements would have
to hold it: one dot per glass. The grip height spreads over 25 mm for a glass
height that varies by 100 mm. The relationship is loose enough that no single
number works, which is exactly what makes a lookup table the wrong shape for
this problem.

One rule covers all of them. Adding a ninth glass to the left panel needs no
change at all, and *that* is the property the project is really built around.

## The gripper has a body

![Held too low, the body is through the table](../images/the-gripper-has-a-body.png)

`lowest_vertical_section` did its job on the first straight glass it was given.
It came back with a grip 18 mm above the table. That is a perfectly good piece
of upright wall, and an impossible place to hold a glass. The gripper comes in
level, so its body lies *across* the grip height rather than above it. The body
is a 90 mm box. Holding a glass 18 mm up therefore puts 27 mm of gripper
through the table.

What came back from that was not a refusal. It was a path that solved none of
the way, which reads exactly like an arm that cannot lift a glass, and it sent
the search off in the wrong direction for some time. `LOWEST_GRIP` is half the
body plus a little clearance. It bounds the band each rule *searches*, rather
than checking the answer at the end. That distinction is the whole of it. Every
rule on this page looks for the lowest wall that will do. A floor applied
afterwards would therefore turn "hold it a little higher" into "this glass
cannot be held", on every single glass.

It does mean some glasses cannot be held at all. Below 50 mm the gripper is
through the table. Above half the glass's own height the fingers end up among
the rack pegs after the turn. A glass under roughly 120 mm tall has nothing
left in between. That is a fact about this gripper and this rack, not a failure
of measurement, and it is now reported as a reason rather than as a crash.

## Looking down the fingers before closing

Everything on this page decides *where* to hold a glass from pictures taken
half a metre away. The answer was landing about 10 mm out. That was enough for
the fingers to arrive beside the glass rather than around it, close on its
shoulder or on nothing, and have the width check in step 5 refuse the grasp.
The measurement was not the problem. The aim was.

The camera is bolted to the wrist. At the grasp pose it is therefore looking
straight down the approach at the glass, from a hand's breadth away. That is by
far the best view of the glass anything in this task ever gets: a millimetre on
the table is worth many pixels from there. So the arm takes one look from that
position before the fingers close, and shifts sideways onto what it sees. The
shift is along the axis the fingers close on, and no further than half the
gripper's opening — a glass further off than that is not the one about to be
held. The width at first contact went from 10 mm out to the fingers finding
76.6 mm where the camera had said 76.9.

It corrects sideways and nothing else, on purpose. How high up to hold the
glass came from the measured profile, which knows it better than this view
could. How far *along* the approach the glass is, this view cannot see at all.
What it can see better than anything else is whether the glass is between the
fingers or beside them. That is exactly what was going wrong.

## Where this approach can fail

**The rule is only as good as the profile.** Everything here is arithmetic on
step 2's measurement. A waist invented by a reflection becomes a grip in mid
air. Nothing on this page can tell a real stem from a measured one.

**Every kind needs a rule written by hand.** Four kinds, three rules. A fifth
shape — a coupe, a tankard, a bowl — has no rule, so step 3 returns nothing and
the glass is left standing. That is the honest outcome, and it is still a
glass not picked up.

**Short glasses have nowhere to be held.** The gripper body may not go below
50 mm, and the grip may not go above half the glass's height. So a glass under
about 120 mm tall has no band left in between, and is refused every time. It is
a fact about this gripper and this rack rather than about the glass.

**The pad-slip limit is a guess dressed as arithmetic.** `VERTICAL_TOLERANCE`
is 6 degrees, from `atan(1.2/12)` on a 12 mm pad that conforms by 1.2 mm. The
1.2 mm was estimated, not measured. The friction between silicone and wet glass
is not in the calculation at all, and a wet glass is the whole point of a
drying rack.

**Nudging the aim assumes the right glass is in the picture.** The look down
the fingers shifts sideways onto whatever it sees, up to `GRASP_NUDGE_LIMIT`.
If a neighbouring glass is closer to the middle of that view than the target,
the arm nudges towards the wrong one. The limit caps the damage; it does not
prevent it.

**The choice is made once, and not reconsidered.** If the grasp fails, the arm
does not try a different height on the same glass. It refuses the glass. A
ranked search, described in [`step4-approaches.md`](step4-approaches.md), is
what would change that.

## Other ways to choose a grip

The rules are one way of answering "where do I hold this?". Ranked search,
feeling for the stem, learning from examples, grasp networks and others are
compared in [`step4-approaches.md`](step4-approaches.md), along with which of
them to try next.

→ [Step 5 — how hard to squeeze](step5-how-hard-to-squeeze.md)
