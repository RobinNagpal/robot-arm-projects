# Turn results: one joint or the whole arm, and onto the legs

What happened when the table top was turned from hanging to flat, in
Gazebo, all three ways:

- `make wrist`: in the air, wrist 1 turns 90° and every other joint stays
  still.
- `make whole-arm`: in the air, the board turns about its own gripped edge,
  and any joint may move.
- `make tilt`: the board's lower edge rests on the two far legs, and it is
  tilted down about that edge onto all four (section 5).

The numbers are the task's own report at the end of each run. How far each
joint moved, and the effort it took, come from `/joint_states`. Where the top
really ended up comes from asking Gazebo (`gz model -m table_top -p`), which
the robot never does.

Unless it says otherwise, every run is seed 1: a top 24.4 x 16.5 x 1.9 cm, as
measured. Every turn runs at a tenth of the arm's speed.

---

## 1. The light top: one joint or the whole arm

The default density, 400 kg/m³, gives a top of 0.31 kg.

| Joint | Wrist: moved | Wrist: peak | Wrist: holding | Whole arm: moved | Whole arm: peak | Whole arm: holding |
| --- | --- | --- | --- | --- | --- | --- |
| base | 0.0° | 0.33 | 0.00 | 0.0° | 0.30 | 0.00 |
| shoulder | 0.0° | 26.77 | 24.93 | 17.0° (net +0.5°) | 25.28 | 18.01 |
| elbow | 0.0° | 27.25 | 25.88 | 51.3° | 27.21 | 18.54 |
| wrist 1 | **90.0°** | **4.07** | **2.71** | **141.8°** | **4.17** | **2.71** |
| wrist 2 | 0.0° | 0.04 | 0.00 | 0.0° | 0.04 | 0.00 |
| wrist 3 | 0.0° | 0.04 | 0.04 | 0.0° | 0.04 | 0.04 |
| how long | 7.7 s | | | 8.7 s | | |

Efforts are in N·m. "Peak" is the most during the turn; "holding" is the
average over the 5 s the top is then held flat.

Both runs left the top flat and still held. The arm put it 0.1° off level.
Gazebo had it level to within 0.005° both times: 72 cm up after the wrist
turn, and 40 cm up, its edge where it started, after the whole-arm turn. Seed
7, a top 19.4 cm wide, came out the same (wrist 1 peak 4.87 N·m by the wrist,
4.93 by the whole arm, holding 2.75 both).

What it shows:

1. **The wrist turn really is one joint.** Wrist 1 turned exactly 90° and
   every other joint 0.0°.
2. **The whole arm uses three joints, not six.** The shoulder, elbow and
   wrist 1 all turn about parallel, level axes, so the tool's tilt is the sum
   of their turns: −141.8 + 51.3 + 0.5 = −90°. The shoulder swings out 17°
   and comes back. The base and wrists 2 and 3 were free to move and never
   needed to, because the top's edge is lined up with wrist 1's axis before
   the turn.
3. **Wrist 1 turns further in the whole-arm turn: 142°, not 90°.** As the
   elbow tilts the forearm by 51°, wrist 1 has to turn that much more to make
   up for it. That is why the whole-arm turn is slower: every joint has the
   same speed limit, and wrist 1 has further to go.
4. **Wrist 1's effort is about the same either way.** The peaks were 4.07 and
   4.17 N·m, and the holding was 2.71 both times. Nearly all of it is holding
   the weight up, which depends on where the board is, not on which joints
   put it there. Moving more joints does not share the load.
5. **The shoulder and elbow mostly carry the arm itself.** They sat at 25–28
   N·m, a fifth of their 150 N·m limit. In the whole-arm turn they end at 18
   N·m holding, because that turn finishes with the arm drawn in towards the
   base.
6. **The base and wrists 2 and 3 feel almost nothing.** Gravity twists the
   board about level axes, and those three joints point other ways.
7. **The joints are nowhere near their limits.** Wrist 1 used about 15% of
   its 28 N·m.

