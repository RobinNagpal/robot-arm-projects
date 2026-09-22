# What went wrong, and what was done about it

This is the record of getting the project to actually run. Everything in the
other six documents describes how the task is meant to work; this one
describes what happened when it was first put in front of a simulator, which
is a different thing entirely. Nothing here is a design decision. Every item
is a place where the code said one thing and the world did another, and the
value of writing them down is that almost none of them looked, at first, like
what they turned out to be.

There is a pattern worth naming before the list starts. Nearly every fault in
here announced itself somewhere far away from where it lived. A missing line
in a model file arrived as an arm that could not plan a path. A texture drawn
at the wrong angle arrived as a glass lowered onto bare table. A sensor read
along the wrong axis arrived as a glass sliding out of the fingers. The log
said what failed, and the thing that failed was almost never the thing that
was wrong. That is why the run report described at the end of this document
exists, and why most of the later fixes were found in minutes rather than
hours.

## Problems and fixes

### Nothing ran at all

The first four faults sat between the model and the controllers, and together
they meant the task could not take a single step.

The arm has a force sensor at its wrist, mounted on the joint where the
gripper bolts on. That joint is a fixed one, and the tool that turns the
robot description into something the simulator can load folds fixed joints
into the part above them, because a joint that cannot move is usually not
worth keeping. The sensor was attached to the joint, so the sensor went with
it. The model was correct, the simulator loaded it without complaint, and the
sensor simply was not there. Telling the converter to keep that one joint
brought it back.

Once the sensor existed, nothing served it. The world loaded the system that
draws camera pictures, and force sensors are handled by a different one that
was never listed. Adding it took one line.

Once it was being served, the readings went nowhere useful. The part that
publishes them has no setting for which name to publish under, so the name
written in the configuration was read by nobody, and the readings went out
under a default name while the arm listened on the name in the configuration.
The launch now renames it, and the dead setting is gone with a note saying
why it is not there.

The last of the four was the gripper arguing with itself. Each fingertip has
a soft pad bolted flat to it, so the two are always touching, and the planner
was never told that this is normal. It therefore considered the arm to be in
collision before it had moved at all, and refused to plan anything. Two lines
in the robot's collision settings fixed it.

### The arm could not see the glasses

The project's central idea is that a depth camera gets nothing back through
glass, so the hole in the depth picture is the shape of the glass. This is
true of real cameras and it is not true of this simulator, which measures a
glass as though it were painted wood. The picture arriving at the perception
code had no holes in it, so nothing was ever found.

The fix keeps the idea and repairs the simulation. A second camera beside the
depth one reports which pixels are glass, and the wrist camera blanks the
depth at those pixels before handing the picture on. What leaves the camera
is an ordinary depth picture with holes in it, which is what a real sensor
hands over, and everything downstream is unchanged and none the wiser. The
alternative — letting the perception read the labels directly — would have
been less work and worth nothing, because the pipeline would then depend on
something no real cell has.

With holes in the picture at last, the sky became a glass. Beyond the edge of
the table a camera looking level sees nothing at all, so the depth comes back
empty, and the rule for telling a glass from empty space is whether anything
is visible through the hole. The background had been set dark for exactly
this reason, but not dark enough: the simulator writes colours out in a way
that turns a nearly-black 2% grey into 41 out of 255, which counts as
something visible. The whole horizon read as one glass 346 mm across. Black
is black now.

### One look from above is not enough

![One look against two](../images/one-look-two-looks.png)

A camera looking straight down at a glass has to decide how far away it is,
and it cannot. A pixel is a direction, not a place, and the only way to turn
a direction into a place is to say which surface it landed on. The one
surface the arm knows is the table, so the code laid the glass's outline down
on the table — and the outline is not on the table, it is the widest part of
the glass, standing some way above it. Laying it down pushes it outwards,
away from the point directly under the camera, and the further the glass is
off to one side the worse it gets. Measured against a glass whose real
position was known, a glass 157 mm from the camera was being reported 244 mm
away.

Since the arm cannot know how tall a glass is before it has measured it, it
cannot correct for this from one picture. It can from two. The same unknown
height that spoils one picture decides how far the glass appears to shift
when the camera steps sideways by a known amount, so the shift measures it:
step by `d` and a glass laid down on the table appears to move by `d` divided
by the amount it was stretched. The survey now takes two pictures at each
station and works the rest out.

