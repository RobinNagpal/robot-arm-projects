# Everything we tried to make problem 4 work better

## Introduction

Problem 4 asks an arm with a camera on its wrist to drag crowded drinking
glasses apart until each one has room for the gripper, and then to say that it
has finished. Six solutions were written for it, and when they were first
measured the result was uncomfortable: the solutions that worked everything out
with plain arithmetic were safe and useful, while every solution with a trained
model inside it either knocked glasses over or did nothing at all. This page is
the story of what was done about that. It explains, in order, what "better"
means here, why the trained solutions failed, which repairs worked and the
reason each one worked, which repairs failed and the reason each one failed, and
what is worth trying next.

By the end you should be able to answer three questions without looking at any
code: why a trained model fails at a task like this even when it has learned
something real, which kinds of repair are cheap and which are wasted effort,
and how to tell an improvement from luck.

This page is about reasons. The matching record of each individual change,
with the before-and-after numbers that decided it, is in
[what changed](what-changed.md), and the six results side by side are on
[the comparison page](../../04-clear-the-table/results/README.md). Read this
page first if you want to understand the problem, and read those if you want
the measurements.

## What "better" means in this problem

Before we can say that something improved, we need to agree on what is being
measured, because this problem is scored on three numbers rather than one.

The first number is **tables separated**: a table counts only when every glass
on it ends with enough free space around it for the gripper to reach in. The
second is **glasses freed**: how many individual glasses gained that free space,
counted across all the tables, which gives partial credit for partial work. The
third is **glasses broken**: how many glasses were knocked over. A broken glass
is treated as unrecoverable, so the whole table it stood on is thrown away and
counts for nothing at either end.

There is also a summary number called the **pickable share**, which is the
fraction of all the glasses in a set of tables that a gripper could pick up at
the end. It is convenient, and it has one weakness we keep running into. The copying
solution scored 0.400 in the measurement where it left every table exactly as it
found it, and it scores 0.359 now that it pushes glasses about, because a table
where it topples a glass is thrown away and a table it attempts and leaves
crowded still counts every glass on it. **A share can fall when a solution
starts doing the task.** That is why every result here is reported as the three
numbers together, and why no claim on this page rests on the share alone.

Two more rules shape everything below. First, **the budget is the arm's own
time**, fifteen minutes for a queue of fifty tables, so a slow solution simply
reaches fewer tables, and reaching more tables is itself a way to score higher.
Second, **every choice was made on tables numbered below ten thousand, and the
tables from ten thousand upward were used only to report the final score.** That
separation is what makes the numbers mean anything, and one decision near the
end of this page turns on it.

## The starting point

The first measurement gave a clean split between the two kinds of solution.

The two solutions that choose a push with ordinary geometry — one that always
makes the same small nudge, and one that ranks candidate nudges — broke no
glasses at all and separated the most tables per table attempted. The four
solutions with a trained model inside them did badly in two different ways. The
world model, which learns what a push does and then searches for a good one,
freed more glasses than anything else and still scored below plain geometry,
because it broke eight glasses in a single *walk* of the queue, where a walk
means one pass through the fifty tables until the arm time runs out. The three
solutions that answer straight from a camera picture — one trained here by
copying a *teacher*, which is the plain geometry solution whose answers were
recorded as examples to imitate, and one borrowed general-purpose robot model
used in two forms — freed nothing whatsoever between them and broke
twenty-eight glasses.

So the work had two targets that needed different treatment: stop the breaking,
and make a trained solution actually act on a glass.

## Why the trained solutions failed

Every repair below answers one of four causes, so the causes come first. They
were measured rather than guessed, and that matters, because three of them are
not what you would assume from watching the arm.

### Cause 1: most of the task is looking, so looking is what gets learned

When the camera sat above the table, every solution could see the whole table at
once. In problem 4 the camera rides on the wrist, so the only way to see the far
corner is to drive the arm there. This changes the teacher's behaviour
completely: **four out of every five answers the teacher gives are a move to see
from somewhere else, and only about one answer in thirty-five is a push at a
glass.**

