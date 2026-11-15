# tiny-chess-01 engine draft v1 (dev version, readable).
# 0x88 board, negamax alpha-beta + quiescence + transposition table,
# iterative deepening to depth 4 under a fixed node budget (deterministic:
# no clock anywhere). Root moves come from the env's legal_moves list, so
# legality at the root is guaranteed by the env even if search move-gen
# had a subtle bug; internal move-gen is still perft-tested (see test file).
# Entry rules: main.py <= 4096 bytes, stdlib only. This dev file is packed
# (minify + lzma) into main.py by pack.py; the packed form is what ships.
import json
import os
import sys
import urllib.error
import urllib.request

ENV_URL = os.environ.get("MAKEFUN_ENV_URL") or sys.exit("MAKEFUN_ENV_URL is not set")

VAL = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 0}
# Piece-square tables, rank 8 first (Tomasz Michniewski's simplified set).
PST = {
    "P": [0, 0, 0, 0, 0, 0, 0, 0, 50, 50, 50, 50, 50, 50, 50, 50,
          10, 10, 20, 30, 30, 20, 10, 10, 5, 5, 10, 25, 25, 10, 5, 5,
          0, 0, 0, 20, 20, 0, 0, 0, 5, -5, -10, 0, 0, -10, -5, 5,
          5, 10, 10, -20, -20, 10, 10, 5, 0, 0, 0, 0, 0, 0, 0, 0],
    "N": [-50, -40, -30, -30, -30, -30, -40, -50, -40, -20, 0, 0, 0, 0, -20, -40,
          -30, 0, 10, 15, 15, 10, 0, -30, -30, 5, 15, 20, 20, 15, 5, -30,
          -30, 0, 15, 20, 20, 15, 0, -30, -30, 5, 10, 15, 15, 10, 5, -30,
          -40, -20, 0, 5, 5, 0, -20, -40, -50, -40, -30, -30, -30, -30, -40, -50],
    "B": [-20, -10, -10, -10, -10, -10, -10, -20, -10, 0, 0, 0, 0, 0, 0, -10,
          -10, 0, 5, 10, 10, 5, 0, -10, -10, 5, 5, 10, 10, 5, 5, -10,
          -10, 0, 10, 10, 10, 10, 0, -10, -10, 10, 10, 10, 10, 10, 10, -10,
          -10, 5, 0, 0, 0, 0, 5, -10, -20, -10, -10, -10, -10, -10, -10, -20],
    "R": [0, 0, 0, 0, 0, 0, 0, 0, 5, 10, 10, 10, 10, 10, 10, 5,
          -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5,
          -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5,
          -5, 0, 0, 0, 0, 0, 0, -5, 0, 0, 0, 5, 5, 0, 0, 0],
    "Q": [-20, -10, -10, -5, -5, -10, -10, -20, -10, 0, 0, 0, 0, 0, 0, -10,
          -10, 0, 5, 5, 5, 5, 0, -10, -5, 0, 5, 5, 5, 5, 0, -5,
          0, 0, 5, 5, 5, 5, 0, -5, -10, 5, 5, 5, 5, 5, 0, -10,
          -10, 0, 5, 0, 0, 0, 0, -10, -20, -10, -10, -5, -5, -10, -10, -20],
    "K": [-30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30,
          -30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30,
          -20, -30, -30, -40, -40, -30, -30, -20, -10, -20, -20, -20, -20, -20, -20, -10,
          20, 20, 0, 0, 0, 0, 20, 20, 20, 30, 10, 0, 0, 10, 30, 20],
}
KNIGHT_D = (-33, -31, -18, -14, 14, 18, 31, 33)
KING_D = (-17, -16, -15, -1, 1, 15, 16, 17)
BISHOP_D = (-17, -15, 15, 17)
ROOK_D = (-16, -1, 1, 16)
MATE = 100000
NODES = 30000  # fixed node budget per move, shared across depths (deterministic, no clock)


def sq_name(sq):
    return "abcdefgh"[sq & 7] + str((sq >> 4) + 1)


def sq_from_name(name):
    return ("abcdefgh".index(name[0])) + (int(name[1]) - 1) * 16


def parse_fen(fen):
    """Return (board, white_to_move, castling, ep_sq). Board is a 128-list."""
    parts = fen.split()
    board = [" "] * 128
    rank, file = 7, 0
    for c in parts[0]:
        if c == "/":
            rank -= 1
            file = 0
        elif c.isdigit():
            file += int(c)
        else:
            board[rank * 16 + file] = c
            file += 1
    for i in range(128):
        if board[i] == " ":
            board[i] = "." if not (i & 0x88) else " "
    ep = -1
    if len(parts) > 3 and parts[3] != "-":
        ep = sq_from_name(parts[3])
    return board, parts[1] == "w", parts[2] if len(parts) > 2 else "", ep


def pst_index(piece, sq):
    r, f = sq >> 4, sq & 7
    return (7 - r) * 8 + f if piece.isupper() else r * 8 + f


def evaluate(board):
    s = 0
    for sq in range(128):
        if sq & 0x88:
            continue
        p = board[sq]
        if p == ".":
            continue
        v = VAL[p.upper()] + PST[p.upper()][pst_index(p, sq)]
        s += v if p.isupper() else -v
    return s


