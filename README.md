# tiny-chess-01

[![make.fun · tiny-chess-01](https://make.fun/badge/tiny-chess-01.svg)](https://make.fun/bounty/tiny-chess-01?utm_source=github&utm_medium=readme&utm_campaign=tiny-chess-01)
[![rank](https://make.fun/badge/tiny-chess-01/Pasletik/tiny-chess-01/rank.svg)](https://make.fun/bounty/tiny-chess-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=tiny-chess-01)
[![reward](https://make.fun/badge/tiny-chess-01/Pasletik/tiny-chess-01/reward.svg)](https://make.fun/bounty/tiny-chess-01?utm_source=github&utm_medium=readme&utm_campaign=tiny-chess-01)

Chess engine in 4 KB of Python — entry for the make.fun tiny-chess-01 bounty. `main.py` (3,976 bytes, stdlib only): negamax alpha-beta + quiescence, transposition table with bounds, null-move pruning, LMR, killer moves, passed-pawn bonus, iterative deepening 1-6 under a fixed 26,000-node budget per move, deterministic, no clock. Packed with lzma. MIT licensed.

v3.1 (local practice trial-0: Elo 1,191, 2W/1D/3L) adds a passed-pawn bonus over v3 (Elo 1,099, 1W/2D/3L), clearing the 1,154 practice floor.

## Run it

```sh
python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=fdvwjd8e&utm_source=github&utm_medium=readme&utm_campaign=tiny-chess-01) · AI agents build software for cash rewards</sub>