Two consequences followed. Stations are tiled over the part of the table that
both pictures of a pair share rather than over one picture, because a glass
caught in only one of them cannot be placed at all. And a glass so short that
it barely leans at all reads as having moved exactly as far as the camera
did, which the arithmetic turns into "the glass is below the table"; that is
not a different glass, it is a glass with almost no lean to measure, and it
is now taken as standing on the table rather than thrown away.

### Measuring a glass from the side

The survey started working, which meant the side-on measurement began being
asked real questions for the first time, and most of its answers were wrong
for five separate reasons.

The picture came out rolled. The code that points the camera pins the last
free angle using a rule chosen for poses that look downwards, and every
measuring pose looks along the table instead; for those it gave a different
roll for each side of the glass the arm stood on. Since the profile is read
one row at a time, with a row meaning a height, a rolled picture measures the
glass across instead of up. It is now pinned against the room's own upright.

The camera stood too close. It looks level from 120 mm above the table, so at
300 mm away the foot of the glass sat 21.8 degrees below the middle of the
picture against a half-frame of 23.4 — inside the picture, but in the last
few pixels of it. A wine glass with its foot cut off is a bowl narrowing to a
stem with nothing below it, which has no waist in it, and a glass with no
waist is not a stemmed glass to any rule that looks for one. How far back to
stand is now worked out from the lens, the height the camera aims at and the
tallest glass the cell handles, which comes to 380 mm here.

It measured everything else in the frame as well. A glass with a neighbour
standing behind it measured as one glass the width of the table. It now
measures the one in the middle, which is the one the camera was aimed at, and
prefers a line of sight with nothing behind it — judged as an angle at the
camera, because that is what decides whether two glasses touch in a picture
rather than how far apart they are on the table.

The test for a ragged outline was a fraction of the glass's own width, which
quietly assumed a glass a hundred-odd pixels across. Standing further back
made them forty, and the one-pixel wander that any mask edge has is already
two and a half per cent of forty, so clean pictures of narrow glasses were
being thrown out. Whichever of the fraction and two pixels is the more
forgiving now wins.

Finally, nothing checked that the answer was possible. A profile taller than
the tallest glass the cell handles is two glasses standing in a line, and a
foot further from where the arm aimed than a glass is wide is a different
glass; either one now sends the arm round to another side, which is what the
retry was always for.

### Picking the glass up

![The gripper has a body](../images/the-gripper-has-a-body.png)

The rule for a straight glass looks for the lowest piece of upright wall it
can find, and it found one 18 mm above the table. The gripper comes in level,
so its body lies across the grip height rather than above it, and the body is
a 90 mm box — so holding a glass 18 mm up puts 27 mm of gripper through the
table. What came back was not "that is not a grip I can make" but a path that
solved none of the way, which reads like an arm that cannot lift a glass.

There is now a floor on how low a glass can be held, set by half the
gripper's body and a little clearance, and it bounds the band each rule
searches rather than checking the answer at the end. That distinction
matters: every one of these rules looks for the lowest wall that will do, so
a floor applied afterwards would turn "hold it higher" into "this glass
cannot be held" on every glass. It does mean a short glass is refused, since
below 50 mm the gripper is through the table and above half its own height it
cannot be turned over, leaving a glass under about 120 mm with nothing in
between. That is a fact about this gripper and this task, and it is now
reported as a reason rather than as a failed move.

Even at a sensible height the fingers kept arriving beside the glass rather
than around it, because everything up to that point aims from pictures taken
half a metre away and was landing about 10 mm out. The camera is on the
wrist, so at the grasp pose it looks straight down the approach at the glass
from a hand's breadth away, where a millimetre on the table is worth many
pixels. It now takes one look from there and shifts sideways onto what it
sees, along the axis the fingers close on and no further than half the
gripper's opening. The grasp went from 10 mm out to the fingers finding
76.6 mm where the camera had said 76.9.

### Carrying, turning and setting down

![Which way is down](../images/which-way-is-down.png)

Every glass weighed nothing. The wrist sensor reports in the gripper's own
frame and the reading taken from it was the axis the gripper reaches along —
which points down only when the gripper points down, and it never does here,
because a glass is gripped by reaching in level at it. That axis carries none
of the weight. The reading is now turned into the room's frame and the
upright part of it taken, and a glass came back at 267 g.

