"""Builds the README's animated SVGs: uv run python docs/assets/generate.py

GitHub shows an <img> SVG with its CSS animations but no scripts, no web fonts and no outside files, so every asset
here is self-contained: system fonts, shapes drawn in code, screenshots embedded as data URIs.

Outputs (docs/assets/): banner.svg, rain-divider.svg, phone-demo.svg, databricks.svg, elevenlabs.svg, figma.svg,
devpost.svg. The sponsor marks are simple redraws of each logo, not the official artwork.
"""
import base64
import io
import random
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
SCREENS = HERE / "screens"
FONT = "ui-rounded, 'SF Pro Rounded', 'Segoe UI', system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif"

# --- shared pieces ---------------------------------------------------------------------------------------------

REDUCED = "@media (prefers-reduced-motion: reduce){*{animation:none !important}}"

RAIN_CSS = """
.fall{animation:fall linear infinite}
.sway{animation:sway ease-in-out infinite alternate}
.flip{animation:flutter ease-in-out infinite}
@keyframes fall{from{transform:translateY(var(--y0))}to{transform:translateY(var(--h))}}
@keyframes sway{from{transform:translateX(calc(var(--dx) * -1))}to{transform:translateX(var(--dx))}}
@keyframes flutter{0%,100%{transform:rotate(var(--r0)) scaleX(1)}50%{transform:rotate(var(--r1)) scaleX(.22)}}
@keyframes fadeedge{0%{opacity:0}12%{opacity:var(--o)}82%{opacity:var(--o)}100%{opacity:0}}
"""

RAIN_DEFS = """
<linearGradient id="billg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3DDC84"/><stop offset="1" stop-color="#16954A"/></linearGradient>
<radialGradient id="coing" cx=".35" cy=".3" r=".9"><stop offset="0" stop-color="#FFE48A"/><stop offset="1" stop-color="#F2A100"/></radialGradient>
<g id="bill">
  <rect x="-32" y="-15" width="64" height="30" rx="5" fill="url(#billg)" stroke="#0B6B35" stroke-width="1.2"/>
  <rect x="-27" y="-10" width="54" height="20" rx="3" fill="none" stroke="#C8F8D6" stroke-opacity=".7"/>
  <circle r="8.5" fill="#C8F8D6" fill-opacity=".92"/>
  <text y="4.4" text-anchor="middle" font-family="__FONT__" font-weight="800" font-size="12" fill="#0B6B35">$</text>
  <circle cx="-22" cy="-5" r="1.6" fill="#C8F8D6"/><circle cx="22" cy="5" r="1.6" fill="#C8F8D6"/>
</g>
<g id="coin">
  <circle r="12" fill="url(#coing)" stroke="#B87400" stroke-width="1.4"/>
  <circle r="8.2" fill="none" stroke="#B87400" stroke-opacity=".55"/>
  <text y="4.6" text-anchor="middle" font-family="__FONT__" font-weight="800" font-size="12.5" fill="#9A6200">$</text>
</g>
""".replace("__FONT__", FONT)


def rain(width, height, count, seed, sizes=(0.55, 1.15), opacity=(0.55, 1.0), speed=(7.0, 14.0), edge_fade=False):
    """`count` bills and coins at random x, each falling, swaying and fluttering on its own clock. Negative delays
    start every piece mid-fall, so the very first frame is already a full shower."""
    rng = random.Random(seed)
    out = []
    for _ in range(count):
        x = rng.uniform(-10, width + 10)
        scale = rng.uniform(*sizes)
        coin = rng.random() < 0.28
        dur = rng.uniform(*speed) * (1.15 - 0.35 * (scale - sizes[0]) / max(sizes[1] - sizes[0], 0.01))
        delay = -rng.uniform(0, dur)
        dx = rng.uniform(10, 38)
        r0, r1 = rng.uniform(-35, 35), rng.uniform(-35, 35)
        o = rng.uniform(*opacity)
        # Fading in and out at the strip's edges needs its own wrapper: a second `animation` on the falling group
        # would replace the fall itself.
        outer = f'<g style="animation:fadeedge {dur:.2f}s linear {delay:.2f}s infinite;--o:{o:.2f}">' if edge_fade else ""
        close = "</g>" if edge_fade else ""
        still = "" if edge_fade else f"opacity:{o:.2f};"
        out.append(
            f'<g transform="translate({x:.0f},0)">{outer}<g class="fall" style="animation-duration:{dur:.2f}s;animation-delay:{delay:.2f}s;{still}">'
            f'<g class="sway" style="animation-duration:{rng.uniform(2.2, 4.4):.2f}s;animation-delay:{-rng.uniform(0, 3):.2f}s;--dx:{dx:.0f}px">'
            f'<g class="flip" style="animation-duration:{rng.uniform(1.6, 3.4) * (0.5 if coin else 1):.2f}s;animation-delay:{-rng.uniform(0, 3):.2f}s;--r0:{r0:.0f}deg;--r1:{r1:.0f}deg">'
            f'<use href="#{"coin" if coin else "bill"}" transform="scale({scale:.2f})"/></g></g></g>{close}</g>'
        )
    return "".join(out)


def svg(width, height, body, css="", defs="", y0=-90, drop=110):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'font-family="{FONT}" style="--h:{height + drop}px;--y0:{y0}px">'
        f"<style>{css}{REDUCED}</style><defs>{defs}</defs>{body}</svg>"
    )