Now think about what training on that material does. A model trained by copying
a teacher is trained to make the distance between its answer and the teacher's
answer as small as possible. When the picture does not clearly say which kind of
answer the teacher would give, the answer with the smallest average distance is
the average answer, and the average of this material is a look. So the model
learns to travel well and never to push. This single fact explains all
three of the picture-driven solutions, and it is why one of them, before any
repair, declared nine of its ten tables finished while they were still crowded.

### Cause 2: searching over an uncertain prediction selects the error

The world model works differently. It learns to predict where the glasses end up
after a push, and then tries a few thousand imaginary pushes against that
prediction and carries out the best one.

The trap is that the prediction is not equally good everywhere. Where the model
has seen pushes like the one being asked about, it predicts well; where it has
not, it guesses. A search that takes the *best predicted outcome* over thousands
of candidates will therefore tend to land exactly where the model is most
wrongly optimistic, because an over-optimistic guess looks the same as a genuinely
good push. **Taking the maximum over an uncertain estimate is a way of selecting
the largest error, not the best action.** That is why this solution broke glasses
while being the best at freeing them.

### Cause 3: a correct answer carried out with the wrong geometry

The third cause has nothing to do with learning at all, and it was the cheapest
to remove. A path is described by points that name the middle of the hand, but
the fingers hang about seventy millimetres below that middle. So a path drawn at
the height the teacher travels at still drags the fingers through the top of a
tall glass. Most of the early breakages came from this, not from any push: the
arm was destroying glasses while merely moving between viewpoints. It is a
mistake in carrying out an answer rather than in choosing one, which is why
arithmetic can fix it and more training cannot.

### Cause 4: the thing being copied is smaller than the copier's own error

The fourth cause only became visible once the picture-driven solutions started
pushing at all, and it is the most instructive of the four. Three measured
distances will not fit together:

| | |
| --- | --- |
| how far one of the teacher's pushes moves a glass | about 13 mm |
| how much room a glass needs before the gripper fits | 76 mm |
| how accurately the trained network places a point on a path | about 20 mm |

The teacher frees a glass over a long run of small pushes, looking again after
each one, so no single teacher push is meant to finish the job. The *student*,
which is the name used here for the trained model doing the copying, is
therefore copying a motion that is smaller than its own error. Measured over
twenty tables, the pushes the student carried out moved their glass a median of
**zero** millimetres: the hand stopped at the near edge of the glass instead of
driving past its middle. No amount of extra training fixes a target that sits
below your own noise, because the signal you are asked to reproduce is smaller
than the mistakes you make reproducing it.

## What worked, and why it worked

The repairs that worked fall into four groups. Reading them as groups is more
useful than reading them one by one, because each group is one idea applied in
several places.

### Group 1: let a solution check its own answer before handing it over

The largest single improvement in the problem came from a piece of shared
arithmetic that every solution now runs over its own answer, just before giving
it to the examiner, which is the program that carries the answer out and marks
the work. The rule it applies is simple to state. An answer is either
a *look*, in which case every point on its path must be at the height the arm
travels at, where nothing on the table can be touched; or it is a *push at one
named glass*, in which case the path may reach that glass and no other glass,
and it must stay low, at the height where a shove goes through the glass's foot.
Anything else is lifted to travel height, which touches nothing and costs the
same time. Each glass is treated as slightly bigger than it was measured,
because a camera reading carries error.

**Why this worked so well.** It converts a dangerous answer into a harmless one
instead of letting it through, and that is worth far more here than it sounds,
because of how the scoring treats a broken glass. Losing one glass throws away a
whole table, so refusing a doubtful push protects every other glass on that
table. The borrowed model used exactly as it downloads went from twenty broken
glasses in a walk to none at all through this change alone.

Three further details inside this group each closed a hole that the first version
left open, and each hole is worth knowing because they are easy to leave open
again.

**The shape of the path matters, not only the glasses it passes.** The first
version counted glasses and stopped there, so a path that swept across the whole
table at the height of the glasses' rims passed the check — it reached exactly
one glass, legally — and then tipped that glass over instead of sliding it. A
glass slides when it is shoved low, at its foot, and tips when it is shoved high.
So the rule had to become a rule about shape: across the table high, or across
the table low, and never in between.

