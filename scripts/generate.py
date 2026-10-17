#!/usr/bin/env python3
"""Genera profiles/default/{dark,light}.svg con datos reales de GitHub.

Solo usa la biblioteca estándar. Con GITHUB_TOKEN en el entorno evita límites
de la API; sin red usa valores de respaldo para que el SVG siempre se genere.
"""
import hashlib
import json
import re
import os
import urllib.request
from datetime import datetime, timezone
from html import escape
from pathlib import Path

USER = os.environ.get("PROFILE_USER", "romartak")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "profiles" / "default"
RAMP = " .:-=+*#%@"
BG_PATTERN = "0 1 . 0 1 : 1 0 . 1 0 "
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


BEAT = [(0, 0), (22, 0), (28, -7), (34, 0), (50, 0), (54, 5), (60, -40), (66, 18),
        (72, 0), (90, 0), (101, -11), (112, 0), (150, 0)]   # P-QRS-T


def ecg_path(x0, x1, base, amp=1.0):
    """Trazado ECG realista (ondas P, QRS y T) repetido entre x0 y x1."""
    pts, x = [], x0
    while x < x1:
        pts += [(x + bx, base + by * amp) for bx, by in BEAT]
        x += 150
    return "M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in pts if px <= x1)


STYLE = """<style>
.draw{stroke-dasharray:1000;stroke-dashoffset:1000;animation:draw 4s linear infinite}
@keyframes draw{0%{stroke-dashoffset:1000;opacity:1}75%{stroke-dashoffset:0;opacity:1}92%{stroke-dashoffset:0;opacity:0}100%{stroke-dashoffset:1000;opacity:0}}
.cur{animation:blink 1s steps(1) infinite}
@keyframes blink{50%{opacity:0}}
.glow{filter:url(#glow)}
</style>
<defs><filter id="glow" x="-5%" y="-50%" width="110%" height="200%"><feGaussianBlur stdDeviation="2.2" result="b"/>
<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<linearGradient id="name" x1="0" x2="1"><stop offset="0" stop-color="__A__"/><stop offset="1" stop-color="__B__"/></linearGradient></defs>"""


def api(path, with_headers=False):
    req = urllib.request.Request(f"https://api.github.com{path}")
    req.add_header("Accept", "application/vnd.github+json")
    if os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    with urllib.request.urlopen(req, timeout=20) as r:
        body = json.load(r)
        return (body, dict(r.headers)) if with_headers else body


def commit_count(repo):
    """Número de commits de la rama principal (usa la cabecera Link de la paginación)."""
    body, headers = api(f"/repos/{USER}/{repo}/commits?per_page=1", with_headers=True)
    m = re.search(r'page=(\d+)>; rel="last"', headers.get("Link", ""))
    return int(m.group(1)) if m else len(body)


def fetch():
    data = dict(name=USER, bio="médico · vibe coder", repos=2, followers=0,
                commits=17, stars=0, langs={"Shell": 60, "Python": 30, "JavaScript": 10}, since="2026",
                pinned=("sdrkit", "Analizador de espectro y radio multimodo en una Raspberry Pi Zero 2 W + RTL-SDR."))
    try:
        u = api(f"/users/{USER}")
        data.update(name=u.get("name") or USER, repos=u["public_repos"], followers=u["followers"],
                    since=u["created_at"][:4])
        repos = [r for r in api(f"/users/{USER}/repos?per_page=100&type=owner")
                 if not r["fork"]]
        data["stars"] = sum(r["stargazers_count"] for r in repos)
        langs, commits = {}, 0
        for r in repos:
            for name, size in api(f"/repos/{USER}/{r['name']}/languages").items():
                langs[name] = langs.get(name, 0) + size
            commits += commit_count(r["name"])
        if langs:
            data["langs"] = langs
        data["commits"] = commits
        star = max(repos, key=lambda r: r["stargazers_count"], default=None)
        feat = next((r for r in repos if r["name"] == "sdrkit"), star)
        if feat:
            data["pinned"] = (feat["name"], feat.get("description") or "")
    except Exception as e:  # sin red o límite de API: se usan los respaldos
        if os.environ.get("GITHUB_ACTIONS"):   # en el Action no se publican datos inventados
            raise SystemExit(f"error leyendo la API de GitHub: {e}")
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


