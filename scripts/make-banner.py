#!/usr/bin/env python3
"""Regenerate the local-ai README banner and logo.

Renders hand-authored SVG (abstract node/network artwork) to PNG via headless
Chrome, since this box has no rsvg/cairosvg/inkscape available.

Usage:
    python3 scripts/make-banner.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "assets"

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("chromium"),
    shutil.which("google-chrome"),
]

BG = "#05070f"

# --- palette -----------------------------------------------------------
CYAN = "#38bdf8"
VIOLET = "#a78bfa"
MINT = "#34d399"
CLOUD = "#f0abfc"

BANNER_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 1600 400">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#070912"/>
      <stop offset="55%" stop-color="#0b0f1f"/>
      <stop offset="100%" stop-color="#121a33"/>
    </linearGradient>
    <linearGradient id="aiText" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{cyan}"/>
      <stop offset="55%" stop-color="{violet}"/>
      <stop offset="100%" stop-color="{mint}"/>
    </linearGradient>
    <radialGradient id="glowCyan" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="{cyan}" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="{cyan}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glowViolet" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="{violet}" stop-opacity="0.5"/>
      <stop offset="100%" stop-color="{violet}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glowMint" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="{mint}" stop-opacity="0.45"/>
      <stop offset="100%" stop-color="{mint}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="fabric" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{cyan}"/>
      <stop offset="100%" stop-color="{violet}"/>
    </linearGradient>
    <filter id="blurSoft" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="14"/>
    </filter>
    <filter id="blurTiny" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="2.2"/>
    </filter>
    <filter id="blurNode" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="5"/>
    </filter>
  </defs>

  <rect width="1600" height="400" fill="url(#bg)"/>

  <g stroke="#7dd3fc" stroke-opacity="0.05" stroke-width="1">
    <path d="M0,40 H1600 M0,80 H1600 M0,120 H1600 M0,160 H1600 M0,200 H1600 M0,240 H1600 M0,280 H1600 M0,320 H1600 M0,360 H1600"/>
    <path d="M40,0 V400 M120,0 V400 M200,0 V400 M280,0 V400 M360,0 V400 M440,0 V400 M520,0 V400 M600,0 V400 M680,0 V400 M760,0 V400 M840,0 V400 M920,0 V400 M1000,0 V400 M1080,0 V400 M1160,0 V400 M1240,0 V400 M1320,0 V400 M1400,0 V400 M1480,0 V400 M1560,0 V400"/>
  </g>

  <ellipse cx="980" cy="150" rx="260" ry="200" fill="url(#glowCyan)"/>
  <ellipse cx="1320" cy="260" rx="260" ry="220" fill="url(#glowViolet)"/>
  <ellipse cx="700" cy="320" rx="220" ry="160" fill="url(#glowMint)"/>

  <g id="mesh">
    <g stroke="#8fb8ff" stroke-opacity="0.14" stroke-width="1.2" fill="none">
      <path d="M640,90 L760,150 L900,80 L1040,140 L1180,70 L1320,130 L1460,80"/>
      <path d="M660,330 L800,270 L940,340 L1090,260 L1230,330 L1380,270 L1500,320"/>
      <path d="M760,150 L800,270"/>
      <path d="M900,80 L940,340" stroke-opacity="0.08"/>
      <path d="M1040,140 L1090,260"/>
      <path d="M1180,70 L1230,330" stroke-opacity="0.08"/>
      <path d="M1320,130 L1380,270"/>
      <path d="M700,220 L1500,210" stroke-opacity="0.08"/>
    </g>

    <g fill="#8fb8ff">
      <circle cx="640" cy="90" r="4" opacity="0.55"/>
      <circle cx="760" cy="150" r="4" opacity="0.6"/>
      <circle cx="900" cy="80" r="4" opacity="0.55"/>
      <circle cx="1040" cy="140" r="4" opacity="0.6"/>
      <circle cx="1180" cy="70" r="4" opacity="0.55"/>
      <circle cx="1320" cy="130" r="4" opacity="0.6"/>
      <circle cx="1460" cy="80" r="4" opacity="0.55"/>
      <circle cx="1580" cy="150" r="3.5" opacity="0.5"/>
      <circle cx="660" cy="330" r="4" opacity="0.55"/>
      <circle cx="800" cy="270" r="4" opacity="0.6"/>
      <circle cx="940" cy="340" r="4" opacity="0.55"/>
      <circle cx="1090" cy="260" r="4" opacity="0.6"/>
      <circle cx="1230" cy="330" r="4" opacity="0.55"/>
      <circle cx="1380" cy="270" r="4" opacity="0.6"/>
      <circle cx="1500" cy="320" r="4" opacity="0.55"/>
      <circle cx="1590" cy="360" r="3.5" opacity="0.5"/>
      <circle cx="1560" cy="40" r="3.5" opacity="0.45"/>
      <circle cx="600" cy="370" r="3.5" opacity="0.4"/>
    </g>

    <g id="cloud">
      <path d="M1250,205 C1380,140 1420,150 1470,175" stroke="{cloud}" stroke-opacity="0.28" stroke-width="1.6" fill="none" stroke-dasharray="2 6"/>
      <circle cx="1470" cy="175" r="20" fill="url(#glowViolet)" filter="url(#blurSoft)" opacity="0.7"/>
      <circle cx="1470" cy="175" r="9" fill="none" stroke="{cloud}" stroke-width="1.6" stroke-opacity="0.75"/>
      <circle cx="1470" cy="175" r="3.5" fill="#f5d0fe"/>
    </g>

    <g id="localCluster">
      <line x1="905" y1="205" x2="960" y2="175" stroke="#60d6ff" stroke-width="2" stroke-opacity="0.55"/>
      <line x1="905" y1="205" x2="955" y2="235" stroke="#60d6ff" stroke-width="2" stroke-opacity="0.55"/>
      <line x1="960" y1="175" x2="955" y2="235" stroke="#60d6ff" stroke-width="2" stroke-opacity="0.4"/>
      <circle cx="960" cy="175" r="7" fill="{cyan}" filter="url(#blurNode)"/>
      <circle cx="955" cy="235" r="7" fill="{cyan}" filter="url(#blurNode)"/>
      <circle cx="905" cy="205" r="11" fill="#7fe3ff"/>
      <circle cx="960" cy="175" r="6" fill="#bff0ff"/>
      <circle cx="955" cy="235" r="6" fill="#bff0ff"/>
      <circle cx="905" cy="205" r="5" fill="#ffffff"/>
    </g>

    <g>
      <line x1="1000" y1="205" x2="1250" y2="205" stroke="url(#fabric)" stroke-width="5" stroke-linecap="round" filter="url(#blurTiny)"/>
      <line x1="1000" y1="205" x2="1250" y2="205" stroke="url(#fabric)" stroke-width="2" stroke-linecap="round"/>
      <g stroke="#cdeeff" stroke-width="2" stroke-opacity="0.8">
        <line x1="1050" y1="195" x2="1050" y2="215"/>
        <line x1="1090" y1="195" x2="1090" y2="215"/>
        <line x1="1130" y1="195" x2="1130" y2="215"/>
        <line x1="1170" y1="195" x2="1170" y2="215"/>
        <line x1="1210" y1="195" x2="1210" y2="215"/>
      </g>
    </g>

    <g id="sparkA">
      <circle cx="1000" cy="205" r="34" fill="url(#glowViolet)" filter="url(#blurSoft)"/>
      <circle cx="1000" cy="205" r="21" fill="none" stroke="{violet}" stroke-width="2" stroke-opacity="0.7"/>
      <circle cx="1000" cy="205" r="14" fill="#c4b5fd"/>
      <circle cx="1000" cy="205" r="6" fill="#ffffff"/>
    </g>
    <g id="sparkB">
      <circle cx="1250" cy="205" r="34" fill="url(#glowMint)" filter="url(#blurSoft)"/>
      <circle cx="1250" cy="205" r="21" fill="none" stroke="{mint}" stroke-width="2" stroke-opacity="0.7"/>
      <circle cx="1250" cy="205" r="14" fill="#86efac"/>
      <circle cx="1250" cy="205" r="6" fill="#ffffff"/>
    </g>

    <circle cx="1000" cy="205" r="46" fill="none" stroke="{violet}" stroke-opacity="0.25" stroke-width="1"/>
    <circle cx="1250" cy="205" r="46" fill="none" stroke="{mint}" stroke-opacity="0.25" stroke-width="1"/>
  </g>

  <g>
    <text x="90" y="196" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-weight="700" font-size="86" letter-spacing="-2">
      <tspan fill="#f5f7fb">local</tspan><tspan fill="#5b6472">-</tspan><tspan fill="url(#aiText)">ai</tspan>
    </text>
    <rect x="92" y="222" width="230" height="2.5" fill="{cyan}" opacity="0.55"/>
    <text x="92" y="256" font-family="Menlo, Consolas, monospace" font-size="19" letter-spacing="1.5" fill="#8b96ad">
      self-hosted &#183; dual-GPU cluster &#183; always-on
    </text>
  </g>
</svg>
""".format(w=3200, h=800, cyan=CYAN, violet=VIOLET, mint=MINT, cloud=CLOUD)

