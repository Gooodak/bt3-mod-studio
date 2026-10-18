"""Test bench: applies a mod pack, runs the game's attract-demo fight and reports what happened.

The demo fight is the same every time (Super Saiyan Goku against Vegeta), so two runs with different packs can be
compared hit by hit. Usage:
    py -I tools/testbench.py <pack.json | -> <out dir> [--shots N] [--from F] [--to T] [--seconds S]
With "-" the game runs without any mod of this tool.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from bt3mod import game, modpack  # noqa: E402


def run(pack_path, out, shots=0, first=None, last=None, seconds=70, seed=None):
    g = game.Game(game.find_gamedata())
    if pack_path == "-":
        g.remove()
    else:
        g.apply(modpack.load(pack_path))
    exe = os.path.join(os.path.dirname(g.root), "Tenkaichi3Decomp.exe")
    os.makedirs(os.path.join(out, "port", "build", "shots"), exist_ok=True)
    env = dict(os.environ, BT3_DATA=g.root, BT3_DEMO="1", BT3_TRACE="10", BT3_NOSOUND="1")
    if seed is not None:
        env["BT3_SEED"] = str(seed)
    if shots:
        env["BT3_SHOT"] = str(shots)
        if first is not None:
            env["BT3_SHOT_FROM"] = str(first)
        if last is not None:
            env["BT3_SHOT_TO"] = str(last)
    with open(os.path.join(out, "out.txt"), "w") as so, open(os.path.join(out, "err.txt"), "w") as se:
        try:
            subprocess.run([exe], cwd=out, env=env, stdout=so, stderr=se, timeout=seconds)
        except subprocess.TimeoutExpired:
            pass
    events, prev = [], None
    for line in open(os.path.join(out, "out.txt")):
        if not line.startswith("vb "):
            continue
        parts = line.split("|")
        vb = int(parts[0].split()[1])
        hp = tuple(int(x) for x in parts[1].split()[1:3])
        if hp != prev:
            events.append((vb, hp))
            prev = hp
    with open(os.path.join(out, "hp.txt"), "w") as f:
        for vb, (a, b) in events:
            f.write(f"{vb} {a} {b}\n")
    return events


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pack")
    ap.add_argument("out")
    ap.add_argument("--shots", type=int, default=0)
    ap.add_argument("--from", dest="first", type=int)
    ap.add_argument("--to", dest="last", type=int)
    ap.add_argument("--seconds", type=int, default=70)
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()
    for vb, (p0, p1) in run(a.pack, a.out, a.shots, a.first, a.last, a.seconds, a.seed)[:30]:
        print(vb, p0, p1)
