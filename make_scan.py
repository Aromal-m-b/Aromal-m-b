"""
Turn your photo into an animated, single-colour "digital scan" SVG.

Usage:
    python make_scan.py my_photo.jpg            # -> assets/scan-profile.svg
    python make_scan.py my_photo.jpg --color 00e5ff

Needs:  pip install pillow
"""
import argparse, base64, io, sys
from PIL import Image, ImageOps

SIZE = 400


def hex_to_rgb01(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def build_svg(photo_b64, color):
    r, g, b = hex_to_rgb01(color)
    c = f"#{color.lstrip('#')}"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{SIZE}" height="{SIZE}" viewBox="0 0 {SIZE} {SIZE}">
  <defs>
    <!-- single-colour (monochrome) look: luminance -> one hue -->
    <filter id="mono" color-interpolation-filters="sRGB">
      <feColorMatrix type="matrix" values="
        {r:.3f} {r:.3f} {r:.3f} 0 0
        {g:.3f} {g:.3f} {g:.3f} 0 0
        {b:.3f} {b:.3f} {b:.3f} 0 0
        0 0 0 1 0"/>
      <feComponentTransfer>
        <feFuncR type="linear" slope="1.5" intercept="-0.1"/>
        <feFuncG type="linear" slope="1.5" intercept="-0.1"/>
        <feFuncB type="linear" slope="1.5" intercept="-0.1"/>
      </feComponentTransfer>
    </filter>

    <pattern id="lines" width="4" height="4" patternUnits="userSpaceOnUse">
      <rect width="4" height="1.5" fill="#000" opacity="0.45"/>
    </pattern>

    <linearGradient id="beam" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{c}" stop-opacity="0"/>
      <stop offset="1" stop-color="{c}" stop-opacity="0.55"/>
    </linearGradient>

    <clipPath id="reveal">
      <rect x="0" y="0" width="{SIZE}" height="0">
        <animate attributeName="height" values="0;{SIZE};{SIZE};0;0"
                 keyTimes="0;0.45;0.55;0.56;1" dur="6s" repeatCount="indefinite"/>
      </rect>
    </clipPath>
    <clipPath id="frame"><rect x="20" y="20" width="360" height="360" rx="6"/></clipPath>
  </defs>

  <rect width="{SIZE}" height="{SIZE}" fill="#1a1a1a"/>

  <g clip-path="url(#frame)">
    <!-- faint base image -->
    <image href="data:image/jpeg;base64,{photo_b64}" x="20" y="20" width="360" height="360"
           preserveAspectRatio="xMidYMid slice" filter="url(#mono)" opacity="0.22"/>
    <!-- bright image, revealed by the scan -->
    <g clip-path="url(#reveal)">
      <image href="data:image/jpeg;base64,{photo_b64}" x="20" y="20" width="360" height="360"
             preserveAspectRatio="xMidYMid slice" filter="url(#mono)"/>
    </g>
    <rect x="20" y="20" width="360" height="360" fill="url(#lines)"/>

    <!-- scan beam -->
    <g>
      <rect x="20" y="-40" width="360" height="40" fill="url(#beam)"/>
      <rect x="20" y="-1.5" width="360" height="3" fill="{c}"/>
      <animateTransform attributeName="transform" type="translate"
        values="0 20; 0 380; 0 380; 0 20; 0 20" keyTimes="0;0.45;0.55;0.56;1"
        dur="6s" repeatCount="indefinite"/>
    </g>
  </g>

  <!-- corner brackets -->
  <g stroke="{c}" stroke-width="3" fill="none" stroke-linecap="square">
    <path d="M20 52 V20 H52"/><path d="M348 20 H380 V52"/>
    <path d="M20 348 V380 H52"/><path d="M348 380 H380 V348"/>
  </g>

  <!-- HUD text -->
  <g font-family="'Courier New', monospace" font-size="11" fill="{c}" letter-spacing="1.5">
    <text x="30" y="14">AROMAL-M-B // AI-ML</text>
    <text x="370" y="14" text-anchor="end">
      SCAN
      <animate attributeName="opacity" values="1;0.2;1" dur="1s" repeatCount="indefinite"/>
    </text>
    <text x="30" y="396">STATUS: <tspan>IDENTIFIED</tspan></text>
  </g>
</svg>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("--color", default="00ff9c", help="hex accent colour, no #")
    ap.add_argument("--out", default="assets/scan-profile.svg")
    a = ap.parse_args()

    img = Image.open(a.photo).convert("RGB")
    img = ImageOps.fit(img, (360, 360), Image.LANCZOS)
    img = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=2).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    b64 = base64.b64encode(buf.getvalue()).decode()

    with open(a.out, "w", encoding="utf-8") as f:
        f.write(build_svg(b64, a.color))
    print(f"wrote {a.out}  ({len(b64) // 1024} KB image)")


if __name__ == "__main__":
    sys.exit(main())