def data_uri(path: Path, width: int, quality: int = 80) -> str:
    im = Image.open(path).convert("RGB")
    im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def card(width, height, c1, c2, glow):
    """The rounded dark panel every sponsor card sits on, with a soft coloured glow in one corner."""
    return (
        f'<linearGradient id="cardg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient>'
        f'<radialGradient id="glow" cx="0" cy="0" r="1"><stop offset="0" stop-color="{glow}" stop-opacity=".55"/><stop offset="1" stop-color="{glow}" stop-opacity="0"/></radialGradient>',
        f'<rect width="{width}" height="{height}" rx="26" fill="url(#cardg)"/>'
        f'<rect width="{width}" height="{height}" rx="26" fill="url(#glow)" transform="scale(1)" opacity=".9"/>'
        f'<rect x=".75" y=".75" width="{width - 1.5}" height="{height - 1.5}" rx="25.5" fill="none" stroke="#fff" stroke-opacity=".12" stroke-width="1.5"/>',
    )


# --- logos (simple redraws) -----------------------------------------------------------------------------------


def databricks_mark():
    """Three stacked chevron bands under a diamond cap: the layered 'lakehouse' mark, as plain paths."""
    band = "M0 10 L34 -8 L68 10 L68 20 L34 2 L0 20 Z"
    return '<path d="M0 -2 L34 -20 L68 -2 L34 16 Z"/>' + "".join(f'<path d="{band}" transform="translate(0,{i * 17})"/>' for i in range(3))


def logo_databricks(x, y, s=1.0, fill="#FF3621"):
    return f'<g transform="translate({x},{y}) scale({s})" fill="{fill}">{databricks_mark()}</g>'


def logo_elevenlabs(x, y, s=1.0, fill="#fff"):
    return f'<g transform="translate({x},{y}) scale({s})" fill="{fill}"><rect x="0" y="0" width="13" height="52" rx="4"/><rect x="25" y="0" width="13" height="52" rx="4"/></g>'


def logo_figma(x, y, s=1.0):
    return (
        f'<g transform="translate({x},{y}) scale({s})">'
        '<path d="M19 28.5a9.5 9.5 0 1 1 19 0 9.5 9.5 0 0 1-19 0z" fill="#1abcfe"/>'
        '<path d="M0 47.5A9.5 9.5 0 0 1 9.5 38H19v9.5a9.5 9.5 0 1 1-19 0z" fill="#0acf83"/>'
        '<path d="M19 0v19h9.5a9.5 9.5 0 1 0 0-19H19z" fill="#ff7262"/>'
        '<path d="M0 9.5A9.5 9.5 0 0 0 9.5 19H19V0H9.5A9.5 9.5 0 0 0 0 9.5z" fill="#f24e1e"/>'
        '<path d="M0 28.5A9.5 9.5 0 0 0 9.5 38H19V19H9.5A9.5 9.5 0 0 0 0 28.5z" fill="#a259ff"/></g>'
    )


def logo_devpost(x, y, s=1.0):
    return (
        f'<g transform="translate({x},{y}) scale({s})"><rect width="52" height="52" rx="12" fill="#00B8D4"/>'
        '<path d="M15 13h11c9 0 14 5.5 14 13s-5 13-14 13H15z M22 20v12h4c4.5 0 7-2.2 7-6s-2.500-6-7-6z" fill="#fff" fill-rule="evenodd"/></g>'
    )


# --- banner: money rain over the title -------------------------------------------------------------------------


def banner():
    w, h = 1280, 400
    css = RAIN_CSS + """
.line{opacity:0;animation:cycle 16s ease-in-out infinite}
@keyframes cycle{0%{opacity:0;transform:translateY(10px)}4%,21%{opacity:1;transform:none}25%,100%{opacity:0;transform:translateY(-8px)}}
.swing{animation:swing 3.2s ease-in-out infinite alternate;transform-origin:0 0}
@keyframes swing{from{transform:rotate(-9deg)}to{transform:rotate(9deg)}}
.pulse{animation:pulse 2.8s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:.55}50%{opacity:.95}}
"""
    defs = RAIN_DEFS + """
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#06311D"/><stop offset=".55" stop-color="#0E6A37"/><stop offset="1" stop-color="#17A150"/></linearGradient>
<radialGradient id="vig" cx=".5" cy=".48" r=".55"><stop offset="0" stop-color="#021A0E" stop-opacity=".72"/><stop offset="1" stop-color="#021A0E" stop-opacity="0"/></radialGradient>
<filter id="sh" x="-20%" y="-30%" width="140%" height="160%"><feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#021A0E" flood-opacity=".8"/></filter>
"""
    body = (
        f'<rect width="{w}" height="{h}" rx="22" fill="url(#bg)"/>'
        f'<g class="pulse"><circle cx="1090" cy="60" r="190" fill="#7CFFB0" fill-opacity=".12"/><circle cx="150" cy="360" r="170" fill="#FFE48A" fill-opacity=".1"/></g>'
        f'<g>{rain(w, h, 26, 3, sizes=(0.45, 0.7), opacity=(0.35, 0.6), speed=(11, 17))}</g>'  # far layer, slow and faint
        f'<g>{rain(w, h, 24, 8, sizes=(0.85, 1.35), opacity=(0.8, 1.0), speed=(5.5, 9))}</g>'  # near layer, big and quick, behind the words
        f'<rect width="{w}" height="{h}" fill="url(#vig)"/>'
        '<g filter="url(#sh)" text-anchor="middle">'
        '<text x="640" y="205" font-size="132" font-weight="900" fill="#fff" letter-spacing="-3">Savy</text></g>'
        '<g text-anchor="middle" font-size="27" font-weight="600" fill="#D6FFE5">'
        '<text class="line" x="640" y="262" style="animation-delay:0s">Every grocery flyer near you, in one place.</text>'
        '<text class="line" x="640" y="262" style="animation-delay:4s">Matched to what you actually buy.</text>'
        '<text class="line" x="640" y="262" style="animation-delay:8s">The cheapest store for your whole basket.</text>'
        '<text class="line" x="640" y="262" style="animation-delay:12s">Say it, snap it, or tap it: it is on your list.</text></g>'
        '<g transform="translate(1085,0)"><g class="swing"><line x1="0" y1="0" x2="0" y2="62" stroke="#E8FFF0" stroke-opacity=".7" stroke-width="2"/>'
        '<g transform="translate(0,62)"><path d="M-58 0h94l20 22-20 22h-94z" fill="#FFD23F" stroke="#B88700" stroke-width="2"/>'
        '<circle cx="-44" cy="22" r="4.5" fill="#06311D"/>'
        '<text x="6" y="31" text-anchor="middle" font-size="24" font-weight="900" fill="#3B2A00">$3.99</text></g></g></g>'
        '<text x="640" y="352" text-anchor="middle" font-size="17" font-weight="700" letter-spacing="3" fill="#BFF5CF" fill-opacity=".9">'
        'HACKCAMP 2026  ·  DATABRICKS  ·  GEMINI  ·  ELEVENLABS  ·  FIGMA</text>'
    )
    return svg(w, h, body, css, defs)