LOGO_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 512 512">
  <defs>
    <radialGradient id="bgGlow" cx="50%" cy="42%" r="65%">
      <stop offset="0%" stop-color="#182449"/>
      <stop offset="55%" stop-color="#0c1226"/>
      <stop offset="100%" stop-color="#05070f"/>
    </radialGradient>
    <linearGradient id="ring" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{cyan}"/>
      <stop offset="50%" stop-color="{violet}"/>
      <stop offset="100%" stop-color="{mint}"/>
    </linearGradient>
    <linearGradient id="hexStroke" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#7dd3fc"/>
      <stop offset="100%" stop-color="#c4b5fd"/>
    </linearGradient>
    <filter id="glowBlur" x="-80%" y="-80%" width="260%" height="260%">
      <feGaussianBlur stdDeviation="10"/>
    </filter>
    <filter id="glowBlurBig" x="-100%" y="-100%" width="300%" height="300%">
      <feGaussianBlur stdDeviation="26"/>
    </filter>
  </defs>

  <rect x="0" y="0" width="512" height="512" rx="112" fill="url(#bgGlow)"/>
  <rect x="10" y="10" width="492" height="492" rx="104" fill="none" stroke="#ffffff" stroke-opacity="0.06" stroke-width="2"/>

  <polygon points="256,90 372,158 372,294 256,362 140,294 140,158"
           fill="none" stroke="url(#hexStroke)" stroke-width="6" stroke-opacity="0.85"/>
  <polygon points="256,90 372,158 372,294 256,362 140,294 140,158"
           fill="none" stroke="url(#hexStroke)" stroke-width="14" stroke-opacity="0.15"/>

  <g stroke="#9fb3d9" stroke-width="5" stroke-opacity="0.6" stroke-linecap="round">
    <line x1="256" y1="90" x2="256" y2="60"/>
    <line x1="140" y1="158" x2="112" y2="142"/>
    <line x1="140" y1="294" x2="112" y2="310"/>
    <line x1="256" y1="362" x2="256" y2="392"/>
    <line x1="372" y1="294" x2="400" y2="310"/>
    <line x1="372" y1="158" x2="400" y2="142"/>
  </g>
  <g fill="#c7d6f5" opacity="0.8">
    <circle cx="256" cy="60" r="5"/>
    <circle cx="112" cy="142" r="5"/>
    <circle cx="112" cy="310" r="5"/>
    <circle cx="256" cy="392" r="5"/>
    <circle cx="400" cy="310" r="5"/>
    <circle cx="400" cy="142" r="5"/>
  </g>

  <circle cx="256" cy="226" r="120" fill="url(#ring)" opacity="0.16" filter="url(#glowBlurBig)"/>

  <g>
    <line x1="256" y1="168" x2="204" y2="256" stroke="url(#ring)" stroke-width="6"/>
    <line x1="256" y1="168" x2="308" y2="256" stroke="url(#ring)" stroke-width="6"/>
  </g>

  <g>
    <circle cx="256" cy="168" r="26" fill="{cyan}" filter="url(#glowBlur)" opacity="0.9"/>
    <circle cx="204" cy="256" r="26" fill="{violet}" filter="url(#glowBlur)" opacity="0.9"/>
    <circle cx="308" cy="256" r="26" fill="{mint}" filter="url(#glowBlur)" opacity="0.9"/>
  </g>
  <g>
    <circle cx="256" cy="168" r="17" fill="#bff0ff"/>
    <circle cx="204" cy="256" r="17" fill="#e4d9ff"/>
    <circle cx="308" cy="256" r="17" fill="#c3f7d8"/>
    <circle cx="256" cy="168" r="7" fill="#ffffff"/>
    <circle cx="204" cy="256" r="7" fill="#ffffff"/>
    <circle cx="308" cy="256" r="7" fill="#ffffff"/>
  </g>