**A drawn answer has to be pulled onto those heights rather than refused.** A
solution that computes its answer puts the path at exactly the right height,
because that is the number it worked from. A solution that *draws* its answer
predicts that height and misses it by a centimetre or two. The check was
therefore satisfiable by arithmetic and impossible for a trained model: over
twenty tables, every single push the trained solution asked for was refused. The
repair is to first move each point to the nearer of the two legal heights and
then check again, and it is what produced the first pushes this solution had ever
made.

**The check must also ask where the pushed glass goes, not only where the hand
goes.** A shove that slides its own glass into a neighbour passed every test,
and the glass that broke was one the hand never came near. Interestingly, closing
this hole changed the numbers very little, which told us that driving one glass
into another was not the main way glasses were being lost. A repair is only worth
the size of the hole it closes, and measuring that size is the only way to know.

### Group 2: remember the whole table, not only the current picture

A solution now keeps the newest reading of every glass this table has shown it,
and checks its answer against all of them. Before this it checked against the
glasses inside the current picture.

**Why this was needed.** With the camera on the wrist, one picture holds the
glasses in front of the jaw rather than the glasses on the table. A check given
one picture is being asked about part of the table, and the part left out is
exactly where the damage happens, because a glass that is out of view cannot be
on any list to check against.

**Why it worked best where it did.** The improvement was largest for the
borrowed model, which does not aim at a particular glass — it comes down
somewhere, and the arithmetic afterwards reads back which glass the path came
nearest. A blind shove is the one most likely to drive a glass into something
nobody is looking at. For the solution that does choose a glass deliberately the
gain was small, and its own record says why: the wrist camera usually does see
the whole of a small table, so the memory held only a few glasses the picture did
not.

It is worth adding where this idea came from, because it is a good habit. The
geometry solutions never had this hole: they had always built a belief about the
whole table out of several looks. The trained solutions were built around
answering from one picture, so they held one picture, and they were the
solutions breaking glasses. **When one family of solutions does not have a bug,
look at what it does differently.**

### Group 3: make the model answer the question it can actually answer

This group is about the shape of the learning problem rather than about safety,
and it is what moved the picture-driven solutions from doing nothing to doing
something.

**One model doing two jobs became two models with one job each.** The trained
solution now has a small network that decides *which kind of answer is wanted*
— go and look, test a glass with a tiny shove, push a glass properly, or declare
the table finished — and which glass to act on. A second network then draws only
the kind of answer it was told to draw. This works because the two jobs have
different difficulties: deciding is a choice between four options, where being
right most of the time is achievable, while drawing is a continuous path, where
the average of mixed material is useless. Separating them stops the averaging
described in cause 1 from destroying the decision. Measured on tables it had
never seen, the deciding network gets the kind of answer right about seven times
in ten, where the single model had never once proposed a push.

**Rare answers must be made common during training.** Two matching changes do
this. Training batches for the drawing network are filled evenly from the kinds
of answer rather than in the teacher's own four-to-one proportion, and the
deciding network's training is weighted so that a mistake on a rare kind of
answer costs more. Without that weighting the deciding network learned three of
the four kinds well and **never once said "push"**, which is the correct way to
make the smallest average mistake and completely useless as a decision. The same
reweighting is the only change made to the fine-tuned borrowed model, and it had
the same effect: it stopped drawing paths whose middle sat a quarter of a metre
above the table.

**A decision needs history, not just a picture.** The teacher's real push is the
last step of a short sequence: reach in until the jaw touches, shove five
millimetres to find out whether the glass slides, and only then push it
somewhere. Which step is wanted therefore depends entirely on what has already
been tried on that glass, and a network shown one picture cannot see any of
that. Giving the deciding network two extra numbers for each glass — how many of
its own answers were aimed at that glass, and how far that glass has moved since
it was first measured — improved every part of its output, and most of all its
ability to find the teacher's testing shoves. The lesson generalises: **if the
right answer depends on what you did a moment ago, then a single snapshot is not
enough input, however good the model is.**

### Group 4: make the search and the arithmetic distrustful

The last group is about acting under uncertainty, and it is what fixed the world
model.

