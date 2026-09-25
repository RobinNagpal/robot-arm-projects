# Problem 2 — the learned way

Several glasses of one kind on the table. Find each one from above, choose
where to photograph it from the side, and read its profile from that picture.
Here a small model does each of the three jobs. Each model is trained on 200
pictures, which takes about a minute on a laptop.

## The workflow

```
1. overhead depth picture ──TopNet──▶ each glass: where it stands, how wide
2. 24 places round each glass ──geometry veto──▶ allowed places ──Ranker──▶ best first
3. side depth picture from the best place ──SideNet──▶ height, and width at 16 heights
```

**Training.** `train.py` draws 200 scenes. Each gives one picture from
above and one side picture of one glass. The simulator knows the answers:
which glass each pixel shows, each glass's true shape, and whether the side
picture was spoiled. The models learn from those.

**1. Find — TopNet**, a small convolutional network.
- In: the depth picture from above.
- Out, for every pixel: is it glass, and which way is the middle of its glass.
- Each glass pixel casts a vote where it points. Where 30 or more votes land
  together, that is one glass. Two glasses that overlap in the picture still
  vote for two different middles, so they come apart.
- The pixels that voted for a middle give the glass's place on the table and
  its width.

**2. Choose a place — geometry, then the Ranker**, a small MLP.
- Try 24 places in a circle round the glass.
- Geometry throws out places the arm cannot reach, and places with another
  glass squarely in the way.
- The Ranker scores each place that is left: the chance the side picture
  will be clean. It is given 7 numbers about the place, such as the reach and
  the gap to the nearest glass in front and behind. It cannot be given a
  picture, because there is none until the arm goes there.
- Take the best place. If it scores under 0.5, hand the glass to problem 3.
  Because the ranker only orders places geometry allowed, a bad ranking
  wastes a look but never makes an unsafe move.

**3. Measure — SideNet**, a small convolutional network.
- In: the side depth picture from the chosen place.
- Out: the glass's height, and its width at 16 evenly spaced heights.
- One picture, no retry, and nothing checks that the picture was good.

## Running it

```
make train      # 200 scenes, all three models, about a minute
make run        # the 50 held-out scenes; writes results.json
make test
```

## Results — 50 held-out scenes, 250 glasses

| Step | Result |
|---|---|
| Find | 250 found, 0 missed, merged or split. Position 0.4 mm median, 1.3 mm worst |
| Choose | best-ranked place unspoiled 232 of 245; a random allowed place 219 of 245. 5 handed over |
| Measure | height 5.4 mm median, 36 mm worst; width 2.4 mm median |

SideNet's worst errors all read the tallest stemmed glasses short. That is
regression to the mean from 200 examples.

The scenes, the renderer and the scoring are in `../problem-2-sim`, shared with
`../problem-2-programmed`, so both approaches are tested on the same pictures.