**Which to use:** the wrist turn is simpler and a second quicker, but the
board swings round the wrist and needs about 40 cm of clear space. The
whole-arm turn keeps the edge in one place and needs only the board's own
width.

This agrees with the calculation in
[`one-joint-or-many.md`](approaches/one-joint-or-many.md), section 2, which predicted
wrist 1 turning 142° in the whole-arm turn, the base and wrists 2 and 3 doing
nothing, and wrist 1's torque about the same either way.

---

## 2. Heavier tops

`DENSITY` sets the top's density without changing its size. The robot is not
told.

| `DENSITY` | Mass | Turn | What the arm reported | What Gazebo showed |
| --- | --- | --- | --- | --- |
| 400 | 0.31 kg | both | flat, still held | flat |
| 2000 | 1.53 kg | wrist | flat, still held | flat, drooping 1.0° in the fingers |
| 3000 | 2.29 kg | wrist | lost the top 82° into the turn (83° in a second run) | twisted in the fingers, 45° off flat, still held up |
| 3000 | 2.29 kg | whole arm | lost the top 78° into the turn | not checked |
| 4000 | 3.06 kg | wrist | lost the top 87° into the turn | fallen to the floor |
| 5000 | 3.82 kg | wrist | lost the top 48° into the turn | fallen to the floor |
| 5000 | 3.82 kg | whole arm | lost the top 46° into the turn | fallen to the floor |

Every one of these tops was picked up, lifted out of its holders and carried
hanging round to the turning spot without trouble. Only the turn failed.

At 3000, the peak efforts were:

| | Wrist | Whole arm |
| --- | --- | --- |
| shoulder | 46.89 | 34.70 |
| elbow | 44.13 | 49.89 |
| wrist 1 | 10.47 | 12.62 |

What it shows:

1. **The two turns fail at the same point.** At 3000 the fingertips lost the
   top 82° and 78° into the turn; at 5000, 48° and 46°. The few degrees
   between them are about as big as the error in placing the moment of loss
   (section 4). Which joints turn the board makes no difference to the grip.
2. **Hanging is easy; flat is hard.** Hanging, the weight pulls straight
   along the fingers. As the board turns, its weight moves out from the
   fingers and tries to twist it out of them. That twist is zero when
   hanging and largest when flat, which is why the lighter of the failing
   tops held almost all the way round and only let go near flat.
3. **The joints were fine every time.** Even at 3000, wrist 1 peaked at 10.5
   to 12.6 N·m, under half of its 28 N·m, and the shoulder and elbow at 35
   to 50 N·m of their 150. The peaks at a failed turn also include the jolt
   of the board twisting or dropping, so they read a little high.
4. **Wrist 1's effort does not grow as fast as the top's weight.** The 3000
   top is 7.5 times heavier than the 400 one, but wrist 1's peak went up only
   about 2.6 times, from about 4 to about 10.5 N·m. Part of what wrist 1
   holds up is always the wrist and gripper themselves.

---

## 3. How heavy a top the grip can turn

Held flat, the top's weight sits out beyond the fingers and twists it about
them. The pads resist it about their own middle, which is 2.7 cm down from
the gripped edge, so the lever is from there to the board's centre: half the
board's 16.5 cm width, less 2.7 cm, is 5.55 cm. That is the same way the
estimate in [`one-joint-or-many.md`](approaches/one-joint-or-many.md), section 5, was
worked out.

| Mass | Twist when flat | Result |
| --- | --- | --- |
| 1.53 kg | 1.53 × 9.81 × 0.0555 ≈ 0.83 N·m | held flat |
| 2.29 kg | 2.29 × 9.81 × 0.0555 ≈ 1.25 N·m | could not be held flat |

So this simulated grip holds a twist of somewhere between about 0.8 and 1.2
N·m. For this size of top, that is between about 1.5 and 2.3 kg. The
estimate in `one-joint-or-many.md` was 0.6 N·m, about 0.8 kg. The simulator
holds one and a half to two times that, but it is still the grip that gives
out, never a joint.

To turn heavier tops, the twist on the fingers has to come down or the grip
has to resist more:

- rest the top's lower edge on the legs before it goes flat, so it is never
  held flat in the air at all. This is part 2,
  [`tilt-onto-legs.md`](approaches/tilt-onto-legs.md);
- spread the pad rows further apart, or grip deeper;
- squeeze harder than the fingers' 25 N.

---

## 4. What the numbers cannot tell

- **Twisted or fallen.** The fingertip contact sensors are on the tip pads
  only. They say when the top has gone from those pads, not whether it has
  twisted down in the fingers, still pinched by the inner pads, or fallen.
  At 3000 it had twisted, and at 4000 and 5000 it had fallen. Only Gazebo
  could say which.
- **A small droop counts as held.** At 2000 the top drooped 1° in the
  fingers, and the arm still reported it 0.1° off level. The arm works out
  the top's tilt from its own joint angles, as if the top had not moved in
  the fingers.
- **The angle it was lost at is a few degrees late.** A reading counts as
  touching if a contact report came in the last 0.15 s. The turn runs at up
  to about 18° a second, so the moment of loss is placed up to a few degrees
  late. A board can also start to twist a while before the tip pads lose it,
  so the angle is when the grip had clearly failed, not when it began to.
- **Peaks vary from run to run.** The same light-top wrist turn has given
  wrist 1 peaks of 4.07 and 4.54 N·m. The holding values are steady, and are
  the better ones to compare.

---

## 5. Onto the legs: rest on two, tilt down onto four

`make tilt`. The arm measures the four legs, lifts the top out of its
holders, leans it 20° towards itself in the air, carries it out over the far
legs, and lets it down until it feels them take its weight. Then it tilts it
down about the edge resting on them until it is 3 mm above the near legs,
lets go, and checks the table. [`tilt-onto-legs.md`](approaches/tilt-onto-legs.md) has
the plan, and at its end, where the build differs from it.

### Every top made a table

| Seed | `DENSITY` | Mass | Table height (expected) | Top off level | Worst leg afterwards |
| --- | --- | --- | --- | --- | --- |
| 1 | 400 | 0.31 kg | 18.6 cm (18.6) | 0.0° | moved 0.1 mm |
| 2 | 400 | 0.37 kg | 17.8 cm (17.9) | 0.0° | moved 0.1 mm |
| 3 | 400 | 0.39 kg | 18.9 cm (18.9) | 0.0° | moved 0.2 mm |
| 7 | 400 | 0.31 kg | 16.8 cm (16.9) | 0.0° | moved 1.0 mm |
| 1 | 3000 | 2.29 kg | 18.6 cm (18.6) | 0.0° | moved 2.2 mm |
| 1 | 4000 | 3.06 kg | 18.6 cm (18.6) | 0.0° | moved 1.9 mm, tipped 0.2° |
| 1 | 5000 | 3.82 kg | 18.6 cm (18.6) | 0.1° | moved 2.7 mm, tipped 0.2° |

The height and level are the arm's own check, from the camera. The legs are
Gazebo's view: how far the worst of the four ended up from where it started.
Every leg was still standing. Asked directly, Gazebo had every top lying
level to within 0.05°.

The three heavy tops are the ones that could not be turned flat in the air
(section 2): at 2.29 kg the top twisted in the fingers near flat, and at 3.06
and 3.82 kg it fell out. Resting on the legs, all three made a table.

### What the joints did

The light top and the heaviest, during the tilt down about the far legs,
from leaning 20° to 3 mm above the near legs:

| Joint | 0.31 kg: moved | 0.31 kg: peak | 3.82 kg: moved | 3.82 kg: peak |
| --- | --- | --- | --- | --- |
| base | 10.7° | 0.72 | 10.7° | 1.47 |
| shoulder | 33.3° | 42.54 | 33.0° | 67.46 |
| elbow | 51.5° | 26.73 | 52.0° | 46.78 |
| wrist 1 | 141.0° | 4.71 | 141.0° | 11.36 |
| wrist 2 | 20.6° | 0.88 | 20.6° | 2.15 |
| wrist 3 | 13.9° | 0.51 | 13.9° | 0.70 |
| how long | 8.6 s | | 8.6 s | |

