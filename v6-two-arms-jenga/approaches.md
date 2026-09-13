# Approaches: how to program an arm that plays Jenga

[`problem-statement.md`](problem-statement.md) says what the game is. This file
is about the code: five ways to program an arm to play it, what each would be
built with, roughly how it would be built, how hard it is, and how they
compare. It ends with which two to put against each other first.

## What every approach has to do

Every turn, whatever the approach, the arm does the same five things:

1. **Look** at the tower and work out where each block is.
2. **Choose** a block to take.
3. **Test** it, if the approach tests at all — push gently and see what happens.
4. **Take** it out and put it on top.
5. **Back off** to its parked pose and wait.

Most of that is the same for every approach, and it is worth building once.
Seeing the tower, knowing where each block sits, and having reliable moves for
"push this block", "pinch the end of this block" and "set this block on top" —
none of those depend on how clever the arm is. The five approaches differ in
only two places:

- **how the arm chooses** which block to take, and
- **how the arm moves** the block — by following a fixed path, or by feeling
  its way.

That matters for planning the work. The shared part is where most of the
effort goes, and every approach below is built on top of it.

### The shared part

The same tools as v1 and v2: **ROS 2** to carry messages, **MoveIt 2** to plan
the arm's moves, **ros2_control** to drive the joints, and the wrist camera for
seeing.

- **Tower perception.** The camera sees a stack of identical blocks. Because the
  block size is known, the job is to fit the camera's points to a grid of
  blocks, level by level, and say which slots are full and which are empty.
- **Motion pieces.** A push with a fingertip, a pinch of a block's end, a lift,
  and a placement on the top level, each built from MoveIt moves the way v1's
  touch and v2's placements are.
- **The turn loop.** Wait for the referee, take a turn, report, park.

## The five approaches

Each approach gets a short name that says what it relies on.

| # | Name | In one line |
| --- | --- | --- |
| 1 | **Rules** | Look, then follow a fixed recipe. Never feel anything. |
| 2 | **Feel** | Push each candidate gently and keep the ones that give. |
| 3 | **Think** | Keep a physics model of the tower in its head, and try moves there first. |
| 4 | **Practise** | Learn by trial and error from millions of simulated games. |
| 5 | **Copy** | Learn by watching a person play through the arm. |

How hard each one is, is given against the largest working project in this
repo, v2:

- **Low** — less work than v2.
- **Medium** — about as much as v2.
- **High** — a few times v2, and a second set of tools to learn.
- **Very high** — all of that, plus training runs that need a GPU and can fail
  in ways that are hard to see.

---

### 1. Rules — look, then follow a recipe

**The idea.** The arm never tests a block. It chooses using rules of thumb that
people know from playing: prefer the middle block of a level, prefer levels
near the bottom, never take a block that would leave a level standing on one
side only. Then it pushes the chosen block out along a fixed path.

**Why it could work.** Jenga has real patterns, and good rules capture some of
them. The middle block of a full level is often loose, because the level above
can rest on the two outer blocks.

**Where it breaks.** Everything that matters about a block — whether it is
loose — is invisible, and this arm never finds out. It is guessing, every turn.
It also pushes with a fixed movement, so a block that is tighter than expected
gets shoved rather than eased, and takes the tower with it.

**Frameworks.** Only the shared part: ROS 2, MoveIt 2, ros2_control, and the
camera for perception.

**How it would be built.**

- The shared part, above.
- A scoring function over the blocks the rules allow, choosing the best one.
- A fixed push: approach the block's end, move straight in a set distance, then
  pinch the part that comes out on the far side and lift it.
- Place on top, park.

**Complexity: Low.** Nearly all the work is the shared part. The rules
themselves are a page of code.

**Why it is on the list.** Not to win. It is the baseline every other approach
has to beat, and it *is* the shared part, so it gets built first no matter
which two approaches end up playing.

---

### 2. Feel — push gently, keep the ones that give

**The idea.** This is how people play. Choose a few candidate blocks, then test
each one: push it slowly while watching the force sensor. A loose block slides
with almost no force. A tight block pushes back. If the force climbs past a
limit, stop, pull back, and try the next candidate. Only take a block that
moved easily.

**Why it could win.** It is the only approach so far that actually measures
the thing the game is about. It does not need to be clever about the tower,
because it asks the tower directly, one block at a time.

**Where it breaks.** It only knows about the blocks it has tested, and each
test takes time and disturbs the tower a little. It does not think ahead: it
takes the easiest safe block now, even if that leaves the tower worse for its
next turn. And the force limit has to be right. Too low and it rejects every
block; too high and it has already disturbed the tower by the time it stops.

**Frameworks.** The shared part, plus:

- the wrist **force-torque sensor**, simulated in Gazebo and bridged into ROS
  like the fingertip contact sensors in v1;
- ros2_control's **admittance controller**, which makes the arm soft along the
  push direction — it gives way when pushed back, rather than holding its
  position no matter what;