# --- divider: a thin strip of rain between README sections -------------------------------------------------------


def divider():
    w, h = 1280, 84
    body = f'<g>{rain(w, h, 34, 21, sizes=(0.4, 0.7), opacity=(0.55, 1.0), speed=(3.4, 6.0), edge_fade=True)}</g>'
    return svg(w, h, body, RAIN_CSS, RAIN_DEFS, y0=-34, drop=34)  # starts just above the strip, so it is always in view


# --- phone demo: the real screens, cross-fading inside a phone ---------------------------------------------------

SCREEN_TAGS = [
    ("flyers", "Flyers", "Every deal in every flyer near you", "Searchable, filterable by store and category."),
    ("pricematch", "Price Match", "The real printed flyer page", "Your item outlined, with a link to the store."),
    ("pantry", "Pantry", "What you buy, and where it is cheapest", "Matched to this week's flyers."),
    ("basket", "Basket", "A checklist for the trip", "Tick items off, undo, clear done."),
    ("voice", "Say it", "Hold to talk, or just type", "Parsed into brand, item, variant and size."),
    ("ask", "Ask", "Questions in plain words", "Answered by Databricks Genie, with the SQL."),
]


def phone_demo():
    w, h = 1100, 760
    cycle = len(SCREEN_TAGS) * 4
    css = RAIN_CSS + f"""
.scr{{opacity:0;animation:scr {cycle}s ease-in-out infinite}}
@keyframes scr{{0%{{opacity:0}}3%,{100 / len(SCREEN_TAGS) - 0.3:.2f}%{{opacity:1}}{100 / len(SCREEN_TAGS) + 2.7:.2f}%,100%{{opacity:0}}}}
.cap{{opacity:0;animation:cap {cycle}s ease-in-out infinite}}
@keyframes cap{{0%{{opacity:0;transform:translateX(-14px)}}3.5%,{100 / len(SCREEN_TAGS) - 0.6:.2f}%{{opacity:1;transform:none}}{100 / len(SCREEN_TAGS) + 2.2:.2f}%,100%{{opacity:0;transform:translateX(10px)}}}}
.dot{{fill:#fff;fill-opacity:.25;animation:dot {cycle}s ease-in-out infinite}}
@keyframes dot{{0%{{fill-opacity:.25}}3%,{100 / len(SCREEN_TAGS) - 0.3:.2f}%{{fill-opacity:1}}{100 / len(SCREEN_TAGS) + 2.7:.2f}%,100%{{fill-opacity:.25}}}}
.float{{animation:float 5s ease-in-out infinite alternate}}
@keyframes float{{from{{transform:translateY(-8px)}}to{{transform:translateY(8px)}}}}
"""
    defs = RAIN_DEFS + '<clipPath id="screen"><rect x="0" y="0" width="318" height="688" rx="38"/></clipPath>'
    defs += (
        '<linearGradient id="pbg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0B2217"/><stop offset="1" stop-color="#14392A"/></linearGradient>'
        '<filter id="psh" x="-30%" y="-10%" width="160%" height="130%"><feDropShadow dx="0" dy="18" stdDeviation="22" flood-color="#000" flood-opacity=".55"/></filter>'
    )
    px, py = 640, 36
    shots = "".join(
        f'<image class="scr" href="{data_uri(SCREENS / (k + ".jpg"), 390, 82)}" width="318" height="688" preserveAspectRatio="xMidYMid slice" style="animation-delay:{i * 4 - 0.8:.1f}s"/>'
        for i, (k, *_r) in enumerate(SCREEN_TAGS)
    )
    caps = ""
    for i, (_k, name, headline, sub) in enumerate(SCREEN_TAGS):
        words = headline.split()
        mid = (len(words) + 1) // 2  # break the headline near the middle so it fits beside the phone
        l1, l2 = " ".join(words[:mid]), " ".join(words[mid:])
        caps += (
            f'<g class="cap" style="animation-delay:{i * 4 - 0.8:.1f}s">'
            f'<text x="70" y="300" font-size="22" font-weight="800" letter-spacing="4" fill="#7CFFB0">{name.upper()}</text>'
            f'<text x="70" y="356" font-size="38" font-weight="800" fill="#fff">{l1}</text>'
            f'<text x="70" y="402" font-size="38" font-weight="800" fill="#fff">{l2}</text>'
            f'<text x="70" y="448" font-size="20" font-weight="500" fill="#BFF5CF">{sub}</text></g>'
        )
    dots = "".join(
        f'<circle class="dot" cx="{70 + i * 26}" cy="520" r="6" style="animation-delay:{i * 4 - 0.8:.1f}s"/>' for i in range(len(SCREEN_TAGS))
    )
    body = (
        f'<rect width="{w}" height="{h}" rx="28" fill="url(#pbg)"/>'
        f'<g opacity=".8">{rain(w, h, 16, 5, sizes=(0.4, 0.7), opacity=(0.3, 0.55), speed=(9, 15))}</g>'
        f'<g class="float" filter="url(#psh)"><g transform="translate({px},{py})">'
        '<rect x="-14" y="-14" width="346" height="716" rx="54" fill="#0B0B0D" stroke="#3A3F44" stroke-width="3"/>'
        f'<g clip-path="url(#screen)">{shots}</g>'
        '<rect x="119" y="10" width="80" height="22" rx="11" fill="#0B0B0D"/></g></g>'
        f"{caps}{dots}"
        '<text x="70" y="96" font-size="19" font-weight="700" letter-spacing="3" fill="#BFF5CF" fill-opacity=".85">THE APP, AS IT RUNS TODAY</text>'
        '<text x="70" y="136" font-size="15" fill="#BFF5CF" fill-opacity=".6">Real screenshots, real flyers near V6T 1Z4.</text>'
    )
    return svg(w, h, body, css, defs)


