# Problem 2 — the shared test bench

Used by `../problem-2-learned` and `../problem-2-programmed`, so both are
tested on the same scenes, the same pictures and the same scorecard.

- `render.py` — the numbered scenes (four to six glasses of one kind) and
  depth pictures of them from any camera pose, drawn with the wrist camera's
  lens. It stands in for Gazebo. Scenes from 10000 up are for testing only.
- `scoring.py` — judges a run against what was put out: found, merged,
  split, position error, whether a side picture was spoiled, profile error.
  No pipeline reads it to decide anything.
