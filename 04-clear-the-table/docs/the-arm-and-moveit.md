# The arm and MoveIt

This page explains job 3, moving the arm, and how the arm looks at the table. The solutions
only say what push they want. Everything on this page turns that wish into a motion of six
joints. By the end you will know what MoveIt is asked for, how one push becomes four
planned motions, and why the arm cannot make most of the pushes a person would choose.

## The cell

The arm is a UR5e standing at the table in the MuJoCo physics engine. MuJoCo is used
because the learned solutions need thousands of pushes, and it runs a push much faster than
real time. The MuJoCo arm is built from the same robot description file that MoveIt plans
with, so the arm MoveIt plans for and the arm the physics moves are the same arm. Each
joint follows its commanded angle with a stiff servo, so the arm tracks its planned path
closely and gives a little under load, as a real arm does.

The hand is turned on its side, so its two fingers sit one above the other. This makes it
narrow from side to side, which helps it fit between glasses, but it is still tall.

## How the cell talks to MoveIt

MoveIt 2 runs in the ROS environment, while the physics and the learning run in a different
Python environment. So MoveIt runs as a small server, and the cell talks to it through a
pipe, one line of JSON each way. This works like a function call: a goal pose and some
settings go in, and a list of joint angles with a time for each comes out.

## One push is four motions

MoveIt plans each push as four motions:

1. a free move to a point just behind the glass;
2. a straight drop down to pushing height;
3. the straight stroke that pushes the glass;
4. a straight move back and up, away from the glass.

All four are planned before the arm moves. If any one of them cannot be planned, the push is
**refused**, and the arm never starts it. This matters, because a push stopped halfway would
leave the hand down between the glasses. A refused push also costs no arm time.

The free move is planned round every glass's box by a sampling planner, which searches for a
path through free space. The three straight motions are made by working out the joint
angles at closely spaced points along each line. Every motion is checked against the boxes,
so a motion that would hit something is refused, not made.

An arm like the UR5e can reach one hand pose in several different joint postures, and only
some of them can then drop and push without the forearm meeting the table. So when MoveIt
chooses where the free move ends, it also checks that the drop and the stroke can follow
from that posture.

## A path of straight lines

The first cell's solutions, which were written for a jaw with no arm behind it,
answer with a path of waypoints instead of a push. On the arm, the waypoints are
joined into straight stretches, and MoveIt plans a free move to travel height
above the first point, a straight drop to it, a straight motion along every
stretch, and a straight lift at the end. As with a push, every motion is planned
before the arm moves, and a path with any motion MoveIt cannot plan is refused.
Each stretch keeps the speed the first cell gave it: MoveIt plans the motion,
and its timing is then stretched evenly until it is no faster than that speed.

## The six settings

The six settings in a push are all things MoveIt itself is given. A solution chooses them,
and MoveIt uses them.

| Setting | What it changes |
|---|---|
| push height | how high above the table the hand meets the glass |
| stroke speed | how fast the hand moves during the stroke |
| approach speed | how fast the free move and the drop are |
| padding | extra room added round every box before MoveIt plans |
| standoff | how far behind the glass the hand comes down |
| overreach | how far the stroke carries on past the point that would place the glass |

Each setting has a fixed range, so a solution cannot ask for a value the cell does not
allow. The ranges say what is possible, not what is good.

## How the arm looks

The camera is on the wrist, so looking costs arm time. The camera sits to one side of the
hand, a little above it, because a camera on the hand's own axis would mostly see the arm.

There are two places to look from, one on each side of the glass zone, and the box model
was trained on pictures from exactly these two. One place is not always enough, because a
glass behind another glass does not appear in the picture. MoveIt would not know about that
glass, and the arm could hit it.

Each solution decides when to look. At the start of a table, every solution takes a picture
from both places and joins the two lists of boxes. After a push, a solution that reads only
the boxes goes to the nearer place first. It goes on to the other place only when the first
picture shows fewer glasses than the table has, because a glass is never taken away, so a
picture that shows every glass has missed none. SmolVLA reads the two pictures themselves, so
it takes both on every turn.

A picture costs a quarter of a second of arm time, because the arm must stand still while it
is taken. While the arm travels to the second place, the whole glass zone is treated as one
solid block, so the arm flies over it and cannot hit a glass the first picture missed.

## What the arm cannot do

To push a glass straight away from its neighbour, the hand has to come down in the gap
between the two glasses, and the hand and wrist do not fit in that gap. So the most obvious
push is never possible. Pushes at a right angle to that line are possible about a third of
the time. [What the pushes show](what-the-pushes-show.md#the-obvious-push-is-the-one-the-arm-cannot-make)
gives the measurement. Every learned solution has to learn this.