# --- Databricks: a wall of bricks, one per thing we built on it -----------------------------------------------------

BRICKS = [
    # row (0 = bottom), col, span, label, sublabel
    (0, 0, 1, "Flyers → Unity Catalog", "live flyers, synced"),
    (0, 1, 1, "Volumes", "pages and receipts"),
    (0, 2, 1, "Lakeflow", "Bronze → Silver → Gold"),
    (1, 0, 1, "SQL Statement API", "every read and write"),
    (1, 1, 1, "live_listings", "+ price_history"),
    (1, 2, 1, "ai_query", "extractor, opt-in"),
    (2, 0, 1, "Genie", "Ask in plain words"),
    (2, 1, 1, "Model Serving", "AI product names"),
    (2, 2, 1, "Databricks App", "hosts the API"),
]


def databricks():
    w, h = 1280, 520
    c_defs, c_body = card(w, h, "#0E1B20", "#1B3139", "#FF3621")
    css = """
.brick{opacity:0;animation:drop 11s cubic-bezier(.3,.7,.4,1) infinite}
@keyframes drop{
 0%{opacity:0;transform:translateY(-340px) rotate(-6deg)}
 5%{opacity:1}
 11%{transform:translateY(0) rotate(0)}
 14%{transform:translateY(-16px)}
 17%{transform:translateY(0)}
 19%{transform:translateY(-5px)}
 21%,86%{opacity:1;transform:translateY(0)}
 94%,100%{opacity:0;transform:translateY(14px)}}
.shine{animation:shine 11s ease-in-out infinite}
@keyframes shine{0%,30%{opacity:0}45%{opacity:.5}60%,100%{opacity:0}}
.logo{animation:breathe 3.6s ease-in-out infinite;transform-origin:0 0}
@keyframes breathe{0%,100%{transform:scale(1)}50%{transform:scale(1.06)}}
"""
    bx, by, bw, bh, gap = 504, 40, 240, 92, 14
    bricks = ""
    for i, (row, col, _span, label, sub) in enumerate(BRICKS):
        x = bx + col * (bw + gap)
        y = by + (2 - row) * (bh + gap) + 110
        shade = ["#FF3621", "#E8321F", "#FF5A44"][(row + col) % 3]
        bricks += (
            f'<g class="brick" style="animation-delay:{i * 0.42:.2f}s"><g transform="translate({x},{y})">'
            f'<rect width="{bw}" height="{bh}" rx="12" fill="{shade}"/>'
            f'<rect width="{bw}" height="{bh}" rx="12" fill="url(#brickhi)"/>'
            f'<rect x="1.5" y="1.5" width="{bw - 3}" height="{bh - 3}" rx="10.5" fill="none" stroke="#fff" stroke-opacity=".28"/>'
            f'<circle cx="18" cy="18" r="3" fill="#fff" fill-opacity=".55"/><circle cx="{bw - 18}" cy="18" r="3" fill="#fff" fill-opacity=".55"/>'
            f'<text x="{bw / 2}" y="{bh / 2 - 2}" text-anchor="middle" font-size="22" font-weight="800" fill="#fff">{label}</text>'
            f'<text x="{bw / 2}" y="{bh / 2 + 24}" text-anchor="middle" font-size="15" font-weight="600" fill="#fff" fill-opacity=".86">{sub}</text>'
            "</g></g>"
        )
    defs = c_defs + RAIN_DEFS + '<linearGradient id="brickhi" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".22"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".2"/></linearGradient>'
    body = (
        c_body
        + f'<g opacity=".55">{rain(w, h, 12, 31, sizes=(0.4, 0.65), opacity=(0.25, 0.5), speed=(9, 15))}</g>'
        + f'<g transform="translate(70,98)"><g class="logo" fill="#FF3621"><g transform="scale(1.35)">{databricks_mark()}</g></g></g>'
        + '<text x="70" y="250" font-size="52" font-weight="900" fill="#fff" letter-spacing="-1">Databricks</text>'
        + '<text x="70" y="300" font-size="22" font-weight="600" fill="#FFB4A8">The lakehouse under the whole app</text>'
        + '<g font-size="17" font-weight="500" fill="#D7E3E8"><text x="70" y="352">Live flyers become tables.</text>'
        '<text x="70" y="380">Tables become answers.</text>'
        '<text x="70" y="408">Writes only when you switch it on.</text></g>'
        + bricks
    )
    return svg(w, h, body, css, defs)


# --- ElevenLabs: a voice wave that becomes a list item ------------------------------------------------------------