**Ask the most pessimistic opinion rather than the average one.** Three copies of
the prediction network are trained from different starting points. Where they
agree, the model has seen pushes like this one; where they disagree, it has not.
Every quantity the search uses is now the least favourable of the three copies
instead of the average, so disagreement *costs* the search something instead of
being something it can exploit. This directly removes cause 2.

**Put a price on risk, not only a limit.** There was already a limit on the
predicted chance of toppling a glass, and a limit alone makes every candidate
under it equally attractive, so the search happily chose the candidate sitting
right at the edge of what was allowed. Adding a price — a push now pays a small
amount of its predicted benefit for each chance in a hundred of putting a glass
over — makes the search prefer the safe middle of the allowed region. Together
these two changes took this solution from eight broken glasses in a walk to one,
while also making it quicker per table, so it reached forty tables instead of
thirty-two inside the same budget, and it now separates more tables than any
other solution in the problem.

**Require evidence before moving a glass.** This one comes from a measurement
nobody had written down. The shared rule that predicts whether a shove slides a
glass or tips it gives three answers: it will slide, it will tip, or it depends
on friction that no camera here can see. Over sixteen hundred glasses generated
the way this problem generates the glasses on its tables, **not one single glass
gets the answer "it will slide"**, about one in six gets "it will tip", and all
the rest get "it depends". A glass would need a foot wider than any this problem
ever puts on a table before sliding were certain. So every glass in this problem is one whose behaviour cannot be
predicted in advance, which is exactly why the teacher tests a glass with a tiny
shove before pushing it. The arithmetic now enforces that discipline: a shove
that would *move* a glass is allowed only at a glass this solution has itself
watched moving, while a shove that merely comes to rest against a glass is
allowed anywhere, because that is how the evidence is gathered.

Two things about this rule are worth copying. The first is that it was checked
against the teacher before being trusted: the teacher's own answers were put
through the rule, and ninety-nine in a hundred came out exactly as they were
given, with none at all refused for want of evidence. **A safety rule that would
refuse the teacher's own answers is a broken rule, and that is a cheap test to
run.** The second is that each solution must be allowed to offer its own kind of
evidence. The rule was written with the testing solutions in mind, and the world
model, which never tests anything because it predicts instead, immediately lost
a third of its separated tables. Its evidence is now written down in its own
terms: the most pessimistic of its three copies must keep the push within the
topple limit its search already applied.

**Let arithmetic finish what the model started.** This is the repair for cause 4,
and it is the one that needs the most honesty in reporting. When a push passes
every check, the solution now continues that same shove along the model's own
line, one small step at a time, and stops at the first of two events: the glass
has the room it needs, or the next step would fail one of the checks. The model
still chooses everything that is hard — whether to act, which glass to act on,
and which direction to shove it — and only the distance is arithmetic. This took
the trained solution from freeing no glasses at all to freeing some, and the
division of labour is stated plainly in the record rather than hidden, because
the alternative would be to claim that the model learned to free glasses, which
it did not.

**Stop at the distance the glass has earned.** The continuation above was later
limited by how far that same glass has already been watched sliding under this
solution's own shoves. A glass that has slid five millimetres has earned a
five-millimetre drive, and one that has slid forty has earned forty. The reason
is that evidence gathered from a five-millimetre test is evidence about a
five-millimetre action, and a sixty-millimetre drive is a different action. On
the tables where it was chosen, this was the first time any version of the
solution walked all twenty tables without losing a glass.

### Group 5: give a model more examples only where its own record asks for them

The four groups above change what a solution is asked to do. This last group
changes only how much material it is fitted on, and it is placed last because it
is the weakest of the five — which is itself a result, since more data is usually
the first thing anyone reaches for.

**A model's two distances say whether it is short of examples.** Every fitted
solution here measures how far its answers sit from its teacher's twice over:
once on tables it was fitted on, and once on tables it has never seen. When the
two distances are close, the model is doing as well on new tables as on old ones,
so it is limited by what it can represent. When the distance on fitted tables is
much the smaller of the two, the model has learned the particular tables rather
than the task, which is called memorising, and memorising is the one fault that
more examples is the right cure for.

