# Problem statement: two arms play Jenga

## The idea in one paragraph

Two robot arms sit on opposite sides of a table with a Jenga tower between
them. They take turns pulling a block out of the tower and putting it on top,
exactly as two people would. Each arm is programmed with a **different
approach**. Whichever arm makes the tower fall loses. We play enough games to
see, fairly, which approach is better at the game.

This is a question about approaches, not about robots. Both arms are the same
arm with the same sensors. The only difference between them is the code, so if
one wins more often, the code is the reason.

## Why Jenga

The earlier projects in this repo each push on one hard thing. v1 is about
seeing: measure a box and act on it. v2 is about several parts that have to
agree. Jenga adds two things none of them have.

**The important information cannot be seen.** Some blocks in a Jenga tower are
loose and slide out easily. Others are gripped by the blocks above and below
them, and pulling one of those brings the tower down. The two kinds look
identical. The difference comes from tiny differences in block size — a tenth
of a millimetre — that no camera can measure. The only way to find out is to
touch: push a block gently and feel whether it gives. So an arm that can only
see is playing half blind.

**There is an opponent.** In v1 and v2 the arm is alone with the world. In
Jenga every move also changes what the other player is left with. A good move
is not just safe for you; it can also leave the tower harder for the other side.
That turns a manipulation problem into a game.

Between them, those two make Jenga a clean test of an approach. Moving one
block is easy. Moving the right block, gently enough, on the fortieth move,
with someone trying to make you fail, is not.

## The setup

- **A table**, with the tower standing in the middle of it.
- **Two UR5e arms**, the same arm as v1 and v2, bolted to the table at opposite
  ends and facing each other. Each is about half a metre from the tower, close
  enough to reach its own side of the tower and both flanks.
- **The same tools on each arm:**
  - a two-finger gripper;
  - an RGB-D camera on the wrist;
  - a force-torque sensor at the wrist. The real UR5e has one built in, so this
    is not an extra — and without it neither arm could feel a block.
- **A standard Jenga tower:** 54 blocks in 18 levels of three. Each level lies
  at right angles to the one below it. A block is 7.5 × 2.5 × 1.5 cm.
- **Tightness that varies from block to block.** Each tower is built with small
  random differences in block thickness, so that some blocks are loose and some
  are tight, just like a real set. Without this the game would be pointless:
  every block would be equally easy to take.

Everything runs in simulation.

## The rules

These are the normal Jenga rules, written down precisely enough that a
program can check them.

1. **Take turns.** Only the arm whose turn it is may move. The other arm waits
   in its parked pose, clear of the tower.
2. **Take one block** from any level below the top completed level.
3. **Use one arm.** That is automatic here; each player only has one.
4. **Testing is allowed.** An arm may push blocks to find a loose one. If it
   moves a block and then decides not to take it, it must leave the tower
   standing and choose another. It may not take two blocks in one turn.
5. **Put the block on top.** It goes on the top level, at right angles to the
   level below, completing a level of three before a new one is started.
6. **The tower must stand.** The turn ends ten seconds after the arm lets go of
   the block and returns to its parked pose, if the tower is still standing.
7. **Time limit.** A turn must be finished within three minutes of simulated
   time.

**You lose the game if, on your turn or in the ten seconds after it:**

- the tower falls;
- any block falls off the tower, other than the one you are moving;
- you break a rule or run out of time.

If the tower is ever left with no legal move, the game is a draw. This is rare.

## What each arm knows

This follows the rule from v2: **an arm knows itself, and the rules, and
nothing else about the world.**

It knows:

- where its own base is, and how its arm, gripper, camera and force sensor are
  built;
- the rules above;
- what a Jenga block looks like and how big it nominally is. A person knows
  that before they sit down to play, so the arm may too.

It does not know:

- where the tower is, or how it is leaning;
- which blocks have been taken, or where each block sits;
- which blocks are loose. **That is the whole game.** It has to be found out by
  looking and feeling, on every turn, because every move changes it.

An arm may not read the simulator's own state, and may not talk to the other
arm. Everything it knows about the tower, it has to have measured.

## Who decides who won

A separate program, **the referee**, runs the game. Unlike the arms, the
referee can read the simulator directly, so it knows the true position of every
block. It uses that to:

- tell each arm when its turn starts;
- check every move against the rules;
- notice when the tower falls, or when a block drops;
- record who won each game, and why.

Keeping the referee separate from the arms matters. It is what stops either
approach from quietly using information a real robot would not have.

## How we tell which approach is better

One game proves very little. A tower can come out unlucky for whoever happens
to be playing when it gets shaky. So a match is many games, arranged so that
luck cancels out:

- **Every tower is played twice**, once with each arm going first. The same
  random tower, the same loose and tight blocks, both ways round. A seed makes
  each tower repeatable.
- **Twenty games per match**: ten different towers, each played both ways.

The approach that wins more games wins the match. Twenty games is enough to
tell a real difference from a lucky one, but only a clear one: 15 wins to 5
means something, 11 to 9 does not. A close result means the approaches are
close, and more games are needed to say more.

Besides who won, the match records the things that explain *why*:

- how many turns each arm survived, on average;
- how long each arm took per turn;
- how many blocks it tested before choosing one;
- how often it had to give up on a block it had started moving;
- how each game ended — tower fall, dropped block, time, or rule.

## What is out of scope

- **Real hardware.** Everything is simulated.
- **Humans.** Robot against robot only.
- **Rule variants.** Standard rules only, as written above.
- **Picking the approaches.** That is what [`approaches.md`](approaches.md) is
  for.

## Decisions still open

**Which simulator runs the arena.** Jenga asks a lot of a physics engine: 54
blocks stacked with nothing holding them but friction, which must stand still
when untouched and still slide when pushed. Two sensible choices:

- **Gazebo**, like v1 and v2. Everything in the repo would stay on one set of
  tools. The risk is that its physics is weaker at exactly this — tall stacks of
  small, touching, friction-held objects tend to jitter or creep.
- **MuJoCo.** Its contact physics is strong at exactly this, and it is fast.
  The cost is a second set of tools in the repo, and redoing the arm and sensor
  setup that v1 and v2 already have for Gazebo.

The way to decide is to try it before writing either arm. **The first
milestone is the arena on its own:** a full tower that stands for ten minutes
untouched, and where a gentle push slides a loose block out but not a tight
one. If Gazebo can do that, use Gazebo. If it cannot, nothing built on top of it
will be worth trusting, and MuJoCo is the answer.