def elevenlabs():
    w, h = 1280, 480
    c_defs, c_body = card(w, h, "#08080C", "#15151D", "#7C5CFF")
    css = """
.bar{transform-box:fill-box;transform-origin:center;animation:wave var(--d) ease-in-out infinite alternate}
@keyframes wave{from{transform:scaleY(.12)}to{transform:scaleY(1)}}
.live{animation:live 10s ease-in-out infinite}
@keyframes live{0%,40%{opacity:1}47%,94%{opacity:.14}100%{opacity:1}}
.word{opacity:0;animation:word 10s ease-in-out infinite}
@keyframes word{0%,42%{opacity:0;transform:translateY(8px)}48%,90%{opacity:1;transform:none}95%,100%{opacity:0}}
.chip{opacity:0;transform-box:fill-box;transform-origin:center;animation:chip 10s cubic-bezier(.3,1.5,.5,1) infinite}
@keyframes chip{0%,66%{opacity:0;transform:scale(.7)}72%,90%{opacity:1;transform:scale(1)}95%,100%{opacity:0;transform:scale(.9)}}
.ring{transform-box:fill-box;transform-origin:center;animation:ring 1.6s ease-out infinite}
@keyframes ring{from{transform:scale(.9);opacity:.7}to{transform:scale(2.1);opacity:0}}
.mic{animation:mic 10s ease-in-out infinite}
@keyframes mic{0%,40%{opacity:1}47%,94%{opacity:.35}100%{opacity:1}}
"""
    rng = random.Random(7)
    n, x0, gapx, bw_ = 54, 470, 14, 7
    bars = ""
    for i in range(n):
        env = 0.35 + 0.65 * (1 - abs(i - n / 2) / (n / 2)) ** 0.8  # tallest in the middle, like a spoken word
        bh = 190 * env * rng.uniform(0.65, 1.0)
        bars += (
            f'<rect class="bar" x="{x0 + i * gapx}" y="{150 - bh / 2:.1f}" width="{bw_}" height="{bh:.1f}" rx="3.5" fill="url(#wavefill)" '
            f'style="--d:{rng.uniform(0.35, 0.8):.2f}s;animation-delay:{-rng.uniform(0, 0.8):.2f}s"/>'
        )
    words = ["add", "a", "4&#160;L", "jug", "of", "2%", "milk"]
    wx, wtxt = 470, ""
    for i, wd in enumerate(words):
        wtxt += f'<text class="word" x="{wx}" y="318" font-size="34" font-weight="700" fill="#fff" style="animation-delay:{i * 0.16:.2f}s">{wd}</text>'
        wx += 22 + len(wd.replace('&#160;', ' ')) * 19
    defs = (
        c_defs
        + '<linearGradient id="wavefill" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#7C5CFF"/><stop offset=".5" stop-color="#4FC3F7"/><stop offset="1" stop-color="#FF8A5C"/></linearGradient>'
        + '<radialGradient id="orb" cx=".35" cy=".3" r=".9"><stop offset="0" stop-color="#9D8BFF"/><stop offset="1" stop-color="#2B1FA8"/></radialGradient>'
    )
    body = (
        c_body
        + logo_elevenlabs(70, 78, 1.35)
        + '<text x="70" y="226" font-size="52" font-weight="800" fill="#fff" letter-spacing="-1">ElevenLabs</text>'
        + '<text x="70" y="274" font-size="22" font-weight="600" fill="#C9C1FF">Hold the button. Say what you need.</text>'
        + '<g font-size="17" font-weight="500" fill="#CFCFE0"><text x="70" y="326">Scribe speech-to-text via our API,</text>'
        '<text x="70" y="354">so the key never reaches the phone.</text>'
        '<text x="70" y="382">Silence is caught before it costs.</text></g>'
        + f'<g class="live">{bars}</g>'
        + '<g transform="translate(1160,150)"><circle class="ring" r="34" fill="none" stroke="#9D8BFF" stroke-width="3"/><circle class="ring" r="34" fill="none" stroke="#9D8BFF" stroke-width="3" style="animation-delay:.8s"/>'
        '<g class="mic"><circle r="38" fill="url(#orb)"/><rect x="-7" y="-17" width="14" height="24" rx="7" fill="#fff"/>'
        '<path d="M-14 0a14 14 0 0 0 28 0M0 14v9" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"/></g></g>'
        + wtxt
        + '<g class="chip"><rect x="470" y="352" width="470" height="62" rx="18" fill="#fff"/>'
        '<circle cx="506" cy="383" r="14" fill="#1FA350"/><path d="M499 383l5 5 9-10" fill="none" stroke="#fff" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<text x="534" y="378" font-size="21" font-weight="800" fill="#111">Milk</text>'
        '<text x="534" y="402" font-size="15" font-weight="600" fill="#555">2%  ·  4 L  ·  added to your Pantry</text></g>'
        + '<text x="470" y="70" font-size="15" font-weight="700" letter-spacing="3" fill="#C9C1FF" fill-opacity=".8">HOLD TO TALK</text>'
        + '<text x="1210" y="250" text-anchor="end" font-size="14" font-weight="600" fill="#9A93C8">/intake/voice</text>'
    )
    return svg(w, h, body, css, defs)


# --- Figma: five shapes become the logo, then frames become the real app ----------------------------------------