**The copying solution had exactly that signature, so its material was tripled.**
Its drawing network sat about nine millimetres from its teacher on fitted tables
and about twenty-four on unseen ones. Collecting from nine hundred tables instead
of three hundred closed that gap from the wrong end, as it should: the error on
fitted tables rose by three millimetres and the error on unseen tables fell by
one. On the tables it halved the broken glasses, from two a walk to one, and
moved nothing else outside its spread. **So the diagnosis was right and the cure
was small**, which together say that what limits this solution is the model and
the task rather than the number of examples.

**The world model's extra pushes only worked with a second change beside them.**
Doubling its random pushes improved its aim and, as a side effect, made its
topple head stop sounding the alarm: with more pushes it flagged fewer safe
pushes, and a fixed caution threshold turns that straight into broken glasses.
Charging the fit ten times as much for a topple it fails to predict put the alarm
back. Neither change is any good alone — more pushes alone breaks glasses, and
the heavier charge on the smaller set refuses so much that it frees thirty-four
fewer glasses — and together they separate about one and a half more tables a
walk and lose about half as many glasses on the tables they were chosen on.
**Two changes that each fail alone and work together are worth remembering**,
because a method that tries changes one at a time will reject both.

## What did not work, and why

A record of only the successes would teach the next person very little, so the
failures are kept with the same care. They fall into a few kinds, and the kinds
are more useful to remember than the individual attempts.

### Making the actions smaller or safer, when the task rewards finishing

Several attempts tried to buy safety by making pushes shorter or more cautious,
and every one of them cost more than it bought.

Charging the world model's search more for each millimetre it pushes, and
separately capping how long a push may be, each saved one glass out of three and
each cost between nine and fifteen separated tables out of a hundred. Putting
the teacher's small test shove in front of every long push cut breakages from
four to one, exactly as hoped, and cut separated tables from seventeen to eight,
because a glass that does not visibly move during the test is then left alone for
the rest of the table. Tightening the allowed chance of toppling cost two
separated tables and saved nothing at all.

Both of those were tried again in a narrower form, on the chance that they
failed only because they were applied to every push. They failed in the same
way. The allowed chance of toppling was tightened at four settings on two
different fits of the world model, from one chance in a hundred down to three in
ten thousand, and the broken glasses went up rather than down. The test shove
was put in front of only those pushes the three copies of the model disagreed
about, which is the smallest set it could sensibly be applied to, and at three
thresholds it cost between one and four separated tables a walk and saved no
glass at all.

**Those two failures share one cause, and it is the most useful thing in this
section.** A threshold can only refuse an answer the model thinks is risky, and
the pushes that actually topple glasses are the ones the model gives almost no
chance of toppling, so there is nothing for a threshold to catch. A test shove
can only report what a small push does, and in this cell a glass goes over under
a *long* push for reasons the tipping rule cannot predict for any glass, so
there is nothing for the test to report. **Neither instrument can see the thing
that is going wrong**, and tightening an instrument that cannot see a fault only
costs work.

**Why this whole family fails.** It is tempting to think that caution is free
because a broken glass is so expensive. It is not free, because **a table left
crowded also scores nothing**, and the share counts every glass still standing on
it. Caution and inaction are scored the same way here, so a change that trades
many unfinished tables for one saved glass is a bad trade even though the
headline risk went down. If you want to be safer without being less useful, the
place to do it is in refusing *specific* unsafe answers, which is group 1, and
not in making all answers smaller.

One attempt in this family failed for a more physical reason, which is worth
keeping. Moving a shove's touchdown point backwards, so that the fingers come
down over bare table rather than near the glass, sounds safer and measured worse:
the further back the hand lands, the longer it ploughs along the table before
reaching the glass, and the longer it ploughs the more it can disturb.

### Asking a model to rank things it was not trained to judge

One solution generates every push that geometry already approves and uses trained
decision trees to put them in order. It never breaks a glass, because every
candidate was already safe, and it is measurably worse at *choosing* than the
printed rule it replaced: with the arm and the clock taken out of the picture
entirely, the printed rule separates thirty-four of fifty tables and the trained
ranker separates twenty-nine, needing more pushes to do it.

