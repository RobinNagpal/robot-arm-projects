# v6: two arms play Jenga

This folder is plans only. There is no code in it yet.

Two robot arms sit on opposite sides of a Jenga tower and take turns, pulling a
block out and putting it on top. Each arm is programmed with a different
approach. The one that makes the tower fall loses, and a match of many games
shows which approach plays better.

Both arms are the same arm with the same sensors. The only difference between
them is the code — so when one wins more often, the code is why.

## Why this is worth doing

Moving one Jenga block is easy. What makes the game hard for a robot is that
the thing that matters most — which blocks are loose — cannot be seen. It can
only be felt, by pushing gently and noticing whether the block gives. On top of
that there is an opponent, and every move changes what the other side is left
with.

So Jenga tests exactly what the earlier projects in this repo did not:
information that has to be gathered by touch, and a second player. It turns
"can the arm do this?" into "which way of programming an arm is better?", and
answers it with a score.

## The two documents

| File | What it answers |
| --- | --- |
| [`PROBLEM_STATEMENT.md`](PROBLEM_STATEMENT.md) | What exactly the game is: the table and the two arms, the rules, what each arm is allowed to know, how the referee decides, and how many games it takes to call a winner fairly. |
| [`APPROACHES.md`](APPROACHES.md) | Five ways to program an arm to play — follow rules, feel, think ahead with a physics model, learn by trial and error, learn by copying a person — with the tools each needs, how each would be built, how hard it is, and how they compare. |

## The short answers

**The game.** Two UR5e arms, each with a gripper, a wrist camera and a wrist
force sensor, play a standard 54-block tower under normal Jenga rules. Each
arm knows only itself and the rules; everything about the tower it has to see
or feel. A separate referee, which can read the simulator directly, runs the
game and decides who lost. A match is twenty games — ten towers, each played
once with each arm going first — so that luck cancels out.

**The first match.** *Feel* against *Think*. Both arms test blocks by touch.
One simply takes a block that moves easily. The other keeps a physics model of
the tower in its head, tries moves there first, and looks ahead at what it
leaves its opponent. It asks a real question — does reasoning beat careful
reacting? — with two approaches whose every decision can be read back from the
log.

**The first milestone, before either arm is written.** A simulated tower that
stands still when left alone, and where a gentle push slides a loose block out
but not a tight one. Everything else depends on the physics getting that
right, and it decides which simulator to use.