def figma():
    w, h = 1280, 520
    c_defs, c_body = card(w, h, "#1E1E1E", "#2C2C2C", "#A259FF")
    css = """
.s1{animation:s1 12s cubic-bezier(.2,.9,.3,1.2) infinite}
.s2{animation:s2 12s cubic-bezier(.2,.9,.3,1.2) infinite}
.s3{animation:s3 12s cubic-bezier(.2,.9,.3,1.2) infinite}
.s4{animation:s4 12s cubic-bezier(.2,.9,.3,1.2) infinite}
.s5{animation:s5 12s cubic-bezier(.2,.9,.3,1.2) infinite}
@keyframes s1{0%{transform:translate(-140px,-120px) rotate(-90deg);opacity:0}8%,100%{transform:none;opacity:1}}
@keyframes s2{0%{transform:translate(160px,-130px) rotate(80deg);opacity:0}8%,100%{transform:none;opacity:1}}
@keyframes s3{0%{transform:translate(-150px,20px) rotate(70deg);opacity:0}8%,100%{transform:none;opacity:1}}
@keyframes s4{0%{transform:translate(170px,60px) rotate(-60deg);opacity:0}8%,100%{transform:none;opacity:1}}
@keyframes s5{0%{transform:translate(-120px,150px) rotate(100deg);opacity:0}8%,100%{transform:none;opacity:1}}
.wire{opacity:0;animation:wire 12s ease-in-out infinite}
@keyframes wire{0%,8%{opacity:0;transform:translateY(16px)}15%,50%{opacity:1;transform:none}58%,100%{opacity:0}}
.shot{opacity:0;animation:shot 12s ease-in-out infinite}
@keyframes shot{0%,50%{opacity:0}60%,92%{opacity:1}98%,100%{opacity:0}}
.sel{opacity:0;animation:sel 12s ease-in-out infinite}
@keyframes sel{0%,22%{opacity:0}28%,46%{opacity:1}52%,100%{opacity:0}}
.cur1{animation:cur1 12s ease-in-out infinite}
.cur2{animation:cur2 12s ease-in-out infinite}
.cur3{animation:cur3 12s ease-in-out infinite}
@keyframes cur1{0%{transform:translate(500px,430px)}20%{transform:translate(560px,180px)}40%{transform:translate(790px,300px)}60%{transform:translate(1010px,150px)}80%{transform:translate(900px,400px)}100%{transform:translate(500px,430px)}}
@keyframes cur2{0%{transform:translate(1150px,100px)}25%{transform:translate(980px,420px)}50%{transform:translate(700px,200px)}75%{transform:translate(620px,420px)}100%{transform:translate(1150px,100px)}}
@keyframes cur3{0%{transform:translate(800px,470px)}30%{transform:translate(1100px,300px)}55%{transform:translate(880px,120px)}80%{transform:translate(560px,300px)}100%{transform:translate(800px,470px)}}
.done{opacity:0;animation:done 12s ease-in-out infinite}
@keyframes done{0%,62%{opacity:0;transform:translateY(8px)}70%,92%{opacity:1;transform:none}98%,100%{opacity:0}}
"""
    keys = ["flyers", "pricematch", "pantry", "basket", "voice"]
    names = ["Flyers", "Price match", "Pantry", "Basket", "Add by voice"]
    fw, fh, fx0, fy, fg = 134, 290, 450, 120, 24
    frames = ""
    for i, (k, nm) in enumerate(zip(keys, names, strict=True)):
        x = fx0 + i * (fw + fg)
        delay = f"animation-delay:{i * 0.35:.2f}s"
        frames += (
            f'<g transform="translate({x},{fy})">'
            f'<text x="0" y="-12" font-size="14" font-weight="600" fill="#B3B3B3">{nm}</text>'
            f'<g class="wire" style="{delay}"><rect width="{fw}" height="{fh}" rx="14" fill="#1A1A1A" stroke="#5A5A5A" stroke-dasharray="5 4"/>'
            f'<rect x="12" y="16" width="70" height="12" rx="6" fill="#3D3D3D"/><rect x="12" y="44" width="{fw - 24}" height="26" rx="8" fill="#303030"/>'
            f'<rect x="12" y="86" width="{fw - 24}" height="34" rx="8" fill="#303030"/><rect x="12" y="130" width="{fw - 24}" height="34" rx="8" fill="#303030"/>'
            f'<rect x="12" y="174" width="{fw - 24}" height="34" rx="8" fill="#303030"/><rect x="12" y="{fh - 38}" width="{fw - 24}" height="24" rx="12" fill="#3A2A5A"/></g>'
            f'<g class="shot" style="{delay}"><clipPath id="fc{i}"><rect width="{fw}" height="{fh}" rx="14"/></clipPath>'
            f'<g clip-path="url(#fc{i})"><image href="{data_uri(SCREENS / (k + ".jpg"), 270, 78)}" width="{fw}" height="{fh}" preserveAspectRatio="xMidYMin slice"/></g>'
            f'<rect width="{fw}" height="{fh}" rx="14" fill="none" stroke="#fff" stroke-opacity=".25"/></g>'
            f'<g class="sel" style="{delay}"><rect x="-3" y="-3" width="{fw + 6}" height="{fh + 6}" rx="16" fill="none" stroke="#0D99FF" stroke-width="2"/>'
            + "".join(f'<rect x="{cx - 4}" y="{cy - 4}" width="8" height="8" fill="#fff" stroke="#0D99FF"/>' for cx, cy in [(-3, -3), (fw + 3, -3), (-3, fh + 3), (fw + 3, fh + 3)])
            + f'<rect x="{fw / 2 - 42}" y="{fh + 12}" width="84" height="20" rx="4" fill="#0D99FF"/><text x="{fw / 2}" y="{fh + 26}" text-anchor="middle" font-size="12" font-weight="700" fill="#fff">390 × 844</text></g>'
            "</g>"
        )

    def cursor(cls, color, label):
        return (
            f'<g class="{cls}"><path d="M0 0l0 18 5-4.600 3.600 8.200 3.500-1.500-3.600-8.200 6.600-.4z" fill="{color}" stroke="#fff" stroke-width="1.2"/>'
            f'<rect x="14" y="16" width="{22 + len(label) * 7.5:.0f}" height="20" rx="10" fill="{color}"/>'
            f'<text x="25" y="30" font-size="12" font-weight="700" fill="#fff">{label}</text></g>'
        )

    body = (
        c_body
        + '<g transform="translate(70,70) scale(1.7)">'
        '<path class="s1" d="M0 9.5A9.5 9.5 0 0 0 9.5 19H19V0H9.5A9.5 9.5 0 0 0 0 9.5z" fill="#f24e1e"/>'
        '<path class="s2" d="M19 0v19h9.5a9.5 9.5 0 1 0 0-19H19z" fill="#ff7262"/>'
        '<path class="s3" d="M0 28.5A9.5 9.5 0 0 0 9.5 38H19V19H9.5A9.5 9.5 0 0 0 0 28.5z" fill="#a259ff"/>'
        '<path class="s4" d="M19 28.5a9.5 9.5 0 1 1 19 0 9.5 9.5 0 0 1-19 0z" fill="#1abcfe"/>'
        '<path class="s5" d="M0 47.5A9.5 9.5 0 0 1 9.5 38H19v9.5a9.5 9.5 0 1 1-19 0z" fill="#0acf83"/></g>'
        + '<text x="70" y="256" font-size="52" font-weight="800" fill="#fff" letter-spacing="-1">Figma</text>'
        + '<text x="70" y="304" font-size="22" font-weight="600" fill="#D9C2FF">18 screens, designed first, then built.</text>'
        + '<g font-size="17" font-weight="500" fill="#CFCFCF"><text x="70" y="356">Mobile frames for every tab and sheet,</text>'
        '<text x="70" y="384">light and dark, before any UI code.</text>'
        '<text x="70" y="412">The PWA matches: same tokens, states.</text></g>'
        + frames
        + cursor("cur1", "#F24E1E", "Design")
        + cursor("cur2", "#0D99FF", "Frontend")
        + cursor("cur3", "#0ACF83", "Backend")
        + '<g class="done"><rect x="450" y="466" width="136" height="30" rx="15" fill="#0ACF83"/><text x="518" y="486" text-anchor="middle" font-size="14" font-weight="800" fill="#06281B">Shipped as a PWA</text></g>'
    )
    return svg(w, h, body, css, c_defs)


