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

| Step | Model | In | Out |
|---|---|---|---|
| 1. Find | **TopNet**, a small convolutional network | overhead depth | per pixel: glass or not, and the way to its glass's middle. Pixels voting for the same middle are one glass. |
| 2. Choose a place | geometry veto, then **Ranker**, a small MLP | 7 numbers about one place: reach, gap to the glass in front, gap to the glass behind, … | chance the side picture is unspoiled |
| 3. Measure | **SideNet**, a small convolutional network | side depth | height, and width at 16 fractions of it |

The veto drops places out of reach or with a glass squarely in the way. The
ranker only orders the rest, so a bad ranking costs a wasted look, never an
unsafe move. A glass whose best place scores under 0.5 is handed to
problem 3.

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
