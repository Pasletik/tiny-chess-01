# tiny-chess-01

Chess engine in 4 KB of Python — entry for the make.fun tiny-chess-01 bounty.

- `main.py` — the engine (3,802 bytes, stdlib only): negamax alpha-beta + quiescence, transposition table with bounds, null-move pruning, LMR, killer moves, iterative deepening 1-6 under a fixed 26,000-node budget per move, deterministic, no clock. Packed with minify + lzma + base85.
- `LICENSE` — MIT.

Run: `python3 main.py` (reads the harness env protocol).