def ascii_avatar():
    """Lee assets/avatar.txt (rampa vacío→denso; "~" = fondo)."""
    return (ROOT / "assets" / "avatar.txt").read_text(encoding="utf-8").splitlines()


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
    AW, GAP = 268, 12                      # avatar a la izquierda
    RX, RW = AW + GAP, W - AW - GAP        # columna derecha
    avatar = ascii_avatar()
    LH = 6.9
    ah = int(40 + len(avatar) * LH + 8)
    mh = (ah - 130 - 16 - 12) // 2
    # el avatar va siempre sobre panel oscuro, también en el tema claro
    o.append(f'<rect x="0" y="0" width="{AW}" height="{ah}" fill="{THEMES["dark"]["bg"]}" stroke="{c["line"]}"/>')
    t_(14, 26, "// avatar", 10, THEMES["dark"]["dim"])
    # "~" marca el fondo: se rellena con un patrón tenue de dígitos y puntos (estilo terminal)
    bg = ["".join(BG_PATTERN[(i * 7 + j * 13 + (i * j) % 5) % len(BG_PATTERN)] if ch == "~" else " "
                  for j, ch in enumerate(r)) for i, r in enumerate(avatar)]
    fg = [r.replace("~", " ") for r in avatar]
    for rows_, color, op in ((bg, THEMES["dark"]["acc"], 0.22), (fg, THEMES["dark"]["acc"], 1)):
        o.append(f'<text font-family="{MONO}" font-size="6.7" fill="{color}" fill-opacity="{op}" xml:space="preserve">'
                 + "".join(f'<tspan x="{(AW - 62 * 4.02) / 2:.1f}" y="{y + 40 + i * LH:.1f}">{escape(r)}</tspan>'
                           for i, r in enumerate(rows_)) + "</text>")

    # Cabecera
    box(RX, y, RW, 130, "// ident")
    o.append(f'<text x="{RX + 18}" y="{y + 70}" font-family="{MONO}" font-size="46" font-weight="800" '
             f'letter-spacing="3" fill="url(#name)" class="glow">ROMARTAK</text>')
    o.append(f'<rect class="cur" x="{RX + 18 + 8 * 30.6 + 8:.0f}" y="{y + 36}" width="16" height="36" fill="{c["acc2"]}"/>')
    t_(RX + 18, y + 104, f"@{USER}", 14, c["acc2"])
    t_(RX + 18 + 110, y + 104, d["bio"], 12, c["dim"])
    t_(W - 18, y + 26, f"[ desde {d['since']} ]", 10, c["dim"], "end")
    y += 146

    # Métricas (2x2)
    cells = [("repos", d["repos"]), ("estrellas", d["stars"]),
             ("commits", d["commits"]), ("seguidores", d["followers"])]
    cw = (RW - 12) / 2
    for i, (lab, val) in enumerate(cells):
        x, yy = RX + (i % 2) * (cw + 12), y + (i // 2) * (mh + 12)
        box(x, yy, cw, mh, f"// {lab}")
        t_(x + 18, yy + mh - 18, val, 34, c["acc"], weight=300)
    y = ah + 16

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
    desc = wrap(d["pinned"][1], 46)
    if len(desc) > 3:
        desc = desc[:3]
        desc[2] = desc[2][:43].rstrip(" ,.") + "…"
    for i, ln in enumerate(desc):
        t_(x2 + 18, y + 80 + i * 16, ln, 11, c["dim"])
    t_(x2 + 18, y + 140, f"github.com/{USER}/{d['pinned'][0]}", 10, c["acc"])
    y += 166

    # Pulso (ECG): papel milimetrado + trazo animado con brillo
    PH = 96
    box(0, y, W, PH, "// pulso")
    for gx in range(0, W + 1, 20):
        o.append(f'<line x1="{gx}" y1="{y + 30}" x2="{gx}" y2="{y + PH}" stroke="{c["line"]}" stroke-width="0.5"/>')
    for gy in range(30, PH + 1, 20):
        o.append(f'<line x1="0" y1="{y + gy}" x2="{W}" y2="{y + gy}" stroke="{c["line"]}" stroke-width="0.5"/>')
    d_ = ecg_path(10, W - 10, y + 70, 0.9)
    o.append(f'<path d="{d_}" pathLength="1000" fill="none" stroke="{c["line"]}" stroke-width="2"/>')
    o.append(f'<path class="draw glow" d="{d_}" pathLength="1000" fill="none" stroke="{c["acc"]}" '
             f'stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>')
    t_(W - 24, y + 14, "72 bpm", 10, c["acc2"], "end")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    t_(100, y + 26, f"actualizado {stamp}", 10, c["dim"])
    y += PH

    head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{y}" '
            f'viewBox="0 0 {W} {y}" role="img" aria-label="Perfil de {USER}">')
    style = STYLE.replace("__A__", c["acc"]).replace("__B__", c["acc2"])
    return head + style + f'<rect width="{W}" height="{y}" fill="{c["bg"]}"/>' + "".join(o) + "</svg>\n"