The obvious explanation is that the ranker prefers long pushes because it does
not know what a push costs. That explanation was tested at four different prices
per millimetre and is **wrong**: the prices changed nothing. The real reason is
what the trees were trained to answer. They were trained to judge whether a push
would tip a glass, which is a question about risk, and they are being used to
judge whether a push will free a glass, which is a question about gain. A model
asked a question next to the one it was trained on will answer confidently and
badly, and no amount of adjusting the surrounding arithmetic repairs that.

### Letting a model keep asking until something is allowed

The deciding network scores every glass, so it has a full order over them and not
only a favourite. The idea was that when the arithmetic refuses an answer at its
favourite glass, the solution should ask for its next choice and try that, with
the model still choosing and the arithmetic keeping only the power to refuse. It
was built, measured, and removed, because it broke more glasses and lost the one
table that had been separated.

The run's own record explains why it never had much chance. The first choice was
accepted several hundred times in a walk and the later choices only a few dozen
times, so the change touched roughly one answer in twenty — and those were
answers at glasses the network itself had ranked low, where its accuracy at
choosing a glass is barely better than a coin toss. **A refusal is sometimes the
better outcome, and a solution that keeps asking until something is permitted is
choosing by what is permitted rather than by what it believes.**

### Collecting the examples the model is least sure about

The world model is three copies of the same network fitted from different
starting points, and where the three disagree is where the model does not know
what a push will do. That makes an obvious proposal: collect training pushes
there instead of at random. It was built — forty candidate pushes are drawn, and
the one the copies disagree about most is the one carried out — and the pushes it
collects are genuinely the interesting ones, because 17.3 per cent of them put a
glass over against 10.4 per cent of random pushes.

Fitted on them, the model separated the same number of tables and lost two and a
half more glasses. **The reason is that a model cannot learn to refuse from
examples it cannot tell apart.** The pushes the copies disagree about are not
pushes with a visible warning sign in them; they are pushes whose outcome
depends on the friction and the exact contact that no camera here can see. More
of them teaches the topple head that the same-looking situation sometimes ends
badly, which makes it less certain everywhere rather than more accurate
anywhere. The collecting round is kept behind its own switch, and the file it
writes is named so that a fit cannot read it by accident, because the
measurement is worth repeating and the data is not worth training on.

### More training steps, when the copying is already better than the task needs

The fine-tuned borrowed model was fitted for three times as many steps, on three
times the demonstrations, which is the one change its own record had been asking
for. Everything about the *form* of its answers moved towards its teacher: the
distance from the teacher's waypoints halved, the paths came lower and shorter,
and more of them reached the height at which a push works. Nothing about the
table moved. It broke the same two glasses over three walks, its share of
pickable glasses was identical to the third decimal place, and the glasses it
freed went from two to none, which is a change the size of its own spread.

The fit measures its distance from the teacher every five hundred steps, so the
same run also says which half of the change did the work: at the same thousand
steps, three times the demonstrations moved nothing, and the extra steps moved
everything. **So the limit on this solution is not how closely it copies its
teacher.** It is that the teacher's answers are mostly looking, so a close copy
of them is a solution that mostly looks. Copying better cannot fix a target that
is wrong, and this is the sharpest demonstration of cause 1 on this page.

### Two repairs that were impossible rather than merely unhelpful

These two are different in kind, because they could not work at all, and knowing
that saves the next person the attempt.

**A solution cannot diagnose its own broken glasses.** Every camera reading says
whether a glass is standing, so it looks as though a solution could notice a
fallen glass and record the answer it gave just before. That was built, and it
recorded nothing at all during runs that broke eleven glasses between them. The
examiner ends a table the instant a glass goes over, so the look that would show
the damage is never taken. The diagnosis therefore has to live outside the
solution, in the measuring script, which pairs each table's last answer with how
that table ended — and once it lived there, it immediately produced the sharpest
finding on this page.

**Straightening the path did not change the result, and is kept anyway.** Every
remaining topple followed a push that had passed every check about *where* the
path goes, which pointed at the *shape* of the path instead. The arm turns the
hand to each leg's own direction as that leg begins, so a wandering push turns
the hand while the fingers are against the glass, and a glass twisted at its foot
goes over rather than sliding. The teacher's pushes stray from straight by
nothing at all and the student's by a few millimetres with some turning, so the
cause was real and clearly measured. Replacing the driving part of the push with
a straight line changed the outcome by less than the difference between runs. It
is kept because its own measurement is sharp and it makes the student's push the
same shape as the teacher's, and the record says plainly that the numbers did not
move.

