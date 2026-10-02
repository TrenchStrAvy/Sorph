"""Startup splash: a white card in the style of macOS "About This Mac", with the
Sorph orb (in Singe's glass), the name, a caption and a thin progress bar in black, shown while
Sorph loads its speech model, then faded away once dictation is ready.
Sized like a small Terminal window (410 × 202 pt); Singe uses the same card.

Gives the launcher click immediate visible feedback (think FL Studio's
splash) instead of several silent seconds before the mic icon appears.
Pure Cocoa via pyobjc, same look as the recording pill in overlay.py.

Public methods are safe to call from any thread.
"""

import os
import time

import objc
from AppKit import (
    NSAffineTransform,
    NSBackingStoreBuffered,
    NSBezierPath,
    NSColor,
    NSFont,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSGraphicsContext,
    NSImage,
    NSScreen,
    NSShadow,
    NSStatusWindowLevel,
    NSView,
    NSWindow,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorStationary,
    NSWindowStyleMaskBorderless,
)
from Foundation import (NSMakePoint, NSMakeRect, NSMakeSize, NSObject,
                        NSString, NSTimer)
from PyObjCTools import AppHelper


CARD_W, CARD_H = 410, 202    # a small Terminal window without its title bar
CORNER_RADIUS = 12           # like a macOS window
PAD = 30                     # transparent margin so the shadow isn't clipped
LOGO = 64                    # the orb, drawn above the name
LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "launcher", "orb.png")
BAR_W, BAR_H = 240, 4
TICK_SEC = 1 / 60
FADE_SEC = 0.35
HOLD_SEC = 0.45              # show "ready" briefly before fading
CREEP = 0.06                 # per-second drift toward the stage target


class SplashView(NSView):

    def initWithFrame_(self, frame):
        self = objc.super(SplashView, self).initWithFrame_(frame)
        if self is None:
            return None
        self.progress = 0.0
        self.target = 0.08
        self.caption = "starting…"
        self.alpha = 1.0
        self.logo = (NSImage.alloc().initWithContentsOfFile_(LOGO_PATH)
                     if os.path.exists(LOGO_PATH) else None)
        return self

    def isFlipped(self):
        return False

    def drawRect_(self, rect):
        W, H = CARD_W, CARD_H
        ctx = NSGraphicsContext.currentContext()
        ctx.saveGraphicsState()
        xf = NSAffineTransform.transform()
        xf.translateXBy_yBy_(PAD, PAD)
        xf.concat()

        # the white card, with a soft shadow and a hairline border
        card = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(0, 0, W, H), CORNER_RADIUS, CORNER_RADIUS)
        ctx.saveGraphicsState()
        shadow = NSShadow.alloc().init()
        shadow.setShadowColor_(NSColor.colorWithCalibratedWhite_alpha_(0.0, 0.28))
        shadow.setShadowBlurRadius_(22)
        shadow.setShadowOffset_(NSMakeSize(0, -8))
        shadow.set()
        NSColor.whiteColor().setFill()
        card.fill()
        ctx.restoreGraphicsState()
        NSColor.colorWithCalibratedWhite_alpha_(0.0, 0.12).setStroke()
        card.setLineWidth_(1.0)
        card.stroke()

        ink = NSColor.colorWithSRGBRed_green_blue_alpha_(0.07, 0.075, 0.09, 1.0)

        # vertical rhythm: orb 64, gap 12, title, gap 4, caption, gap 20, bar 4, centred
        logo_y = H - 27 - LOGO
        if self.logo is not None:
            # the orb in Singe's glass (launcher/orb.png), edge to edge
            self.logo.drawInRect_fromRect_operation_fraction_(
                NSMakeRect((W - LOGO) / 2, logo_y, LOGO, LOGO), NSMakeRect(0, 0, 0, 0), 2, 1.0)

        title_attrs = {
            NSFontAttributeName: NSFont.systemFontOfSize_weight_(22, 0.56),
            NSForegroundColorAttributeName: ink,
        }
        title = NSString.stringWithString_("Sorph")
        ts = title.sizeWithAttributes_(title_attrs)
        title_y = logo_y - 12 - ts.height
        title.drawAtPoint_withAttributes_(
            NSMakePoint((W - ts.width) / 2, title_y), title_attrs)

        cap_attrs = {
            NSFontAttributeName: NSFont.systemFontOfSize_(12),
            NSForegroundColorAttributeName: ink.colorWithAlphaComponent_(0.55),
        }
        cap = NSString.stringWithString_(self.caption)
        cs = cap.sizeWithAttributes_(cap_attrs)
        cap_y = title_y - 4 - cs.height
        cap.drawAtPoint_withAttributes_(
            NSMakePoint((W - cs.width) / 2, cap_y), cap_attrs)

        # progress track + fill
        x0, y0 = (W - BAR_W) / 2, cap_y - 20 - BAR_H
        track = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(x0, y0, BAR_W, BAR_H), BAR_H / 2, BAR_H / 2)
        ink.colorWithAlphaComponent_(0.10).setFill()
        track.fill()
        fw = max(BAR_H, BAR_W * min(1.0, self.progress))
        fill = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(x0, y0, fw, BAR_H), BAR_H / 2, BAR_H / 2)
        ink.setFill()
        fill.fill()
        ctx.restoreGraphicsState()