- **All six joints move.** The edge the top turns on runs along the far
  legs, and that is not along wrist 1's axis the way the air turns lined it
  up, so the base and wrists 2 and 3 have to help.
- **Wrist 1 turns 141°**, for the same reason as in the whole-arm turn in the
  air: the shoulder and elbow tilt the forearm as they carry the wrist round.
- **The joints stay well inside their limits**, even with the heaviest top:
  wrist 1 at 11.4 of its 28 N·m, the shoulder at 67 of its 150.

### Feeling for the legs

The arm comes down half a millimetre at a time. With the top hanging just
clear of the legs, its joints' efforts hardly change from one step to the
next: at most 0.06 N·m, as the arm's own weight shifts. On the step where the
legs take the top's weight, they jump by 2.9 to 5.2 N·m, fifty times as much,
so the moment is never in doubt.

| Top | Legs felt, from where they were measured |
| --- | --- |
| 0.31–0.39 kg | 0.5 to 2.0 mm high, over ten runs in four rooms |
| 2.29 kg | 2.0 mm high |
| 3.06 kg | 2.5 mm high |
| 3.82 kg | 4.5 mm high: on the very first step |

The legs were always felt a little high. The measurements of the legs and of
where the top's edge is in the fingers are each good to a millimetre or two,
and a heavy top sags a little in the fingers on the way out. That is why the
arm feels for them instead of trusting the numbers.

### What leaning 30° did

The first version leaned the top 30° in the air, not 20°. It made the same
tables with the light top, and with the 2.29 kg one, but:

- **3.06 kg knocked all four legs over.** The top sagged in the fingers on
  the way out — the legs were felt 4 mm high — and about 30° into the tilt it
  twisted out of the grip, slid, and took the legs with it.
- **3.82 kg missed the legs.** It sagged about 20° back towards hanging on
  the way out, so its lower edge came down short of the far legs. The arm
  felt nothing 6 mm past where they should have been, and stopped. The legs
  were untouched.

Both showed in the efforts before anything went wrong. Coming down, the
3.82 kg top's readings crept up step by step to 0.33 N·m with nothing
touching — the top slipping in the fingers. And the 3.06 kg top's "touch" was
a change of just 0.51 N·m, barely over the 0.5 N·m that counts as one, where
a top landing squarely on the legs gives 3 to 5.

At 30° the twist on the grip is half what it is flat; at 20°, a third. That
was the difference. The arm now leans 20° if it can reach the far legs that
way, and 30° only if it cannot. In every room tried, it could.

### What these runs cannot tell

- **A top that sags before it reaches the legs.** The 3.82 kg top was felt
  on the very first step down, so it had sagged at least 4.5 mm. A heavier
  one could already be resting on the legs before the arm starts feeling for
  them, and the arm would not notice. Nor does the arm yet treat a weak touch
  or a creeping reading as a warning, though both showed up in the runs that
  went wrong.
- **Legs knocked during the tilt.** The arm does not look at the legs again
  until the table is built. A leg knocked over shows up in the table check,
  as a table too low or not level, not at the moment it happens.
- **Legs shorter than 15 cm.** At the end of the tilt the arm holds the top
  level by its near edge. With legs 13 cm tall, that is so low that the arm's
  wrist is down at the floor, and the planner refuses before touching the
  top. The room's legs are 15–17 cm.

---

## How to repeat these

From `v3-turn-top-flat/`:

```
make wrist                      # the light top, by the wrist
make whole-arm                  # the light top, by the whole arm
make wrist DENSITY=3000         # a 2.3 kg top, by the wrist
make whole-arm DENSITY=3000     # the same top, by the whole arm
make wrist SEED=7               # a different room
make tilt                       # onto the legs
make tilt DENSITY=5000          # a 3.8 kg top, onto the legs
```

While the cell is still up after a run, this shows where the top really is.
A roll and pitch near 0 is flat; a height near 0 is on the floor:

```
pixi run gz model -m table_top -p
```