### One measurement that was simply wrong

Finally, one piece of evidence behind a failed repair was withdrawn, because
being wrong about a measurement is a distinct kind of failure. It had reported
that nine shoves in ten came down with the hand already over the glass, and it
had asked that question using arithmetic that treats the hand as a long box
reaching back from the fingertips. Asked instead of the fingertips against the
glass's own circle, which is the thing that actually matters, the answer is
different. The rule built on the wrong reading refused every push in the whole
project, including the teacher's own pushes, which is how it was caught. **When
a new rule refuses the teacher, the measurement behind the rule is what is
wrong, not the teacher.**

## What the three rounds of repair came to

Putting the groups together, the outcome divides into four kinds.

**Arithmetic safety was decisive and cheap.** Across the three picture-driven
solutions, broken glasses went from twenty-eight in a walk to one, and the world
model's eight became one. None of this required any retraining, because none of
it was a learning problem.

**Reshaping the learning problem made a trained solution act, and did not make
it good.** The copying solution went from leaving every table exactly as it found
it — not one glass given room it did not start with — to pushing glasses about,
separating two tables in one of its three walks, and ending a queue one glass
down on balance. The fine-tuned borrowed model gives the clearest reading of all,
because it can be compared against the same weights with no training on this task
at all: trained, it moves at the length and speed of its teacher's pushes and
frees glasses the untrained one does not, and it also topples glasses the
untrained one does not. **Fitting bought work, and it did not buy care.**

**The best solution in the problem is now a trained one, and for a specific
reason.** The world model leads because it reaches many more tables inside the
same arm-time budget and separates more of them, and the reason it reaches more
is that it became much quicker per table: a separated table costs it about
twenty-five arm seconds against the geometry reference's forty-four. On the
twenty-six tables the two of them both reach they are level. That is a reminder
that in a problem with one shared budget, speed is part of accuracy.

**The last round bought tables and paid for them in glasses, which is the
clearest trade in the record.** More pushes and a heavier charge for a missed
topple made the world model separate more tables, and it now breaks five glasses
over a queue where the version before it broke one. The two measurements
disagree about whether that was worth it, and the next section explains why they
can disagree at all.

### The instrument has to ask the score's own question

This finding cost two wrong turns, and it changes how every number above was
produced, so it is worth a section of its own.

**A measurement that gives every table as much arm time as it wants asks a
different question from the score.** The score hands fifty tables fifteen arm
minutes between them, so it asks how much a solution finishes before the clock
stops. A measurement with no clock asks only whether a table *can* be separated.
A change that trades time for thoroughness — looking more often, testing before
pushing, pushing in smaller steps — wins the second and loses the first.

**That is exactly what happened.** Two configurations of the world model were
chosen on the unclocked measurement and both came back from the scored queue
with a lower share than the version they replaced. The repair was to build a
clocked queue of fifty tables below the held-out line, walked three times and
pooled over three different starting tables, which is the score's own shape on
tables that may be chosen on. Every choice in the last round was made on that
instrument instead.

**One such queue is still not enough**, because the same model scored 0.647 on
one band of fifty tables and 0.570 on another. This is also why the world model's
kept change looks good below the line and bad on the held-out queue: fifty
tables is a small sample, and a single walk of one band cannot settle a
difference of one or two glasses. The rule the project follows is that choices
are made below the held-out line, so the change was kept and the disagreement
was written down beside it rather than quietly resolved in its favour.

## What is worth trying next, and why

The useful thing about the measurements above is that they do not leave the next
step to taste. Each candidate below has a measured reason behind it, and they are
roughly in order of how much evidence supports them.