# --- Devpost: the submission, section by section -------------------------------------------------------------------


def devpost():
    w, h = 1280, 420
    c_defs, c_body = card(w, h, "#06232C", "#0B3A47", "#00B8D4")
    css = """
.pill{opacity:0;transform-box:fill-box;transform-origin:center;animation:pill 9s cubic-bezier(.3,1.5,.5,1) infinite}
@keyframes pill{0%{opacity:0;transform:translateY(40px) scale(.6)}8%,86%{opacity:1;transform:none}94%,100%{opacity:0;transform:scale(.9)}}
.step{opacity:.35;animation:step 9s ease-in-out infinite}
@keyframes step{0%,2%{opacity:.35}8%,24%{opacity:1}30%,100%{opacity:.35}}
.bar{transform-box:fill-box;transform-origin:left;animation:bar 9s ease-in-out infinite}
@keyframes bar{0%{transform:scaleX(.04)}90%,100%{transform:scaleX(1)}}
.btn{animation:btn 9s ease-in-out infinite;transform-box:fill-box;transform-origin:center}
@keyframes btn{0%,76%{transform:scale(1)}82%{transform:scale(.94)}88%,100%{transform:scale(1)}}
"""
    tags = ["Databricks", "Genie", "Gemini", "ElevenLabs", "Figma", "Claude", "Next.js", "FastAPI"]
    colors = ["#FF3621", "#FF6A4D", "#6E9BFF", "#8B6CFF", "#A259FF", "#D97757", "#EDEDED", "#10B981"]
    pills, px, py = "", 470, 80
    for i, (t, c) in enumerate(zip(tags, colors, strict=True)):
        pw = 44 + len(t) * 12
        if px + pw > 1220:
            px, py = 470, py + 58
        pills += (
            f'<g class="pill" style="animation-delay:{i * 0.24:.2f}s"><g transform="translate({px},{py})"><rect width="{pw}" height="42" rx="21" fill="#fff" fill-opacity=".08" stroke="{c}" stroke-opacity=".8" stroke-width="1.6"/>'
            f'<circle cx="22" cy="21" r="6" fill="{c}"/><text x="38" y="27" font-size="18" font-weight="700" fill="#fff">{t}</text></g></g>'
        )
        px += pw + 14
    steps = ["The story", "Built with", "Try it out", "Demo video"]
    srows = "".join(
        f'<g class="step" style="animation-delay:{i * 2.2:.2f}s"><circle cx="{490 + i * 190}" cy="268" r="9" fill="#00B8D4"/>'
        f'<text x="{508 + i * 190}" y="274" font-size="18" font-weight="700" fill="#fff">{s}</text></g>'
        for i, s in enumerate(steps)
    )
    body = (
        c_body
        + logo_devpost(70, 70, 1.3)
        + '<text x="70" y="206" font-size="52" font-weight="900" fill="#fff" letter-spacing="-1">Devpost</text>'
        + '<text x="70" y="254" font-size="22" font-weight="600" fill="#9BE7F2">HackCamp 2026  ·  Databricks track</text>'
        + '<g font-size="17" font-weight="500" fill="#CDEFF4"><text x="70" y="304">One page for judges: what it does, what it is</text>'
        '<text x="70" y="332">built with, and how to try it in a minute.</text></g>'
        + pills
        + '<rect x="470" y="300" width="760" height="8" rx="4" fill="#fff" fill-opacity=".12"/><rect class="bar" x="470" y="300" width="760" height="8" rx="4" fill="#00B8D4"/>'
        + srows.replace('cy="268"', 'cy="346"').replace('y="274"', 'y="352"')
    )
    return svg(w, h, body, css, c_defs)


# --- Gemini: a receipt is scanned and its lines become items ----------------------------------------------------