def banner():
    """banner.svg animado: nombre con degradado, ECG que se dibuja y frases que rotan."""
    a, b = THEMES["dark"]["acc"], THEMES["dark"]["acc2"]
    phrases = ["médico en formación", "vibe coder", "construyendo SDR-Kit", "ideas → herramientas"]
    n, per = len(phrases), 3.0
    css = "".join(
        f".p{i}{{opacity:0;animation:ph{i} {n * per}s infinite}}"
        f"@keyframes ph{i}{{0%{{opacity:0}}{100 * i / n:.1f}%{{opacity:0}}{100 * i / n + 2:.1f}%{{opacity:1}}"
        f"{100 * (i + 1) / n - 3:.1f}%{{opacity:1}}{100 * (i + 1) / n - 1:.1f}%{{opacity:0}}100%{{opacity:0}}}}"
        for i in range(n))
    texts = "".join(
        f'<text class="p{i}" x="500" y="196" text-anchor="middle" font-family="{MONO}" font-size="22" fill="#9fb3c8">'
        f'<tspan fill="{a}">&gt;</tspan> {escape(ph)}</text>' for i, ph in enumerate(phrases))
    grid = "".join(f'<line x1="{x}" y1="0" x2="{x}" y2="300" />' for x in range(0, 1001, 25)) + \
           "".join(f'<line x1="0" y1="{y}" x2="1000" y2="{y}" />' for y in range(0, 301, 25))
    ecg = ecg_path(0, 1000, 258, 1.1)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 300" role="img" aria-label="romartak — médico y vibe coder">