</svg>
""".format(w=1024, h=1024, cyan=CYAN, violet=VIOLET, mint=MINT)


def find_chrome() -> str:
    for candidate in CHROME_CANDIDATES:
        if candidate and Path(candidate).exists():
            return candidate
    raise SystemExit("No Chrome/Chromium binary found for headless rendering.")


def render(chrome: str, svg: str, out_png: Path, width: int, height: int, bg: str = BG) -> None:
    html_path = out_png.with_suffix(".render.html")
    html_path.write_text(
        f"<!DOCTYPE html><html><head><style>"
        f"html,body{{margin:0;padding:0;background:{bg};}}"
        f"</style></head><body>{svg}</body></html>"
    )
    subprocess.run(
        [
            chrome,
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--screenshot={out_png}",
            f"--window-size={width},{height}",
            f"file://{html_path}",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    html_path.unlink()


def to_jpg(png_path: Path, jpg_path: Path) -> None:
    subprocess.run(
        [
            "sips",
            "-s",
            "format",
            "jpeg",
            "-s",
            "formatOptions",
            "90",
            str(png_path),
            "--out",
            str(jpg_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> None:
    chrome = find_chrome()
    ASSETS.mkdir(exist_ok=True)

    banner_png = ASSETS / "local-ai-banner.png"
    logo_png = ASSETS / "local-ai-logo.png"
    banner_jpg = ASSETS / "local-ai-banner.jpg"

    render(chrome, BANNER_SVG, banner_png, 3200, 800)
    render(chrome, LOGO_SVG, logo_png, 1024, 1024)
    to_jpg(banner_png, banner_jpg)

    print(f"wrote {banner_png}")
    print(f"wrote {logo_png}")
    print(f"wrote {banner_jpg}")


if __name__ == "__main__":
    if sys.platform != "darwin":
        print("warning: JPEG conversion uses macOS `sips`; skip on other platforms", file=sys.stderr)
    main()
