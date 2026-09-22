# Robot arm projects

A learning repo. It holds robot arm projects, each written to showcase a
different set of the concepts you run into when a 6-axis arm has to look at
something and then do something about it: where to put a camera, how pixels
become millimetres, what a plan is worth once a part lands somewhere other
than where it was aimed.

| Folder | What the arm does | State |
| --- | --- | --- |
| [`v1-touch-biggest-face`](v1-touch-biggest-face) | Measures cuboids and touches the biggest face of each | Working |
| [`v2-assemble-table`](v2-assemble-table) | Stands four legs up and lays a table top on them | Working |
| [`v3-turn-top-flat`](v3-turn-top-flat) | Lifts a table top straight up out of two holders and turns it flat before building the table | Plans only |
| [`v5-pick-glasses`](v5-pick-glasses) | Measures each drinking glass on a table, picks it up, turns it over and stands it on a drying rack | Working |
| [`v6-two-arms-jenga`](v6-two-arms-jenga) | Two arms, programmed two different ways, play Jenga against each other | Plans only |

Each folder's name is its version, then what it does. The projects run
entirely in simulation — Gazebo, ROS 2, MoveIt — so none of them needs
hardware to try.

## v1 — touch the centre of the biggest face

Cuboids of random sizes sit on a table. For each one the arm measures it with a
wrist camera, works out which of its faces has the largest area, and presses a
fingertip into the middle of that face.

It is the smallest complete example of an arm that looks before it moves:
carrying a camera to a viewpoint, separating coloured pixels from a grey world,
turning those pixels into points in the room, fitting a box to the points, and
finishing with a contact sensor so the last line of the log is a fact rather
than a calculation. The pick-and-place in the middle is there to serve
perception, not the other way round — moving a box to the far half of the table
is how the arm remembers which boxes it has already done, without keeping a
list.

→ [`v1-touch-biggest-face/README.md`](v1-touch-biggest-face/README.md)

## v2 — build a table

A table top lies flat on two stands and four legs stand on the floor. The arm
measures the top, works out where the legs have to stand to hold up a top that
size, moves the four of them there, and lays the top on them.

→ [`v2-assemble-table/README.md`](v2-assemble-table/README.md)

## v3 — turn the table top flat

The same job as v2, with one thing made harder: the table top starts standing
upright, held between two heavy holders that cannot move, instead of lying
flat. The arm lifts it straight up out of the holders, turns it 90° to flat
without dropping it, and lays it on the legs without knocking one over.

There is no code yet. The work is in two parts:

1. **Now:** turning the top 90° in the air — with one joint, or with several
   joints together — and what that asks of each joint.
2. **Next:** resting the top on two legs, then tilting it down, with the arm
   moving as it turns, until it sits on all four.

→ [`v3-turn-top-flat/README.md`](v3-turn-top-flat/README.md)

## v5 — pick up a glass and stand it upside down

Drinking glasses of several shapes stand on a table. The arm measures each one,
works out where on it there is anything safe to hold, picks it up, turns it
through 180 degrees and stands it mouth-down on a drying rack.

The constraint that shapes the whole project is that **the shapes are known and
the sizes are not**. The arm knows what a wine glass is — a bowl on a stem on a
foot — but not how tall this one is or where its stem begins, and it cannot be
told, because two wine glasses from different sets do not share proportions.
So there is no table of measurements anywhere in it. There are rules about
shapes, applied to a profile the camera measured a second earlier, and adding a
new kind of glass means writing a rule rather than measuring a glass.

It is also where this repo stops being able to rely on the things that make a
cuboid easy. A depth camera returns nothing where a glass is, so the hole in
the depth image is the signal. A glass's walls are not parallel, so there is
usually exactly one place on it a flat pad can sit. Its weight does not follow
from its size, because wall thickness is invisible, so the arm lifts it ten
millimetres and weighs it before committing. And dropping one costs more than a
retry, so every doubtful glass is left standing with a reason written next
to it.

→ [`v5-pick-glasses/README.md`](v5-pick-glasses/README.md)

## v6 — two arms play Jenga

Two identical arms face each other across a Jenga tower and take turns, each
programmed with a different approach; whichever makes the tower fall loses. It
adds the two things none of the other projects have: information that can only
be found by touch — which blocks are loose — and an opponent.

There is no code yet. The folder sets out the game precisely enough for a
referee program to judge it, and compares five ways to program a player —
rules, feel, an internal physics model, reinforcement learning and imitation
learning — before choosing which two play first.

→ [`v6-two-arms-jenga/README.md`](v6-two-arms-jenga/README.md)

## Why there are two

`v2` is not `v1` cleaned up. It exists to push on the two things `v1` deliberately
made easy.

**How much the robot is told.** In `v1` the table is a known quantity: its
height, its edges and the two halves it is divided into are numbers in the code,
and only the cuboids have to be measured. In `v2` the robot knows where it is
bolted down and how its own gripper and camera are built, and nothing else — the
floor height, where the top is and how big, and where every leg is and how long
are all drawn at random per run and have to be measured. That is the harder and
more realistic arrangement, and it is easy to break by accident, so a test
fails if any robot code so much as imports the simulator's side.

**One object, or several that have to agree.** `v1` measures a box and acts on
that one box; a millimetre of error costs a millimetre. `v2` has to make four
legs and a top into a single thing that stands up, where being right depends on
every part at once. Parts land a few millimetres off where they were aimed and
sometimes tip over, so the arm has to look again after each placement and put
the top down over where the legs actually are. Measure, act, look again, correct
— that loop is the whole point of the second project.

Each working folder is a project of its own. They share no code and no
configuration, only the same tools, and each has its own environment and its
own `make run`. Start with the README inside whichever one you are reading.