- **MoveIt Servo**, for small, continuous corrections while the push is going
  on, instead of one planned path fixed in advance.

**How it would be built.**

- Everything from approach 1.
- A *probe* move: push slowly under force control, stop at a force limit or a
  distance, whichever comes first.
- A rule for reading the probe: how far the block moved for how much force.
- A test budget per turn, so the arm does not run out of time testing.
- Tuning the force limit, which is most of the real work.

**Complexity: Medium.** Force control is the new skill. It is well supported in
ROS 2, but getting a push that is firm enough to move a loose block and gentle
enough not to rock the tower takes careful tuning, in a simulator that has to
get the friction right.

---

### 3. Think — a physics model of the tower, in the arm's head

**The idea.** The arm keeps its own simulation of the tower, separate from the
arena. Every time it pushes a block, it learns something about how tight that
block is, and updates its model. Before each move, it tries the candidate moves
in its head first — simulating what would happen if it pulled each one — and
chooses the one that keeps the tower most stable. It can go one step further
and ask what each move leaves for the opponent.

**Why it could win.** It is the only approach that reasons about consequences.
Approach 2 knows which block is loose *now*. This one can estimate what
happens to the whole tower when that block is gone, including to blocks it has
never touched, because it understands why a block is loose: the weight above
it is resting somewhere else. And it can play the game, not just the move:
choosing the safe move that leaves the opponent the fewest safe moves.

**Where it breaks.** The model is only as good as what it has measured. Early
in a game it knows little, so its predictions are rough. Keeping a second
simulation matched to the real tower is hard, and if the two drift apart, the
arm will confidently choose moves that were only safe in its head. It is also
slow: simulating many candidate moves takes time out of a three-minute turn.

**Frameworks.** The shared part, the force sensing from approach 2, plus:

- **MuJoCo** (or **Drake**) as the internal simulator. Both are strong at
  contact physics and fast enough to run many short "what if" simulations per
  turn.
- A **particle filter** — many guesses about each block's tightness at once,
  kept or thrown away as pushes confirm or contradict them.
- Optionally, a **game-tree search** such as Monte Carlo tree search, to look
  ahead at the opponent's options.

**How it would be built.**

- Everything from approach 2.
- Building the internal tower model from what the camera sees.
- Updating the guesses about each block's tightness after every push.
- Simulating each candidate move and scoring how stable the tower stays.
- Keeping the internal model in step with the real tower after every turn,
  including the opponent's.
- Optionally, the lookahead over the opponent's replies.

**Complexity: High.** Two simulators have to agree, and the hardest part —
estimating tightness from a few pushes — is research-level. It has been done:
MIT's Jenga-playing robot (Fazeli and others, *Science Robotics*, 2019) is close
to this approach, pushing blocks while measuring force and learning, from a few
hundred pushes, which pushes were safe. But it is not a weekend project.

---

### 4. Practise — learn by trial and error

**The idea.** Nobody writes down how to play. Instead, a neural network
controls the arm, and it plays Jenga millions of times in a fast simulator. At
first it knocks the tower over constantly. Each time, it is rewarded for moves
that keep the tower up and punished for moves that bring it down, and it slowly
gets better. This is *reinforcement learning*. To learn the game side, two
copies can be trained against each other — *self-play* — the way game-playing
programs learn chess and Go.

**Why it could win.** It is not limited to what its programmers understood.
Given enough practice, it can find ways of testing and pushing that nobody
thought to write down, and through self-play it can learn to play against an
opponent, not just against the tower.

**Where it breaks.** It needs a huge amount of practice, which means a
simulator that runs thousands of towers at once — usually not the arena. So it
learns in one simulator and plays in another, and anything that differs
between them, like slightly different friction, it has never seen. Designing
the rewards is hard: reward the wrong thing and it learns the wrong thing. And
when it loses, there is no rule to point at; it is hard to say why it did what
it did.

**Frameworks.**

- **Isaac Lab** (on NVIDIA Isaac Sim), or **MuJoCo** with its GPU version, to run
  thousands of towers in parallel;
- **PyTorch**, with an RL library such as **rsl_rl** or **Stable-Baselines3**;
- a ROS 2 node that runs the trained network in the arena.

**How it would be built.**

- A training copy of the tower and arm in the parallel simulator, with block
  tightness randomised far more widely than the arena's, so the arena is not a
  surprise.
- A reward for a turn: a block moved to the top with the tower still standing.
- Probably split in two: one learned skill for *how* to push, and a simpler
  layer on top for *which* block — learning both at once is much harder.
- Training runs, many of them, adjusting as each one fails.
- Moving the trained network into the arena, and checking it still works
  there.

**Complexity: Very high.** New tools, GPU time, and the most unpredictable of
the five: a training run can take days and still come back useless, and it is
often unclear why.

---

### 5. Copy — learn by watching a person play