<style>
.draw{{stroke-dasharray:1000;stroke-dashoffset:1000;animation:draw 5s linear infinite}}
@keyframes draw{{0%{{stroke-dashoffset:1000;opacity:1}}80%{{stroke-dashoffset:0;opacity:1}}94%{{stroke-dashoffset:0;opacity:0}}100%{{stroke-dashoffset:1000;opacity:0}}}}
.float{{animation:float 6s ease-in-out infinite}}@keyframes float{{50%{{transform:translateY(-4px)}}}}
.cur{{animation:blink 1s steps(1) infinite}}@keyframes blink{{50%{{opacity:0}}}}
{css}
</style>
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#060b0f"/><stop offset="1" stop-color="#0b2a33"/></linearGradient>
<linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient>
<filter id="glow" x="-5%" y="-50%" width="110%" height="200%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<rect width="1000" height="300" rx="18" fill="url(#bg)"/>
<g stroke="#fff" stroke-opacity=".04">{grid}</g>
<g class="float">
<text x="500" y="124" text-anchor="middle" font-family="{MONO}" font-size="92" font-weight="800" letter-spacing="6" fill="url(#g)" filter="url(#glow)">ROMARTAK</text>
<text x="500" y="156" text-anchor="middle" font-family="{MONO}" font-size="15" letter-spacing="8" fill="#7d8b99">MÉDICO · VIBE CODER</text>
</g>
{texts}
<path d="{ecg}" pathLength="1000" fill="none" stroke="#1d2a33" stroke-width="2"/>
<path class="draw" d="{ecg}" pathLength="1000" fill="none" stroke="{a}" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round" filter="url(#glow)"/>
</svg>
"""


def terminal():
    """terminal.svg: ventana de terminal con líneas que se escriben solas."""
    a, b = THEMES["dark"]["acc"], THEMES["dark"]["acc2"]
    lines = [
        ("$ whoami", "romartak — médico en formación & vibe coder"),
        ("$ cat mision.txt", "convertir ideas en herramientas que funcionan"),
        ("$ ls proyectos/", "sdrkit/  investigaciones-personales/  ..."),
        ("$ ./sdrkit --status", "radio 0.5 → 1766 MHz · Raspberry Pi Zero 2 W · OK"),
    ]
    step, css, body = 2.4, [], []
    tot = len(lines) * step + 3
    for i, (cmd, out) in enumerate(lines):
        t0 = i * step
        y1, y2 = 74 + i * 44, 74 + i * 44 + 20
        css.append(f".l{i}{{opacity:0;animation:s{i} {tot}s infinite}}"
                   f"@keyframes s{i}{{0%,{max(100 * t0 / tot - 0.1, 0):.1f}%{{opacity:0}}"
                   f"{100 * t0 / tot:.1f}%,94%{{opacity:1}}100%{{opacity:0}}}}")
        body.append(f'<g class="l{i}"><text x="28" y="{y1}" font-family="{MONO}" font-size="15" fill="{a}">{escape(cmd)}</text>'
                    f'<text x="28" y="{y2}" font-family="{MONO}" font-size="13" fill="#9fb3c8">{escape(out)}</text></g>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 270" role="img" aria-label="terminal de romartak">
<style>{"".join(css)}.cur{{animation:blink 1s steps(1) infinite}}@keyframes blink{{50%{{opacity:0}}}}</style>
<rect width="1000" height="270" rx="12" fill="#060b0f" stroke="#1d2a33"/>
<rect width="1000" height="34" rx="12" fill="#0b1319"/><rect y="20" width="1000" height="14" fill="#0b1319"/>
<circle cx="22" cy="17" r="6" fill="#ff5f56"/><circle cx="42" cy="17" r="6" fill="#ffbd2e"/><circle cx="62" cy="17" r="6" fill="#27c93f"/>
<text x="500" y="22" text-anchor="middle" font-family="{MONO}" font-size="12" fill="#7d8b99">romartak@perfil: ~</text>
{"".join(body)}
<text x="28" y="{74 + 4 * 44}" font-family="{MONO}" font-size="15" fill="{a}">$ <tspan class="cur" fill="{b}">█</tspan></text>
</svg>
"""


def bump_readme():
    """Pone ?v=<huella> en las imágenes del README: si un SVG cambia, cambia su URL y
    GitHub (y el navegador) dejan de mostrar la copia vieja que tenían en caché."""
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    for rel in ("banner.svg", "terminal.svg", "profiles/default/dark.svg", "profiles/default/light.svg"):
        v = hashlib.sha1((ROOT / rel).read_bytes()).hexdigest()[:8]
        text = re.sub(r'(?<=["/ ])' + re.escape(rel) + r'(\?v=[0-9a-f]+)?(?=")', f"{rel}?v={v}", text)
    readme.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    (ROOT / "banner.svg").write_text(banner(), encoding="utf-8")
    (ROOT / "terminal.svg").write_text(terminal(), encoding="utf-8")
    data = fetch()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, theme in THEMES.items():
        (OUT / f"{name}.svg").write_text(render(data, theme), encoding="utf-8")
    bump_readme()
    print("ok:", OUT)
