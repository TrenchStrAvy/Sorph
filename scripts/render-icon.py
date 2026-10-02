#!/usr/bin/env python3
"""Render launcher/icon.png: the Sorph orb on a white macOS icon square.

Matches Singe's icon: the same 824 px body inset 100 px in a 1024 canvas (radius 185),
white to #F2F3F7 gradient and soft shadow. The orb comes from docs/logo.png, sized
588 px (picked side by side with Singe's 680 px glass bar), with its shadows deepened
so its blacks are as intense as Singe's.

    .venv/bin/python scripts/render-icon.py            # writes launcher/icon.png
"""

import os
import sys

import numpy as np
import Quartz as Q
from AppKit import NSBitmapImageRep, NSImage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "docs", "logo.png")
OUT = os.path.join(ROOT, "launcher", "icon.png")

SIZE = 1024
ORB = 588                 # orb diameter, px of 1024
BLACK_POINT = 0.065       # tones at or below this become black (Singe's bar reaches ~0.03)
SHADOW_GAMMA = 1.12       # a gentle extra push in the darks; highlights stay put


def load_rgba(path):
    rep = NSBitmapImageRep.imageRepWithData_(NSImage.alloc().initWithContentsOfFile_(path).TIFFRepresentation())
    w, h = rep.pixelsWide(), rep.pixelsHigh()
    out = np.zeros((h, w, 4), dtype=np.float64)
    data = np.frombuffer(rep.bitmapData().tobytes(), dtype=np.uint8)
    spp, bpr = rep.samplesPerPixel(), rep.bytesPerRow()
    rows = data[: bpr * h].reshape(h, bpr)[:, : w * spp].reshape(h, w, spp) / 255.0
    out[..., :3] = rows[..., :3]
    out[..., 3] = rows[..., 3] if spp == 4 else 1.0
    return out


def sphere_crop(img):
    """The orb is the non-white part of logo.png; crop to its bounding square."""
    dark = img[..., :3].sum(axis=2) < 3 * 0.925
    ys, xs = np.where(dark)
    size = max(xs.max() - xs.min(), ys.max() - ys.min())
    cx, cy = (xs.min() + xs.max()) // 2, (ys.min() + ys.max()) // 2
    half = size // 2
    return img[cy - half: cy + half, cx - half: cx + half]


def deepen(rgb):
    """Levels with a black point, then a light gamma on the shadows only."""
    x = np.clip((rgb - BLACK_POINT) / (1 - BLACK_POINT), 0, 1)
    shadows = x ** SHADOW_GAMMA
    w = np.clip(x / 0.5, 0, 1)                  # blend back to linear above the midtones
    return shadows * (1 - w) + x * w


def to_cgimage(rgba):
    h, w = rgba.shape[:2]
    premul = rgba.copy()
    premul[..., :3] *= premul[..., 3:4]
    buf = (np.clip(premul, 0, 1) * 255).astype(np.uint8).tobytes()
    provider = Q.CGDataProviderCreateWithData(None, buf, len(buf), None)
    return Q.CGImageCreate(w, h, 8, 32, w * 4, Q.CGColorSpaceCreateWithName(Q.kCGColorSpaceSRGB),
                           Q.kCGImageAlphaPremultipliedLast, provider, None, True, Q.kCGRenderingIntentDefault), buf


def main():
    orb = sphere_crop(load_rgba(SRC))
    orb[..., :3] = deepen(orb[..., :3])
    # circular mask, so the white corners of logo.png never show
    n = orb.shape[0]
    yy, xx = np.mgrid[0:n, 0:n]
    r = np.hypot(xx - n / 2 + 0.5, yy - n / 2 + 0.5) / (n / 2)
    orb[..., 3] = np.clip((1 - r) * n / 2, 0, 1)
    orb_img, _keep = to_cgimage(orb)

    cs = Q.CGColorSpaceCreateWithName(Q.kCGColorSpaceSRGB)
    ctx = Q.CGBitmapContextCreate(None, SIZE, SIZE, 8, 0, cs, Q.kCGImageAlphaPremultipliedLast)
    body = Q.CGRectMake(100, 100, 824, 824)
    path = Q.CGPathCreateWithRoundedRect(body, 185, 185, None)

    Q.CGContextSaveGState(ctx)
    Q.CGContextSetShadowWithColor(ctx, (0, -8), 24, Q.CGColorCreateSRGB(0, 0, 0, 0.22))
    Q.CGContextAddPath(ctx, path)
    Q.CGContextSetRGBFillColor(ctx, 1, 1, 1, 1)
    Q.CGContextFillPath(ctx)
    Q.CGContextRestoreGState(ctx)

    Q.CGContextSaveGState(ctx)
    Q.CGContextAddPath(ctx, path)
    Q.CGContextClip(ctx)
    grad = Q.CGGradientCreateWithColorComponents(cs, (1, 1, 1, 1, 0.95, 0.955, 0.97, 1), (0, 1), 2)
    Q.CGContextDrawLinearGradient(ctx, grad, (512, 924), (512, 100), 0)
    # the orb with a soft contact shadow, like the bar in Singe's icon
    orb_rect = Q.CGRectMake(512 - ORB / 2, 512 - ORB / 2, ORB, ORB)
    Q.CGContextSetShadowWithColor(ctx, (0, -14), 30, Q.CGColorCreateSRGB(0.08, 0.09, 0.2, 0.35))
    Q.CGContextDrawImage(ctx, orb_rect, orb_img)
    Q.CGContextRestoreGState(ctx)

    image = Q.CGBitmapContextCreateImage(ctx)
    rep = NSBitmapImageRep.alloc().initWithCGImage_(image)
    rep.representationUsingType_properties_(4, None).writeToFile_atomically_(OUT, True)
    print(f"wrote {OUT} (orb {ORB} px, black point {BLACK_POINT})")


if __name__ == "__main__":
    sys.exit(main())
