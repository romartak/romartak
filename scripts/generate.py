#!/usr/bin/env python3
"""Genera profiles/default/{dark,light}.svg con datos reales de GitHub.

Solo usa la biblioteca estándar. Con GITHUB_TOKEN en el entorno evita límites
de la API; sin red usa valores de respaldo para que el SVG siempre se genere.
"""
import json
import os
import urllib.request
from datetime import datetime, timezone
from html import escape
from pathlib import Path

USER = os.environ.get("PROFILE_USER", "romartak")
OUT = Path(__file__).resolve().parent.parent / "profiles" / "default"
W, PAD = 800, 24
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace"

THEMES = {
    "dark": dict(bg="#060b0f", panel="#0b1319", line="#1d2a33", fg="#e6edf3",
                 dim="#7d8b99", acc="#2dd4bf", acc2="#ffd400"),
    "light": dict(bg="#f6f8fa", panel="#ffffff", line="#d0d7de", fg="#1f2328",
                  dim="#59636e", acc="#0f766e", acc2="#9a6700"),
}

ASCII_NAME = [
    "█▀█ █▀█ █▀▄▀█ ▄▀█ █▀█ ▀█▀ ▄▀█ █▄▀",
    "█▀▄ █▄█ █ ▀ █ █▀█ █▀▄  █  █▀█ █ █",
]


def api(path):
    req = urllib.request.Request(f"https://api.github.com{path}")
    req.add_header("Accept", "application/vnd.github+json")
    if os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def fetch():
    data = dict(name=USER, bio="médico · programador", repos=2, followers=0,
                following=0, stars=0, langs={"Shell": 60, "Python": 30, "JavaScript": 10}, since="2026",
                pinned=("sdrkit", "Analizador de espectro y radio multimodo en una Raspberry Pi Zero 2 W + RTL-SDR."))
    try:
        u = api(f"/users/{USER}")
        data.update(name=u.get("name") or USER, bio=u.get("bio") or data["bio"],
                    repos=u["public_repos"], followers=u["followers"],
                    following=u["following"], since=u["created_at"][:4])
        repos = [r for r in api(f"/users/{USER}/repos?per_page=100&type=owner")
                 if not r["fork"]]
        data["stars"] = sum(r["stargazers_count"] for r in repos)
        for r in repos:
            if r.get("language"):
                data["langs"][r["language"]] = data["langs"].get(r["language"], 0) + r["size"] + 1
        star = max(repos, key=lambda r: r["stargazers_count"], default=None)
        feat = next((r for r in repos if r["name"] == "sdrkit"), star)
        if feat:
            data["pinned"] = (feat["name"], feat.get("description") or "")
    except Exception as e:  # sin red o límite de API: se usan los respaldos
        print(f"aviso: usando datos de respaldo ({e})")
    return data


def wrap(text, n):
    lines, cur = [], ""
    for w in text.split():
        if len(cur) + len(w) + 1 > n:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return lines + [cur] if cur else lines


def render(d, t):
    c, o = t, []
    t_ = lambda x, y, s, size=12, fill=None, anchor="start", weight=400: o.append(
        f'<text x="{x}" y="{y}" font-family="{MONO}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill or c["fg"]}" text-anchor="{anchor}" '
        f'xml:space="preserve">{escape(str(s))}</text>')

    def box(x, y, w, h, label):
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c["panel"]}" '
                 f'stroke="{c["line"]}"/>')
        t_(x + 6, y + 13, "+", 10, c["acc"])
        t_(x + w - 6, y + 13, "+", 10, c["acc"], "end")
        t_(x + 14, y + 26, label, 10, c["dim"])

    y = 0
    # Cabecera
    box(0, y, W, 130, "// ident")
    for i, row in enumerate(ASCII_NAME):
        t_(PAD, y + 56 + i * 20, row, 22, c["acc"], weight=700)
    t_(PAD, y + 104, f"@{USER}", 14, c["acc2"])
    t_(PAD + 110, y + 104, d["bio"], 12, c["dim"])
    t_(W - PAD, y + 56, "🩺 médico", 12, c["fg"], "end")
    t_(W - PAD, y + 76, "💻 programador", 12, c["fg"], "end")
    t_(W - PAD, y + 104, f"[ desde {d['since']} ]", 12, c["dim"], "end")
    y += 146

    # Métricas
    cells = [("repos", d["repos"]), ("estrellas", d["stars"]),
             ("seguidores", d["followers"]), ("siguiendo", d["following"])]
    cw = (W - 3 * 12) / 4
    for i, (lab, val) in enumerate(cells):
        x = i * (cw + 12)
        box(x, y, cw, 84, f"// {lab}")
        t_(x + PAD - 6, y + 66, val, 32, c["acc"], weight=300)
    y += 100

    # Lenguajes + proyecto destacado
    half = (W - 12) / 2
    box(0, y, half, 150, "// lenguajes")
    langs = sorted(d["langs"].items(), key=lambda kv: -kv[1])[:5]
    total = sum(v for _, v in langs) or 1
    if not langs:
        t_(PAD - 6, y + 60, "sin datos aún", 12, c["dim"])
    for i, (name, v) in enumerate(langs):
        ly = y + 52 + i * 20
        pct = v / total
        t_(PAD - 6, ly, name, 11, c["fg"])
        o.append(f'<rect x="{PAD + 90}" y="{ly - 9}" width="150" height="8" fill="{c["line"]}"/>')
        o.append(f'<rect x="{PAD + 90}" y="{ly - 9}" width="{150 * pct:.0f}" height="8" fill="{c["acc"]}"/>')
        t_(half - 14, ly, f"{pct:.0%}", 11, c["dim"], "end")

    x2 = half + 12
    box(x2, y, half, 150, "// proyecto destacado")
    t_(x2 + 18, y + 56, f"▸ {d['pinned'][0]}", 15, c["acc2"], weight=600)
    for i, ln in enumerate(wrap(d["pinned"][1], 44)[:4]):
        t_(x2 + 18, y + 80 + i * 16, ln, 11, c["dim"])
    t_(x2 + 18, y + 140, f"github.com/{USER}/{d['pinned'][0]}", 10, c["acc"])
    y += 166

    # Pulso (ECG)
    box(0, y, W, 70, "// pulso")
    pts, x = [], 20
    while x < W - 40:
        pts += [(x, 50), (x + 30, 50), (x + 38, 44), (x + 46, 50), (x + 62, 50),
                (x + 68, 56), (x + 76, 26), (x + 84, 62), (x + 90, 50)]
        x += 140
    path = " ".join(f"{px},{y + py - 10}" for px, py in pts if px < W - 20)
    o.append(f'<polyline points="{path}" fill="none" stroke="{c["acc"]}" stroke-width="2" '
             f'stroke-linejoin="round" stroke-linecap="round"/>')
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    t_(W - PAD, y + 26, f"actualizado {stamp}", 10, c["dim"], "end")
    y += 70

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{y}" '
            f'viewBox="0 0 {W} {y}" role="img" aria-label="Perfil de {USER}">'
            f'<rect width="{W}" height="{y}" fill="{c["bg"]}"/>' + "".join(o) + "</svg>\n")


if __name__ == "__main__":
    data = fetch()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, theme in THEMES.items():
        (OUT / f"{name}.svg").write_text(render(data, theme), encoding="utf-8")
    print("ok:", OUT)