**Change the mixture of the demonstrations, not their number.** Simply
collecting three times as many was measured and is reported above: it stopped the
copying solution from memorising and halved its broken glasses, and it moved
nothing else. What it could not change is the *proportion* of the material that
shows a push at a crowded glass, which stayed at about one answer in
thirty-five, because tripling the tables triples the looks as well. The version
of this idea that remains untried is to collect only on crowded tables, so that
pushes are a much larger share of what the model is shown. That is the one thing
reweighting a batch cannot do, since reweighting makes rare examples appear more
often but cannot add information that was never recorded. The honest expectation
is small, because the same solution's deciding network got no better at all on
three times the material.

**Retrain the ranking trees on the question they are being asked.** As explained
above, they judge risk and are used to judge gain. Training them on how much room
a push actually frees, measured by carrying the push out rather than by asking the
tipping rule, turns a mismatched model into a matched one, and that costs nothing
but a new set of labels.

**Average repeated readings of a glass instead of keeping only the newest one.**
The geometry solutions average their readings, which halves the camera's error,
and the trained solutions keep the newest reading. Averaging needs the solution
to say when a glass has been pushed, so that the average starts again from the
glass's new place, and that information is already recorded. The expected gain is small and honestly
stated as such, because the check already treats every glass as slightly larger
than measured.

**Choose the push direction by arithmetic, as the distance already is.** This
would almost certainly help, because the commonest reason a push is now refused
is that the hand would meet a glass it was not aimed at, and the measured
neighbours say which directions are open. It is deliberately not done inside the
copying solution, and the reason is worth understanding rather than treating as
red tape: that solution exists to measure what copying a teacher achieves, and a
version of it that no longer copies the teacher's choice of direction would be
the geometry solution with a trained chooser in front of it. That may well be the
right thing to build, and it should be built as a *new* solution, so that both
questions keep an answer.

**Give the drawing network a longer view of the recent past.** Adding two numbers
of history to the deciding network improved every part of it, which suggests the
same deficiency exists in the network that draws the path, since it also sees
only one picture. Letting it see a short series of recent pictures and actions is
the natural next version of that repair.

## The rules that make this record trustworthy

The last thing to explain is not a change to any solution, but the discipline
that made the comparisons above worth reading. It is short, and it is what a new
developer should carry into the next problem.

**Choose on one set of tables and report on another.** Every decision here was
made on tables numbered below ten thousand, and the fifty tables from ten
thousand upward were used only to report the result. This matters because of what
happened with the last repair on the list of successes: it was clearly better on
the tables it was chosen on, and it came out slightly worse on the final queue,
by an amount that cannot be told apart from the ordinary difference between runs.
It was kept. Reverting it *because* the final queue disagreed would mean choosing
by the final queue, which is the one thing that separation exists to prevent, and
it would quietly weaken every other number on the page. So the change stays, the
queue's verdict is printed beside it, and the summary says that this repair
closed a real cause and bought nothing that can be proved.

**A result without a spread is not a result.** A spread is the range a number
takes across repeated runs, and every number here comes from several runs and
several separately trained copies and is reported with that range. Most of the attempts that were rejected were rejected because the change
they produced was smaller than that range, and most of the mistakes that were
caught were caught because someone compared a single run against a single run.

**Choose on an instrument shaped like the score.** Choosing below the held-out
line is not enough on its own, because a measurement below the line can still
ask a different question from the score. Two choices here were made on a
measurement that gave every table unlimited arm time, and both of them lost on
the clocked queue. The section above explains the repair, and the rule that came
out of it is short: when you build a measurement to choose on, give it the
score's own budget, its own number of tables and its own way of walking them,
and only change which tables it uses.

**Measure the size of the hole before celebrating the repair.** Two of the
successful changes above closed causes that were real, clearly described and
almost irrelevant in practice. Writing that down is more useful than hiding it,
because the next person's time should go to the big holes.

## Where to read more

- [What changed, and what each change bought](what-changed.md) — the same
  changes taken one at a time, each beside the before-and-after measurement that
  justified it, including the nine that were measured and thrown away.
- [The six solutions side by side](../../04-clear-the-table/results/README.md) —
  every column of every result, what perfect play achieves on the same tables,
  and which columns mislead when read alone.
- [The problem](problem.md) and [the examiner](the-examiner.md) — what is on the
  table, what a solution is given and must hand back, and how a walk of tables
  is marked.
- One page for each solution under [solutions](solutions/), where the
  measurements quoted above were taken.
