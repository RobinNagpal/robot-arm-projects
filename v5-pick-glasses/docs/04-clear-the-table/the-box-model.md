# The box model

MoveIt can only plan round things it has been told about, so before any push someone has
to say where each glass stands and how much room it takes. This page explains job 0: a
network that reads a wrist picture and draws a box round every glass in it. By the end you
will know what the network returns, how it finds a glass's position, and how accurate its
boxes are.

## What a box is

A box is an upright box centred on a glass. It is as wide as the glass is at its widest
point, and as tall as the glass. The network also returns the radius of the glass's foot,
because whether a glass tips depends on how wide its foot is.

A box is wider than the glass is where the hand touches it, because glasses narrow towards
the base or the stem. This is on purpose. A box that is too big only makes MoveIt keep more
distance, while a box that is too small would let MoveIt plan a path through a glass.

## How the network works

The network is a small detector in the style of CenterNet. It divides the picture into a
grid of small cells. For each cell it says how likely it is that the foot of a glass stands
there, exactly where inside the cell, and the glass's radius, height and foot radius. Each
peak in the first map is one glass.

The network does not learn where a glass is on the table. It finds the pixel of the glass's
foot, and geometry turns that pixel into a point on the table, by following the camera's ray
down until it meets the table top. So the network never has to learn how the camera is
placed. It only learns to recognise glasses and judge their size.

One network serves both viewing places. Two extra input planes tell it which way the camera
is pointing.

## How it was trained

The simulator knows every glass, so it provides the correct answers for training. A glass
is labelled only when at least half of it is visible. The network never sees these answers
when it runs; it sees only the picture.

It was trained on 1,600 pictures of 400 tables and tested on 400 pictures of 100 other
tables. Each training table was photographed once as drawn and once with its glasses scattered
at random, because later in a run the glasses are no longer where they started.

## How accurate it is

| On 400 pictures it was not trained on | |
|---|---|
| Glasses found | 91.7 % |
| Boxes that really were a glass | 92.9 % |
| Position, typical error | 1.2 mm (90 % within 5.0 mm) |
| Radius, typical error | 1.3 mm (90 % within 4.2 mm) |
| Foot radius, typical error | 0.8 mm (90 % within 3.6 mm) |
| Height, typical error | 4.7 mm (90 % within 16.7 mm) |

Height is the least accurate, and it matters least, because the hand travels well above
the tallest glass. A glass that is more than half hidden is not found from that place, which
is why the arm looks from two places and joins the two lists of boxes.

The box model is not what limits the results. The world model scored about the same with
the simulator's exact boxes (+7, no glass broken) as with this network's boxes (+9, two
broken).