def is_attacked(board, sq, by_white):
    # Pawns: a white pawn attacks from sq-15/sq-17; black from sq+15/sq+17.
    for d in ((-15, -17) if by_white else (15, 17)):
        t = sq + d
        if not (t & 0x88) and board[t] == ("P" if by_white else "p"):
            return True
    for d in KNIGHT_D:
        t = sq + d
        if not (t & 0x88) and board[t] == ("N" if by_white else "n"):
            return True
    for d in KING_D:
        t = sq + d
        if not (t & 0x88) and board[t] == ("K" if by_white else "k"):
            return True
    for d in BISHOP_D:
        t = sq + d
        while not (t & 0x88):
            p = board[t]
            if p != ".":
                if p == ("B" if by_white else "b") or p == ("Q" if by_white else "q"):
                    return True
                break
            t += d
    for d in ROOK_D:
        t = sq + d
        while not (t & 0x88):
            p = board[t]
            if p != ".":
                if p == ("R" if by_white else "r") or p == ("Q" if by_white else "q"):
                    return True
                break
            t += d
    return False


def king_sq(board, white):
    k = "K" if white else "k"
    for sq in range(128):
        if not (sq & 0x88) and board[sq] == k:
            return sq
    return -1


def gen_pseudo(board, white, castling, ep):
    """Pseudo-legal moves as (from, to, promo) with promo '' or 'qrnb' (lower)."""
    moves = []
    us = "PNBRQK" if white else "pnbrqk"
    them = "pnbrqk" if white else "PNBRQK"
    direction = 16 if white else -16
    start_rank = 1 if white else 6
    promo_rank = 7 if white else 0
    for sq in range(128):
        if sq & 0x88:
            continue
        p = board[sq]
        if p not in us:
            continue
        up = p.upper()
        if up == "P":
            one = sq + direction
            if board[one] == ".":
                if (one >> 4) == promo_rank:
                    for pr in "qrbn":
                        moves.append((sq, one, pr))
                else:
                    moves.append((sq, one, ""))
                    if (sq >> 4) == start_rank:
                        two = sq + direction * 2
                        if board[two] == ".":
                            moves.append((sq, two, ""))
            for d in (direction - 1, direction + 1):
                t = sq + d
                if t & 0x88:
                    continue
                if board[t] in them:
                    if (t >> 4) == promo_rank:
                        for pr in "qrbn":
                            moves.append((sq, t, pr))
                    else:
                        moves.append((sq, t, ""))
                elif t == ep:
                    moves.append((sq, t, ""))
        elif up in "NK":
            dirs = KNIGHT_D if up == "N" else KING_D
            for d in dirs:
                t = sq + d
                if t & 0x88:
                    continue
                if board[t] == "." or board[t] in them:
                    moves.append((sq, t, ""))
        else:
            dirs = BISHOP_D if up == "B" else ROOK_D if up == "R" else KING_D
            for d in dirs:
                t = sq + d
                while not (t & 0x88):
                    if board[t] == ".":
                        moves.append((sq, t, ""))
                    elif board[t] in them:
                        moves.append((sq, t, ""))
                        break
                    else:
                        break
                    t += d
    # Castling (king moves two squares; rook move handled in make_move).
    if white:
        if "K" in castling and board[5] == "." and board[6] == "." and board[7] == "R":
            if not is_attacked(board, 4, False) and not is_attacked(board, 5, False) and not is_attacked(board, 6, False):
                moves.append((4, 6, ""))
        if "Q" in castling and board[3] == "." and board[2] == "." and board[1] == "." and board[0] == "R":
            if not is_attacked(board, 4, False) and not is_attacked(board, 3, False) and not is_attacked(board, 2, False):
                moves.append((4, 2, ""))
    else:
        if "k" in castling and board[117] == "." and board[118] == "." and board[119] == "r":
            if not is_attacked(board, 116, True) and not is_attacked(board, 117, True) and not is_attacked(board, 118, True):
                moves.append((116, 118, ""))
        if "q" in castling and board[115] == "." and board[114] == "." and board[113] == "." and board[112] == "r":
            if not is_attacked(board, 116, True) and not is_attacked(board, 115, True) and not is_attacked(board, 114, True):
                moves.append((116, 114, ""))
    return moves


def make_move(board, white, castling, ep, move):
    """Return new (board, white_to_move, castling, ep) after a pseudo-legal move."""
    f, t, promo = move
    nb = board[:]
    p = nb[f]
    nb[f] = "."
    if t == ep and p.upper() == "P":
        nb[t + (-16 if white else 16)] = "."
    nb[t] = (promo.upper() if white else promo) if promo else p
    if p.upper() == "K" and abs(t - f) == 2:  # castling: move the rook too
        if t > f:
            nb[t - 1], nb[t + 1] = nb[t + 1], "."
        else:
            nb[t + 1], nb[t - 2] = nb[t - 2], "."
    new_ep = -1
    if p.upper() == "P" and abs(t - f) == 32:
        new_ep = (f + t) // 2
    nc = castling
    if f == 4 or t == 4:
        nc = nc.replace("K", "").replace("Q", "")
    if f == 116 or t == 116:
        nc = nc.replace("k", "").replace("q", "")
    if f == 7 or t == 7:
        nc = nc.replace("K", "")
    if f == 0 or t == 0:
        nc = nc.replace("Q", "")
    if f == 119 or t == 119:
        nc = nc.replace("k", "")
    if f == 112 or t == 112:
        nc = nc.replace("q", "")
    return nb, not white, nc, new_ep