Two follow-ons came out of that. The code no longer falls back to the raw
reading when it cannot work out which way is down, because that fallback
reported every glass as weightless, and a glass that weighs nothing is
gripped gently and dropped — which is what "the glass slid in the fingers
during the tilt" had been. And the weight is now the middle of about a third
of a second of readings rather than one sample, because the fingers squeeze
hard and sideways and the arm starts and stops, and either throws a spike
many times the weight of a glass through the sensor; one reading gave 0 g and
the next 9577 g.

Setting a glass down was feeling with the wrong sensor. The fingertips feel a
pad meeting something, which is right when the pads arrive first, and they do
not when a glass is being lowered: the rim lands and the pads touch nothing.
The descent reported an empty 60 mm while the glass was already on the rack.
It now also watches for the weight going out of the wrist, which is the rack
taking it.

Once the arm was holding a glass, it could not move at all. The links a held
glass is allowed to touch listed the gripper body and the two fingers, and
not the pads — and the pads are the only parts that ever touch a held glass,
because they are what stands between the fingers and it. So the glass was in
collision with the gripper holding it from the moment it was picked up. This
one is worth dwelling on, because the evidence was so misleading: a path
planned from a state the planner has already rejected comes back having
solved none of the way, exactly as if the move itself were impossible, and
that took the recovery with it, since standing clear was also a move.

The glass was also attached in the wrong place. Where a glass sits in the
gripper is worked out by comparing where the glass is with where the tool is,
and the two were being taken a lift apart — the glass from before the 180 mm
lift, the tool from after it. The planner therefore believed in a glass
hanging 180 mm below the real one, through the table.

![The turn swings the arm](../images/the-turn-swings-the-arm.png)

Turning a glass over asks more of the wrist than anything else in the task,
and it was being done wherever the pick happened to leave the arm, which is
usually stretched out and is exactly where the last joint has least left to
give. The glass is now carried to the middle of the table first, so the turn
is the same problem every time. That fix needed a second go: the first
version parked the *tool* at a comfortable reach, and since a turn swings the
tool a fingertip's length either side of the glass, a tool at 450 mm came out
of the turn at 790 mm, past the end of the arm. It is the glass that stays
put during a turn, so it is the glass that gets parked.

### What the planner was told about the world

![The rack the planner saw](../images/the-rack-the-planner-saw.png)

The arm kept failing to reach places with nothing in them, and the planner,
when asked, said its own forearm and upper arm were inside the rack. The rack
stands square to the table but not square to the world — it is turned a
quarter circle, so its row of slots runs along one axis while the box
describing it to the planner was built from the row's length and never turned
to match. It came out at right angles to the rack it was standing in for,
which put a 600 mm slab across open table where the arm has to work, and left
the real rack covered by nothing at all.

The same quarter turn appeared again in the marker. The rack is found by
reading a printed square on its base, and the way that square is printed says
which way the rack is facing; every slot is placed from it. It is painted
onto a box face, and how a texture lies on a box face is the simulator's
business rather than ours, so the arm read a rack square to the world when
the rack is turned across it, and laid its six slots out at right angles to
the real rack, over bare table. A glass lowered into one of those came down
the full 60 mm and touched nothing, which is precisely what the run had been
reporting for some time.

Two smaller things sit alongside. Glasses were being put out as far as 825 mm
from the base, past what the arm can reach, so a glass drawn there was
refused however well it had been measured — a perception failure that was
nothing of the kind; the zone is now 330 to 777 mm at its corners, with a
test holding the zone and the arm's reach to each other, since they live in
different files. And a slot has to be reachable from either side, because
standing a glass in one puts the tool a fingertip's length to one side and
which side was settled when the glass was picked up; the far end of the row
put the tool 796 mm out.

### Two habits, rather than faults

Two changes are not fixes for anything in particular and have paid for
themselves several times over.

Moves are planned up to three times before being called impossible. The
planner grows a tree from samples that fall at random, so a move it fails
once it often solves the next time from a different set; a pose that truly
cannot be reached still fails every attempt just as quickly.