def gemini_star(x, y, s_=1.0):
    return (
        f'<g transform="translate({x},{y}) scale({s_})"><path d="M30 0C30 16.5 43.5 30 60 30C43.5 30 30 43.5 30 60C30 43.5 16.5 30 0 30C16.5 30 30 16.5 30 0Z" fill="url(#gstar)"/></g>'
    )


def gemini():
    w, h = 1280, 480
    c_defs, c_body = card(w, h, "#0B1020", "#1A2147", "#4C7DFF")
    css = """
.paper{animation:paper 9s ease-in-out infinite}
@keyframes paper{0%{opacity:0;transform:translateY(40px)}8%,78%{opacity:1;transform:none}88%,100%{opacity:0;transform:translateY(-30px)}}
.scan{animation:scan 9s ease-in-out infinite}
@keyframes scan{0%,10%{transform:translateY(0);opacity:0}14%{opacity:1}44%{transform:translateY(300px);opacity:1}48%,100%{transform:translateY(300px);opacity:0}}
.ln{animation:ln 9s ease-in-out infinite}
@keyframes ln{0%,12%{fill:#CBD3F2}30%,46%{fill:#7FA6FF}60%,100%{fill:#CBD3F2}}
.out{opacity:0;animation:out 9s cubic-bezier(.3,1.4,.5,1) infinite}
@keyframes out{0%,34%{opacity:0;transform:translateX(-30px) scale(.85)}42%,82%{opacity:1;transform:none}90%,100%{opacity:0;transform:translateX(20px)}}
.spark{transform-box:fill-box;transform-origin:center;animation:spark 4s ease-in-out infinite}
@keyframes spark{0%,100%{transform:scale(1) rotate(0)}50%{transform:scale(1.14) rotate(45deg)}}
"""
    defs = c_defs + '<linearGradient id="gstar" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#4C7DFF"/><stop offset=".5" stop-color="#9B72F2"/><stop offset="1" stop-color="#F08FB8"/></linearGradient>'
    rows = [("Milk", "2%  ·  4 L", "#4C7DFF"), ("Eggs", "large  ·  12 ea", "#9B72F2"), ("Oats", "900 g", "#F08FB8"), ("Cheddar", "400 g", "#35D0A0")]
    chips = ""
    for i, (a, b, c) in enumerate(rows):
        y = 96 + i * 82
        chips += (
            f'<g class="out" style="animation-delay:{i * 0.22:.2f}s"><g transform="translate(790,{y})"><rect width="380" height="62" rx="16" fill="#fff" fill-opacity=".08" stroke="{c}" stroke-opacity=".9" stroke-width="1.6"/>'
            f'<circle cx="32" cy="31" r="9" fill="{c}"/><text x="56" y="28" font-size="21" font-weight="800" fill="#fff">{a}</text>'
            f'<text x="56" y="49" font-size="15" font-weight="600" fill="#B8C4F0">{b}</text></g></g>'
        )
    lines = "".join(
        f'<rect class="ln" x="{470 + 22}" y="{126 + i * 36}" width="{[170, 130, 150, 100, 160, 120, 140][i]}" height="10" rx="5" fill="#CBD3F2" style="animation-delay:{i * 0.12:.2f}s"/>'
        f'<rect x="{470 + 22 + 190}" y="{126 + i * 36}" width="{[44, 36, 40, 30, 44, 36, 40][i]}" height="10" rx="5" fill="#9AA8D8" fill-opacity=".7"/>'
        for i in range(7)
    )
    body = (
        c_body
        + f'<g class="spark">{gemini_star(70, 78, 1.35)}</g>'
        + '<text x="70" y="232" font-size="52" font-weight="800" fill="#fff" letter-spacing="-1">Gemini</text>'
        + '<text x="70" y="280" font-size="22" font-weight="600" fill="#B9C9FF">A second pair of eyes for receipts.</text>'
        + '<g font-size="17" font-weight="500" fill="#CBD3F2"><text x="70" y="330">Reads a receipt, a product photo,</text>'
        '<text x="70" y="358">or a line you typed, into items.</text>'
        '<text x="70" y="386">One setting: EXTRACTOR=gemini.</text></g>'
        + '<g class="paper"><g transform="translate(470,64)"><path d="M0 0h250v320l-16-10-16 10-16-10-16 10-16-10-16 10-16-10-16 10-16-10-16 10-16-10-16 10-16-10z" fill="#F4F6FF" fill-opacity=".1" stroke="#CBD3F2" stroke-opacity=".5" stroke-width="1.4"/>'
        '<text x="125" y="40" text-anchor="middle" font-size="16" font-weight="800" letter-spacing="3" fill="#E7ECFF">GROCERY</text></g>'
        + f'<g transform="translate(0,0)">{lines}</g>'
        + '<g class="scan"><rect x="458" y="100" width="274" height="3" rx="1.5" fill="#7FA6FF"/><rect x="458" y="100" width="274" height="26" fill="url(#scanfade)"/></g></g>'
        + chips
        + '<text x="790" y="76" font-size="15" font-weight="700" letter-spacing="3" fill="#9FB4FF" fill-opacity=".85">READ INTO ITEMS</text>'
    )
    defs += '<linearGradient id="scanfade" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#7FA6FF" stop-opacity=".45"/><stop offset="1" stop-color="#7FA6FF" stop-opacity="0"/></linearGradient>'
    return svg(w, h, body, css, defs)



def main():
    outputs = {
        "banner.svg": banner(),
        "rain-divider.svg": divider(),
        "phone-demo.svg": phone_demo(),
        "databricks.svg": databricks(),
        "elevenlabs.svg": elevenlabs(),
        "figma.svg": figma(),
        "devpost.svg": devpost(),
        "gemini.svg": gemini(),
    }
    for name, text in outputs.items():
        (HERE / name).write_text(text)
        print(f"{name:18} {len(text) // 1024:5d} KB")


if __name__ == "__main__":
    main()