def gen_legal(board, white, castling, ep):
    out = []
    for m in gen_pseudo(board, white, castling, ep):
        nb, nw, nc, ne = make_move(board, white, castling, ep, m)
        if not is_attacked(nb, king_sq(nb, white), not white):
            out.append((m, (nb, nw, nc, ne)))
    return out


class Abort(Exception):
    pass


TT = {}
NODES_USED = [0]


def order(moves_with_pos, board, tt_move):
    def score(item):
        (f, t, promo), _ = item
        s = 0
        if tt_move and (f, t, promo) == tt_move:
            s += 10000
        victim = board[t]
        if victim != ".":
            s += 10 * VAL[victim.upper()] - VAL[board[f].upper()] // 10
        if promo:
            s += 900
        return -s

    moves_with_pos.sort(key=score)
    return moves_with_pos


def quiesce(board, white, castling, ep, alpha, beta, ply):
    NODES_USED[0] += 1
    if NODES_USED[0] > NODES:
        raise Abort
    stand = evaluate(board) * (1 if white else -1)
    if stand >= beta:
        return beta
    if stand > alpha:
        alpha = stand
    if ply > 12:
        return alpha
    moves = [it for it in gen_legal(board, white, castling, ep)
             if board[it[0][1]] != "." or it[0][2]]
    order(moves, board, None)
    for _, pos in moves:
        sc = -quiesce(pos[0], pos[1], pos[2], pos[3], -beta, -alpha, ply + 1)
        if sc >= beta:
            return beta
        if sc > alpha:
            alpha = sc
    return alpha


def search(board, white, castling, ep, depth, alpha, beta, ply):
    NODES_USED[0] += 1
    if NODES_USED[0] > NODES:
        raise Abort
    if depth <= 0:
        return quiesce(board, white, castling, ep, alpha, beta, ply)
    key = ("".join(board), white, castling, ep, depth)
    tt = TT.get(key)
    tt_move = tt[2] if tt else None
    if tt and tt[1] == "exact":
        return tt[0]
    moves = order(gen_legal(board, white, castling, ep), board, tt_move)
    if not moves:
        if is_attacked(board, king_sq(board, white), not white):
            return -MATE + ply
        return 0
    best = -MATE
    best_move = None
    for m, pos in moves:
        sc = -search(pos[0], pos[1], pos[2], pos[3], depth - 1, -beta, -alpha, ply + 1)
        if sc > best:
            best, best_move = sc, m
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break
    if alpha < beta:
        TT[key] = (best, "exact", best_move)
    return best


def move_to_uci(move):
    f, t, promo = move
    return sq_name(f) + sq_name(t) + promo


def uci_to_move(uci):
    f = sq_from_name(uci[:2])
    t = sq_from_name(uci[2:4])
    return (f, t, uci[4:5])


def choose(fen, legal_uci):
    """Best move (UCI) from the env's legal list, iterative deepening 1..4."""
    global TT
    TT = {}
    board, white, castling, ep = parse_fen(fen)
    root = {}
    for u in legal_uci:
        root[uci_to_move(u)] = u
    # Score root moves in the order of the previous iteration (best first).
    ordered = list(root.keys())
    best_uci = legal_uci[0]
    NODES_USED[0] = 0  # one budget for the whole move, shared by all depths
    for depth in (1, 2, 3, 4):
        try:
            scored = []
            alpha = -MATE
            for m in ordered:
                nb, nw, nc, ne = make_move(board, white, castling, ep, m)
                sc = -search(nb, nw, nc, ne, depth - 1, -MATE, -alpha, 1)
                scored.append((sc, m))
                if sc > alpha:
                    alpha = sc
            scored.sort(key=lambda x: -x[0])
            ordered = [m for _, m in scored]
            best_uci = root[ordered[0]]
        except Abort:
            break  # keep the last completed depth's best move
    return best_uci


def post(path, body):
    req = urllib.request.Request(
        ENV_URL + path,
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as res:
            return json.load(res)
    except urllib.error.HTTPError as e:
        sys.exit(f"{path}: HTTP {e.code} {e.read().decode(errors='replace')}")


while True:
    g = post("/game", {})
    if g["status"] == "done":
        break
    while g["status"] == "your_move":
        g = post("/move", {"game": g["game"], "move": choose(g["fen"], g["legal_moves"])})
    print(f"game {g.get('game')}: {g.get('outcome')} by {g.get('reason')}", file=sys.stderr)
    if g["status"] == "done":
        break
print(f"done: {g.get('wins')} won, {g.get('draws')} drawn, {g.get('losses')} lost", file=sys.stderr)