class Splash(NSObject):

    def init(self):
        self = objc.super(Splash, self).init()
        if self is None:
            return None
        rect = NSMakeRect(0, 0, CARD_W + 2 * PAD, CARD_H + 2 * PAD)
        self.view = SplashView.alloc().initWithFrame_(rect)
        self.window = NSWindow.alloc(
        ).initWithContentRect_styleMask_backing_defer_(
            rect, NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False)
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(NSColor.clearColor())
        self.window.setHasShadow_(False)   # we draw our own, softer one
        self.window.setLevel_(NSStatusWindowLevel)
        self.window.setIgnoresMouseEvents_(True)
        self.window.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary)
        self.window.setContentView_(self.view)

        screen = NSScreen.mainScreen()
        if screen is not None:
            f = screen.frame()
            self.window.setFrameOrigin_(NSMakePoint(
                f.origin.x + (f.size.width - CARD_W) / 2 - PAD,
                f.origin.y + (f.size.height - CARD_H) / 2 + 40 - PAD))

        self.timer = None
        self.last_tick = time.time()
        self.fade_started = None
        self.done_at = None
        return self

    # -- public, any thread

    def show(self):
        AppHelper.callAfter(self._show)

    def set_stage(self, caption, target):
        """Update caption and the progress the bar should approach (0-1)."""
        AppHelper.callAfter(self._set_stage, caption, float(target))

    def finish(self, caption="ready — hold Right-Option to dictate"):
        """Fill the bar, hold briefly, fade out, close."""
        AppHelper.callAfter(self._finish, caption)

    # -- main thread

    def _show(self):
        self.window.setAlphaValue_(0.0)
        self.window.orderFrontRegardless()
        self.fade_in_started = time.time()
        self._ensure_timer()

    @objc.python_method
    def _set_stage(self, caption, target):
        self.view.caption = caption
        self.view.target = max(self.view.target, target)
        self.view.setNeedsDisplay_(True)

    @objc.python_method
    def _finish(self, caption):
        self.view.caption = caption
        self.view.target = 1.0
        self.done_at = time.time()
        self.view.setNeedsDisplay_(True)

    def _ensure_timer(self):
        if self.timer is None:
            self.timer = (
                NSTimer.
                scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                    TICK_SEC, self, b"tick:", None, True))

    def tick_(self, _timer):
        now = time.time()
        dt = min(0.1, now - self.last_tick)
        self.last_tick = now
        v = self.view

        # progress eases toward its target; between stages it creeps a
        # little so the bar never looks frozen during a long model load
        gap = v.target - v.progress
        if self.done_at is not None:
            v.progress = min(1.0, v.progress + max(gap * 8.0, 1.2) * dt)
        elif gap > 0.001:
            v.progress += gap * 4.0 * dt
        else:
            v.target = min(v.target + CREEP * dt, 0.93)

        # fade in
        alpha = min(1.0, (now - self.fade_in_started) / 0.2)
        # hold on "ready", then fade out and close
        if self.done_at is not None and v.progress >= 0.999:
            if now - self.done_at >= HOLD_SEC:
                if self.fade_started is None:
                    self.fade_started = now
                alpha = max(0.0, 1.0 - (now - self.fade_started) / FADE_SEC)
                if alpha <= 0.0:
                    self.timer.invalidate()
                    self.timer = None
                    self.window.orderOut_(None)
                    return
        self.window.setAlphaValue_(alpha)
        v.setNeedsDisplay_(True)


def create_splash():
    """Main thread only; the caller must run AppHelper.runEventLoop()."""
    return Splash.alloc().init()