**The idea.** A person plays Jenga through the arm, in the arena, using a
controller to steer it, while every camera image, force reading and arm
movement is recorded. After a few hundred moves, a neural network is trained
to do what the person did in the same situation. This is *imitation learning*.
Recent methods — *Diffusion Policy* and *ACT* are the best known — are
particularly good at the delicate, contact-heavy movements Jenga needs.

**Why it could win.** Humans are good at Jenga, and a lot of that skill is in
the hands, not in rules anyone can write down. Copying a person's actual
movements captures that. And because the demonstrations are recorded in the
arena itself, there is no gap between where it learned and where it plays.

**Where it breaks.** It can only be as good as the person it copies, and only
in situations it has seen. It needs a lot of careful demonstrations, which
means a person spending days at the controller. It does not plan and does not
think about the opponent; it reacts. And like approach 4, when it fails it is
hard to see why.

**Frameworks.**

- **LeRobot** (from Hugging Face), which provides Diffusion Policy and ACT ready
  to train;
- **PyTorch**;
- **MoveIt Servo** and a 3D controller such as a SpaceMouse, so a person can
  steer the arm smoothly;
- **rosbag2** to record the demonstrations.

**How it would be built.**

- The shared part, and a way for a person to drive the arm live.
- Recording sessions: many towers, many moves, including the force readings,
  so the network can learn to feel as well as see.
- Training, and checking the result on towers it has not seen.
- Probably a simple rule-based chooser on top, with the learned network doing
  the delicate push and pull.

**Complexity: High.** Less unpredictable than approach 4 — learning from
examples is steadier than trial and error — but the demonstrations are real,
slow, human work, and there is no shortcut round them.

---

## Also considered

**Large vision-language-action models**, such as OpenVLA or π0 — big networks
trained on many robots and many tasks, which can be told what to do in words.
They are the most general option there is. They are left off the list because
Jenga is the thing they are weakest at today: millimetre-level pushes where
the answer is in the force, not the picture. They may be worth revisiting as
they improve.

## How they compare

| | 1 Rules | 2 Feel | 3 Think | 4 Practise | 5 Copy |
| --- | --- | --- | --- | --- | --- |
| **Finds loose blocks by** | guessing | touching | touching and predicting | learned instinct | copying a person |
| **Moves the block** | fixed path | softly, by feel | softly, by feel | learned | learned |
| **Thinks about the opponent** | no | no | yes, with lookahead | yes, if trained by self-play | no |
| **Main new tools** | none | force control | MuJoCo, particle filter | Isaac Lab, RL, GPU | LeRobot, teleoperation |
| **Complexity** | Low | Medium | High | Very high | High |
| **Most work goes into** | the shared part | tuning the push | keeping two simulations in step | training runs | human demonstrations |
| **When it loses, can you tell why?** | yes | yes | yes, mostly | rarely | rarely |
| **How sure it is to work at all** | certain | likely | uncertain | uncertain | likely |

A few things stand out.

**Feeling is the dividing line.** Approach 1 is the only one that never
touches a block before choosing it, and in a game decided by something
invisible, that is expected to be decisive. Approach 2 should beat it nearly
every game, and that alone would show something worth knowing: how much the
force sensor is worth.

**Only two approaches can play the game, not just the move.** Approach 3
through lookahead, approach 4 through self-play. The others choose the safest
block for themselves and ignore what they leave behind. Against each other
that may not matter much. Against an opponent that deliberately leaves bad
towers, it could decide matches.

**Understanding versus learning.** Approaches 1 to 3 are written by people who
understand why they work, so when one loses, you can read the log and see the
mistake. Approaches 4 and 5 learn their behaviour, which may make them
stronger, but when they lose you mostly cannot tell why. For a learning repo,
that is a real cost.

**Risk grows with ambition.** Approach 1 will certainly work, and certainly be
weak. Approach 2 will almost certainly work. Approach 3 might be the strongest
of all, or might never get its internal model close enough to the real tower.
Approach 4 could be brilliant or could fail to learn at all after days of
training.

## Which two to play first

**Feel (2) against Think (3).**

- **It asks the most interesting question.** Both arms test blocks by touch, so
  this is not the easy win of feeling against not feeling. It is *reacting*
  against *reasoning*: does it pay to understand the tower and look ahead, or
  is testing carefully and taking the easy block good enough? Nobody knows the
  answer to that in advance.
- **Both can be understood.** When either wins or loses a game, the logs say
  why, which is the point of a learning repo.
- **They build on each other.** Approach 3 starts from approach 2, which starts
  from approach 1, which is the shared part. So the work goes in order: build
  approach 1 and play it against itself to prove the arena and the referee;
  add feel to get approach 2; add the internal model to get approach 3. Every
  step is useful even if the next one stalls.
- **Both use tools this repo already uses.** Everything except MuJoCo is
  already here in v1 and v2.

Approaches 4 and 5 are the natural next match. Once the arena, the referee and
the shared part exist, either learned approach could be trained and put
against whichever of 2 and 3 won — which would ask the next question: can an
arm that learned the game beat one that was designed?