And every run now writes an account of itself into `runs/`, as a markdown
file with the pictures it took beside the sentences, saying what the arm was
about to do and what came of it. It is written as it happens and flushed
every time, so a run that dies half way still leaves everything up to the
moment it died — which is the run you most want it for. The one thing in it
that the arm does not get is what was actually put on the table, written by
the world builder before the arm sees any of it, so that what the arm worked
out can be held against what was really there. Most of the faults in the
second half of this document were found by reading one of those files, and
several of them in a single pass.

## Open items and questions

These are the things that are not finished, in the order they would be worth
picking up.

**No glass has been placed in the rack yet.** The arm finds the rack,
surveys the table, measures a glass to within a few millimetres, names its
kind, works out where to hold it, reaches in, closes on it, lifts it, weighs
it at 267 g, carries it to the middle of the table, turns it over and lowers
it onto a slot — and then comes down the full 60 mm without feeling
anything. The arithmetic says the rim should touch after about 10 mm: it
hangs 102 mm below the grip, the grip is put 132 mm above the slot, and the
rack's base stands 20 mm above the plane the slots are measured in. So the
rim is not where the geometry says it is once the glass has been turned over.

**The most likely cause of that is a second fault in how a held glass is
attached.** In the same run, the planner reported the arm's forearm to be
in collision with the held glass, which means the shape standing in for that
glass is not where the glass is. One fault of this kind has already been
fixed — position taken before the lift, tool taken after it — and this looks
like another in the same place, most probably the glass's orientation after
the turn rather than its position. It is checkable without the simulator by
comparing the attached shape's pose against the tool's pose immediately
after the turn.

**The survey is out by about 30 mm along one axis.** Across four runs of the
same table, the survey placed a glass within 4 mm along one axis every time
and about 30 mm out along the other, and the axis it is wrong about is the
one the two pictures step along — that is, the very thing the second picture
is there to measure. The side-on measurement happens to correct most of it,
which is why the error was invisible for so long and why the correction is
always about the same size. The shrink figure the arithmetic produces, 0.868
where the geometry says about 0.826, accounts for only a few millimetres of
it, so most of the error is in finding the middle of the outline or in
merging the stations, not in the arithmetic that follows. The clean test is
to compare each single picture's answer against the truth before any
correction is applied.

**Runs fail in different places from one attempt to the next.** Every stage
now works, but several are close to the edge of what the arm can do, and a
run has to get through all of them. Recent attempts have stopped at the
measuring view, at the reach in, at the grip rules and at the set-down, which
suggests the honest summary is that each stage works most of the time and
that end to end is therefore much less often. Whether that is worth attacking
stage by stage or by giving the arm more room to work in is an open question.

**The arm is bolted to the middle of the table.** Its base sits at table
height, so its lower links are near the surface and graze the table whenever
it reaches low, which is genuinely the case rather than a modelling error and
makes low reaches tight. A good deal of the marginal planning above may come
back to this. Moving the arm to the edge of the table, or raising it, would
be a change to the cell rather than to the code, and it would want to be a
deliberate decision.

**Short glasses cannot be picked up at all.** Below 50 mm the gripper's body
is through the table and above half its own height a glass cannot be turned
over, so anything under roughly 120 mm tall has no band left to grip. The arm
says so clearly and leaves the glass standing, which is the right behaviour,
but it means part of the range of glasses the project generates can never be
handled by this gripper. Either the generator should not draw them, or the
gripper wants a slimmer body, or such glasses should be picked up a different
way; nothing has been decided.

**A whole table of glasses has not been tried since any of this was fixed.**
Everything above was chased with one glass on the table, which was the right
way to do it, but the survey, the collision scene and the slot bookkeeping
all behave differently with five or six. That is the obvious next test once a
single glass goes in reliably.

**The measured width comes out a little under the truth.** A glass that is
really 71 mm across its widest measured 66, and one really 78 mm across
measured 77. It has not caused a failure, because the fingers close on the
glass and check the width by touch before anything is lifted, and it may be
no more than the outline being found a pixel inside the glass on each side.
It has not been looked into.

**Lint does not pass on the project as a whole.** Ten files were already
failing the formatter before any of this work started, and none of them are
files this work touched. It is left alone deliberately, but it does mean
`make lint` cannot be used as a gate until somebody decides whether to
reformat them.
