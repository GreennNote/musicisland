import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import sys
import os
import random
import math
import time
import threading
import importlib

# Top-level imports so PyInstaller can detect and bundle these packages
# in onefile builds (importlib.import_module is invisible to PyInstaller).
try:
    import dxcam as _dxcam_hint  # type: ignore  # noqa: F401
except Exception:
    pass
try:
    import mss as _mss_hint  # noqa: F401
except Exception:
    pass


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def app_relative_path(relative_path):
    """Path relative to the app location (script dir or frozen exe dir)."""
    try:
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, relative_path)
    except Exception:
        return os.path.join(os.path.abspath('.'), relative_path)


def load_cover_asset_path():
    
    candidates = [
        app_relative_path('load.PNG'),
        app_relative_path('load.png'),
        resource_path('load.PNG'),
        resource_path('load.png'),
    ]
    for p in candidates:
        try:
            if os.path.exists(p):
                return p
        except Exception:
            pass
    return app_relative_path('load.PNG')


def load_drag_asset_path():
    """Resolve drag button icon path for dev and onefile builds."""
    candidates = [
        app_relative_path('drag.png'),
        resource_path('drag.png'),
    ]
    for p in candidates:
        try:
            if os.path.exists(p):
                return p
        except Exception:
            pass
    return app_relative_path('drag.png')


def load_font_asset_path():
    """Resolve island.ttf path for dev and onefile builds."""
    candidates = [
        app_relative_path('island.ttf'),
        resource_path('island.ttf'),
    ]
    for p in candidates:
        try:
            if os.path.exists(p):
                return p
        except Exception:
            pass
    return app_relative_path('island.ttf')


def load_inverted_png_icon(path: str, target: 'QSize' = None) -> 'QPixmap':
    """Load PNG and invert RGB channels while preserving alpha transparency."""
    try:
        pm = QPixmap(path)
        if pm.isNull():
            return QPixmap()
        img = pm.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        try:
            img.invertPixels(QImage.InvertMode.InvertRgb)
        except Exception:
            w = img.width()
            h = img.height()
            for y in range(h):
                for x in range(w):
                    c = img.pixelColor(x, y)
                    img.setPixelColor(x, y, QColor(255 - c.red(), 255 - c.green(), 255 - c.blue(), c.alpha()))
        out = QPixmap.fromImage(img)
        if target is not None and target.width() > 0 and target.height() > 0:
            out = out.scaled(target, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        return out
    except Exception:
        return QPixmap()


def user_data_path(filename):
    """Return a writable per-user path for persistent app data."""
    try:
        if sys.platform == 'win32':
            base_dir = os.path.join(os.getenv('APPDATA') or os.path.expanduser('~'), 'Music Island')
        else:
            base_dir = os.path.join(os.path.expanduser('~'), '.music_island')
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, filename)
    except Exception:
        return os.path.join(os.path.abspath('.'), filename)


def get_config_path():
    """Return the canonical settings.json path under APPDATA/MusicIsland."""
    base = os.getenv("APPDATA")
    if not base:
        base = os.path.expanduser('~')
    path = os.path.join(base, "MusicIsland")
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, "settings.json")

from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel,
    QVBoxLayout, QHBoxLayout, QFileDialog,
    QListWidget, QListWidgetItem, QSlider, QSizePolicy, QLineEdit, QScrollBar,
    QButtonGroup, QRadioButton, QGroupBox, QDialog, QGraphicsOpacityEffect,
    QStyleOptionSlider, QStyle
)

from PyQt6.QtCore import Qt, QUrl, QPoint, QRect, QRectF, QPointF, QPropertyAnimation, QEasingCurve, QSize, QEvent, QTimer, pyqtSignal, QVariantAnimation, QObject
from PyQt6.QtGui import QPainter, QPolygon, QColor, QPixmap, QLinearGradient, QRadialGradient, QPainterPath, QMouseEvent, QCursor, QGuiApplication, QImage, QFontDatabase, QIcon, QRegion, QFont, QFontMetrics
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices

from mutagen.id3 import ID3, APIC


def _enable_win10_blur_behind(hwnd):
    """Enable acrylic/blur-behind effect on a Windows 10+ window using SetWindowCompositionAttribute."""
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        import ctypes.wintypes as wt

        class ACCENTPOLICY(ctypes.Structure):
            _fields_ = [
                ('AccentState', ctypes.c_uint),
                ('AccentFlags', ctypes.c_uint),
                ('GradientColor', ctypes.c_uint),
                ('AnimationId', ctypes.c_uint),
            ]

        class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
            _fields_ = [
                ('Attribute', ctypes.c_uint),
                ('Data', ctypes.POINTER(ACCENTPOLICY)),
                ('SizeOfData', ctypes.c_size_t),
            ]

        # AccentState: 3 = ACCENT_ENABLE_BLURBEHIND, 4 = ACCENT_ENABLE_ACRYLICBLURBEHIND
        # GradientColor: AABBGGRR format — semi-transparent dark tint
        accent = ACCENTPOLICY()
        accent.AccentState = 3  # blur behind
        accent.AccentFlags = 2  # ACCENT_FLAG_DRAW_LEFT_BORDER etc.
        accent.GradientColor = 0x01000000  # nearly transparent black tint

        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = 19  # WCA_ACCENT_POLICY
        data.Data = ctypes.pointer(accent)
        data.SizeOfData = ctypes.sizeof(accent)

        user32 = ctypes.windll.user32
        user32.SetWindowCompositionAttribute(int(hwnd), ctypes.byref(data))
    except Exception:
        pass


class EdgeEnvironmentSampler:
    """Capture thin strips around the app window and expose sampled colors for glass reflections."""

    def __init__(self, fps: int = 15, thickness: int = 28, outward_offset: int = 4, smoothing: float = 0.22):
        self.fps = max(5, int(fps))
        self.thickness = max(8, int(thickness))
        self.outward_offset = max(1, int(outward_offset))
        self.smoothing = max(0.01, min(1.0, float(smoothing)))
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._window_rect = QRect(0, 0, 1, 1)
        self._virtual_rect = QRect(-32768, -32768, 65536, 65536)
        self._front = {
            'top': QColor(255, 255, 255),
            'bottom': QColor(255, 255, 255),
            'left': QColor(255, 255, 255),
            'right': QColor(255, 255, 255),
            'stamp': 0.0,
        }
        self._backend = None
        self._dxcam = None
        self._mss = None

    def _average_image_color(self, img) -> QColor:
        """Extract the average of all saturated pixels from the image.
        Most UI pixels are gray; find the colorful ones and average those."""
        try:
            if img is None or img.isNull():
                return QColor(255, 255, 255)
            w = img.width()
            h = img.height()
            if w <= 0 or h <= 0:
                return QColor(255, 255, 255)
            step_x = max(1, w // 10)
            step_y = max(1, h // 10)
            sat_r = sat_g = sat_b = sat_cnt = 0
            all_r = all_g = all_b = all_cnt = 0
            for y in range(0, h, step_y):
                for x in range(0, w, step_x):
                    argb = img.pixel(x, y)
                    r = (argb >> 16) & 0xFF
                    g = (argb >> 8) & 0xFF
                    b = argb & 0xFF
                    all_r += r
                    all_g += g
                    all_b += b
                    all_cnt += 1
                    mx = max(r, g, b)
                    if mx > 15:
                        sat = (mx - min(r, g, b)) / float(mx)
                        if sat > 0.08:
                            # Weight by saturation so vivid pixels dominate.
                            w_s = sat * sat
                            sat_r += r * w_s
                            sat_g += g * w_s
                            sat_b += b * w_s
                            sat_cnt += w_s
            if all_cnt <= 0:
                return QColor(255, 255, 255)
            # Use the weighted average of all saturated pixels if any exist.
            if sat_cnt > 0.001:
                return QColor(int(sat_r / sat_cnt), int(sat_g / sat_cnt), int(sat_b / sat_cnt))
            return QColor(all_r // all_cnt, all_g // all_cnt, all_b // all_cnt)
        except Exception:
            return QColor(255, 255, 255)

    def _blend_color(self, old_c: QColor, new_c: QColor) -> QColor:
        try:
            if old_c is None or not old_c.isValid():
                return QColor(new_c)
            a = self.smoothing
            inv = 1.0 - a
            return QColor(
                int((old_c.red() * inv) + (new_c.red() * a)),
                int((old_c.green() * inv) + (new_c.green() * a)),
                int((old_c.blue() * inv) + (new_c.blue() * a)),
            )
        except Exception:
            return QColor(new_c)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        t = self._thread
        if t is not None:
            try:
                t.join(timeout=0.6)
            except Exception:
                pass
        self._thread = None
        try:
            if self._mss is not None:
                self._mss.close()
        except Exception:
            pass
        self._mss = None
        self._dxcam = None
        self._backend = None

    def set_geometry(self, window_rect: QRect, virtual_rect: QRect):
        with self._lock:
            try:
                self._window_rect = QRect(window_rect)
            except Exception:
                self._window_rect = QRect(0, 0, 1, 1)
            try:
                self._virtual_rect = QRect(virtual_rect)
            except Exception:
                pass

    def sample_edge_color(self, side: str, u: float = 0.5, v: float = 0.5, blur_radius: int = 1, distortion: float = 0.01, t: float = None) -> QColor:
        with self._lock:
            col = self._front.get(side)
        if col is None:
            return QColor(255, 255, 255)
        return QColor(col)

    def _capture_loop(self):
        self._init_backend()
        dt = 1.0 / float(self.fps)
        while self._running:
            t0 = time.time()
            with self._lock:
                wr = QRect(self._window_rect)
                vr = QRect(self._virtual_rect)
            rects = self._edge_rects(wr, vr)

            captured = {}
            for side, rect in rects.items():
                img = self._capture_rect(rect)
                if img is None or img.isNull():
                    continue
                # Capture a much smaller proxy area, then smooth colors over time.
                tw = 18 if side in ('top', 'bottom') else 6
                th = 6 if side in ('top', 'bottom') else 18
                try:
                    img = img.scaled(tw, th, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
                except Exception:
                    pass
                captured[side] = self._average_image_color(img)

            if captured:
                with self._lock:
                    for k in ('top', 'bottom', 'left', 'right'):
                        if k in captured:
                            self._front[k] = self._blend_color(self._front.get(k), captured[k])
                    self._front['stamp'] = time.time()

            elapsed = time.time() - t0
            sl = dt - elapsed
            if sl > 0:
                time.sleep(sl)

    def _init_backend(self):
        if self._backend is not None:
            return
        try:
            if sys.platform == 'win32':
                dxcam = importlib.import_module('dxcam')
                cam = dxcam.create(output_color='RGB')
                if cam is not None:
                    # Validate grab actually works (requires cv2 which may not be installed)
                    cam.grab(region=(0, 0, 32, 32))
                    self._dxcam = cam
                    self._backend = 'dxcam'
                    return
        except Exception:
            self._dxcam = None
        try:
            mss = importlib.import_module('mss')
            self._mss = mss.mss()
            self._backend = 'mss'
            return
        except Exception:
            self._mss = None
        # Fallback: use Win32 GDI screen capture via ctypes (no external deps)
        if sys.platform == 'win32':
            try:
                import ctypes
                import ctypes.wintypes  # noqa: F401
                self._backend = 'win32gdi'
                return
            except Exception:
                pass
        self._backend = 'none'

    def _edge_rects(self, wr: QRect, vr: QRect):
        t = self.thickness
        g = self.outward_offset

        left = wr.left()
        top = wr.top()
        right = wr.right()
        bottom = wr.bottom()

        out = {
            'top': QRect(left, top - g - t, wr.width(), t),
            'bottom': QRect(left, bottom + g + 1, wr.width(), t),
            'left': QRect(left - g - t, top, t, wr.height()),
            'right': QRect(right + g + 1, top, t, wr.height()),
        }

        safe = {}
        for k, r in out.items():
            rr = r.intersected(vr)
            if rr.width() > 1 and rr.height() > 1:
                safe[k] = rr
        return safe

    def _capture_rect(self, rect: QRect):
        if rect.width() <= 1 or rect.height() <= 1:
            return None
        l, t, w, h = int(rect.left()), int(rect.top()), int(rect.width()), int(rect.height())
        if self._backend == 'dxcam' and self._dxcam is not None:
            try:
                frame = self._dxcam.grab(region=(l, t, l + w, t + h))
                if frame is None:
                    return None
                qimg = QImage(frame.data, frame.shape[1], frame.shape[0], frame.strides[0], QImage.Format.Format_RGB888)
                return qimg.copy()
            except Exception:
                return None
        if self._backend == 'mss' and self._mss is not None:
            try:
                shot = self._mss.grab({'left': l, 'top': t, 'width': w, 'height': h})
                qimg = QImage(shot.rgb, shot.width, shot.height, shot.width * 3, QImage.Format.Format_RGB888)
                return qimg.copy()
            except Exception:
                return None
        if self._backend == 'win32gdi':
            return self._capture_rect_win32gdi(l, t, w, h)
        return None

    def _capture_rect_win32gdi(self, l, t, w, h):
        """Capture a screen rectangle using Win32 GDI via ctypes (no external deps)."""
        try:
            import ctypes
            import ctypes.wintypes as wt

            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32

            hdesktop = user32.GetDesktopWindow()
            hdc = user32.GetDC(hdesktop)
            mem_dc = gdi32.CreateCompatibleDC(hdc)
            hbm = gdi32.CreateCompatibleBitmap(hdc, w, h)
            old_bm = gdi32.SelectObject(mem_dc, hbm)
            gdi32.BitBlt(mem_dc, 0, 0, w, h, hdc, l, t, 0x00CC0020)  # SRCCOPY

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ('biSize', wt.DWORD), ('biWidth', wt.LONG),
                    ('biHeight', wt.LONG), ('biPlanes', wt.WORD),
                    ('biBitCount', wt.WORD), ('biCompression', wt.DWORD),
                    ('biSizeImage', wt.DWORD), ('biXPelsPerMeter', wt.LONG),
                    ('biYPelsPerMeter', wt.LONG), ('biClrUsed', wt.DWORD),
                    ('biClrImportant', wt.DWORD),
                ]

            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = w
            bmi.biHeight = -h  # top-down DIB
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = 0  # BI_RGB

            buf = (ctypes.c_char * (w * h * 4))()
            gdi32.GetDIBits(mem_dc, hbm, 0, h, buf, ctypes.byref(bmi), 0)

            gdi32.SelectObject(mem_dc, old_bm)
            gdi32.DeleteObject(hbm)
            gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(hdesktop, hdc)

            qimg = QImage(bytes(buf), w, h, w * 4, QImage.Format.Format_RGB32)
            return qimg.copy()
        except Exception:
            return None


def _owner_player(widget):
    p = widget
    while p is not None:
        if hasattr(p, '_edge_sampler'):
            return p
        try:
            p = p.parent()
        except Exception:
            p = None
    return None


GLOBAL_CHAMFER_SCALE = 0.5


def _chamfered_path(
    rectf: QRectF,
    chamfer: float = 14.0,
    chamfer_tl: bool = True,
    chamfer_tr: bool = True,
    chamfer_br: bool = True,
    chamfer_bl: bool = True,
) -> QPainterPath:
    p = QPainterPath()
    if rectf.width() <= 0 or rectf.height() <= 0:
        return p
    c = max(2.0, min(float(chamfer) * GLOBAL_CHAMFER_SCALE, min(rectf.width(), rectf.height()) * 0.45))
    l, t, r, b = rectf.left(), rectf.top(), rectf.right(), rectf.bottom()
    p.moveTo(l + (c if chamfer_tl else 0.0), t)
    p.lineTo(r - (c if chamfer_tr else 0.0), t)
    p.lineTo(r, t + (c if chamfer_tr else 0.0))
    p.lineTo(r, b - (c if chamfer_br else 0.0))
    p.lineTo(r - (c if chamfer_br else 0.0), b)
    p.lineTo(l + (c if chamfer_bl else 0.0), b)
    p.lineTo(l, b - (c if chamfer_bl else 0.0))
    p.lineTo(l, t + (c if chamfer_tl else 0.0))
    p.closeSubpath()
    return p


def _chamfered_polygon(
    rect,
    chamfer: float = 14.0,
    chamfer_tl: bool = True,
    chamfer_tr: bool = True,
    chamfer_br: bool = True,
    chamfer_bl: bool = True,
) -> QPolygon:
    rf = QRectF(rect)
    if rf.width() <= 0 or rf.height() <= 0:
        return QPolygon()
    c = max(2.0, min(float(chamfer) * GLOBAL_CHAMFER_SCALE, min(rf.width(), rf.height()) * 0.45))
    l, t, r, b = rf.left(), rf.top(), rf.right(), rf.bottom()
    return QPolygon([
        QPoint(int(round(l + (c if chamfer_tl else 0.0))), int(round(t))),
        QPoint(int(round(r - (c if chamfer_tr else 0.0))), int(round(t))),
        QPoint(int(round(r)), int(round(t + (c if chamfer_tr else 0.0)))),
        QPoint(int(round(r)), int(round(b - (c if chamfer_br else 0.0)))),
        QPoint(int(round(r - (c if chamfer_br else 0.0))), int(round(b))),
        QPoint(int(round(l + (c if chamfer_bl else 0.0))), int(round(b))),
        QPoint(int(round(l)), int(round(b - (c if chamfer_bl else 0.0)))),
        QPoint(int(round(l)), int(round(t + (c if chamfer_tl else 0.0)))),
    ])


def _apply_chamfer_mask(widget, chamfer: float = 12.0):
    try:
        poly = _chamfered_polygon(widget.rect(), chamfer)
        if poly.isEmpty():
            return
        widget.setMask(QRegion(poly))
    except Exception:
        pass


def _draw_chamfered_rect(painter: QPainter, rectf: QRectF, chamfer: float = 14.0):
    painter.drawPath(_chamfered_path(rectf, chamfer))


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _mix(a: float, b: float, t: float) -> float:
    return (a * (1.0 - t)) + (b * t)


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge0 == edge1:
        return 0.0
    t = _clamp01((x - edge0) / (edge1 - edge0))
    return t * t * (3.0 - 2.0 * t)


def _luminance(c: QColor) -> float:
    return (
        (c.redF() * 0.299)
        + (c.greenF() * 0.587)
        + (c.blueF() * 0.114)
    )


def _estimate_widget_base_color(widget) -> QColor:
    # Prefer an actual painted background color when possible.
    try:
        pal = widget.palette()
        c = pal.color(widget.backgroundRole())
        if c.isValid() and c.alpha() > 0:
            return QColor(c)
    except Exception:
        pass
    try:
        pal = widget.palette()
        c = pal.color(widget.foregroundRole())
        if c.isValid() and c.alpha() > 0:
            return QColor(c)
    except Exception:
        pass
    try:
        p = _owner_player(widget)
        if p is not None and hasattr(p, '_theme_color'):
            c = QColor(getattr(p, '_theme_color'))
            if c.isValid():
                return c
    except Exception:
        pass
    return QColor(36, 38, 44)


def applyGlassReflection(baseColor: QColor, reflectionColor: QColor, uv, normal, viewDir, baseIntensity: float = 0.18, t: float = 0.0):
    """Adaptive, shader-style reflection blend.
    Returns: (blended_color, adaptive_intensity, fresnel_gain)
    """
    try:
        ux = _clamp01(float(uv[0]))
        uy = _clamp01(float(uv[1]))
    except Exception:
        ux, uy = 0.5, 0.5

    bx, by, bz = _clamp01(baseColor.redF()), _clamp01(baseColor.greenF()), _clamp01(baseColor.blueF())
    rx, ry, rz = _clamp01(reflectionColor.redF()), _clamp01(reflectionColor.greenF()), _clamp01(reflectionColor.blueF())

    base_lum = (bx * 0.299) + (by * 0.587) + (bz * 0.114)
    refl_lum = (rx * 0.299) + (ry * 0.587) + (rz * 0.114)

    # Dark UI gets more help; bright UI stays subtle.
    dark_boost = 1.0 - _smoothstep(0.22, 0.68, base_lum)
    bright_falloff = _smoothstep(0.56, 0.92, base_lum)
    adaptive_intensity = baseIntensity * (1.0 + (0.78 * dark_boost)) * (1.0 - (0.38 * bright_falloff))
    adaptive_intensity = max(0.16, min(0.48, adaptive_intensity))

    # Tone-map/lift reflection in dark ranges without flattening.
    gamma = 1.0 - (0.18 * dark_boost)
    rx = pow(max(0.0, rx), gamma)
    ry = pow(max(0.0, ry), gamma)
    rz = pow(max(0.0, rz), gamma)

    lift = (0.12 + (0.18 * dark_boost)) * (1.0 - refl_lum)
    rx = _mix(rx, 1.0, lift * 0.45)
    ry = _mix(ry, 1.0, lift * 0.45)
    rz = _mix(rz, 1.0, lift * 0.45)

    # Optional subtle saturation boost (stronger on dark base).
    sat_gain = 1.0 + (0.10 * dark_boost)
    rlum = (rx * 0.299) + (ry * 0.587) + (rz * 0.114)
    rx = _clamp01(rlum + ((rx - rlum) * sat_gain))
    ry = _clamp01(rlum + ((ry - rlum) * sat_gain))
    rz = _clamp01(rlum + ((rz - rlum) * sat_gain))

    # Fresnel-style edge emphasis: ndotv + geometric edge proximity.
    try:
        nx, ny, nz = float(normal[0]), float(normal[1]), float(normal[2])
    except Exception:
        nx, ny, nz = 0.0, 0.0, 1.0
    try:
        vx, vy, vz = float(viewDir[0]), float(viewDir[1]), float(viewDir[2])
    except Exception:
        vx, vy, vz = 0.0, 0.0, 1.0

    nlen = max(1e-6, math.sqrt((nx * nx) + (ny * ny) + (nz * nz)))
    vlen = max(1e-6, math.sqrt((vx * vx) + (vy * vy) + (vz * vz)))
    ndotv = _clamp01(((nx * vx) + (ny * vy) + (nz * vz)) / (nlen * vlen))
    fresnel = pow(1.0 - ndotv, 3.1)

    edge_dist = min(ux, 1.0 - ux, uy, 1.0 - uy)
    edge_geo = 1.0 - _smoothstep(0.03, 0.32, edge_dist)
    fresnel_gain = 1.0 + (0.60 * max(fresnel, edge_geo * 0.75))

    # Optional dark-surface screen blend to improve visibility.
    screen_mix = 0.35 * dark_boost
    sx = 1.0 - ((1.0 - bx) * (1.0 - rx))
    sy = 1.0 - ((1.0 - by) * (1.0 - ry))
    sz = 1.0 - ((1.0 - bz) * (1.0 - rz))
    rx = _mix(rx, sx, screen_mix)
    ry = _mix(ry, sy, screen_mix)
    rz = _mix(rz, sz, screen_mix)

    # Very subtle animation hook (safe to beat-modulate later).
    pulse = 1.0 + (0.025 * math.sin((t * 0.85) + (ux * 6.28318) + (uy * 3.14159)))
    fresnel_gain *= pulse

    out_r = _clamp01(_mix(bx, rx, adaptive_intensity * fresnel_gain))
    out_g = _clamp01(_mix(by, ry, adaptive_intensity * fresnel_gain))
    out_b = _clamp01(_mix(bz, rz, adaptive_intensity * fresnel_gain))

    out = QColor()
    out.setRgbF(out_r, out_g, out_b, 1.0)
    return out, adaptive_intensity, fresnel_gain


def _paint_glass_reflections(widget, painter: QPainter, radius: float = 8.0, intensity: float = 0.18, spread_scale: float = 1.0, interior_scale: float = 1.0, target_rect: QRectF = None):
    player = _owner_player(widget)
    if player is None:
        return
    if not getattr(player, '_reflections_enabled', True):
        return
    sampler = getattr(player, '_edge_sampler', None)
    if sampler is None:
        return

    try:
        r = QRectF(target_rect) if target_rect is not None else QRectF(widget.rect())
    except Exception:
        r = QRectF(widget.rect())
    if r.width() <= 4 or r.height() <= 4:
        return

    # Global attenuation keeps the profile strong but slightly less intense overall.
    global_gain = 0.90
    spread_scale = max(0.45, min(1.35, float(spread_scale)))
    interior_scale = max(0.0, min(1.25, float(interior_scale)))

    target_intensity = float(intensity) * 2.15 * global_gain
    edge_w = max(3.0, min(r.width(), r.height()) * 0.22 * spread_scale)
    alpha = max(0.12, min(0.74, target_intensity))
    t = time.time()
    base_col = _estimate_widget_base_color(widget)
    base_lum = _luminance(base_col)

    top_c = sampler.sample_edge_color('top', 0.5, 0.5, blur_radius=1, distortion=0.012, t=t)
    bottom_c = sampler.sample_edge_color('bottom', 0.5, 0.5, blur_radius=1, distortion=0.012, t=t)
    left_c = sampler.sample_edge_color('left', 0.5, 0.5, blur_radius=1, distortion=0.012, t=t)
    right_c = sampler.sample_edge_color('right', 0.5, 0.5, blur_radius=1, distortion=0.012, t=t)

    top_mix, top_i, top_f = applyGlassReflection(base_col, top_c, (0.5, 0.02), (0.0, -0.65, 0.76), (0.0, 0.0, 1.0), baseIntensity=target_intensity, t=t)
    bot_mix, bot_i, bot_f = applyGlassReflection(base_col, bottom_c, (0.5, 0.98), (0.0, 0.65, 0.76), (0.0, 0.0, 1.0), baseIntensity=target_intensity, t=t)
    left_mix, left_i, left_f = applyGlassReflection(base_col, left_c, (0.02, 0.5), (-0.65, 0.0, 0.76), (0.0, 0.0, 1.0), baseIntensity=target_intensity, t=t)
    right_mix, right_i, right_f = applyGlassReflection(base_col, right_c, (0.98, 0.5), (0.65, 0.0, 0.76), (0.0, 0.0, 1.0), baseIntensity=target_intensity, t=t)

    side_state = {
        'top': (top_mix, top_i, top_f),
        'bottom': (bot_mix, bot_i, bot_f),
        'left': (left_mix, left_i, left_f),
        'right': (right_mix, right_i, right_f),
    }

    is_square_shape = bool(getattr(widget, '_square_shape', False))
    disable_tl = False
    chamfer_px = 0.0
    if is_square_shape:
        path = QPainterPath()
        path.addRect(r)
    else:
        chamfer = max(8.0, float(radius) * 1.8)
        disable_tl = bool(getattr(widget, 'expanded', False) and hasattr(widget, '_edge_sampler'))
        chamfer_px = max(2.0, min(float(chamfer) * GLOBAL_CHAMFER_SCALE, min(r.width(), r.height()) * 0.45))
        path = _chamfered_path(r, chamfer, chamfer_tl=not disable_tl)

    painter.save()
    painter.setClipPath(path)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)

    def _edge_grad(side, c: QColor):
        mixed_c, side_intensity, side_fresnel = side_state.get(side, (c, target_intensity, 1.0))
        side_alpha_scale = max(0.78, min(1.70, (side_intensity / max(1e-4, target_intensity)) * side_fresnel))
        a0 = int(max(8, min(255, 255 * alpha * side_alpha_scale)))
        c0 = QColor(mixed_c.red(), mixed_c.green(), mixed_c.blue(), a0)
        c_mid = QColor(mixed_c.red(), mixed_c.green(), mixed_c.blue(), int(a0 * 0.42))
        c1 = QColor(mixed_c.red(), mixed_c.green(), mixed_c.blue(), int(a0 * 0.04))
        if side == 'top':
            g = QLinearGradient(r.left(), r.top(), r.left(), r.top() + edge_w)
        elif side == 'bottom':
            g = QLinearGradient(r.left(), r.bottom(), r.left(), r.bottom() - edge_w)
        elif side == 'left':
            g = QLinearGradient(r.left(), r.top(), r.left() + edge_w, r.top())
        else:
            g = QLinearGradient(r.right(), r.top(), r.right() - edge_w, r.top())
        g.setColorAt(0.0, c0)
        g.setColorAt(0.35, c_mid)
        g.setColorAt(1.0, c1)
        return g

    painter.fillPath(path, _edge_grad('top', top_c))
    painter.fillPath(path, _edge_grad('bottom', bottom_c))
    painter.fillPath(path, _edge_grad('left', left_c))
    painter.fillPath(path, _edge_grad('right', right_c))

    # Interior reflection wash so highlights are visible beyond borders.
    interior_a = int(max(0, min(120, 255 * alpha * 0.15 * interior_scale)))
    interior_grad = QLinearGradient(r.left(), r.top(), r.right(), r.bottom())
    interior_grad.setColorAt(0.0, QColor(top_mix.red(), top_mix.green(), top_mix.blue(), int(interior_a * 1.00)))
    interior_grad.setColorAt(0.35, QColor(left_mix.red(), left_mix.green(), left_mix.blue(), int(interior_a * 0.72)))
    interior_grad.setColorAt(0.65, QColor(right_mix.red(), right_mix.green(), right_mix.blue(), int(interior_a * 0.72)))
    interior_grad.setColorAt(1.0, QColor(bot_mix.red(), bot_mix.green(), bot_mix.blue(), int(interior_a * 0.88)))
    painter.fillPath(path, interior_grad)

    # Soft artificial light keeps reflections legible over very dark UI.
    ambient_strength = (0.05 + (0.14 * (1.0 - _smoothstep(0.22, 0.72, base_lum))))
    top_light = QLinearGradient(r.left(), r.top(), r.left(), r.bottom())
    top_light.setColorAt(0.0, QColor(255, 255, 255, int(255 * ambient_strength * 0.65)))
    top_light.setColorAt(0.34, QColor(255, 255, 255, int(255 * ambient_strength * 0.22)))
    top_light.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.fillPath(path, top_light)

    glow_center = QPointF(r.center().x(), r.top() + (r.height() * 0.25))
    glow_radius = max(r.width(), r.height()) * 0.62
    ambient_glow = QRadialGradient(glow_center, glow_radius)
    ambient_glow.setColorAt(0.0, QColor(255, 255, 255, int(255 * ambient_strength * 0.30)))
    ambient_glow.setColorAt(0.7, QColor(255, 255, 255, int(255 * ambient_strength * 0.08)))
    ambient_glow.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.fillPath(path, ambient_glow)

    # Chamfer-edge glints: tiny diagonal highlights so cut corners read as reflective.
    try:
        if (not is_square_shape) and chamfer_px > 1.5:
            glint_w = max(0.9, min(2.2, min(r.width(), r.height()) * 0.08))
            glint_a = int(max(18, min(210, 255 * alpha * 0.62)))

            def _mix_col(a: QColor, b: QColor, aa: int) -> QColor:
                return QColor(
                    int((a.red() + b.red()) * 0.5),
                    int((a.green() + b.green()) * 0.5),
                    int((a.blue() + b.blue()) * 0.5),
                    aa,
                )

            pen = painter.pen()
            pen.setWidthF(glint_w)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)

            # top-left chamfer (optional, disabled for big-mode window)
            if not disable_tl:
                pen.setColor(_mix_col(top_mix, left_mix, glint_a))
                painter.setPen(pen)
                painter.drawLine(
                    QPointF(r.left() + 0.4, r.top() + chamfer_px - 0.4),
                    QPointF(r.left() + chamfer_px - 0.4, r.top() + 0.4),
                )

            # top-right chamfer
            pen.setColor(_mix_col(top_mix, right_mix, glint_a))
            painter.setPen(pen)
            painter.drawLine(
                QPointF(r.right() - chamfer_px + 0.4, r.top() + 0.4),
                QPointF(r.right() - 0.4, r.top() + chamfer_px - 0.4),
            )

            # bottom-right chamfer
            pen.setColor(_mix_col(bot_mix, right_mix, int(glint_a * 0.92)))
            painter.setPen(pen)
            painter.drawLine(
                QPointF(r.right() - 0.4, r.bottom() - chamfer_px + 0.4),
                QPointF(r.right() - chamfer_px + 0.4, r.bottom() - 0.4),
            )

            # bottom-left chamfer
            pen.setColor(_mix_col(bot_mix, left_mix, int(glint_a * 0.92)))
            painter.setPen(pen)
            painter.drawLine(
                QPointF(r.left() + chamfer_px - 0.4, r.bottom() - 0.4),
                QPointF(r.left() + 0.4, r.bottom() - chamfer_px + 0.4),
            )
    except Exception:
        pass

    # Add a thin reflective rim so window edges read as glass borders.
    try:
        top_a = int(max(20, min(180, 255 * alpha * 0.95 * top_f)))
        bot_a = int(max(16, min(160, 255 * alpha * 0.72 * bot_f)))
        side_a = int(max(14, min(150, 255 * alpha * 0.62 * max(left_f, right_f))))
        rim_w = max(1.2, min(3.2, min(r.width(), r.height()) * 0.006))

        # top rim
        pen = painter.pen()
        pen.setWidthF(rim_w)
        pen.setColor(QColor(top_mix.red(), top_mix.green(), top_mix.blue(), top_a))
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        corner_inset = 0.0 if is_square_shape else (radius * 0.5)
        painter.drawLine(QPointF(r.left() + corner_inset, r.top() + rim_w * 0.5), QPointF(r.right() - corner_inset, r.top() + rim_w * 0.5))

        # bottom rim
        pen.setColor(QColor(bot_mix.red(), bot_mix.green(), bot_mix.blue(), bot_a))
        painter.setPen(pen)
        painter.drawLine(QPointF(r.left() + corner_inset, r.bottom() - rim_w * 0.5), QPointF(r.right() - corner_inset, r.bottom() - rim_w * 0.5))

        # left rim
        pen.setColor(QColor(left_mix.red(), left_mix.green(), left_mix.blue(), side_a))
        painter.setPen(pen)
        painter.drawLine(QPointF(r.left() + rim_w * 0.5, r.top() + corner_inset), QPointF(r.left() + rim_w * 0.5, r.bottom() - corner_inset))

        # right rim
        pen.setColor(QColor(right_mix.red(), right_mix.green(), right_mix.blue(), side_a))
        painter.setPen(pen)
        painter.drawLine(QPointF(r.right() - rim_w * 0.5, r.top() + corner_inset), QPointF(r.right() - rim_w * 0.5, r.bottom() - corner_inset))
    except Exception:
        pass
    painter.restore()

# Optional Windows system volume control (pycaw) with a ctypes fallback
SystemVolumeController = None
try:
    from pycaw.pycaw import AudioUtilities

    class _PycawVolume:
        def __init__(self):
            self._endpoint = None
            try:
                device = AudioUtilities.GetSpeakers()
                self._endpoint = device.EndpointVolume
            except Exception:
                self._endpoint = None

        def available(self):
            return self._endpoint is not None

        def set_volume(self, percent: int):
            if not self.available():
                return
            try:
                self._endpoint.SetMasterVolumeLevelScalar(max(0.0, min(1.0, percent / 100.0)), None)
            except Exception:
                pass

        def get_volume(self) -> int:
            if not self.available():
                return 70
            try:
                v = self._endpoint.GetMasterVolumeLevelScalar()
                return int(max(0.0, min(1.0, v)) * 100)
            except Exception:
                return 70

    SystemVolumeController = _PycawVolume
except Exception:
    # fallback to waveOutSetVolume (older API) via ctypes on Windows
    try:
        import ctypes
        from ctypes import wintypes

        winmm = ctypes.windll.winmm

        class _WaveOutVolume:
            def __init__(self):
                self._available = True

            def available(self):
                return self._available

            def set_volume(self, percent: int):
                try:
                    # waveOutSetVolume takes a DWORD with low-order word = left, high-order = right
                    v = int(max(0, min(100, percent)) * 0xFFFF / 100)
                    dw = (v & 0xFFFF) | ((v & 0xFFFF) << 16)
                    # (UINT)-1 sets volume for all devices
                    winmm.waveOutSetVolume(wintypes.UINT(-1 & 0xFFFFFFFF), wintypes.DWORD(dw))
                except Exception:
                    pass

            def get_volume(self) -> int:
                try:
                    dw = wintypes.DWORD()
                    res = winmm.waveOutGetVolume(wintypes.UINT(-1 & 0xFFFFFFFF), ctypes.byref(dw))
                    if res == 0:
                        v = dw.value & 0xFFFF
                        return int(v * 100 / 0xFFFF)
                except Exception:
                    pass
                return 70

        SystemVolumeController = _WaveOutVolume
    except Exception:
        SystemVolumeController = None


# ---------- Tutorial Popup ----------
class TutorialPopup(QWidget):
    """One-time welcome popup with key-binding info, semi-transparent with edge reflections."""

    dismissed = pyqtSignal()

    def __init__(self, parent_player):
        super().__init__(parent_player)
        self._parent_player = parent_player
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(340)
        self._build_ui()
        self.adjustSize()

    # ---- UI construction ----
    def _build_ui(self):
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)

        self._container = QWidget()
        self._container.setObjectName("tutContainer")
        self._container.setStyleSheet(
            "#tutContainer{background:rgba(18,18,26,210);border:1px solid rgba(255,255,255,18);}"
        )

        inner = QVBoxLayout()
        inner.setContentsMargins(18, 14, 18, 14)
        inner.setSpacing(10)

        # Title
        title = QLabel("Welcome to Music Island!")
        title.setStyleSheet("font-size:15px;font-weight:bold;color:white;background:transparent;")
        inner.addWidget(title)

        # --- F9 row ---
        f9_row = QHBoxLayout()
        f9_row.setSpacing(8)
        f9_key = self._key_graphic("F9")
        f9_row.addWidget(f9_key)
        f9_lbl = QLabel("Toggle big / small mode.\nPress anywhere to bring the player back.")
        f9_lbl.setWordWrap(True)
        f9_lbl.setStyleSheet("font-size:12px;color:rgba(255,255,255,210);background:transparent;")
        f9_row.addWidget(f9_lbl, 1)
        inner.addLayout(f9_row)

        # --- F10 row with drag icon ---
        f10_row = QHBoxLayout()
        f10_row.setSpacing(8)
        f10_key = self._key_graphic("F10")
        f10_row.addWidget(f10_key)
        # Try to load drag.png
        drag_lbl = QLabel()
        drag_lbl.setFixedSize(28, 28)
        drag_lbl.setStyleSheet("background:transparent;")
        try:
            dp = load_drag_asset_path()
            pm = QPixmap(dp)
            if not pm.isNull():
                drag_lbl.setPixmap(pm.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        except Exception:
            pass
        f10_row.addWidget(drag_lbl)
        f10_lbl = QLabel("Hold to drag. In small mode snaps\nto nearest window when released.")
        f10_lbl.setWordWrap(True)
        f10_lbl.setStyleSheet("font-size:12px;color:rgba(255,255,255,210);background:transparent;")
        f10_row.addWidget(f10_lbl, 1)
        inner.addLayout(f10_row)

        # --- PgUp / PgDn row ---
        pg_row = QHBoxLayout()
        pg_row.setSpacing(8)
        pgup_key = self._key_graphic("PgUp")
        pgdn_key = self._key_graphic("PgDn")
        pg_row.addWidget(pgup_key)
        pg_row.addWidget(pgdn_key)
        pg_lbl = QLabel("Next / Previous song.")
        pg_lbl.setStyleSheet("font-size:12px;color:rgba(255,255,255,210);background:transparent;")
        pg_row.addWidget(pg_lbl, 1)
        inner.addLayout(pg_row)

        # --- Pause/Break row ---
        pause_row = QHBoxLayout()
        pause_row.setSpacing(8)
        pause_key = self._key_graphic("Pause")
        pause_row.addWidget(pause_key)
        pause_lbl = QLabel("Pause / Resume playback.")
        pause_lbl.setStyleSheet("font-size:12px;color:rgba(255,255,255,210);background:transparent;")
        pause_row.addWidget(pause_lbl, 1)
        inner.addLayout(pause_row)

        # Dismiss button
        dismiss = QPushButton("Got it!")
        dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,20);border:1px solid rgba(255,255,255,30);"
            "color:white;padding:6px 18px;font-size:12px;font-weight:bold;}"
            "QPushButton:hover{background:rgba(255,255,255,35);}"
        )
        dismiss.clicked.connect(self._on_dismiss)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(dismiss)
        inner.addLayout(btn_row)

        self._container.setLayout(inner)
        root.addWidget(self._container)
        self.setLayout(root)

    @staticmethod
    def _key_graphic(label: str) -> QLabel:
        """Create a small rounded-rect key cap label."""
        w = QLabel(label)
        w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        w.setFixedSize(38, 28)
        w.setStyleSheet(
            "QLabel{background:rgba(255,255,255,18);border:1px solid rgba(255,255,255,45);"
            "color:white;font-size:11px;font-weight:bold;font-family:monospace;}"
        )
        return w

    def _on_dismiss(self):
        self.dismissed.emit()
        self.close()

    # ---- painting with edge reflections ----
    def paintEvent(self, ev):
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            _paint_glass_reflections(self, p, radius=6.0, intensity=0.20, spread_scale=0.9, interior_scale=0.7)
            p.end()
        except Exception:
            pass


# ---------- Cover Widget ----------
class CoverWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(144, 144)
        self.setStyleSheet("background:transparent;")
        self.setMouseTracking(True)
        self.cover_pixmap = None
        # Tell _paint_glass_reflections to use a rectangular clip (no chamfered corners)
        self._square_shape = True
        self._hover_controls = []
        self._hover_prev_btn = None
        self._hover_play_btn = None
        self._hover_next_btn = None
        # animation state for small-mode no-song corner gradients
        self._corner_hues = [random.random() for _ in range(4)]
        self._corner_phase = [random.random() * 2.0 for _ in range(4)]
        self._corner_saturation = [0.1 + random.random() * 0.1 for _ in range(4)]
        self._corner_lightness = [0.08 + random.random() * 0.08 for _ in range(4)]
        from PyQt6.QtCore import QTimer
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(150)
        self._anim_timer.timeout.connect(self._update_corner_animation)
        self._anim_timer.start()

    def _ensure_hover_controls(self):
        if self._hover_controls:
            return
        try:
            host = _owner_player(self)
            if host is None:
                host = self

            self._hover_prev_btn = GlassButton("⏮", host, reflection_radius=3.0, reflection_intensity=0.15)
            self._hover_play_btn = GlassButton("▶", host, reflection_radius=3.0, reflection_intensity=0.18)
            self._hover_next_btn = GlassButton("⏭", host, reflection_radius=3.0, reflection_intensity=0.15)
            self._hover_controls = [self._hover_prev_btn, self._hover_play_btn, self._hover_next_btn]

            for b in self._hover_controls:
                b.set_square_shape(True)
                b.setFixedSize(22, 22)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setStyleSheet(
                    "QPushButton{background:rgba(24,24,28,178);border:1px solid rgba(255,255,255,35);border-radius:0px;color:white;font-size:11px;}"
                    "QPushButton:hover{background:rgba(52,52,58,210);}"
                    "QPushButton:pressed{background:rgba(16,16,20,220);}"
                )
                b.hide()

            self._hover_prev_btn.clicked.connect(self._on_hover_prev)
            self._hover_play_btn.clicked.connect(self._on_hover_play_pause)
            self._hover_next_btn.clicked.connect(self._on_hover_next)
        except Exception:
            self._hover_controls = []

    def _can_show_hover_controls(self) -> bool:
        try:
            p = _owner_player(self)
            return bool(p is not None and not getattr(p, 'expanded', True) and getattr(p, 'current_index', -1) != -1)
        except Exception:
            return False

    def _refresh_hover_play_icon(self):
        try:
            self._ensure_hover_controls()
            p = _owner_player(self)
            playing = False
            if p is not None and hasattr(p, 'player'):
                try:
                    playing = (p.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
                except Exception:
                    playing = False
            if self._hover_play_btn is not None:
                self._hover_play_btn.setText("⏸" if playing else "▶")
        except Exception:
            pass

    def _update_hover_controls_geometry(self):
        try:
            self._ensure_hover_controls()
            if not self._hover_controls:
                return
            host = _owner_player(self)
            if host is None:
                host = self

            bw = self._hover_controls[0].width()
            bh = self._hover_controls[0].height()
            gap = 4
            total_h = (bh * 3) + (gap * 2)

            try:
                tl = self.mapTo(host, QPoint(0, 0))
            except Exception:
                tl = QPoint(0, 0)

            # Pop out on the side of the album cover.
            x = tl.x() + self.width() + 8
            y0 = tl.y() + max(2, int((self.height() - total_h) / 2))

            # If no space on the right, pop out to the left.
            try:
                if x + bw > host.width() - 2:
                    x = tl.x() - bw - 8
            except Exception:
                pass

            x = max(2, x)
            y0 = max(2, y0)
            for i, b in enumerate(self._hover_controls):
                b.move(x, y0 + i * (bh + gap))
                b.raise_()
        except Exception:
            pass

    def _set_hover_controls_visible(self, visible: bool):
        try:
            self._ensure_hover_controls()
            self._refresh_hover_play_icon()
            self._update_hover_controls_geometry()
            show_now = bool(visible and self._can_show_hover_controls())
            for b in self._hover_controls:
                b.setVisible(show_now)
        except Exception:
            pass

    def _hide_hover_controls_if_outside(self):
        try:
            if self.underMouse():
                return
            for b in self._hover_controls:
                if b.underMouse():
                    return
            self._set_hover_controls_visible(False)
        except Exception:
            pass

    def _on_hover_prev(self):
        try:
            p = _owner_player(self)
            if p is not None:
                p.prev_track()
            self._refresh_hover_play_icon()
        except Exception:
            pass

    def _on_hover_play_pause(self):
        try:
            p = _owner_player(self)
            if p is not None:
                p.toggle_play()
            self._refresh_hover_play_icon()
        except Exception:
            pass

    def _on_hover_next(self):
        try:
            p = _owner_player(self)
            if p is not None:
                p.next_track()
            self._refresh_hover_play_icon()
        except Exception:
            pass
    
    def set_cover(self, pixmap):
        """Accept either a QPixmap or a file path; normalize to QPixmap or None.
        This avoids leaving cover_pixmap as a raw string which later may fail to draw.
        """
        try:
            if isinstance(pixmap, str):
                pm = QPixmap(pixmap)
                if pm and not pm.isNull():
                    self.cover_pixmap = pm
                else:
                    self.cover_pixmap = None
            elif isinstance(pixmap, QPixmap):
                if pixmap.isNull():
                    self.cover_pixmap = None
                else:
                    self.cover_pixmap = pixmap
            else:
                # allow None or other falsy values to clear the cover
                self.cover_pixmap = None
        except Exception:
            self.cover_pixmap = None
        try:
            pass
        except Exception:
            pass
        # Ensure the cover widget is visible so paintEvent runs and fallbacks are drawn
        try:
            self.show()
        except Exception:
            pass
        # clear parent's blurred-background cache when cover changes (avoid stale/incorrect imagery)
        try:
            p = self.parent()
            while p is not None and not hasattr(p, 'bottom_widget'):
                try:
                    p = p.parent()
                except Exception:
                    p = None
            if p is not None:
                bw = getattr(p, 'bottom_widget', None)
                if bw is not None and hasattr(bw, '_cache'):
                    bw._cache['pixmap'] = None
                    bw._cache['blurred'] = None
                    bw._cache['size'] = None
                    try:
                        bw.update()
                    except Exception:
                        pass
        except Exception:
            pass
        self.update()
    
    def paintEvent(self, event):
        super().paintEvent(event)

        # quick debug to verify paint is invoked and state
        try:
            p = self.parent()
            exp = getattr(p, 'expanded', None) if p is not None else None
            idx = getattr(p, 'current_index', None) if p is not None else None
            has = 'yes' if self.cover_pixmap else 'no'
        except Exception:
            pass

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        r = self.rect()
        path = QPainterPath()
        path.addRect(QRectF(r))
        try:
            self._update_hover_controls_geometry()
        except Exception:
            pass

        # clip to rounded rect but do not draw a background (keep transparent)
        painter.setClipPath(path)

        parent = self.parent()
        no_song_small_mode = False
        try:
            if parent is not None and hasattr(parent, 'expanded') and not parent.expanded and getattr(parent, 'current_index', -1) == -1:
                no_song_small_mode = True
        except Exception:
            pass
            no_song_small_mode = False

        if no_song_small_mode:
            # if playlist is empty (no songs uploaded), draw a small moving linear
            # gradient like the main player; otherwise fall back to corner radial
            # accents.
            player = None
            try:
                # find owning player if present
                p = self.parent()
                while p is not None and not (hasattr(p, 'expanded') and hasattr(p, 'current_index')):
                    try:
                        p = p.parent()
                    except Exception:
                        p = None
                player = p
            except Exception:
                player = None

            w, h = self.width(), self.height()
            if player is not None and (not getattr(player, 'playlist', None)):
                # If no songs are uploaded, prefer showing a bundled "load.png" image
                # located next to this script. Fall back to the original gradient if
                # the image is not present or fails to load.
                try:
                    fn = load_cover_asset_path()
                    if os.path.exists(fn):
                        try:
                            pm = QPixmap(fn)
                            if pm and not pm.isNull():
                                # scale to widget size while preserving aspect ratio
                                target = self.size()
                                scaled = pm.scaled(target, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                                x = (self.width() - scaled.width()) // 2
                                y = (self.height() - scaled.height()) // 2
                                painter.drawPixmap(x, y, scaled)
                                painter.end()
                                return
                        except Exception:
                            pass

                    # fallback: draw a scaled linear gradient using player's theme color and grad offset
                    base_col = QColor(getattr(player, '_theme_color', QColor('#1f1f23')))
                    bmul = getattr(player, '_auto_brightness', 1.0)
                    rr = min(255, max(0, int(base_col.red() * bmul)))
                    gg = min(255, max(0, int(base_col.green() * bmul)))
                    bb = min(255, max(0, int(base_col.blue() * bmul)))
                    base = QColor(rr, gg, bb)

                    off = getattr(player, '_grad_offset', QPointF(0.0, 0.0))
                    sx = 0 + (w * (0.5 + off.x()))
                    sy = 0 + (h * (0.5 + off.y()))
                    ex = w - (w * (0.5 - off.x()))
                    ey = h - (h * (0.5 - off.y()))

                    grad = QLinearGradient(QPointF(sx, sy), QPointF(ex, ey))
                    grad.setColorAt(0.0, base)
                    try:
                        end_col = QColor(base)
                        end_col = end_col.darker(180)
                        grad.setColorAt(1.0, end_col)
                    except Exception:
                        grad.setColorAt(1.0, QColor(0, 0, 0))
                    from PyQt6.QtGui import QBrush
                    brush = QBrush(grad)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(brush)
                    painter.drawRect(QRectF(self.rect()))
                except Exception:
                    pass
            else:
                # draw four corner radial gradients with low lightness and low saturation
                from PyQt6.QtGui import QRadialGradient, QBrush
                for i in range(4):
                    if i == 0:
                        cx, cy = 0, 0
                    elif i == 1:
                        cx, cy = w, 0
                    elif i == 2:
                        cx, cy = 0, h
                    else:
                        cx, cy = w, h

                    hue = self._corner_hues[i] % 1.0
                    sat = max(0.0, min(0.2, self._corner_saturation[i]))
                    light = max(0.0, min(0.2, self._corner_lightness[i]))
                    color = QColor.fromHslF(hue, sat, light)
                    grad = QRadialGradient(QPointF(cx, cy), max(w, h) * 0.6)
                    c1 = QColor(color)
                    c1.setAlpha(200)
                    c2 = QColor(color)
                    c2.setAlpha(0)
                    grad.setColorAt(0.0, c1)
                    grad.setColorAt(1.0, c2)
                    brush = QBrush(grad)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(brush)
                    radius = max(w, h) * 0.6
                    painter.drawEllipse(QPointF(cx, cy), radius, radius)
        # If we're in small mode and a song is playing but there's no cover,
        # draw the song title centered on the cover area with the theme color
        # determine the real player ancestor (widget added to layout may have an intermediate parent)
        owner = self.parent()
        player = None
        try:
            p = owner
            while p is not None and not (hasattr(p, 'expanded') and hasattr(p, 'current_index')):
                try:
                    p = p.parent()
                except Exception:
                    p = None
            player = p
        except Exception:
            player = None

        # show title only when we have no cover, the player exists and we're in small (not expanded) mode,
        # and a track is selected
        if not self.cover_pixmap and player is not None and not getattr(player, 'expanded', True):
            try:
                cur_idx = getattr(player, 'current_index', -1)
                if cur_idx != -1:
                    # determine the song title to display with multiple fallbacks
                    title = ''
                    try:
                        title = getattr(player.song_label, '_text', '') or ''
                    except Exception:
                        title = ''

                    # fallback: current player's source URL
                    if not title:
                        try:
                            src = getattr(player.player, 'source')()
                            # QMediaPlayer.source() may be a QUrl or a method returning QUrl
                            if src is not None:
                                try:
                                    # if it's a QUrl
                                    pth = src.toLocalFile()
                                except Exception:
                                    try:
                                        pth = str(src)
                                    except Exception:
                                        pth = ''
                                if pth:
                                    title = os.path.splitext(os.path.basename(pth))[0]
                        except Exception:
                            pass

                    # next fallback: playlist entry at current index
                    if not title:
                        try:
                            if 0 <= cur_idx < len(player.playlist):
                                path = player.playlist[cur_idx]
                                title = os.path.splitext(os.path.basename(path))[0]
                        except Exception:
                            pass

                    if not title:
                        title = 'Unknown'

                    # background color: use the stored theme color for this song if available
                    try:
                        file_path = None
                        try:
                            if 0 <= cur_idx < len(player.playlist):
                                file_path = player.playlist[cur_idx]
                        except Exception:
                            file_path = None
                        bg = None
                        if file_path is not None and file_path in getattr(player, '_theme_colors', {}):
                            bg = QColor(player._theme_colors[file_path])
                        else:
                            bg = QColor(getattr(player, '_theme_color', QColor('#343438')))
                    except Exception:
                        bg = QColor(getattr(parent, '_theme_color', QColor('#343438')))

                    # paint a rounded rect background filled with the inverse-of-theme gradient
                    try:
                        # compute an "inverse" accent color (same approach as expanded mode)
                        try:
                            import colorsys
                            r0 = (255 - bg.red()) / 255.0
                            g0 = (255 - bg.green()) / 255.0
                            b0 = (255 - bg.blue()) / 255.0
                            h, s, v = colorsys.rgb_to_hsv(r0, g0, b0)
                            s = min(1.0, s * 4.0)
                            r1, g1, b1 = colorsys.hsv_to_rgb(h, s, v)
                            inv = QColor(int(r1 * 255), int(g1 * 255), int(b1 * 255))
                        except Exception:
                            inv = QColor(255 - bg.red(), 255 - bg.green(), 255 - bg.blue())
                        painter.setPen(Qt.PenStyle.NoPen)
                        rect = self.rect()
                        # inset slightly so corners show
                        r2 = QRect(int(rect.x()+4), int(rect.y()+4), int(rect.width()-8), int(rect.height()-8))
                        rectf = QRectF(r2)
                        grad = QLinearGradient(QPointF(rectf.x(), rectf.y()), QPointF(rectf.x() + rectf.width(), rectf.y() + rectf.height()))
                        grad.setColorAt(0.0, inv)
                        grad.setColorAt(1.0, QColor(0, 0, 0))
                        from PyQt6.QtGui import QBrush
                        painter.setBrush(QBrush(grad))
                        painter.drawRect(rectf)
                    except Exception:
                        pass

                    # prepare wrapped lines (max 3 lines)
                    try:
                        from PyQt6.QtGui import QFont, QFontMetrics
                        fm = QFontMetrics(self.font())
                        maxw = max(20, int(self.width() - 16))
                        words = title.split()
                        lines = []
                        cur_line = ''
                        for w in words:
                            if cur_line:
                                trial = cur_line + ' ' + w
                            else:
                                trial = w
                            if fm.horizontalAdvance(trial) <= maxw:
                                cur_line = trial
                            else:
                                if cur_line:
                                    lines.append(cur_line)
                                cur_line = w
                                if len(lines) >= 2:
                                    # last line: elide remainder
                                    break
                        if cur_line:
                            lines.append(cur_line)
                        # if too many lines, elide the last
                        if len(lines) > 3:
                            lines = lines[:3]

                        # draw text centered vertically and horizontally
                        painter.setPen(QColor(255, 255, 255))
                        font = painter.font()
                        font.setBold(True)
                        # scale font size to cover area for readability
                        font.setPointSize(max(10, min(14, int(self.width() / 10))))
                        painter.setFont(font)
                        fm2 = QFontMetrics(font)
                        total_h = len(lines) * fm2.height()
                        y0 = int((self.height() - total_h) / 2) + fm2.ascent()
                        for i, line in enumerate(lines):
                            y = y0 + i * fm2.height()
                            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignHCenter, line) if len(lines) == 1 else painter.drawText(QRect(8, y - fm2.ascent(), self.width()-16, fm2.height()), Qt.AlignmentFlag.AlignCenter, line)
                    except Exception:
                        pass
                    painter.end()
                    return
            except Exception:
                pass

        # If expanded (big) mode and a track is selected but no cover, draw
        # a square filled with the inverse of the song's theme color.
        try:
            player_for_cover = player if 'player' in locals() else None
        except Exception:
            player_for_cover = None

        if (not self.cover_pixmap) and player_for_cover is not None and getattr(player_for_cover, 'expanded', False) and getattr(player_for_cover, 'current_index', -1) != -1:
            try:
                idx = getattr(player_for_cover, 'current_index', -1)
                file_path = None
                try:
                    if 0 <= idx < len(player_for_cover.playlist):
                        file_path = player_for_cover.playlist[idx]
                except Exception:
                    file_path = None

                try:
                    if file_path and file_path in getattr(player_for_cover, '_theme_colors', {}):
                        base_col = QColor(player_for_cover._theme_colors[file_path])
                    else:
                        base_col = QColor(getattr(player_for_cover, '_theme_color', QColor('#1f1f23')))
                except Exception:
                    base_col = QColor(getattr(player_for_cover, '_theme_color', QColor('#1f1f23')))

                try:
                    import colorsys
                    r0 = (255 - base_col.red()) / 255.0
                    g0 = (255 - base_col.green()) / 255.0
                    b0 = (255 - base_col.blue()) / 255.0
                    h, s, v = colorsys.rgb_to_hsv(r0, g0, b0)
                    s = min(1.0, s * 4.0)
                    r1, g1, b1 = colorsys.hsv_to_rgb(h, s, v)
                    inv = QColor(int(r1 * 255), int(g1 * 255), int(b1 * 255))
                except Exception:
                    inv = QColor(255 - base_col.red(), 255 - base_col.green(), 255 - base_col.blue())
                # draw a centered rounded rectangle filled with a gradient
                try:
                    pad = 0
                    w, h = self.width(), self.height()
                    side = min(w, h) - pad * 2
                    if side < 8:
                        side = min(w, h)
                    x = (w - side) // 2
                    y = (h - side) // 2
                    rectf = QRectF(x, y, float(side), float(side))
                    # gradient from inverse color -> black
                    grad = QLinearGradient(QPointF(x, y), QPointF(x + side, y + side))
                    grad.setColorAt(0.0, inv)
                    grad.setColorAt(1.0, QColor(0, 0, 0))
                    from PyQt6.QtGui import QBrush
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(grad))
                    painter.drawRect(rectf)
                except Exception:
                    pass
            except Exception:
                pass

        # If expanded and no song is loaded, show a neutral light-gray square
        try:
            if (not self.cover_pixmap) and player_for_cover is not None and getattr(player_for_cover, 'expanded', False) and getattr(player_for_cover, 'current_index', -1) == -1:
                try:
                    pad = 0
                    w, h = self.width(), self.height()
                    side = min(w, h) - pad * 2
                    if side < 8:
                        side = min(w, h)
                    x = (w - side) // 2
                    y = (h - side) // 2
                    rectf = QRectF(x, y, float(side), float(side))

                    # try drawing bundled load.png centered inside the square
                    fn = load_cover_asset_path()
                    drew = False
                    try:
                        if os.path.exists(fn):
                            pm = QPixmap(fn)
                            if pm and not pm.isNull():
                                scaled = pm.scaled(int(side), int(side), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                                px = x + (side - scaled.width()) / 2
                                py = y + (side - scaled.height()) / 2
                                painter.drawPixmap(int(px), int(py), scaled)
                                drew = True
                    except Exception:
                        drew = False

                    if not drew:
                        # soft gradient fallback: light gray -> darker gray
                        grad = QLinearGradient(QPointF(x, y), QPointF(x + side, y + side))
                        grad.setColorAt(0.0, QColor(240, 240, 240))
                        grad.setColorAt(1.0, QColor(205, 205, 205))
                        from PyQt6.QtGui import QBrush
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(QBrush(grad))
                        painter.drawRect(rectf)
                except Exception:
                    pass
        except Exception:
            pass

        if self.cover_pixmap:
            # --- Draw glowing gradient around the cover ---
            player = self.parent()
            # Find the player ancestor if needed
            try:
                p = player
                while p is not None and not (hasattr(p, 'expanded') and hasattr(p, 'current_index')):
                    try:
                        p = p.parent()
                    except Exception:
                        p = None
                player = p
            except Exception:
                player = None

            # Get theme color for current song
            glow_color = QColor('#1f1f23')
            try:
                # Use theme color if available from player
                if player is not None and hasattr(player, '_theme_color'):
                    glow_color = getattr(player, '_theme_color', QColor('#1f1f23'))
            except Exception:
                pass

            # Calculate geometry for glow
            try:
                # no inset border — draw cover flush to rounded background
                pad = 0
            except Exception:
                pad = 0
            w, h = self.width(), self.height()
            side = min(w, h) - pad * 2
            if side < 8:
                side = min(w, h)
            x = (w - side) // 2
            y = (h - side) // 2
            rectf = QRectF(x, y, float(side), float(side))
            glow_center = QPointF(x + side / 2, y + side / 2)
            glow_radius = side / 2 + 16

            # In small mode, gather audio-reactive values from the player
            try:
                _is_small = (player is not None and not getattr(player, 'expanded', True))
                _bmul     = float(getattr(player, '_auto_brightness', 1.0)) if player else 1.0
                # Use beat pulse instead of raw volume — colours snap on each beat
                _beat     = max(0.0, min(1.0, float(getattr(player, '_beat_pulse', 0.0)))) if player else 0.0
                _low_e    = _beat
                _high_e   = _beat
            except Exception:
                _is_small = False
                _bmul = 1.0
                _low_e = 0.0
                _high_e = 0.0

            # Draw glowing ellipse — pulse with audio energy in small mode
            try:
                c1 = QColor(glow_color)
                if _is_small:
                    # Strongly amplify: glow alpha 80..255, radius grows with beat
                    glow_alpha   = int(min(255, 80 + 175 * _bmul * (0.4 + 1.6 * _low_e)))
                    glow_radius2 = glow_radius * (1.0 + 0.55 * _low_e)
                else:
                    glow_alpha   = 120
                    glow_radius2 = glow_radius
                c1.setAlpha(glow_alpha)
                c2 = QColor(glow_color)
                c2.setAlpha(0)
                grad = QRadialGradient(glow_center, glow_radius2)
                grad.setColorAt(0.0, c1)
                grad.setColorAt(0.7, QColor(glow_color.red(), glow_color.green(), glow_color.blue(),
                                            int(glow_alpha * 0.33)))
                grad.setColorAt(1.0, c2)
                from PyQt6.QtGui import QBrush
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(grad))
                painter.drawEllipse(glow_center, glow_radius2, glow_radius2)
            except Exception:
                pass
            # Draw a background linear gradient behind the cover that follows
            # the player's top-area gradient (so small-mode borders match big-mode)
            try:
                try:
                    base_col = QColor(getattr(player, '_theme_color', QColor('#1f1f23')))
                except Exception:
                    base_col = QColor('#1f1f23')
                try:
                    off = getattr(player, '_grad_offset', QPointF(0.0, 0.0))
                except Exception:
                    off = QPointF(0.0, 0.0)
                try:
                    # In small mode, boost colors with brightness + spectral energy
                    if _is_small:
                        react = max(0.0, float(getattr(player, '_volume_reactivity', 1.0))) * 6.0
                        low_mul  = _bmul * (1.0 + 2.5 * _low_e  * react)
                        high_mul = _bmul * (1.0 + 2.5 * _high_e * react)
                        sx_c = QColor(
                            min(255, max(0, int(base_col.red()   * low_mul))),
                            min(255, max(0, int(base_col.green() * low_mul))),
                            min(255, max(0, int(base_col.blue()  * low_mul))),
                        )
                        ex_c = QColor(
                            min(255, max(0, int(base_col.red()   * high_mul))),
                            min(255, max(0, int(base_col.green() * high_mul))),
                            min(255, max(0, int(base_col.blue()  * high_mul))),
                        )
                        ex_c = ex_c.darker(160)
                    else:
                        sx_c = base_col
                        ex_c = QColor(base_col).darker(180)

                    sx = x + (side * (0.5 + off.x()))
                    sy = y + (side * (0.5 + off.y()))
                    ex = x + side - (side * (0.5 - off.x()))
                    ey = y + side - (side * (0.5 - off.y()))
                    g = QLinearGradient(QPointF(sx, sy), QPointF(ex, ey))
                    g.setColorAt(0.0, sx_c)
                    g.setColorAt(1.0, ex_c)
                    from PyQt6.QtGui import QBrush
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(g))
                    painter.drawRect(rectf)
                except Exception:
                    pass
            except Exception:
                pass

            # Draw the cover pixmap on top
            try:
                try:
                    # ensure we have a QPixmap and scale it to fit the square area
                    # leave a visible border by drawing the image slightly inset (use pad value)
                    border = pad if 'pad' in locals() else 8
                    img_side = max(8, int(side - border * 2))
                    if isinstance(self.cover_pixmap, QPixmap):
                        scaled = self.cover_pixmap.scaled(img_side, img_side, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    else:
                        scaled = QPixmap(self.cover_pixmap).scaled(img_side, img_side, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                except Exception:
                    scaled = None
                if scaled:
                    px = x + border + (img_side - scaled.width()) / 2
                    py = y + border + (img_side - scaled.height()) / 2
                    painter.drawPixmap(int(px), int(py), scaled)
                else:
                    # fallback: attempt to draw the original pixmap object
                    try:
                        # draw centered with border inset if possible
                        try:
                            if isinstance(self.cover_pixmap, QPixmap):
                                pm = self.cover_pixmap
                            else:
                                pm = QPixmap(self.cover_pixmap)
                            pm_scaled = pm.scaled(img_side, img_side, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            px = x + border + (img_side - pm_scaled.width()) / 2
                            py = y + border + (img_side - pm_scaled.height()) / 2
                            painter.drawPixmap(int(px), int(py), pm_scaled)
                        except Exception:
                            painter.drawPixmap(int(x), int(y), self.cover_pixmap)
                    except Exception:
                        pass
            except Exception:
                pass

        try:
            _paint_glass_reflections(self, painter, radius=10.0, intensity=0.10, spread_scale=0.62, interior_scale=0.32)
        except Exception:
            pass

        painter.end()

    def enterEvent(self, event):
        try:
            self._set_hover_controls_visible(True)
        except Exception:
            pass
        return super().enterEvent(event)

    def leaveEvent(self, event):
        try:
            QTimer.singleShot(0, self._hide_hover_controls_if_outside)
        except Exception:
            self._set_hover_controls_visible(False)
        return super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        try:
            if self._can_show_hover_controls():
                self._set_hover_controls_visible(True)
        except Exception:
            pass
        return super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        # if in small mode with no song, clicking cover should open import dialog
        parent = self.parent()
        try:
            if parent is not None and hasattr(parent, 'expanded') and not parent.expanded and getattr(parent, 'current_index', -1) == -1:
                parent.import_songs()
                return
        except Exception:
            pass
        return super().mousePressEvent(event)

    def _update_corner_animation(self):
        # advance hues and saturation/lightness subtly
        changed = False
        for i in range(4):
            self._corner_phase[i] += 0.08 + random.random() * 0.04
            self._corner_hues[i] = (self._corner_hues[i] + 0.004 * (0.5 - random.random())) % 1.0
            self._corner_saturation[i] = max(0.02, min(0.2, self._corner_saturation[i] + (random.random() - 0.5) * 0.01))
            self._corner_lightness[i] = max(0.02, min(0.2, self._corner_lightness[i] + (random.random() - 0.5) * 0.01))
            changed = True
        if changed:
            self.update()


# ClickableSlider: clicking anywhere on the groove moves the handle there immediately
class ClickableSlider(QSlider):
    def mousePressEvent(self, ev):
        try:
            if ev.button() == Qt.MouseButton.LeftButton:
                # support both Qt6 QMouseEvent.position() and older .pos()
                try:
                    posf = ev.position()
                except Exception:
                    posf = ev.pos()

                if self.orientation() == Qt.Orientation.Horizontal:
                    coord = posf.x()
                    length = max(1, self.width())
                    ratio = coord / length
                else:
                    coord = posf.y()
                    length = max(1, self.height())
                    ratio = 1.0 - (coord / length)

                ratio = max(0.0, min(1.0, float(ratio)))
                new_val = self.minimum() + int(round(ratio * (self.maximum() - self.minimum())))
                try:
                    # set value so valueChanged reflects new position
                    self.setValue(new_val)
                    # emit helpful slider signals used by app
                    try:
                        self.sliderMoved.emit(new_val)
                    except Exception:
                        pass
                    try:
                        self.sliderPressed.emit()
                    except Exception:
                        pass
                except Exception:
                    pass
                # start internal drag tracking
                try:
                    self._mouse_down = True
                except Exception:
                    self._mouse_down = False
                ev.accept()
                return
        except Exception:
            pass
        return super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        try:
            if getattr(self, '_mouse_down', False):
                try:
                    posf = ev.position()
                except Exception:
                    posf = ev.pos()
                if self.orientation() == Qt.Orientation.Horizontal:
                    coord = posf.x()
                    length = max(1, self.width())
                    ratio = coord / length
                else:
                    coord = posf.y()
                    length = max(1, self.height())
                    ratio = 1.0 - (coord / length)
                ratio = max(0.0, min(1.0, float(ratio)))
                new_val = self.minimum() + int(round(ratio * (self.maximum() - self.minimum())))
                try:
                    self.setValue(new_val)
                    try:
                        self.sliderMoved.emit(new_val)
                    except Exception:
                        pass
                except Exception:
                    pass
                ev.accept()
                return
        except Exception:
            pass
        return super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        try:
            if getattr(self, '_mouse_down', False):
                try:
                    self._mouse_down = False
                except Exception:
                    pass
                try:
                    self.sliderReleased.emit()
                except Exception:
                    pass
                ev.accept()
                return
        except Exception:
            pass
        return super().mouseReleaseEvent(ev)

    def paintEvent(self, ev):
        # For the vertical volume slider: paint a soft multi-layer shadow behind
        # the entire groove BEFORE the default slider render so the shadow appears
        # under both the track and the handle (not just the handle).
        try:
            if self.orientation() == Qt.Orientation.Vertical:
                pre = QPainter(self)
                pre.setRenderHint(QPainter.RenderHint.Antialiasing)
                groove_w = 8
                cx = self.width() // 2
                gx = cx - groove_w // 2
                gr = QRectF(gx, 4, groove_w, self.height() - 8)
                # Concentric layers — outermost (faintest) to innermost (darkest)
                for spread, alpha in [(9, 2), (6, 4), (4, 7), (2, 10), (1, 14)]:
                    r2 = gr.adjusted(-spread, -spread, spread, spread)
                    pre.fillRect(r2, QColor(0, 0, 0, alpha))
                pre.end()
        except Exception:
            pass

        super().paintEvent(ev)
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            handle_rect = self.style().subControlRect(
                QStyle.ComplexControl.CC_Slider,
                opt,
                QStyle.SubControl.SC_SliderHandle,
                self,
            )

            if handle_rect is not None and handle_rect.width() > 2 and handle_rect.height() > 2:
                rf = QRectF(handle_rect)
                # Chamfer size matching the rest of the UI
                chamfer = max(2.0, min(3.5, min(rf.width(), rf.height()) * 0.25))
                path = _chamfered_path(rf, chamfer / GLOBAL_CHAMFER_SCALE)

                p.save()
                p.setClipPath(path)
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)

                # Simple top-highlight gradient: correct regardless of slider position in the window
                if self.orientation() == Qt.Orientation.Vertical:
                    # Horizontal highlight band across the handle
                    hi = QLinearGradient(rf.left(), rf.top(), rf.left(), rf.top() + rf.height() * 0.55)
                else:
                    # Vertical highlight band across the handle
                    hi = QLinearGradient(rf.left(), rf.top(), rf.left(), rf.top() + rf.height() * 0.55)
                hi.setColorAt(0.0, QColor(255, 255, 255, 52))
                hi.setColorAt(0.45, QColor(255, 255, 255, 18))
                hi.setColorAt(1.0, QColor(255, 255, 255, 0))
                p.fillPath(path, hi)

                # Subtle left-edge glint
                left_g = QLinearGradient(rf.left(), rf.top(), rf.left() + rf.width() * 0.3, rf.top())
                left_g.setColorAt(0.0, QColor(255, 255, 255, 38))
                left_g.setColorAt(1.0, QColor(255, 255, 255, 0))
                p.fillPath(path, left_g)

                p.restore()

                # Thin rim outline
                p.save()
                rim_pen = p.pen()
                rim_pen.setWidthF(1.0)
                rim_pen.setColor(QColor(255, 255, 255, 45))
                p.setPen(rim_pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
                p.drawPath(path)
                p.restore()

            p.end()
        except Exception:
            pass


# ---------- Marquee Label (scrolling title) ----------
class MarqueeLabel(QLabel):
    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._text = text or ""
        self._text_width = 0
        self._offset = 0.0
        self._gap = 40
        self._scroll_speed_px_per_sec = 42.0
        self._pause_seconds = 2.0
        self._pause_until = time.monotonic() + self._pause_seconds
        self._fit_intro_enabled = False
        self._fit_intro_pending = False
        self._fit_intro_active = False
        self._fit_intro_duration = 2.0
        self._fit_intro_started_at = 0.0
        self._fit_intro_hold_fraction = 0.20
        self._last_tick_time = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(8)
        self._timer.timeout.connect(self._tick)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        # Sync QLabel's internal text so sizeHint reflects the actual content
        if self._text:
            try:
                self._text_width = self.fontMetrics().horizontalAdvance(self._text)
            except Exception:
                self._text_width = 0
            super().setText(self._text)

    def set_fit_intro_enabled(self, enabled: bool):
        try:
            self._fit_intro_enabled = bool(enabled)
            if not self._fit_intro_enabled:
                self._fit_intro_pending = False
                self._fit_intro_active = False
            self._update_timer()
        except Exception:
            pass

    def _bezier_ease(self, progress: float) -> float:
        try:
            t = max(0.0, min(1.0, float(progress)))
            inv = 1.0 - t
            return (3.0 * inv * t * t) + (t * t * t)
        except Exception:
            return 0.0

    def _begin_fit_intro_if_needed(self, available: int):
        try:
            if not self._fit_intro_enabled or not self._fit_intro_pending:
                return
            if not self._text or self._text_width <= max(0, int(available)):
                self._fit_intro_pending = False
                self._fit_intro_active = False
                return
            now = time.monotonic()
            self._fit_intro_pending = False
            self._fit_intro_active = True
            self._fit_intro_started_at = now
            self._pause_until = now + self._fit_intro_duration
            self._last_tick_time = now
        except Exception:
            pass

    def _scroll_start_offset(self, text_width: int = None) -> float:
        try:
            width = max(0, int(self.width()))
            tw = int(self._text_width if text_width is None else text_width)
            return max(0.0, (float(tw) - float(width)) * 0.5)
        except Exception:
            return 0.0

    def _current_intro_scale(self, available: int, text_width: int) -> float:
        try:
            if not self._fit_intro_active or available <= 0 or text_width <= 0:
                return 1.0
            fit_padding = 20.0
            padded_available = max(0.0, float(available) - fit_padding)
            fit_scale = max(0.35, min(1.0, padded_available / float(text_width)))
            if fit_scale >= 0.999:
                return 1.0
            duration = max(0.001, float(self._fit_intro_duration))
            progress = (time.monotonic() - float(self._fit_intro_started_at)) / duration
            progress = max(0.0, min(1.0, progress))
            hold_fraction = max(0.0, min(0.3, float(getattr(self, '_fit_intro_hold_fraction', 0.12))))
            travel_fraction = max(0.001, (1.0 - hold_fraction) * 0.5)
            if progress < travel_fraction:
                eased = self._bezier_ease(progress / travel_fraction)
                return 1.0 - ((1.0 - fit_scale) * eased)
            if progress <= (travel_fraction + hold_fraction):
                return fit_scale
            eased = self._bezier_ease((progress - travel_fraction - hold_fraction) / travel_fraction)
            return fit_scale + ((1.0 - fit_scale) * eased)
        except Exception:
            return 1.0

    def _playing_allows_scroll(self) -> bool:
        try:
            player = _owner_player(self)
            if player is None:
                return False
            try:
                is_playing = player.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
            except Exception:
                is_playing = False
            if not is_playing:
                return False
            if getattr(player, 'song_label', None) is self:
                return True
            host = self.parent()
            while host is not None:
                if hasattr(host, 'parent_player') and hasattr(host, '_path'):
                    try:
                        idx = getattr(player, 'current_index', -1)
                        current_path = player.playlist[idx] if 0 <= idx < len(player.playlist) else None
                    except Exception:
                        current_path = None
                    return bool(current_path and current_path == getattr(host, '_path', None))
                try:
                    host = host.parent()
                except Exception:
                    host = None
            return False
        except Exception:
            return False

    def setText(self, text: str):
        new_text = text or ""
        if new_text == getattr(self, '_text', ''):
            try:
                super().setText(new_text)
                super().update()
            except Exception:
                pass
            return

        self._text = new_text
        fm = self.fontMetrics()
        self._text_width = fm.horizontalAdvance(self._text)
        # reset offset so text starts from left
        self._offset = 0.0
        now = time.monotonic()
        self._fit_intro_pending = bool(self._fit_intro_enabled and self._text)
        self._fit_intro_active = False
        self._fit_intro_started_at = 0.0
        self._pause_until = now + self._pause_seconds
        self._last_tick_time = now
        self._update_timer()
        # Keep QLabel's internal text in sync so sizeHint() returns the
        # correct width, which matters for layout widgets that use sizeHint
        # to allocate space (e.g. PlaylistItemWidget labels with no stretch).
        super().setText(self._text)
        super().update()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._update_timer()

    def _update_timer(self):
        try:
            # if word-wrap is enabled, disable marquee scrolling
            try:
                if self.wordWrap():
                    try:
                        self._timer.stop()
                    except Exception:
                        pass
                    self._offset = 0.0
                    self.update()
                    return
            except Exception:
                pass

            available = max(0, self.width() - 8)
            self._begin_fit_intro_if_needed(available)
            try:
                should_scroll = (
                    hasattr(self, '_text_width')
                    and self._text_width > available
                    and self._playing_allows_scroll()
                )
                if self._fit_intro_active or should_scroll:
                    if not self._timer.isActive():
                        self._last_tick_time = time.monotonic()
                        self._timer.start()
                else:
                    if self._timer.isActive():
                        self._timer.stop()
                    self._offset = 0.0
            except Exception:
                pass
            self.update()
        except Exception:
            pass

    def _tick(self):
        try:
            now = time.monotonic()
            dt = max(0.0, min(0.1, now - float(getattr(self, '_last_tick_time', now))))
            self._last_tick_time = now

            if getattr(self, '_fit_intro_active', False):
                if now < getattr(self, '_pause_until', 0.0):
                    self.update()
                    return
                self._fit_intro_active = False
                self._offset = self._scroll_start_offset()
                self._pause_until = now
            if now < getattr(self, '_pause_until', 0.0):
                self.update()
                return
        except Exception:
            pass

        self._offset += float(getattr(self, '_scroll_speed_px_per_sec', 42.0)) * dt
        if hasattr(self, '_text_width'):
            cycle = self._text_width + self._gap
            if cycle > 0 and self._offset >= cycle:
                self._offset -= cycle
        self.update()

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        text = self._text
        h = self.height()
        avail = max(0, self.width() - 8)
        try:
            # word-wrap mode: draw wrapped text inside label rect
            try:
                if self.wordWrap():
                    rect = self.rect().adjusted(4, 0, -4, 0)
                    flags = Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap
                    painter.drawText(rect, int(flags), text)
                    painter.end()
                    return
            except Exception:
                pass

            draw_font = QFont(painter.font())
            base_metrics = QFontMetrics(draw_font)
            tw = base_metrics.horizontalAdvance(text)
            intro_scale = 1.0
            if self._fit_intro_active and tw > avail and avail > 0:
                intro_scale = self._current_intro_scale(avail, tw)

            if self._fit_intro_active or tw <= avail:
                # static draw — respect whatever alignment was set (defaults to center)
                try:
                    align = self.alignment()
                except Exception:
                    align = Qt.AlignmentFlag.AlignCenter
                rect = self.rect()
                if self._fit_intro_active and intro_scale < 0.999:
                    fm = painter.fontMetrics()
                    text_x = (float(rect.width()) - float(tw)) * 0.5
                    text_y = (float(rect.height()) + float(fm.ascent()) - float(fm.descent())) * 0.5
                    cx = rect.center().x() + 0.5
                    cy = rect.center().y() + 0.5
                    painter.save()
                    painter.translate(cx, cy)
                    painter.scale(intro_scale, intro_scale)
                    painter.translate(-cx, -cy)
                    painter.drawText(QPointF(text_x, text_y), text)
                    painter.restore()
                else:
                    painter.drawText(rect, align, text)
            else:
                x1 = int(round(-self._offset))
                # draw first copy
                painter.drawText(QRect(x1, 0, tw, h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
                # draw second copy after gap for smooth loop
                x2 = int(round(tw - self._offset + self._gap))
                painter.drawText(QRect(x2, 0, tw, h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
        except Exception:
            pass

        painter.end()


# ---------- Blurred Bottom Background Widget ----------
class BlurredBackgroundWidget(QWidget):
    def __init__(self, parent: 'MiniMusicPlayer'):
        super().__init__(parent)
        self.player = parent
        self._cache = {'pixmap': None, 'size': None, 'blurred': None}

    def _make_blurred(self, pixmap: QPixmap, size):
        try:
            if pixmap is None:
                return None
            from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect
            tgt = pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            scene = QGraphicsScene()
            item = QGraphicsPixmapItem(tgt)
            blur = QGraphicsBlurEffect()
            blur.setBlurRadius(24)
            item.setGraphicsEffect(blur)
            scene.addItem(item)
            result = QPixmap(size)
            result.fill(Qt.GlobalColor.transparent)
            painter = QPainter(result)
            scene.render(painter)
            painter.end()
            return result
        except Exception:
            return None

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        size = self.size()
        cover = None
        try:
            cover = getattr(self.player.cover, 'cover_pixmap', None)
        except Exception:
            cover = None

        blurred = None
        key = (id(cover) if cover is not None else None, size.width(), size.height())
        if cover is not None:
            cached = self._cache
            if cached.get('pixmap') is not cover or cached.get('size') != (size.width(), size.height()):
                blurred = self._make_blurred(cover, size)
                cached['pixmap'] = cover
                cached['size'] = (size.width(), size.height())
                cached['blurred'] = blurred
            else:
                blurred = cached.get('blurred')

        if blurred:
            try:
                painter.drawPixmap(0, 0, blurred)
            except Exception:
                pass

        # overlay a very dark translucent layer to make the area dark
        try:
            overlay = QColor(0, 0, 0, 125)
            painter.fillRect(self.rect(), overlay)
        except Exception:
            pass

        painter.end()


# ---------- Shape Button ----------
class ShapeButton(QPushButton):
    def __init__(self, shape="play"):
        super().__init__()
        self.shape = shape
        self.setFixedSize(42, 42)

        self.setStyleSheet("""
            QPushButton {
                background-color: rgba(47, 47, 53, 128);
                border-radius: 0px;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(68, 68, 68, 128);
            }
        """)

        # morph progress: 0.0 = play, 1.0 = pause
        try:
            self._morph = 0.0 if shape == "play" else 1.0
        except Exception:
            self._morph = 0.0
        self._morph_anim = None
        # try to load an external shuffle icon (shuffle.png) located next to the script
        self._shuffle_pixmap = None
        try:
            shuffle_path = resource_path('shuffle.png')
            if os.path.exists(shuffle_path):
                pm = QPixmap(resource_path('shuffle.png'))
                if not pm.isNull():
                    # invert colors while preserving alpha
                    try:
                        img = pm.toImage().convertToFormat(QImage.Format.Format_ARGB32)
                        try:
                            img.invertPixels()
                        except Exception:
                            # fallback to manual invert if method not available
                            img_bits = img.bits()
                            img_bits.setsize(img.byteCount())
                            # leave as-is if manual inversion is complex; use original
                        inv = QPixmap.fromImage(img)
                    except Exception:
                        inv = pm
                    # scale to fit button with some padding and keep transparency
                    try:
                        target = QSize(max(8, self.width()-12), max(8, self.height()-12))
                        inv = inv.scaled(target, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    except Exception:
                        pass
                    self._shuffle_pixmap = inv
        except Exception:
            self._shuffle_pixmap = None

        _apply_chamfer_mask(self, max(8.0, 6.0 * 1.8))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        _apply_chamfer_mask(self, max(8.0, 6.0 * 1.8))

    def set_shape(self, shape):
        # set shape instantly (no animation) to keep programmatic calls deterministic
        self.shape = shape
        try:
            self._morph = 0.0 if shape == "play" else 1.0
        except Exception:
            self._morph = 0.0
        self.update()

    def mousePressEvent(self, ev):
        # start a short morph animation on user press to toggle state visually
        try:
            if getattr(self, 'shape', 'play') in ('play', 'pause'):
                target = 1.0 if getattr(self, 'shape', 'play') == 'play' else 0.0
                self._animate_morph_to(target)
        except Exception:
            pass
        return super().mousePressEvent(ev)

    def _animate_morph_to(self, target: float):
        try:
            from PyQt6.QtCore import QVariantAnimation
            if getattr(self, '_morph_anim', None) is not None:
                try:
                    self._morph_anim.stop()
                except Exception:
                    pass
            anim = QVariantAnimation(self)
            anim.setStartValue(float(getattr(self, '_morph', 0.0)))
            anim.setEndValue(float(target))
            anim.setDuration(120)
            try:
                anim.valueChanged.connect(lambda v: self._set_morph(v))
            except Exception:
                pass
            def _on_finished():
                try:
                    self._morph_anim = None
                    # commit logical shape when animation finishes
                    try:
                        self.shape = 'pause' if target >= 0.5 else 'play'
                    except Exception:
                        pass
                    self._set_morph(target)
                except Exception:
                    pass
            try:
                anim.finished.connect(_on_finished)
            except Exception:
                pass
            self._morph_anim = anim
            try:
                anim.start()
            except Exception:
                # fallback: set instantly
                self._set_morph(target)
                self._morph_anim = None
        except Exception:
            pass

    def _set_morph(self, v):
        try:
            self._morph = float(v)
        except Exception:
            self._morph = 0.0
        try:
            self.update()
        except Exception:
            pass

    def _rounded_polygon_path(self, points, radius: float) -> 'QPainterPath':
        try:
            from PyQt6.QtCore import QPointF
            import math
            path = QPainterPath()
            n = len(points)
            if n == 0:
                return path
            # convert to QPointF list
            pts = [QPointF(p.x(), p.y()) for p in points]
            # compute corner offsets
            for i in range(n):
                p_prev = pts[(i - 1) % n]
                p_curr = pts[i]
                p_next = pts[(i + 1) % n]
                # vectors
                v1 = (p_prev - p_curr)
                v2 = (p_next - p_curr)
                # normalize
                def norm(v):
                    return math.hypot(v.x(), v.y())
                n1 = norm(v1)
                n2 = norm(v2)
                if n1 == 0 or n2 == 0:
                    continue
                # points along edges at distance r (clamped)
                r = float(radius)
                d1 = min(r, n1 / 2.0)
                d2 = min(r, n2 / 2.0)
                p1 = QPointF(p_curr.x() + (v1.x() / n1) * d1, p_curr.y() + (v1.y() / n1) * d1)
                p2 = QPointF(p_curr.x() + (v2.x() / n2) * d2, p_curr.y() + (v2.y() / n2) * d2)
                if i == 0:
                    path.moveTo(p1)
                else:
                    path.lineTo(p1)
                # quadratic curve through corner
                path.quadTo(p_curr, p2)
            path.closeSubpath()
            return path
        except Exception:
            return QPainterPath()

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("white"))
        painter.setPen(Qt.PenStyle.NoPen)

        w, h = self.width(), self.height()
        # draw play/pause morph only for play/pause buttons
        if getattr(self, 'shape', 'play') in ('play', 'pause'):
            morph = max(0.0, min(1.0, getattr(self, '_morph', 0.0)))

            # Play icon (angular triangle) layer
            try:
                painter.save()
                painter.setOpacity(1.0 - morph)
                pts = [
                    QPoint(int(w*0.38), int(h*0.25)),
                    QPoint(int(w*0.38), int(h*0.75)),
                    QPoint(int(w*0.72), int(h*0.50)),
                ]
                painter.drawPolygon(QPolygon(pts))
                painter.restore()
            except Exception:
                pass

            # Pause icon (two chamfered bars) layer.
            try:
                painter.save()
                painter.setOpacity(morph)
                bar_w = int(w*0.12) if int(w*0.12) > 0 else 6
                bar_h = int(h*0.5)
                _draw_chamfered_rect(painter, QRectF(float(int(w*0.32)), float(int(h*0.25)), float(bar_w), float(bar_h)), max(2.0, bar_w * 0.4))
                _draw_chamfered_rect(painter, QRectF(float(int(w*0.58)), float(int(h*0.25)), float(bar_w), float(bar_h)), max(2.0, bar_w * 0.4))
                painter.restore()
            except Exception:
                pass

        if self.shape == "next":
            pts = [
                QPoint(int(w*0.25), int(h*0.25)),
                QPoint(int(w*0.25), int(h*0.75)),
                QPoint(int(w*0.55), int(h*0.50)),
            ]
            painter.drawPolygon(QPolygon(pts))
            # chamfered bar
            bw = max(4, int(w*0.06))
            _draw_chamfered_rect(painter, QRectF(float(int(w*0.65)), float(int(h*0.25)), float(bw), float(int(h*0.5))), max(2.0, bw * 0.4))

        if self.shape == "prev":
            pts = [
                QPoint(int(w*0.75), int(h*0.25)),
                QPoint(int(w*0.75), int(h*0.75)),
                QPoint(int(w*0.45), int(h*0.50)),
            ]
            painter.drawPolygon(QPolygon(pts))
            bw = max(4, int(w*0.06))
            _draw_chamfered_rect(painter, QRectF(float(int(w*0.30)), float(int(h*0.25)), float(bw), float(int(h*0.5))), max(2.0, bw * 0.4))

        if self.shape == "shuffle":
            # if an external shuffle image was loaded, draw it (preserving alpha)
            try:
                if getattr(self, '_shuffle_pixmap', None) is not None and not self._shuffle_pixmap.isNull():
                    pm = self._shuffle_pixmap
                    x = (w - pm.width()) // 2
                    y = (h - pm.height()) // 2
                    painter.drawPixmap(x, y, pm)
                    try:
                        _paint_glass_reflections(self, painter, radius=6.0, intensity=0.18)
                    except Exception:
                        pass
                    return
            except Exception:
                pass

            # fallback: draw two crossing arrows to represent shuffle with rounded arrowheads
            pen = painter.pen()
            pen.setWidth(max(2, int(w*0.04)))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(QColor("white"))

            # first path: top-left to mid-right
            x1 = int(w*0.18)
            y1 = int(h*0.30)
            x2 = int(w*0.58)
            y2 = int(h*0.30)
            painter.drawLine(x1, y1, x2, y2)
            # rounded arrowhead at end
            ah_pts = [QPoint(x2, y2), QPoint(x2-10, y2-7), QPoint(x2-10, y2+7)]
            path = self._rounded_polygon_path(ah_pts, 3.0)
            painter.drawPath(path)

            # second path: bottom-left to mid-right
            x3 = int(w*0.18)
            y3 = int(h*0.70)
            x4 = int(w*0.58)
            y4 = int(h*0.70)
            painter.drawLine(x3, y3, x4, y4)
            ah2_pts = [QPoint(x4, y4), QPoint(x4-10, y4-7), QPoint(x4-10, y4+7)]
            path2 = self._rounded_polygon_path(ah2_pts, 3.0)
            painter.drawPath(path2)

            # crossing connectors (rounded caps)
            painter.drawLine(int(w*0.38), int(h*0.30), int(w*0.22), int(h*0.70))
            painter.drawLine(int(w*0.42), int(h*0.70), int(w*0.62), int(h*0.30))

        try:
            _paint_glass_reflections(self, painter, radius=6.0, intensity=0.18)
        except Exception:
            pass


class GlassButton(QPushButton):
    def __init__(self, *args, reflection_radius: float = 6.0, reflection_intensity: float = 0.18, **kwargs):
        super().__init__(*args, **kwargs)
        self._reflection_radius = float(reflection_radius)
        self._reflection_intensity = float(reflection_intensity)
        self._square_shape = False
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setAutoFillBackground(False)
        except Exception:
            pass

    def set_square_shape(self, enabled: bool = True):
        self._square_shape = bool(enabled)
        if self._square_shape:
            try:
                self.clearMask()
            except Exception:
                pass
        else:
            _apply_chamfer_mask(self, max(8.0, self._reflection_radius * 1.8))
        try:
            self.update()
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._square_shape:
            try:
                self.clearMask()
            except Exception:
                pass
        else:
            _apply_chamfer_mask(self, max(8.0, self._reflection_radius * 1.8))

    def paintEvent(self, event):
        super().paintEvent(event)
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            _paint_glass_reflections(self, p, radius=self._reflection_radius, intensity=self._reflection_intensity)
            p.end()
        except Exception:
            pass


class ReflectiveScrollBar(QScrollBar):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setAutoFillBackground(False)
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        _apply_chamfer_mask(self, max(8.0, 4.0 * 1.8))

    def paintEvent(self, event):
        super().paintEvent(event)
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            _paint_glass_reflections(self, p, radius=4.0, intensity=0.20)
            p.end()
        except Exception:
            pass


# ---------- Playlist Item Widget (with move handle) ----------
class PlaylistItemWidget(QWidget):
    def __init__(self, text: str, path: str, parent_player: 'MiniMusicPlayer', list_item: QListWidget):
        super().__init__()
        self._text = text
        self._path = path
        self.parent_player = parent_player
        self.list_item = list_item

        h = QHBoxLayout()
        h.setContentsMargins(6, 2, 6, 2)
        h.setSpacing(8)

        self.label = MarqueeLabel(text)
        self.label.setStyleSheet("color: white; background: transparent;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        self.move_btn = GlassButton("≡", reflection_radius=4.0, reflection_intensity=0.18)
        self.move_btn.setFixedSize(20, 20)
        self.move_btn.set_square_shape(True)
        self.move_btn.setStyleSheet("QPushButton{background:rgba(255,255,255,8);border:none;border-radius:0px;color:white;}"
                                 "QPushButton:pressed{background:rgba(255,255,255,20);}")
        self.move_btn.setCursor(Qt.CursorShape.OpenHandCursor)

        self.delete_btn = GlassButton("✕", reflection_radius=6.0, reflection_intensity=0.42)
        self.delete_btn.setFixedSize(20, 20)
        self.delete_btn.set_square_shape(True)
        self.delete_btn.setStyleSheet("QPushButton{background:rgba(255,100,100,38);border:none;border-radius:0px;color:white;}"
                         "QPushButton:hover{background:rgba(255,110,110,55);}"
                         "QPushButton:pressed{background:rgba(255,50,50,70);}")
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.setToolTip("Delete Song")

        h.addWidget(self.label)
        h.addStretch(1)
        h.addWidget(self.delete_btn)
        h.addWidget(self.move_btn)

        self.setLayout(h)

        # wire drag start into the main player for playlist reordering
        try:
            def on_move_pressed():
                self.parent_player.start_playlist_drag(self.list_item)
            self.move_btn.pressed.connect(on_move_pressed)
        except Exception:
            pass
        # wire delete button to remove song
        try:
            def on_delete_clicked():
                self.parent_player.delete_song(self.list_item)
            self.delete_btn.clicked.connect(on_delete_clicked)
        except Exception:
            pass

        # inline edit state
        self._edit = None

        # allow double-click on the label to rename as a convenience
        try:
            self.label.mouseDoubleClickEvent = lambda ev: self.start_inline_rename()
        except Exception:
            pass

    def start_inline_rename(self):
        if self._edit is not None:
            return
        try:
            # create line edit and replace label in layout
            self._edit = QLineEdit(self._text, self)
            self._edit.setFixedHeight(self.label.sizeHint().height())
            self._edit.returnPressed.connect(self._finish_inline_rename)
            self._edit.editingFinished.connect(self._finish_inline_rename)

            layout = self.layout()
            # find the label index
            idx = None
            for i in range(layout.count()):
                if layout.itemAt(i).widget() is self.label:
                    idx = i
                    break
            if idx is not None:
                layout.removeWidget(self.label)
                self.label.hide()
                layout.insertWidget(idx, self._edit)
            else:
                layout.addWidget(self._edit)

            self._edit.setFocus()
            self._edit.selectAll()
        except Exception:
            self._edit = None

    def _finish_inline_rename(self):
        if self._edit is None:
            return
        # Grab and clear self._edit immediately to prevent re-entrant calls
        # (removeWidget causes focus loss which fires editingFinished synchronously)
        edit = self._edit
        self._edit = None
        try:
            new_text = edit.text().strip() or self._text
            self._text = new_text
            self.label.setText(new_text)
            self.label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            # restore label in layout
            layout = self.layout()
            # find current position of the edit widget so label goes back there
            edit_idx = 0
            for i in range(layout.count()):
                if layout.itemAt(i).widget() is edit:
                    edit_idx = i
                    break
            try:
                layout.removeWidget(edit)
            except Exception:
                pass
            try:
                edit.deleteLater()
            except Exception:
                pass
            # re-insert label at its original position in the layout
            layout.insertWidget(edit_idx, self.label)
            self.label.show()
            # update associated list item's stored display name
            try:
                if self.list_item is not None:
                    # custom role: UserRole + 1 stores display name
                    self.list_item.setData(Qt.ItemDataRole.UserRole + 1, new_text)
            except Exception:
                pass
        except Exception:
            pass

    def sizeHint(self):
        return QSize(260, 28)


# ---------- Main Player ----------

class MiniMusicPlayer(QWidget):
    # signal emitted by the background hotkey thread when F10 is pressed globally
    global_hotkey = pyqtSignal()
    global_hotkey_next = pyqtSignal()
    global_hotkey_prev = pyqtSignal()
    global_hotkey_pause = pyqtSignal()
    global_hotkey_drag = pyqtSignal()
    global_hotkey_drag_release = pyqtSignal()

    def _update_song_label_color(self):
        # Only update in expanded (big) mode
        if not getattr(self, 'expanded', False):
            return
        if not hasattr(self, 'song_label'):
            return
        label = self.song_label
        # Use the theme color directly instead of expensive self.grab()
        tc = getattr(self, '_theme_color', QColor("#1f1f23"))
        bmul = getattr(self, '_auto_brightness', 1.0)
        r = min(255, max(0, int(tc.red() * bmul)))
        g = min(255, max(0, int(tc.green() * bmul)))
        b = min(255, max(0, int(tc.blue() * bmul)))
        brightness = 0.299 * r + 0.587 * g + 0.114 * b
        new_color = "black" if brightness > 140 else "white"
        # Only update stylesheet if the color actually changed
        old_color = getattr(self, '_last_label_color', None)
        if new_color != old_color:
            self._last_label_color = new_color
            label.setStyleSheet(f"color: {new_color};")

    def _start_song_label_color_timer(self):
        # Start a timer to update the song label color in real time
        from PyQt6.QtCore import QTimer
        if hasattr(self, '_song_label_color_timer') and self._song_label_color_timer is not None:
            return
        self._song_label_color_timer = QTimer(self)
        self._song_label_color_timer.timeout.connect(self._update_song_label_color)
        self._song_label_color_timer.start(250)  # update every 250ms

    def __init__(self):

        # Remove window title bar for a clean, borderless UI
        super().__init__()
        try:
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        except Exception:
            pass

        # --- Hotkey settings ---
        self._hotkey_setting = self._load_hotkey_setting()
        self._hotkey_listen = False
        self._hotkey_pending = None
        
        # Multi-hotkey support
        self._hotkey_toggle_vk = 0x78   # F9 default
        self._hotkey_drag_vk = 0x79     # F10 default
        self._hotkey_next_vk = 0x21     # Page Up default
        self._hotkey_prev_vk = 0x22     # Page Down default
        self._global_hotkeys = {
            'toggle': {'vk': self._hotkey_toggle_vk, 'mod': 0},
            'drag':   {'vk': self._hotkey_drag_vk,   'mod': 0},
            'next': {'vk': self._hotkey_next_vk, 'mod': 0},    # Page Up - next song
            'prev': {'vk': self._hotkey_prev_vk, 'mod': 0},    # Page Down - previous song
            'pause': {'vk': 0x13, 'mod': 0}    # Pause/Break - pause/play
        }
        
        # --- User settings ---
        self._load_settings()
        # Apply saved hotkey VK codes
        self._global_hotkeys['toggle']['vk'] = self._hotkey_toggle_vk
        self._global_hotkeys['drag']['vk'] = self._hotkey_drag_vk
        self._global_hotkeys['next']['vk'] = self._hotkey_next_vk
        self._global_hotkeys['prev']['vk'] = self._hotkey_prev_vk



        self.setStyleSheet(self.dark_style())

        self.expanded = False
        self.playlist = []
        self.current_index = -1
        self._theme_colors = {}
        self._custom_covers = {}
        self._cover_art_cache = {}
        try:
            pending = getattr(self, '_pending_theme_colors', None)
            if isinstance(pending, dict) and pending:
                self._theme_colors.update(pending)
        except Exception:
            pass
        try:
            pending_covers = getattr(self, '_pending_custom_covers', None)
            if isinstance(pending_covers, dict) and pending_covers:
                self._custom_covers.update(pending_covers)
        except Exception:
            pass
        self._theme_color = QColor("#1f1f23")
        self._grad_offset = QPointF(0.0, 0.0)
        self._drag_active = False
        self._drag_pos = QPoint()
        self._f11_move_active = False
        self._f11_move_timer = None
        self._f11_follow_x = 0.0
        self._f11_follow_y = 0.0
        self._f11_vel_x = 0.0
        self._f11_vel_y = 0.0
        self._f11_follow_initialized = False
        self._f10_down = False
        self._f11_down = False
        self._time_left_mode = False
        self._seeking = False
        self._duration_ms = 0
        self._mode_anim = None
        self._snap_anim = None
        self._fade_anim = None
        self._close_anim = None
        self._close_opacity_anim = None
        self._close_audio_anim = None
        self._closing_in_progress = False
        self._allow_close = False
        self._close_restore_volume = None
        self._close_quit_on_last_window_closed = None
        self._rev_player = None
        self._rev_audio = None
        self._rev_effect = None
        self._rev_tmp = None
        self._edge_sampler = None
        # crossfade state
        self._crossfade_timer = None
        self._crossfade_from_player = None
        self._crossfade_from_audio = None
        self._crossfade_to_player = None
        self._crossfade_to_audio = None
        self._crossfade_duration_ms = 500
        self._crossfade_start_time = None
        self._crossfade_target_index = None
        # how strongly the gradient brightness reacts to audio volume (1.0 = as before)
        self._volume_reactivity = 2.5
        # alpha for expanded-mode glass background (lower = more transparent)
        self._expanded_glass_alpha = 146

        self.setMouseTracking(True)
        # accept keyboard focus so keyPressEvent (F10) works
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Show load.PNG on cover if no song is selected (for small mode)

        try:
            if self.current_index == -1 or not self.playlist:
                self.cover.set_cover(load_cover_asset_path())
        except Exception:
            pass

        # graphics mode setting (default)
        self.graphics_mode = "gradient"

        # audio
        self.player = QMediaPlayer()
        self.audio = QAudioOutput()
        self.player.setAudioOutput(self.audio)
        try:
            self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        except Exception:
            pass
        try:
            self.player.playbackStateChanged.connect(self._on_playback_state_changed)
        except Exception:
            pass

        # Follow the default audio output device when the user switches it
        try:
            self._media_devices = QMediaDevices(self)
            self._media_devices.audioOutputsChanged.connect(self._on_audio_outputs_changed)
        except Exception:
            pass

        # spectral probe state
        self._low_energy = 0.0
        self._high_energy = 0.0
        self._audio_probes = []

        # BPM detection state
        self._bpm_onsets = []          # list of (monotonic_time, onset_strength)
        self._current_bpm = 0          # last computed BPM (int)
        self._bpm_confidence = 0.0     # 0.0 -> 1.0 confidence for the current BPM guess
        self._bpm_phase_time = 0.0     # last onset used to align predicted beat pulses
        self._bpm_last_predict = 0.0   # last synthetic beat pulse timestamp
        self._bpm_prev_energy = 0.0    # previous low-band energy sample
        self._bpm_low_floor = 0.0      # adaptive floor for low-frequency energy
        self._bpm_flux_floor = 0.0     # adaptive floor for onset flux
        self._bpm_prev_band_energies = None
        self._beat_pulse = 0.0         # 0→1 flash on each beat, decays to 0

        # Rolling PCM buffer for reversed-audio close animation
        self._pcm_rolling_buffer = bytearray()
        self._pcm_fmt = (44100, 2, 16)  # (sample_rate, channels, sample_size)
        try:
            from PyQt6.QtMultimedia import QAudioProbe
            def _attach(p):
                try:
                    # Clean up old probes before attaching new ones
                    for old_probe in self._audio_probes:
                        try:
                            old_probe.setSource(None)
                        except Exception:
                            pass
                        try:
                            old_probe.deleteLater()
                        except Exception:
                            pass
                    self._audio_probes.clear()
                    probe = QAudioProbe()
                    probe.audioBufferProbed.connect(self._on_audio_buffer_probed)
                    probe.setSource(p)
                    self._audio_probes.append(probe)
                except Exception:
                    pass
            # attach probe to main player
            try:
                _attach(self.player)
            except Exception:
                pass
            self._attach_probe = _attach

            # --- Restore album cover if a song is playing and cover is missing ---
            try:
                if self.current_index != -1 and self.playlist:
                    # Only reload if cover is missing
                    if not getattr(self.cover, 'cover_pixmap', None):
                        self.load_cover_art(self.playlist[self.current_index])
            except Exception:
                pass

        except Exception:
            self._attach_probe = lambda p: None

        self.setup_ui()
        try:
            self._init_system_volume_sync()
        except Exception:
            pass
        try:
            app = QApplication.instance()
            if app is not None:
                app.installEventFilter(self)
        except Exception:
            pass
        try:
            self._edge_sampler = EdgeEnvironmentSampler(fps=12, thickness=28, outward_offset=4, smoothing=0.34)
            self._edge_sampler.start()
            self._update_edge_sampler_geometry()
        except Exception:
            self._edge_sampler = None
        # start with drops disabled; expand_mode will enable drops when showing big UI
        try:
            self.setAcceptDrops(False)
        except Exception:
            pass
        # connect global hotkey signals and start listener
        try:
            self.global_hotkey.connect(self._on_global_hotkey)
            self.global_hotkey_next.connect(self._on_global_hotkey_next)
            self.global_hotkey_prev.connect(self._on_global_hotkey_prev)
            self.global_hotkey_pause.connect(self._on_global_hotkey_pause)
            self.global_hotkey_drag.connect(self._on_global_hotkey_drag)
            self.global_hotkey_drag_release.connect(self._on_global_hotkey_drag_release)
            self._start_global_hotkey_listener()
            self._start_drag_key_poller()
        except Exception:
            pass
        # load saved playlist if present
        try:
            self.load_saved_playlist()
        except Exception:
            pass
        # start the app in expanded (big) mode
        self._startup_sound_suppressed = True
        self.expand_mode()
        self._startup_sound_suppressed = False

        # position the window nearer the screen corner
        self.move(8, 8)

        # start automatic gradient animation (random motion + fade)
        try:
            self._start_auto_gradient()
        except Exception:
            pass

        # optional self-test when env var set
        try:
            if os.environ.get('MUSIC_ISLAND_TEST'):
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(800, self._run_self_test)
        except Exception:
            pass

    def setup_ui(self):
        # Main layout for the widget
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.setLayout(self.main_layout)
        
        # Initialize cover widget
        self.cover = CoverWidget()
        self.cover.setFixedSize(104, 104)
        
        # Player + audio are already created in __init__ (self.player / self.audio);
        # create the alias that the volume slider handler expects.
        self.audio_output = self.audio
        
        # Initialize UI components that were previously scattered
        self._init_ui_components()
        
    def _init_ui_components(self):
        # Import button with overlaid label
        self.import_btn = GlassButton("", self, reflection_radius=8.0, reflection_intensity=0.18)
        self.import_btn.setStyleSheet("""
            QPushButton {
                background: rgba(47, 47, 53, 128);
                border: none;
                border-radius: 0px;

        # Start the real-time song label color updater
        self._start_song_label_color_timer()
                padding: 8px;
                color: white;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(67, 67, 73, 128);
                border: none;
            }
            QPushButton:pressed {
                background: rgba(37, 37, 43, 128);
                border: none;
            }
        """)
        # Label overlaid on top of the button, left-aligned
        self.import_label = QLabel("import music.", self.import_btn)
        self.import_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 0px;
                background: transparent;
            }
        """)
        self.import_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        btn_layout = QHBoxLayout(self.import_btn)
        btn_layout.setContentsMargins(8, 0, 8, 0)
        btn_layout.addWidget(self.import_label, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.import_btn.setFixedHeight(self.import_label.sizeHint().height() + 12)
        try:
            self.import_btn.clicked.connect(self.import_songs)
        except Exception:
            pass
        
        # Playlist widget
        self.list_widget = QListWidget(self)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background: rgba(47, 47, 53, 128);
                border: none;
                border-radius: 0px;
                padding: 0px;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 2px;
                border-bottom: 1px solid rgba(255, 255, 255, 10);
                min-height: 20px;
            }
            QListWidget::item:selected {
                background: rgba(255, 255, 255, 20);
            }
            QScrollBar:vertical {
                background: rgba(255,255,255,10);
                width: 12px;
                margin: 2px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: rgba(74,144,226,128);
                min-height: 24px;
                border-radius: 0px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(90,160,242,150);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                border: none;
                background: transparent;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QScrollBar:horizontal {
                background: rgba(255,255,255,10);
                height: 12px;
                margin: 2px;
                border: none;
            }
            QScrollBar::handle:horizontal {
                background: rgba(74,144,226,128);
                min-width: 24px;
                border-radius: 0px;
            }
            QScrollBar::handle:horizontal:hover {
                background: rgba(90,160,242,150);
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                border: none;
                background: transparent;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
            }
        """)
        try:
            self.list_widget.itemClicked.connect(self.play_selected)
            self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        except Exception:
            pass
        try:
            self.list_widget.setVerticalScrollBar(ReflectiveScrollBar(Qt.Orientation.Vertical, self.list_widget))
            self.list_widget.setHorizontalScrollBar(ReflectiveScrollBar(Qt.Orientation.Horizontal, self.list_widget))
        except Exception:
            pass
        
        # Seek slider
        self.seek_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        try:
            self.seek_slider.sliderPressed.connect(self._on_seek_pressed)
            self.seek_slider.sliderReleased.connect(self._on_seek_released)
            self.seek_slider.sliderMoved.connect(self._on_seek_moved)
        except Exception:
            pass
        
        # Time labels
        self.time_left = QLabel("0:00")
        self.time_right = QLabel("0:00")
        self.time_left.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.time_right.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.time_left.setStyleSheet("color: rgba(255,255,255,200);")
        self.time_right.setStyleSheet("color: rgba(255,255,255,200);")
        self.time_left.mousePressEvent = self._toggle_time_mode
        
        # Setup the rest of the UI
        self._setup_complete_ui()
        
        # Apply initial gray slider style (no song loaded yet)
        try:
            self._update_slider_styles()
        except Exception:
            pass
        
        # Initialize tutorial system
        self._tutorial_popup = None
        self._tutorial_step = 0
        self._tutorial_active = False
        self._check_and_start_tutorial()

    def _check_and_start_tutorial(self):
        """Check if tutorial should be shown and start it if needed"""
        try:
            tutorial_completed = getattr(self, '_tutorial_completed', False)
            if not tutorial_completed:
                QTimer.singleShot(1000, self._start_tutorial)
        except Exception:
            pass

    def _start_tutorial(self):
        """Show the single welcome popup centered on the player."""
        try:
            if self._tutorial_popup:
                self._tutorial_popup.close()
                self._tutorial_popup = None
            popup = TutorialPopup(self)
            popup.dismissed.connect(self._complete_tutorial)
            # Center on the player window
            try:
                pr = self.geometry()
                ps = popup.sizeHint()
                popup.move(
                    pr.x() + (pr.width() - ps.width()) // 2,
                    pr.y() + (pr.height() - ps.height()) // 2,
                )
            except Exception:
                popup.move(self.x() + 40, self.y() + 40)
            popup.show()
            self._tutorial_popup = popup
        except Exception:
            self._complete_tutorial()

    def _complete_tutorial(self):
        """Complete the tutorial"""
        try:
            if self._tutorial_popup:
                self._tutorial_popup.close()
                self._tutorial_popup = None
            self._tutorial_active = False
            self._tutorial_completed = True
            self._save_settings()  # Save that tutorial is completed
        except Exception:
            pass

    def _setup_complete_ui(self):
        # Song label
        self.song_label = MarqueeLabel("No song.")
        self.song_label.set_fit_intro_enabled(True)
        self.song_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Apply font setting based on user preference (loaded earlier)
        self._apply_font_setting()
        
        self.song_label.setMinimumWidth(0)
        # Ignore the label's natural text width so long titles stay within the
        # player bounds and use marquee scrolling instead of widening the app.
        self.song_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        try:
            self.song_label.setWordWrap(False)
        except Exception:
            pass

        self.song_opacity = QGraphicsOpacityEffect(self.song_label)
        self.song_label.setGraphicsEffect(self.song_opacity)
        self.song_opacity.setOpacity(1.0)

        # Ensure song label color is updated after UI changes
        self.song_label.installEventFilter(self)
        self.cover_opacity = QGraphicsOpacityEffect(self.cover)
        self.cover.setGraphicsEffect(self.cover_opacity)
        self.cover_opacity.setOpacity(1.0)

        # Control buttons
        self.btn_prev = ShapeButton("prev")
        self.btn_play = ShapeButton("play")
        self.btn_next = ShapeButton("next")
        self.btn_shuffle = ShapeButton("shuffle")
        
        try:
            self.btn_shuffle.clicked.connect(self.shuffle_playlist)
        except Exception:
            pass

        self.btn_prev.clicked.connect(self.prev_track)
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_next.clicked.connect(self.next_track)
        
        # Volume control
        self.volume = ClickableSlider(Qt.Orientation.Vertical)
        self.volume.setRange(0, 100)
        self.volume.setValue(70)
        try:
            self.volume.valueChanged.connect(self._on_volume_changed)
        except Exception:
            pass

        # Setup layouts
        controls = QHBoxLayout()
        controls.addWidget(self.btn_prev)
        controls.addWidget(self.btn_play)
        controls.addWidget(self.btn_next)
        controls.addWidget(self.btn_shuffle)

        # Seek row
        seek_row = QHBoxLayout()
        seek_row.addWidget(self.time_left)
        seek_row.addWidget(self.seek_slider, 1)
        seek_row.addWidget(self.time_right)

        # Connect player signals
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.positionChanged.connect(self._on_position_changed)

        # Top widget
        self.top_widget = QWidget()
        # Lighter glass layer so cover/title/volume area keeps ambient transparency.
        self.top_widget.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "stop:0 rgba(18,18,24,92), stop:0.38 rgba(18,18,24,72), stop:0.72 rgba(18,18,24,38), stop:1 rgba(18,18,24,0));"
        )
        top_row = QHBoxLayout()
        top_row.setContentsMargins(12, 6, 12, 6)
        top_row.setSpacing(8)

        top_left = QHBoxLayout()
        top_left.setContentsMargins(0, 0, 0, 0)
        top_left.setSpacing(0)
        
        cover_container = QVBoxLayout()
        cover_container.setContentsMargins(0, 0, 0, 0)
        cover_container.setSpacing(0)
        cover_container.addWidget(self.cover, 0, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        top_left.addLayout(cover_container, 0)
        
        text_btns_layout = QVBoxLayout()
        text_btns_layout.setContentsMargins(8, 0, 0, 0)
        text_btns_layout.setSpacing(8)
        text_btns_layout.addWidget(self.song_label)

        # BPM display label (shown below song title in big mode)
        self.bpm_label = QLabel("")
        self.bpm_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bpm_label.setStyleSheet("color: rgba(255,255,255,90); font-size: 10px; background: transparent;")
        self.bpm_label.setFixedHeight(14)
        text_btns_layout.addWidget(self.bpm_label)

        top_left.addLayout(text_btns_layout, 1)

        top_row.addLayout(top_left, 1)
        top_row.addStretch(0)
        top_row.addWidget(self.volume, 0, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        # Keep volume clear of the top-right chamfer cut.
        top_row.addSpacing(14)
        self.top_widget.setLayout(top_row)

        # Bottom widget
        self.bottom_widget = BlurredBackgroundWidget(self)
        bottom_layout = QVBoxLayout()
        bottom_layout.setContentsMargins(12, 6, 12, 12)
        bottom_layout.setSpacing(8)

        bottom_layout.addLayout(seek_row)
        bottom_layout.addLayout(controls)
        bottom_layout.addWidget(self.import_btn)
        bottom_layout.addWidget(self.list_widget)

        self.bottom_widget.setLayout(bottom_layout)

        # Add widgets to main layout
        self.main_layout.addWidget(self.top_widget)
        self.main_layout.addWidget(self.bottom_widget)
        
        # Create window control buttons
        self.drag_btn = GlassButton("", self, reflection_radius=5.0, reflection_intensity=0.20)
        self.drag_btn.setFixedSize(20, 20)
        self.drag_btn.set_square_shape(True)
        self.drag_btn.setCursor(Qt.CursorShape.OpenHandCursor)
        self.drag_btn.setStyleSheet("""
            QPushButton {
                background: rgba(31,31,35,128);
                border: none;
                border-radius: 0px;
            }
            QPushButton:hover {
                background: rgba(51,51,55,160);
            }
        """)
        try:
            drag_pm = load_inverted_png_icon(load_drag_asset_path(), QSize(12, 12))
            if drag_pm is not None and not drag_pm.isNull():
                self.drag_btn.setIcon(QIcon(drag_pm))
                self.drag_btn.setIconSize(drag_pm.size())
                self.drag_btn.setText("")
        except Exception:
            pass
        
        self.settings_btn = GlassButton("⚙", self, reflection_radius=5.0, reflection_intensity=0.20)
        self.settings_btn.setFixedSize(20, 20)
        self.settings_btn.set_square_shape(True)
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background: rgba(31,31,35,128);
                border: none;
                border-radius: 0px;
                color: white;
            }
            QPushButton:hover {
                background: rgba(51,51,55,160);
            }
        """)
        
        self.close_btn = GlassButton("", self, reflection_radius=5.0, reflection_intensity=0.22)
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.set_square_shape(True)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,100,100,38);
                border: none;
                border-radius: 0px;
            }
            QPushButton:hover {
                background: rgba(255,80,80,55);
            }
            QPushButton:pressed {
                background: rgba(255,50,50,70);
            }
        """)
        self.close_btn.clicked.connect(self._on_close_clicked)

        # Drop shadows on all interactive / visible elements (song_label and cover
        # are excluded because they already carry a QGraphicsOpacityEffect and Qt
        # only permits one graphics effect per widget at a time).
        try:
            from PyQt6.QtWidgets import QGraphicsDropShadowEffect

            def _make_shadow(blur=18, alpha=140, ox=0, oy=0):
                s = QGraphicsDropShadowEffect()
                s.setBlurRadius(blur)
                s.setOffset(ox, oy)
                s.setColor(QColor(0, 0, 0, alpha))
                return s

            for _w in (
                self.seek_slider,
                self.time_left, self.time_right,
                self.import_btn,
                self.list_widget,
                self.btn_prev, self.btn_play, self.btn_next, self.btn_shuffle,
                self.drag_btn, self.settings_btn, self.close_btn,
            ):
                try:
                    _w.setGraphicsEffect(_make_shadow())
                except Exception:
                    pass
        except Exception:
            pass

        # Wire the drag and settings buttons
        try:
            def on_drag_pressed():
                self.start_drag()
            self.drag_btn.pressed.connect(on_drag_pressed)
        except Exception:
            pass
            
        try:
            def on_settings_clicked():
                self.open_settings()
            self.settings_btn.clicked.connect(on_settings_clicked)
        except Exception:
            pass

    def _run_self_test(self):
        try:
            self.btn_play.click()
            self.btn_prev.click()
            self.btn_next.click()
        except Exception:
            pass
        sample = os.path.expanduser(r'~/Downloads/HOME - Resonance 4.mp3')
        if os.path.exists(sample):
            try:
                self.load_cover_art(sample)
            except Exception:
                pass

    def _on_global_hotkey(self):
        try:
            if getattr(self, '_f11_down', False):
                return
            # toggle visibility/expanded mode when hotkey pressed
            if self.expanded:
                self.shrink_mode()
            else:
                self.expand_mode()
                try:
                    self.raise_()
                    self.activateWindow()
                except Exception:
                    pass
                # Force the window to the foreground even when the app isn't focused
                try:
                    if sys.platform == 'win32':
                        import ctypes
                        hwnd = int(self.winId())
                        ctypes.windll.user32.ShowWindow(hwnd, 9)   # SW_RESTORE
                        ctypes.windll.user32.SetForegroundWindow(hwnd)
                except Exception:
                    pass
        except Exception:
            pass

    def _on_global_hotkey_next(self):
        """Handler for Page Down - next song"""
        try:
            self.next_track()
        except Exception:
            pass

    def _on_global_hotkey_prev(self):
        """Handler for Page Up - previous song"""
        try:
            self.prev_track()
        except Exception:
            pass

    def _on_global_hotkey_pause(self):
        """Handler for Pause/Break - pause/play"""
        try:
            self.toggle_play()
        except Exception:
            pass

    def _on_global_hotkey_drag(self):
        """Handler for global drag/snap-to-cursor key press."""
        try:
            self._f11_down = True
            if getattr(self, '_f10_down', False):
                return
            self._start_f11_move_mode()
        except Exception:
            pass

    def _on_global_hotkey_drag_release(self):
        """Handler for global drag/snap-to-cursor key release."""
        try:
            self._f11_down = False
            self._stop_f11_move_mode()
        except Exception:
            pass

    def _start_drag_key_poller(self):
        """Poll GetAsyncKeyState for the drag/snap key since RegisterHotKey
        doesn't support key-up detection needed for hold-to-move."""
        if sys.platform != 'win32':
            return
        try:
            import ctypes
            self._drag_key_was_down = False
            self._drag_key_poll_timer = QTimer(self)
            self._drag_key_poll_timer.setInterval(16)

            def _poll():
                try:
                    vk = getattr(self, '_hotkey_drag_vk', 0x79)
                    state = ctypes.windll.user32.GetAsyncKeyState(vk)
                    is_down = bool(state & 0x8000)
                    if is_down and not self._drag_key_was_down:
                        self._drag_key_was_down = True
                        self._on_global_hotkey_drag()
                    elif not is_down and self._drag_key_was_down:
                        self._drag_key_was_down = False
                        self._on_global_hotkey_drag_release()
                except Exception:
                    pass

            self._drag_key_poll_timer.timeout.connect(_poll)
            self._drag_key_poll_timer.start()
        except Exception:
            pass

    def _ensure_always_on_top(self):
        try:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        except Exception:
            pass
        try:
            if sys.platform == 'win32':
                import ctypes
                hwnd = int(self.winId())
                HWND_TOPMOST = -1
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_NOACTIVATE = 0x0010
                SWP_SHOWWINDOW = 0x0040
                ctypes.windll.user32.SetWindowPos(
                    hwnd,
                    HWND_TOPMOST,
                    0,
                    0,
                    0,
                    0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
                )
        except Exception:
            pass

    def _start_global_hotkey_listener(self):
        """Register system-wide hotkeys.  Primary: RegisterHotKey.
        Fallback: WH_KEYBOARD_LL low-level hook (works even if RegisterHotKey
        fails because another process already claimed a key)."""
        if sys.platform != 'win32':
            return
        try:
            import ctypes
            from ctypes import wintypes
            import threading
            import time

            user32 = ctypes.windll.user32

            # --- stop any previous listener ---
            stop_event = getattr(self, '_hotkey_listener_stop', None)
            if stop_event:
                stop_event.set()
                time.sleep(0.05)

            self._hotkey_listener_stop = threading.Event()
            stop_event = self._hotkey_listener_stop

            # VK codes we care about (built from _global_hotkeys)
            toggle_vk = self._global_hotkeys.get('toggle', {}).get('vk', 0x79)
            drag_vk   = self._global_hotkeys.get('drag',   {}).get('vk', 0x7A)
            next_vk   = self._global_hotkeys.get('next',   {}).get('vk', 0x21)
            prev_vk   = self._global_hotkeys.get('prev',   {}).get('vk', 0x22)
            pause_vk  = self._global_hotkeys.get('pause',  {}).get('vk', 0x13)

            def _emit_for_vk(vk):
                if vk == toggle_vk:
                    self.global_hotkey.emit()
                elif vk == drag_vk:
                    self.global_hotkey_drag.emit()
                elif vk == next_vk:
                    self.global_hotkey_next.emit()
                elif vk == prev_vk:
                    self.global_hotkey_prev.emit()
                elif vk == pause_vk:
                    self.global_hotkey_pause.emit()

            def _emit_release_for_vk(vk):
                if vk == drag_vk:
                    self.global_hotkey_drag_release.emit()

            # ── PRIMARY: RegisterHotKey ──────────────────────────────────────
            def register_hotkey_thread():
                """Thread that uses RegisterHotKey + message pump."""
                try:
                    WM_HOTKEY = 0x0312
                    hotkey_ids = {}
                    hk_id = 1
                    for name, hk in self._global_hotkeys.items():
                        # Skip drag key — it needs key-up support via LL hook
                        if name == 'drag':
                            continue
                        if user32.RegisterHotKey(None, hk_id, hk['mod'], hk['vk']):
                            hotkey_ids[hk_id] = hk['vk']
                            hk_id += 1

                    if not hotkey_ids:
                        # Registration failed — the LL-hook fallback will cover us
                        return

                    class MSG(ctypes.Structure):
                        _fields_ = [
                            ('hwnd',    wintypes.HWND),
                            ('message', wintypes.UINT),
                            ('wParam',  wintypes.WPARAM),
                            ('lParam',  wintypes.LPARAM),
                            ('time',    wintypes.DWORD),
                            ('pt',      wintypes.POINT),
                        ]

                    msg = MSG()
                    while not stop_event.is_set():
                        try:
                            if user32.PeekMessageA(ctypes.byref(msg), None, 0, 0, 1):
                                if msg.message == WM_HOTKEY:
                                    vk = hotkey_ids.get(int(msg.wParam))
                                    if vk is not None:
                                        _emit_for_vk(vk)
                            time.sleep(0.008)
                        except Exception:
                            break

                    for hid in hotkey_ids:
                        try:
                            user32.UnregisterHotKey(None, hid)
                        except Exception:
                            pass
                except Exception:
                    pass

            threading.Thread(target=register_hotkey_thread, daemon=True).start()

            # ── FALLBACK: WH_KEYBOARD_LL low-level hook ──────────────────────
            # This always fires regardless of focus and works even if
            # RegisterHotKey couldn't claim the key.
            _watched_vks = {toggle_vk, drag_vk, next_vk, prev_vk, pause_vk}
            _key_pressed = set()  # debounce: emit only on key-down, not repeat

            WH_KEYBOARD_LL = 13
            WM_KEYDOWN     = 0x0100
            WM_SYSKEYDOWN  = 0x0104

            class KBDLLHOOKSTRUCT(ctypes.Structure):
                _fields_ = [
                    ('vkCode',      wintypes.DWORD),
                    ('scanCode',    wintypes.DWORD),
                    ('flags',       wintypes.DWORD),
                    ('time',        wintypes.DWORD),
                    ('dwExtraInfo', wintypes.ULONG_PTR),
                ]

            HOOK_PROC_TYPE = ctypes.WINFUNCTYPE(
                ctypes.c_longlong,
                ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
            )

            def _ll_keyboard_proc(nCode, wParam, lParam):
                try:
                    if nCode == 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                        kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                        vk = int(kb.vkCode)
                        if vk in _watched_vks and vk not in _key_pressed:
                            _key_pressed.add(vk)
                            _emit_for_vk(vk)
                    elif wParam not in (WM_KEYDOWN, WM_SYSKEYDOWN):
                        # key up — clear debounce and emit release signals
                        try:
                            kb2 = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                            vk2 = int(kb2.vkCode)
                            _key_pressed.discard(vk2)
                            _emit_release_for_vk(vk2)
                        except Exception:
                            pass
                except Exception:
                    pass
                return user32.CallNextHookEx(
                    getattr(self, '_ll_kb_hook', None), nCode, wParam, lParam
                )

            _ll_proc_ref = HOOK_PROC_TYPE(_ll_keyboard_proc)

            def ll_hook_thread():
                try:
                    kernel32 = ctypes.windll.kernel32
                    hook = user32.SetWindowsHookExW(
                        WH_KEYBOARD_LL,
                        _ll_proc_ref,
                        kernel32.GetModuleHandleW(None),
                        0,
                    )
                    self._ll_kb_hook = hook
                    if not hook:
                        return

                    class MSG2(ctypes.Structure):
                        _fields_ = [
                            ('hwnd',    wintypes.HWND),
                            ('message', wintypes.UINT),
                            ('wParam',  wintypes.WPARAM),
                            ('lParam',  wintypes.LPARAM),
                            ('time',    wintypes.DWORD),
                            ('pt',      wintypes.POINT),
                        ]

                    msg2 = MSG2()
                    while not stop_event.is_set():
                        # GetMessage blocks until a message arrives — ideal for hooks
                        result = user32.PeekMessageA(ctypes.byref(msg2), None, 0, 0, 1)
                        if result:
                            user32.TranslateMessage(ctypes.byref(msg2))
                            user32.DispatchMessageA(ctypes.byref(msg2))
                        time.sleep(0.005)

                    try:
                        user32.UnhookWindowsHookEx(hook)
                    except Exception:
                        pass
                    self._ll_kb_hook = None
                except Exception:
                    pass

            threading.Thread(target=ll_hook_thread, daemon=True).start()

        except Exception:
            pass

    def _stop_global_hotkey_listener(self):
        """Stop the global hotkey listener"""
        try:
            stop_event = getattr(self, '_hotkey_listener_stop', None)
            if stop_event:
                stop_event.set()
        except Exception:
            pass

    def _save_hotkey_setting(self, vk, mod):
        self._hotkey_setting = {'vk': vk, 'mod': mod}
        try:
            import json
            with open(user_data_path('hotkey_setting.json'), 'w') as f:
                json.dump(self._hotkey_setting, f)
        except Exception:
            pass

    def _load_hotkey_setting(self):
        try:
            import json
            with open(user_data_path('hotkey_setting.json'), 'r') as f:
                return json.load(f)
        except Exception:
            return {'vk': 16777216, 'mod': 0}

    def _start_global_mouse_tilt_listener(self):
        # Windows only: install a low-level mouse hook to listen for WM_MOUSEHWHEEL and WM_APPCOMMAND
        import threading
        import ctypes
        from ctypes import wintypes
        import sys
        if sys.platform != 'win32':
            return

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        WM_MOUSEHWHEEL = 0x020E
        WM_APPCOMMAND = 0x0319
        WH_MOUSE_LL = 14

        class MSLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("pt", wintypes.POINT),
                ("mouseData", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", wintypes.ULONG_PTR),
            ]

        # Store reference to hook to prevent GC
        self._mouse_tilt_hook = None

        def low_level_mouse_proc(nCode, wParam, lParam):
            if nCode == 0:
                if wParam == WM_MOUSEHWHEEL:
                    ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    delta = ctypes.c_short((ms.mouseData >> 16) & 0xFFFF).value
                    if delta < 0:
                        try:
                            self.prev_track()
                        except Exception:
                            pass
                    elif delta > 0:
                        try:
                            self.next_track()
                        except Exception:
                            pass
                elif wParam == WM_APPCOMMAND:
                    cmd = (lParam >> 16) & 0xFFFF
                    APPCOMMAND_MEDIA_NEXTTRACK = 11
                    APPCOMMAND_MEDIA_PREVIOUSTRACK = 12
                    if cmd == APPCOMMAND_MEDIA_PREVIOUSTRACK:
                        try:
                            self.prev_track()
                        except Exception:
                            pass
                    elif cmd == APPCOMMAND_MEDIA_NEXTTRACK:
                        try:
                            self.next_track()
                        except Exception:
                            pass
            return user32.CallNextHookEx(self._mouse_tilt_hook, nCode, wParam, lParam)

        CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        pointer = CMPFUNC(low_level_mouse_proc)

        def hook_thread():
            self._mouse_tilt_hook = user32.SetWindowsHookExW(
                WH_MOUSE_LL, pointer, kernel32.GetModuleHandleW(None), 0)
            if not self._mouse_tilt_hook:
                return
            msg = wintypes.MSG()
            while True:
                bRet = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if bRet == 0:  # WM_QUIT
                    break
                elif bRet == -1:
                    break
                else:
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
            user32.UnhookWindowsHookEx(self._mouse_tilt_hook)

        t = threading.Thread(target=hook_thread, daemon=True)
        t.start()
        pass
        try:
            if getattr(self, 'settings_btn', None) is not None:
                self.settings_btn.hide()
        except Exception:
            pass

        # settings button: same size/margins as other small controls, colored by current theme
        try:
            self.settings_btn = QPushButton("", self)
            self.settings_btn.setToolTip("Settings")
            self.settings_btn.setFixedSize(24, 24)
            try:
                theme_hex = getattr(self, '_theme_color', QColor('#2f2f35')).name()
            except Exception:
                theme_hex = '#2f2f35'
            self.settings_btn.setStyleSheet(
                f"QPushButton{{background:{theme_hex};border:1px solid rgba(255,255,255,40);border-radius:0px;}}"
                "QPushButton:hover{background-color: palette(highlight);}" 
            )
            try:
                self.settings_btn.clicked.connect(self.open_settings)
            except Exception:
                pass
        except Exception:
            self.settings_btn = None
        if getattr(self, 'settings_btn', None) is not None:
            try:
                self.settings_btn.hide()
            except Exception:
                pass

    # ---------- Layout Refresh ----------
    def refresh_layout_size(self):
        self.layout().invalidate()
        self.layout().activate()
        self.adjustSize()

    # ---------- Hover transparency ----------
    def enterEvent(self, event):
        if not self.expanded:
            self.setWindowOpacity(1.0)

    def leaveEvent(self, event):
        if not self.expanded:
            self.setWindowOpacity(1.0)
        else:
            self.setWindowOpacity(1.0)

    def _fade_window_opacity(self, target, duration=300):
        try:
            # Stop any existing opacity animation
            if hasattr(self, '_opacity_anim') and self._opacity_anim is not None:
                try:
                    self._opacity_anim.stop()
                except Exception:
                    pass
            
            # Create smooth opacity animation
            self._opacity_anim = self._create_smooth_animation(self, b"windowOpacity", duration=duration)
            if self._opacity_anim:
                self._opacity_anim.setStartValue(self.windowOpacity())
                self._opacity_anim.setEndValue(target)
                self._opacity_anim.start()
            else:
                # Fallback to original method
                from PyQt6.QtCore import QPropertyAnimation
                self._opacity_anim = QPropertyAnimation(self, b"windowOpacity")
                self._opacity_anim.setDuration(duration)
                self._opacity_anim.setStartValue(self.windowOpacity())
                self._opacity_anim.setEndValue(target)
                self._opacity_anim.start()
        except Exception:
            self.setWindowOpacity(target)

    # ---------- Modes ----------
    def _play_switch_sound(self):
        """Play switch.mp3 using a persistent pre-loaded QMediaPlayer for instant playback."""
        if getattr(self, '_startup_sound_suppressed', False):
            return
        try:
            # Lazily create and keep a single persistent player
            if not hasattr(self, '_switch_sound_player') or self._switch_sound_player is None:
                path = app_relative_path('switch.mp3')
                if not os.path.exists(path):
                    return
                p = QMediaPlayer()
                ao = QAudioOutput()
                p.setAudioOutput(ao)
                p.setSource(QUrl.fromLocalFile(path))
                self._switch_sound_player = p
                self._switch_sound_audio = ao

                def _on_status(status):
                    if status == QMediaPlayer.MediaStatus.LoadedMedia:
                        self._switch_sound_player.setPosition(0)
                        self._switch_sound_player.play()
                    elif status == QMediaPlayer.MediaStatus.EndOfMedia:
                        # Keep audio pipeline warm by pausing at start
                        # instead of letting the backend release the device
                        self._switch_sound_player.setPosition(0)
                        self._switch_sound_player.pause()

                p.mediaStatusChanged.connect(_on_status)
                return  # first call: will play once LoadedMedia fires
            # Already loaded — just seek to start and play immediately
            self._switch_sound_player.setPosition(0)
            self._switch_sound_player.play()
        except Exception:
            pass

    def shrink_mode(self):
        self._play_switch_sound()
        # Show load.PNG on cover if no song is selected (for small mode)
        try:
            if self.current_index == -1 or not self.playlist:
                fn = load_cover_asset_path()
                if os.path.exists(fn):
                    pm = QPixmap(fn)
                    if pm and not pm.isNull():
                        self.cover.set_cover(pm)
                    else:
                        self.cover.set_cover(None)
                else:
                    self.cover.set_cover(None)
            else:
                # Show the current song's cover art in small mode
                self.load_cover_art(self.playlist[self.current_index])
        except Exception:
            self.cover.set_cover(None)
        
        self.expanded = False
        try:
            self.setAcceptDrops(False)
        except Exception:
            pass

        # Smoothly hide widgets with staggered animations
        animations = []
        
        # Hide text and controls first
        animations.append(self._animate_widget_hide(self.song_label, duration=200))
        animations.append(self._animate_widget_hide(self.seek_slider, duration=200))
        animations.append(self._animate_widget_hide(self.time_left, duration=200))
        animations.append(self._animate_widget_hide(self.time_right, duration=200))
        animations.append(self._animate_widget_hide(self.btn_prev, duration=200))
        animations.append(self._animate_widget_hide(self.btn_play, duration=200))
        animations.append(self._animate_widget_hide(self.btn_next, duration=200))
        animations.append(self._animate_widget_hide(self.volume, duration=200))
        
        # Then hide larger elements with slight delay
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, lambda: animations.append(self._animate_widget_hide(self.import_btn, duration=250)))
        QTimer.singleShot(100, lambda: animations.append(self._animate_widget_hide(self.list_widget, duration=250)))
        
        # Hide window controls
        try:
            animations.append(self._animate_widget_hide(self.drag_btn, duration=150))
        except Exception:
            pass
        try:
            animations.append(self._animate_widget_hide(self.settings_btn, duration=150))
        except Exception:
            pass
        animations.append(self._animate_widget_hide(self.close_btn, duration=150))

        # Remove top_widget and bottom_widget from layout, show only the cover centered and flush
        try:
            if hasattr(self, 'top_widget') and self.top_widget is not None:
                try:
                    self.main_layout.removeWidget(self.top_widget)
                except Exception:
                    pass
                try:
                    self.top_widget.hide()
                except Exception:
                    pass
                try:
                    self.top_widget.setParent(None)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if hasattr(self, 'bottom_widget') and self.bottom_widget is not None:
                try:
                    self.main_layout.removeWidget(self.bottom_widget)
                except Exception:
                    pass
                try:
                    self.bottom_widget.hide()
                except Exception:
                    pass
                try:
                    self.bottom_widget.setParent(None)
                except Exception:
                    pass
        except Exception:
            pass
        # Add the cover directly to the main layout, centered and flush
        try:
            self.main_layout.addWidget(self.cover, alignment=Qt.AlignmentFlag.AlignCenter)
        except Exception:
            pass
        # ensure the reparented cover is visible
        try:
            self.cover.show()
        except Exception:
            pass

        self.setWindowOpacity(1.0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        # layout spacing is managed on `main_layout` now (top/bottom widgets)
        self.refresh_layout_size()
        # Remove all padding/margins and set cover size to 104x104 in small mode
        try:
            self.cover.setFixedSize(104, 104)
            self.cover.setContentsMargins(0, 0, 0, 0)
            self.cover.setStyleSheet("margin:0px;padding:0px;border:0px;")
        except Exception:
            pass

        self.setMinimumSize(0, 0)
        self.setMaximumSize(9999, 9999)
        # animate the window geometry to the nearest corner at small size
        try:
            self.refresh_layout_size()
            w_small, h_small = 120, 120
            # make window background transparent during shrink animation to avoid
            # a visible dark margin below the cover area
            try:
                try:
                    self._saved_style = self.styleSheet()
                except Exception:
                    self._saved_style = None
                try:
                    self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                except Exception:
                    pass
                try:
                    self.setStyleSheet("background: transparent;")
                except Exception:
                    pass
            except Exception:
                pass
            # allow song title to wrap into multiple lines in the small/squircle view
            try:
                self.song_label.setWordWrap(True)
                try:
                    self.song_label.setMaximumWidth(w_small - 16)
                except Exception:
                    pass
            except Exception:
                pass
            # prefer the screen that currently contains the window center
            try:
                cur_center = self.frameGeometry().center()
            except Exception:
                try:
                    cur_center = self.geometry().center()
                except Exception:
                    cur_center = None

            geom = None
            try:
                if cur_center is not None:
                    try:
                        screen = QGuiApplication.screenAt(cur_center)
                    except Exception:
                        screen = None
                    if screen is None:
                        try:
                            screen = QApplication.primaryScreen()
                        except Exception:
                            screen = None
                    if screen is not None:
                        geom = screen.availableGeometry()
                if geom is None:
                    try:
                        geom = QApplication.desktop().availableGeometry(self)
                    except Exception:
                        geom = None
            except Exception:
                geom = None

            if geom is not None:
                cur_center = self.frameGeometry().center()
                candidates = [
                    QPoint(geom.x(), geom.y()),
                    QPoint(geom.x() + geom.width() - w_small, geom.y()),
                    QPoint(geom.x(), geom.y() + geom.height() - h_small),
                    QPoint(geom.x() + geom.width() - w_small, geom.y() + geom.height() - h_small),
                ]
                best = min(candidates, key=lambda p: (p.x() - cur_center.x()) ** 2 + (p.y() - cur_center.y()) ** 2)
                snap_x, snap_y = best.x(), best.y()
            else:
                # fallback: shrink in-place
                snap_x, snap_y = self.x(), self.y()

            start_rect = self.geometry()
            end_rect = QRect(snap_x, snap_y, w_small, h_small)

            if self._mode_anim is not None:
                try:
                    self._mode_anim.stop()
                except Exception:
                    pass

            self._mode_anim = QPropertyAnimation(self, b"geometry")
            self._mode_anim.setDuration(260)
            try:
                ec = QEasingCurve(QEasingCurve.Type.OutBack)
                try:
                    ec.setOvershoot(0.85)
                except Exception:
                    pass
                self._mode_anim.setEasingCurve(ec)
            except Exception:
                pass
            self._mode_anim.setStartValue(start_rect)
            self._mode_anim.setEndValue(end_rect)

            def _lock_small():
                try:
                    self.setFixedSize(w_small, h_small)
                except Exception:
                    pass

            try:
                self._mode_anim.finished.connect(_lock_small)
            except Exception:
                pass

            try:
                self._mode_anim.start()
            except Exception:
                try:
                    self.setGeometry(end_rect)
                    _lock_small()
                except Exception:
                    pass
        except Exception:
            # fallback: simple size animate
            try:
                self._animate_to_size(120, 120, lock_fixed=True)
            except Exception:
                pass

    def expand_mode(self):
        self._play_switch_sound()
        self.expanded = True
        try:
            if hasattr(self, 'cover') and self.cover is not None:
                self.cover._set_hover_controls_visible(False)
        except Exception:
            pass
        try:
            self.setAcceptDrops(True)
        except Exception:
            pass
        self.setWindowOpacity(1.0)

        # Remove the cover from the main layout if it was added directly in small mode.
        # If the cover was reparented into `main_layout` during shrink, reinsert it
        # back into the `top_widget` cover container so expanded UI shows it.
        try:
            self.main_layout.removeWidget(self.cover)
        except Exception:
            pass
        try:
            if hasattr(self, 'top_widget') and self.top_widget is not None:
                try:
                    top_row_layout = self.top_widget.layout()
                    if top_row_layout is not None:
                        left_item = top_row_layout.itemAt(0)
                        if left_item is not None and left_item.layout() is not None:
                            left_layout = left_item.layout()
                            cover_container_item = left_layout.itemAt(0)
                            if cover_container_item is not None and cover_container_item.layout() is not None:
                                cover_container = cover_container_item.layout()
                                # add (reparent) cover back into the cover container if needed
                                if self.cover.parent() is not self.top_widget:
                                    cover_container.addWidget(self.cover, 0, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
                except Exception:
                    pass
            # ensure the cover is visible so paintEvent will run
            try:
                self.cover.show()
            except Exception:
                pass
        except Exception:
            pass
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        # Set cover size to match small mode (104x104)
        try:
            self.cover.setFixedSize(104, 104)
            self.cover.setContentsMargins(0, 0, 0, 0)
            self.cover.setStyleSheet("margin:0px;padding:0px;border:0px;")
        except Exception:
            pass

        # Re-add top_widget and bottom_widget to the layout
        try:
            if hasattr(self, 'top_widget') and self.top_widget is not None:
                self.main_layout.insertWidget(0, self.top_widget)
                # remove extra padding around the top section (song/title) in expanded mode
                try:
                    tl = self.top_widget.layout()
                    if tl is not None:
                        tl.setContentsMargins(0, 0, 0, 0)
                        tl.setSpacing(0)
                        # clear inner text container margins (was 8px left)
                        left_item = tl.itemAt(0)
                        if left_item is not None and left_item.layout() is not None:
                            left_layout = left_item.layout()
                            text_item = left_layout.itemAt(1)
                            if text_item is not None and text_item.layout() is not None:
                                text_item.layout().setContentsMargins(0, 0, 0, 0)
                                text_item.layout().setSpacing(0)
                except Exception:
                    pass
                # The main window paintEvent already draws the full gradient background.
                # top_widget's own stylesheet gradient created a visible dark rectangle
                # in the top-right corner (between the buttons and the window edge).
                # Make it transparent in expanded mode so only the window gradient shows.
                try:
                    self.top_widget.setStyleSheet("background: transparent;")
                except Exception:
                    pass
                self.top_widget.show()
        except Exception:
            pass
        try:
            if hasattr(self, 'bottom_widget') and self.bottom_widget is not None:
                self.main_layout.addWidget(self.bottom_widget)
                self.bottom_widget.show()
        except Exception:
            pass

        self.setMinimumSize(0, 0)
        self.setMaximumSize(9999, 9999)

        self.song_label.show()
        self.seek_slider.show()
        self.time_left.show()
        self.time_right.show()
        self.btn_prev.show()
        self.btn_play.show()
        self.btn_next.show()
        self.volume.show()
        self.import_btn.show()
        self.list_widget.show()
        self.drag_btn.show()
        try:
            if getattr(self, 'settings_btn', None) is not None:
                self.settings_btn.show()
                try:
                    self.settings_btn.setEnabled(True)
                except Exception:
                    pass
        except Exception:
            pass
        self.close_btn.show()

        # Restore album cover if missing (e.g., after returning from small mode)
        try:
            if self.current_index != -1 and self.playlist:
                # Only reload if cover is missing
                if not getattr(self.cover, 'cover_pixmap', None):
                    self.load_cover_art(self.playlist[self.current_index])
        except Exception:
            pass

        # show bottom section in expanded mode (re-add if previously removed)
        try:
            if hasattr(self, 'bottom_widget') and self.bottom_widget is not None:
                try:
                    try:
                        self.main_layout.removeWidget(self.bottom_widget)
                    except Exception:
                        pass
                    self.main_layout.addWidget(self.bottom_widget)
                except Exception:
                    pass
                try:
                    self.bottom_widget.show()
                except Exception:
                    pass
        except Exception:
            pass
        # restore window background/style after expand
        try:
            try:
                if getattr(self, '_saved_style', None) is not None:
                    self.setStyleSheet(self._saved_style)
                else:
                    self.setStyleSheet(self.dark_style())
            except Exception:
                try:
                    self.setStyleSheet(self.dark_style())
                except Exception:
                    pass
            try:
                self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            except Exception:
                pass
        except Exception:
            pass
        
        # restore song label to single-line/expanding behavior in expanded mode
        try:
            self.song_label.setWordWrap(False)
            try:
                self.song_label.setMaximumWidth(16777215)
                self.song_label.setMinimumWidth(0)
            except Exception:
                pass
        except Exception:
            pass

        # compute a target geometry so the expanded window is fully visible on the screen
        try:
            w_target, h_target = 320, 520
            # get the screen that currently contains the window center
            try:
                screen = QGuiApplication.screenAt(self.frameGeometry().center())
            except Exception:
                screen = None
            if screen is None:
                try:
                    screen = QApplication.primaryScreen()
                except Exception:
                    screen = None

            if screen is not None:
                geom = screen.availableGeometry()
            else:
                geom = None

            # desired center should be the current small-window center
            cur_center = self.frameGeometry().center()
            if geom is not None:
                # compute top-left such that expanded window is centered on cur_center
                tx = int(cur_center.x() - w_target / 2)
                ty = int(cur_center.y() - h_target / 2)
                # clamp within available geometry
                if tx < geom.x():
                    tx = geom.x()
                if ty < geom.y():
                    ty = geom.y()
                if tx + w_target > geom.x() + geom.width():
                    tx = geom.x() + geom.width() - w_target
                if ty + h_target > geom.y() + geom.height():
                    ty = geom.y() + geom.height() - h_target
            else:
                # fallback: keep current top-left
                tx, ty = self.x(), self.y()

            start_rect = self.geometry()
            end_rect = QRect(tx, ty, w_target, h_target)

            # stop any existing animation
            try:
                if self._mode_anim is not None:
                    self._mode_anim.stop()
            except Exception:
                pass

            # animate geometry to new rect (position + size) so expanded window appears fully on-screen
            try:
                self._mode_anim = QPropertyAnimation(self, b"geometry")
                self._mode_anim.setDuration(260)
                try:
                    self._mode_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type.OutCubic))
                except Exception:
                    pass
                self._mode_anim.setStartValue(start_rect)
                self._mode_anim.setEndValue(end_rect)
                self._mode_anim.start()
            except Exception:
                # fallback to immediate geometry change
                try:
                    self.setGeometry(end_rect)
                except Exception:
                    pass

            # Apply the top_widget corner mask after layout has settled.
            QTimer.singleShot(50, self._apply_top_widget_mask)

        except Exception:
            # fallback to simple size animation
            self.refresh_layout_size()
            self._animate_to_size(320, 520, lock_fixed=False)

    def keyPressEvent(self, event):
        try:
            nvk = event.nativeVirtualKey()
            toggle_vk = getattr(self, '_hotkey_toggle_vk', 0x79)
            drag_vk = getattr(self, '_hotkey_drag_vk', 0x7A)
            if nvk == toggle_vk:
                self._f10_down = True
            elif nvk == drag_vk:
                self._f11_down = True
        except Exception:
            pass

        try:
            nvk = event.nativeVirtualKey()
        except Exception:
            nvk = 0
        toggle_vk = getattr(self, '_hotkey_toggle_vk', 0x79)
        drag_vk = getattr(self, '_hotkey_drag_vk', 0x7A)
        if nvk == drag_vk:
            # Safety: never enter move mode while combo is held.
            try:
                if self._f10_down:
                    event.accept()
                    return
            except Exception:
                pass
            try:
                if not event.isAutoRepeat():
                    self._start_f11_move_mode()
            except Exception:
                self._start_f11_move_mode()
            try:
                event.accept()
            except Exception:
                pass
            return
        if nvk == toggle_vk:
            # Safety: never toggle mode while combo is held.
            try:
                if self._f11_down:
                    try:
                        self._stop_f11_move_mode()
                    except Exception:
                        pass
                    event.accept()
                    return
            except Exception:
                pass
            if self.expanded:
                self.shrink_mode()
            else:
                self.expand_mode()

    def keyReleaseEvent(self, event):
        try:
            nvk = event.nativeVirtualKey()
            toggle_vk = getattr(self, '_hotkey_toggle_vk', 0x79)
            drag_vk = getattr(self, '_hotkey_drag_vk', 0x7A)
            if nvk == toggle_vk:
                self._f10_down = False
            elif nvk == drag_vk:
                self._f11_down = False
        except Exception:
            pass

        try:
            nvk = event.nativeVirtualKey()
        except Exception:
            nvk = 0
        drag_vk = getattr(self, '_hotkey_drag_vk', 0x7A)
        if nvk == drag_vk:
            try:
                if not event.isAutoRepeat():
                    self._stop_f11_move_mode()
            except Exception:
                self._stop_f11_move_mode()
            try:
                event.accept()
            except Exception:
                pass
            return
        return super().keyReleaseEvent(event)

    def eventFilter(self, obj, event):
        # Keep F10/F11 state consistent across child widgets and guard only
        # mode-change/move actions while both keys are held.
        try:
            if not isinstance(obj, QWidget):
                return super().eventFilter(obj, event)
            if obj is not self and not self.isAncestorOf(obj):
                return super().eventFilter(obj, event)

            t = event.type()
            k = None
            if t in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
                try:
                    k = event.key()
                except Exception:
                    k = None

            # Keep key-down state accurate even when focus is on child controls.
            try:
                nvk = event.nativeVirtualKey()
            except Exception:
                nvk = 0
            toggle_vk = getattr(self, '_hotkey_toggle_vk', 0x79)
            drag_vk = getattr(self, '_hotkey_drag_vk', 0x7A)
            if t == QEvent.Type.KeyPress:
                if nvk == toggle_vk:
                    self._f10_down = True
                elif nvk == drag_vk:
                    self._f11_down = True
            elif t == QEvent.Type.KeyRelease:
                if nvk == toggle_vk:
                    self._f10_down = False
                elif nvk == drag_vk:
                    self._f11_down = False

            # Preserve toggle/drag behavior when key events are delivered to children.
            if obj is not self and t == QEvent.Type.KeyPress and nvk == drag_vk:
                try:
                    if self._f10_down:
                        event.accept()
                        return True
                except Exception:
                    pass
                try:
                    if not event.isAutoRepeat():
                        self._start_f11_move_mode()
                except Exception:
                    self._start_f11_move_mode()
                event.accept()
                return True

            if obj is not self and t == QEvent.Type.KeyRelease and nvk == drag_vk:
                try:
                    if not event.isAutoRepeat():
                        self._stop_f11_move_mode()
                except Exception:
                    self._stop_f11_move_mode()
                event.accept()
                return True

            if obj is not self and t == QEvent.Type.KeyPress and nvk == toggle_vk:
                try:
                    if self._f11_down:
                        try:
                            self._stop_f11_move_mode()
                        except Exception:
                            pass
                        event.accept()
                        return True
                except Exception:
                    pass
                try:
                    if self.expanded:
                        self.shrink_mode()
                    else:
                        self.expand_mode()
                except Exception:
                    pass
                event.accept()
                return True
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def _start_f11_move_mode(self):
        try:
            if self._f10_down and self._f11_down:
                return
            if self._f11_move_active:
                return
            self._f11_move_active = True
            try:
                self._f11_follow_x = float(self.x())
                self._f11_follow_y = float(self.y())
                self._f11_vel_x = 0.0
                self._f11_vel_y = 0.0
                self._f11_follow_initialized = True
            except Exception:
                self._f11_follow_initialized = False
            # stop any legacy drag interaction while F11 mode is active
            try:
                self._drag_active = False
            except Exception:
                pass

            if self._f11_move_timer is None:
                self._f11_move_timer = QTimer(self)
                self._f11_move_timer.setInterval(16)
                self._f11_move_timer.timeout.connect(self._update_f11_follow_cursor)
            self._update_f11_follow_cursor()
            self._f11_move_timer.start()
        except Exception:
            pass

    def _stop_f11_move_mode(self):
        try:
            self._f11_move_active = False
            if self._f11_move_timer is not None:
                self._f11_move_timer.stop()
            self._f11_follow_initialized = False
            self._f11_vel_x = 0.0
            self._f11_vel_y = 0.0

            # Anchor exactly under the cursor on release before recoil snap.
            try:
                gp = QCursor.pos()
                nx = int(gp.x() - (self.width() / 2))
                ny = int(gp.y() - (self.height() / 2))
                self.move(nx, ny)
            except Exception:
                pass
        except Exception:
            pass

        # Small mode snaps to nearest corner when F11 is released,
        # but never while the combo lock condition is active.
        try:
            if not getattr(self, 'expanded', False) and not (self._f10_down and self._f11_down):
                self._snap_to_nearest_corner()
        except Exception:
            pass

    def _update_f11_follow_cursor(self):
        try:
            if not self._f11_move_active:
                return
            gp = QCursor.pos()
            target_x = float(gp.x() - (self.width() / 2))
            target_y = float(gp.y() - (self.height() / 2))

            if not self._f11_follow_initialized:
                self._f11_follow_x = float(self.x())
                self._f11_follow_y = float(self.y())
                self._f11_vel_x = 0.0
                self._f11_vel_y = 0.0
                self._f11_follow_initialized = True

            # Spring-damped follow: small mode uses gentler, more damped motion
            # to reduce visible recoil when chasing the cursor.
            if getattr(self, 'expanded', False):
                stiffness = 0.28
                damping = 0.72
            else:
                stiffness = 0.26
                damping = 0.82

            self._f11_vel_x = (self._f11_vel_x * damping) + ((target_x - self._f11_follow_x) * stiffness)
            self._f11_vel_y = (self._f11_vel_y * damping) + ((target_y - self._f11_follow_y) * stiffness)

            if not getattr(self, 'expanded', False):
                vmax = 60.0
                self._f11_vel_x = max(-vmax, min(vmax, self._f11_vel_x))
                self._f11_vel_y = max(-vmax, min(vmax, self._f11_vel_y))

            self._f11_follow_x += self._f11_vel_x
            self._f11_follow_y += self._f11_vel_y

            # Snap very close residuals to avoid tiny jitter.
            if abs(target_x - self._f11_follow_x) < 0.35 and abs(self._f11_vel_x) < 0.08:
                self._f11_follow_x = target_x
                self._f11_vel_x = 0.0
            if abs(target_y - self._f11_follow_y) < 0.35 and abs(self._f11_vel_y) < 0.08:
                self._f11_follow_y = target_y
                self._f11_vel_y = 0.0

            self.move(int(round(self._f11_follow_x)), int(round(self._f11_follow_y)))
        except Exception:
            pass

    def _snap_to_nearest_corner(self):
        try:
            w = int(self.width())
            h = int(self.height())
            if w <= 0 or h <= 0:
                return

            try:
                screen = QGuiApplication.screenAt(self.frameGeometry().center())
            except Exception:
                screen = None
            if screen is None:
                try:
                    screen = QApplication.primaryScreen()
                except Exception:
                    screen = None
            if screen is None:
                return

            geom = screen.availableGeometry()
            candidates = [
                QPoint(geom.x(), geom.y()),
                QPoint(geom.x() + geom.width() - w, geom.y()),
                QPoint(geom.x(), geom.y() + geom.height() - h),
                QPoint(geom.x() + geom.width() - w, geom.y() + geom.height() - h),
            ]
            cur = self.frameGeometry().center()
            best = min(candidates, key=lambda p: (p.x() - cur.x()) ** 2 + (p.y() - cur.y()) ** 2)
            self._animate_snap_to_point(best)
        except Exception:
            pass

    def _animate_snap_to_point(self, target_pos: QPoint, duration: int = 300):
        try:
            # Recoil-style snap with slight overshoot that settles at corner.
            if self._snap_anim is not None:
                try:
                    self._snap_anim.stop()
                except Exception:
                    pass

            anim = QPropertyAnimation(self, b"pos")
            anim.setDuration(max(120, int(duration)))
            try:
                ec = QEasingCurve(QEasingCurve.Type.OutBack)
                try:
                    ec.setOvershoot(0.85)
                except Exception:
                    pass
                anim.setEasingCurve(ec)
            except Exception:
                pass
            anim.setStartValue(self.pos())
            anim.setEndValue(QPoint(int(target_pos.x()), int(target_pos.y())))

            def _finish_exact():
                try:
                    self.move(int(target_pos.x()), int(target_pos.y()))
                except Exception:
                    pass

            try:
                anim.finished.connect(_finish_exact)
            except Exception:
                pass

            self._snap_anim = anim
            anim.start()
        except Exception:
            try:
                self.move(int(target_pos.x()), int(target_pos.y()))
            except Exception:
                pass

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_active:
            try:
                gp = QCursor.pos()
                self.move(gp - self._drag_pos)
            except Exception:
                try:
                    self.move(event.globalPosition().toPoint() - self._drag_pos)
                except Exception:
                    pass
            return

        if self.rect().width() > 0 and self.rect().height() > 0:
            nx = (event.position().x() / self.rect().width()) - 0.5
            ny = (event.position().y() / self.rect().height()) - 0.5
            self._grad_offset = QPointF(nx * 0.12, ny * 0.12)
            self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        try:
            self._update_edge_sampler_geometry()
        except Exception:
            pass
        try:
            self._apply_window_chamfer_mask()
        except Exception:
            pass
        try:
            self._apply_top_widget_mask()
        except Exception:
            pass
        if hasattr(self, "drag_btn"):
            # position drag and close buttons to avoid overlap with the volume slider
            try:
                vol_w = self.volume.width() if hasattr(self, 'volume') else 0
                # In expanded mode, top_row margins are zeroed so the volume slider's
                # left edge sits exactly (addSpacing=14) pixels from the right edge.
                # Using 14 here matches that, closing the gap that previously leaked
                # the window's right-edge glass reflection through the semi-transparent
                # top_widget background (the "weird section" next to the slider).
                close_x = int(self.width() - self.close_btn.width() - vol_w - 14)
                if close_x < 8:
                    close_x = self.width() - self.close_btn.width() - 8
            except Exception:
                close_x = self.width() - self.close_btn.width() - 8
            self.close_btn.move(close_x, 8)

            # place drag button just left of close button
            try:
                if hasattr(self, 'drag_btn'):
                    drag_x = close_x - self.drag_btn.width() - 8
                    if drag_x < 4:
                        drag_x = max(4, self.width() - self.drag_btn.width() - self.close_btn.width() - vol_w - 28)
                    # align drag button vertically with close button
                    self.drag_btn.move(drag_x, 8)
                    # place settings button to the left of drag
                    try:
                        if getattr(self, 'settings_btn', None) is not None:
                            settings_x = drag_x - self.settings_btn.width() - 8
                            if settings_x < 4:
                                settings_x = 4
                            self.settings_btn.move(settings_x, 8)
                    except Exception:
                        pass
            except Exception:
                pass

            # ensure control buttons are on top of any layout widgets (avoid overlays)
            try:
                self.close_btn.raise_()
                self.drag_btn.raise_()
                try:
                    if getattr(self, 'settings_btn', None) is not None:
                        self.settings_btn.raise_()
                except Exception:
                    pass
            except Exception:
                pass

    def moveEvent(self, event):
        super().moveEvent(event)
        try:
            self._update_edge_sampler_geometry()
        except Exception:
            pass

    def _update_edge_sampler_geometry(self):
        sampler = getattr(self, '_edge_sampler', None)
        if sampler is None:
            return

        try:
            wr = self.frameGeometry()
        except Exception:
            return

        screens = []
        try:
            screens = QGuiApplication.screens()
        except Exception:
            screens = []

        if screens:
            vr = QRect(screens[0].geometry())
            for s in screens[1:]:
                try:
                    vr = vr.united(s.geometry())
                except Exception:
                    pass
        else:
            vr = QRect(-32768, -32768, 65536, 65536)

        try:
            sampler.set_geometry(wr, vr)
        except Exception:
            pass

    def _apply_window_chamfer_mask(self):
        try:
            # Keep small mode rectangular; chamfer the actual expanded window shape.
            if not getattr(self, 'expanded', False):
                try:
                    self.clearMask()
                except Exception:
                    pass
                return

            poly = _chamfered_polygon(self.rect(), 20.0, chamfer_tl=False)
            if poly.isEmpty():
                return
            self.setMask(QRegion(poly))
        except Exception:
            pass

    def _apply_top_widget_mask(self):
        """Clip top_widget's top-right corner to match the window chamfer.
        This prevents its semi-transparent background from painting in the
        empty addSpacing strip to the right of the volume slider, which was
        the 'weird section' that let the right-edge glass reflection bleed through.
        """
        try:
            if not getattr(self, 'expanded', False):
                return
            tw = getattr(self, 'top_widget', None)
            if tw is None or not tw.isVisible():
                return
            poly = _chamfered_polygon(
                tw.rect(), 20.0,
                chamfer_tl=False, chamfer_tr=True, chamfer_br=False, chamfer_bl=False,
            )
            if poly.isEmpty():
                try:
                    tw.clearMask()
                except Exception:
                    pass
                return
            tw.setMask(QRegion(poly))
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        try:
            self._ensure_always_on_top()
        except Exception:
            pass
        try:
            self._update_edge_sampler_geometry()
        except Exception:
            pass
        try:
            self._apply_window_chamfer_mask()
        except Exception:
            pass
        try:
            self.setFocus()
        except Exception:
            pass
        # Enable Windows 10 blur-behind effect for the translucent window
        try:
            if sys.platform == 'win32':
                hwnd = int(self.winId())
                _enable_win10_blur_behind(hwnd)
        except Exception:
            pass

    def mousePressEvent(self, event: QMouseEvent):
        # diagnostic: report which child widget is under the cursor when clicked
        try:
            pt = event.position().toPoint()
            w = self.childAt(pt)
            
            # Debug: Check if this is a move or delete button
            if w:
                if hasattr(w, 'text'):
                    try:
                        pass
                    except Exception:
                        pass
                if hasattr(w, 'objectName'):
                    try:
                        pass
                    except Exception:
                        pass
                
                # Check parent widget
                parent = w.parent()
                if parent:
                    if hasattr(parent, '_text'):
                        try:
                            pass
                        except Exception:
                            pass
        except Exception as e:
            pass

        # Disable background window dragging - only use the move button
        # Background clicking should not drag the window anymore
        
        # IMPORTANT: Call super() to ensure the event reaches child widgets
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            # ensure any active drag stops when mouse is released anywhere
            try:
                if self._drag_active:
                    self.stop_drag()
            except Exception:
                pass
            self._drag_pos = QPoint()

    def dragEnterEvent(self, event):
        try:
            if not getattr(self, 'expanded', False):
                event.ignore()
                return
            md = event.mimeData()
            if md.hasUrls():
                for u in md.urls():
                    p = u.toLocalFile()
                    if not p:
                        continue
                    if os.path.isdir(p) or p.lower().endswith('.mp3'):
                        event.acceptProposedAction()
                        return
            event.ignore()
        except Exception:
            try:
                event.ignore()
            except Exception:
                pass

    def dragMoveEvent(self, event):
        try:
            if not getattr(self, 'expanded', False):
                event.ignore()
                return
            event.acceptProposedAction()
        except Exception:
            try:
                event.ignore()
            except Exception:
                pass

    def dropEvent(self, event):
        try:
            if not getattr(self, 'expanded', False):
                event.ignore()
                return
            md = event.mimeData()
            if not md.hasUrls():
                event.ignore()
                return

            files_added = False
            for u in md.urls():
                p = u.toLocalFile()
                if not p:
                    continue
                # if a directory was dropped, walk for mp3 files
                if os.path.isdir(p):
                    for root, dirs, files in os.walk(p):
                        for fn in files:
                            if fn.lower().endswith('.mp3'):
                                full = os.path.join(root, fn)
                                if full not in self.playlist:
                                    self.add_playlist_item(full)
                                    files_added = True
                else:
                    if p.lower().endswith('.mp3'):
                        if p not in self.playlist:
                            self.add_playlist_item(p)
                            files_added = True

            if files_added:
                try:
                    self.dedupe_playlist()
                except Exception:
                    pass
                try:
                    self.save_playlist()
                except Exception:
                    pass

            event.acceptProposedAction()
        except Exception:
            try:
                event.ignore()
            except Exception:
                pass

    def _set_drag_enabled(self, enabled: bool):
        self._drag_active = enabled

    def start_drag(self):
        try:
            # record offset between global cursor and window position
            gp = QCursor.pos()
            try:
                top_left = self.frameGeometry().topLeft()
            except Exception:
                top_left = self.pos()
            self._drag_pos = gp - top_left
            self._drag_active = True
            # grab mouse so this widget receives move/release events
            try:
                self.grabMouse()
            except Exception:
                pass
            # change cursor to closed hand while dragging
            try:
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            except Exception:
                pass
        except Exception:
            pass

    def stop_drag(self):
        try:
            self._drag_active = False
            self._drag_pos = QPoint()
            try:
                self.releaseMouse()
            except Exception:
                pass
            try:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            except Exception:
                pass
        except Exception:
            pass

    # ---------- Import ----------
    def mouseDoubleClickEvent(self, event):
        if not self.expanded:
            self.import_songs()

    def import_songs(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Import MP3", "", "MP3 Files (*.mp3)"
        )

        for f in files:
            if f not in self.playlist:
                self.add_playlist_item(f)
        # remove any accidental duplicates and persist after import
        try:
            self.dedupe_playlist()
        except Exception:
            pass
        try:
            self.save_playlist()
        except Exception:
            pass

    def add_playlist_item(self, file_path: str, display_name: str = None):
        # Add the file to internal playlist and create a widget row with a move handle
        base = display_name or os.path.splitext(os.path.basename(file_path))[0]
        try:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, file_path)
            # store display name in custom role UserRole + 1
            item.setData(Qt.ItemDataRole.UserRole + 1, base)
            # per-item loop flag (UserRole + 2)
            try:
                item.setData(Qt.ItemDataRole.UserRole + 2, False)
            except Exception:
                pass
            widget = PlaylistItemWidget(base, file_path, self, item)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)
            self.playlist.append(file_path)
        except Exception:
            # fallback: plain text — only append to playlist if widget is added
            try:
                it = QListWidgetItem(base)
                it.setData(Qt.ItemDataRole.UserRole, file_path)
                it.setData(Qt.ItemDataRole.UserRole + 1, base)
                self.list_widget.addItem(it)
                self.playlist.append(file_path)
            except Exception:
                pass

        # Auto-generate a theme color once at import time if the song doesn't have one yet
        if file_path not in getattr(self, '_theme_colors', {}):
            self._generate_initial_color(file_path)

    def _generate_initial_color(self, file_path: str):
        """Sample a color from cover art, or fall back to a random theme color."""
        try:
            tags = ID3(file_path)
            for tag in tags.values():
                if isinstance(tag, APIC):
                    pix = QPixmap()
                    pix.loadFromData(tag.data)
                    if not pix.isNull():
                        w, h = pix.width(), pix.height()
                        if w > h:
                            side = h
                            x = max(0, (w - side) // 2)
                            pix = pix.copy(x, 0, side, side)
                        img = pix.toImage()
                        w2, h2 = img.width(), img.height()
                        cx, cy = max(0, min(w2 - 1, w2 // 2)), max(0, min(h2 - 1, h2 // 2))
                        dx, dy = int(w2 * 0.35), int(h2 * 0.35)
                        samples = [
                            img.pixelColor(max(0, min(w2 - 1, cx - dx)), max(0, min(h2 - 1, cy - dy))),
                            img.pixelColor(max(0, min(w2 - 1, cx + dx)), max(0, min(h2 - 1, cy - dy))),
                            img.pixelColor(max(0, min(w2 - 1, cx - dx)), max(0, min(h2 - 1, cy + dy))),
                            img.pixelColor(max(0, min(w2 - 1, cx + dx)), max(0, min(h2 - 1, cy + dy))),
                        ]
                        r = sum(c.red() for c in samples) // 4
                        g = sum(c.green() for c in samples) // 4
                        b = sum(c.blue() for c in samples) // 4
                        self._theme_colors[file_path] = QColor(r, g, b)
                        return
        except Exception:
            pass
        # No cover art — generate a random muted color
        hue = random.random()
        sat = 42.0 / 255.0
        lightness = 26.0 / 255.0
        self._theme_colors[file_path] = QColor.fromHslF(hue, sat, lightness)

    def start_playlist_drag(self, list_item: QListWidgetItem):
        # begin a manual vertical-only drag of the provided list_item
        try:
            if getattr(self, '_playlist_dragging', False):
                return
            self._playlist_dragging = True
            self._playlist_drag_item = list_item
            self._playlist_start_row = self.list_widget.row(list_item)
            self._drag_gap_index = -1
            self._drag_gap_anims = []
            # Hide the dragged item so it doesn't occupy visual space
            try:
                drag_w = self.list_widget.itemWidget(list_item)
                if drag_w:
                    drag_w.setVisible(False)
            except Exception:
                pass
            # Connect scroll to refresh gap positions
            try:
                self.list_widget.verticalScrollBar().valueChanged.connect(self._on_drag_scroll)
            except Exception:
                pass
            # install global event filter to track mouse move/release
            app = QApplication.instance()
            if app:
                app.installEventFilter(self)
            else:
                pass
            # Test: Immediately check if dragging state is set
        except Exception as e:
            pass

        # create a floating preview widget to follow the cursor
        try:
            # capture a pixmap of the item's widget (or text fallback)
            item_widget = None
            try:
                item_widget = self.list_widget.itemWidget(list_item)
            except Exception:
                item_widget = None

            preview = QWidget(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
            preview.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            preview.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
            preview.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

            preview_layout = QHBoxLayout()
            preview_layout.setContentsMargins(0, 0, 0, 0)
            preview.setLayout(preview_layout)

            lbl = QLabel(preview)
            lbl.setStyleSheet('background: rgba(40,40,44,220); color: white; border-radius:0px; padding:6px; font-size: 12px;')
            
            # Get song name for preview
            song_name = "Song"
            try:
                if item_widget is not None and hasattr(item_widget, '_text'):
                    song_name = item_widget._text
                else:
                    # Try to get from list item data
                    try:
                        song_name = list_item.data(Qt.ItemDataRole.UserRole + 1) or "Song"
                    except Exception:
                        song_name = list_item.text() or "Song"
            except Exception:
                song_name = "Song"
            
            # Show simple text preview instead of rendering widget
            lbl.setText(f"≡ {song_name}")

            preview_layout.addWidget(lbl)
            preview.adjustSize()

            # compute offset so cursor appears over middle of preview
            try:
                rect = self.list_widget.visualItemRect(list_item)
                self._preview_offset = QPoint(rect.width() // 2, rect.height() // 2)
            except Exception:
                self._preview_offset = QPoint(20, 10)

            # place preview at current cursor
            try:
                gp = QCursor.pos()
                preview.move(gp - self._preview_offset)
            except Exception:
                pass

            preview.show()
            self._drag_preview = preview
            # animation helper
            try:
                self._drag_preview_anim = QPropertyAnimation(self._drag_preview, b'pos')
                self._drag_preview_anim.setDuration(120)
            except Exception:
                self._drag_preview_anim = None
        except Exception:
            self._drag_preview = None
            self._preview_offset = QPoint(0, 0)
            self._drag_preview_anim = None

        # start a short timer to watch global mouse button state so drag continues
        try:
            from PyQt6.QtCore import QTimer
            self._playlist_watch_timer = QTimer(self)
            self._playlist_watch_timer.setInterval(50)
            def _watch():
                try:
                    from PyQt6.QtGui import QGuiApplication
                    buttons = QGuiApplication.mouseButtons()
                    if not (buttons & Qt.MouseButton.LeftButton):
                        try:
                            self.stop_playlist_drag()
                        except Exception:
                            pass
                except Exception:
                    pass
            self._playlist_watch_timer.timeout.connect(_watch)
            self._playlist_watch_timer.start()
        except Exception:
            self._playlist_watch_timer = None

    def _on_item_double_clicked(self, item: QListWidgetItem):
        try:
            widget = self.list_widget.itemWidget(item)
            if widget and hasattr(widget, 'start_inline_rename'):
                widget.start_inline_rename()
        except Exception:
            pass

    def stop_playlist_drag(self):
        """Stop the current playlist drag operation"""
        try:
            if not getattr(self, '_playlist_dragging', False):
                return
            
            # Reset gap animations before moving items
            self._reset_drag_gap()

            # Show the dragged item widget again
            try:
                drag_item = getattr(self, '_playlist_drag_item', None)
                if drag_item:
                    drag_w = self.list_widget.itemWidget(drag_item)
                    if drag_w:
                        drag_w.setVisible(True)
            except Exception:
                pass
            
            # Use the tracked gap index as the drop target
            target = getattr(self, '_drag_gap_index', -1)
            if target < 0:
                # fallback: compute from mouse position
                pos = QCursor.pos()
                local = self.list_widget.mapFromGlobal(pos)
                target = self._compute_drag_insert_index(local)

            old = self._playlist_start_row
            new = target
            
            if old != new:
                self.move_playlist_item(old, new)
            # cleanup
            self._playlist_dragging = False
            self._playlist_drag_item = None
            try:
                QApplication.instance().removeEventFilter(self)
            except Exception:
                pass
            # persist order
            try:
                self.save_playlist()
            except Exception:
                pass
        except Exception as e:
            pass
        finally:
            # clean up preview widget
            try:
                if getattr(self, '_drag_preview', None) is not None:
                    try:
                        self._drag_preview.hide()
                    except Exception:
                        pass
                    try:
                        self._drag_preview.deleteLater()
                    except Exception:
                        pass
                    self._drag_preview = None
            except Exception:
                pass
            # ensure we release any grabbed mouse from starting the drag
            try:
                if self.hasMouse():
                    try:
                        self.releaseMouse()
                    except Exception:
                        pass
            except Exception:
                pass
            # stop the watch timer if running
            try:
                if getattr(self, '_playlist_watch_timer', None) is not None:
                    try:
                        self._playlist_watch_timer.stop()
                    except Exception:
                        pass
                    try:
                        self._playlist_watch_timer.deleteLater()
                    except Exception:
                        pass
                    self._playlist_watch_timer = None
            except Exception:
                pass

    def _compute_drag_insert_index(self, local_pos):
        """Compute insertion index from local position in list_widget."""
        count = self.list_widget.count()
        if count == 0:
            return 0
        idx = self.list_widget.indexAt(local_pos)
        if idx.isValid():
            row = idx.row()
            rect = self.list_widget.visualItemRect(self.list_widget.item(row))
            if local_pos.y() > rect.center().y():
                return row + 1
            return row
        if local_pos.y() < 0:
            return 0
        return count

    def _on_drag_scroll(self):
        """When the list scrolls during drag, reapply gap positions."""
        gap = getattr(self, '_drag_gap_index', -1)
        if gap >= 0:
            self._drag_gap_index = -1  # force recalc
            self._animate_drag_gap(gap)

    def _animate_drag_gap(self, insert_index):
        """Animate list items to open a gap at insert_index for the dragged item."""
        drag_row = getattr(self, '_playlist_start_row', -1)
        old_gap = getattr(self, '_drag_gap_index', -1)
        if insert_index == old_gap:
            return
        self._drag_gap_index = insert_index

        # Stop any running gap animations
        for anim in getattr(self, '_drag_gap_anims', []):
            try:
                anim.stop()
            except Exception:
                pass
        self._drag_gap_anims = []

        count = self.list_widget.count()

        # Determine the gap height from an item rect
        gap_h = 28
        try:
            r = self.list_widget.visualItemRect(self.list_widget.item(0))
            gap_h = r.height()
        except Exception:
            pass

        for i in range(count):
            if i == drag_row:
                continue
            item = self.list_widget.item(i)
            w = self.list_widget.itemWidget(item)
            if not w:
                continue
            try:
                # Get where Qt naturally places this item (scroll-aware)
                natural_y = self.list_widget.visualItemRect(item).y()

                # Decide if this item needs to shift down to make room
                needs_shift = False
                if drag_row < insert_index:
                    needs_shift = (i >= insert_index)
                elif drag_row > insert_index:
                    needs_shift = (i >= insert_index and i < drag_row)

                target_y = natural_y + (gap_h if needs_shift else 0)
                current_y = w.y()
                if abs(current_y - target_y) < 2:
                    w.move(w.x(), target_y)
                    continue

                anim = QPropertyAnimation(w, b"pos")
                anim.setDuration(180)
                anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                anim.setStartValue(QPoint(w.x(), current_y))
                anim.setEndValue(QPoint(w.x(), target_y))
                anim.start()
                self._drag_gap_anims.append(anim)
            except Exception:
                pass

    def _reset_drag_gap(self):
        """Snap all items back to their natural positions after drag ends."""
        for anim in getattr(self, '_drag_gap_anims', []):
            try:
                anim.stop()
            except Exception:
                pass
        self._drag_gap_anims = []

        # Disconnect scroll handler
        try:
            self.list_widget.verticalScrollBar().valueChanged.disconnect(self._on_drag_scroll)
        except Exception:
            pass

        count = self.list_widget.count()
        for i in range(count):
            item = self.list_widget.item(i)
            w = self.list_widget.itemWidget(item)
            if not w:
                continue
            try:
                natural_y = self.list_widget.visualItemRect(item).y()
                w.move(w.x(), natural_y)
            except Exception:
                pass
        self._drag_gap_index = -1

    def eventFilter(self, obj, event):
        # handle mouse moves while dragging a playlist item to show feedback
        try:
            if getattr(self, '_playlist_dragging', False):
                if event.type() == QEvent.Type.MouseMove:
                    pos = QCursor.pos()
                    local = self.list_widget.mapFromGlobal(pos)
                    # Compute insertion target and animate gap
                    insert_idx = self._compute_drag_insert_index(local)
                    self._animate_drag_gap(insert_idx)
                    # move the floating preview toward cursor with a short animation
                    try:
                        if getattr(self, '_drag_preview', None) is not None:
                            target = QCursor.pos() - getattr(self, '_preview_offset', QPoint(0, 0))
                            if getattr(self, '_drag_preview_anim', None) is not None:
                                try:
                                    self._drag_preview_anim.stop()
                                    self._drag_preview_anim.setStartValue(self._drag_preview.pos())
                                    self._drag_preview_anim.setEndValue(target)
                                    self._drag_preview_anim.start()
                                except Exception:
                                    try:
                                        self._drag_preview.move(target)
                                    except Exception:
                                        pass
                            else:
                                try:
                                    self._drag_preview.move(target)
                                except Exception:
                                    pass
                    except Exception:
                        pass
                elif event.type() == QEvent.Type.MouseButtonRelease:
                    # finalize on release - stop playlist drag regardless of where release occurred
                    try:
                        self.stop_playlist_drag()
                    except Exception:
                        pass
            else:
                # Debug: log first few events to see if filter is working
                if not hasattr(self, '_event_filter_debug_count'):
                    self._event_filter_debug_count = 0
                if self._event_filter_debug_count < 5:
                    self._event_filter_debug_count += 1
        except Exception as e:
            pass
        return super().eventFilter(obj, event)

    def move_playlist_item(self, old_index: int, new_index: int):
        try:
            count = self.list_widget.count()
            if old_index < 0 or old_index >= count:
                return
            if new_index < 0:
                new_index = 0
            if new_index >= count:
                new_index = count - 1

            if old_index == new_index:
                return


            # capture item and widget before removal
            item_ref = self.list_widget.item(old_index)
            try:
                widget = self.list_widget.itemWidget(item_ref)
            except Exception:
                widget = None

            try:
                path = item_ref.data(Qt.ItemDataRole.UserRole)
            except Exception:
                path = None

            # Animate existing items to make space
            try:
                from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QPoint
                animations = []
                
                # Determine direction of movement
                if new_index > old_index:
                    # Moving down: items between old_index+1 to new_index need to move up
                    for i in range(old_index + 1, new_index + 1):
                        if i < self.list_widget.count():
                            item = self.list_widget.item(i)
                            widget = self.list_widget.itemWidget(item)
                            if widget:
                                # Animate the widget position
                                current_pos = widget.pos()
                                target_pos = QPoint(current_pos.x(), current_pos.y() - widget.height())
                                
                                anim = QPropertyAnimation(widget, b"pos")
                                anim.setDuration(200)
                                anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                                anim.setStartValue(current_pos)
                                anim.setEndValue(target_pos)
                                animations.append(anim)
                else:
                    # Moving up: items between new_index to old_index-1 need to move down
                    for i in range(new_index, old_index):
                        if i < self.list_widget.count():
                            item = self.list_widget.item(i)
                            widget = self.list_widget.itemWidget(item)
                            if widget:
                                # Animate the widget position
                                current_pos = widget.pos()
                                target_pos = QPoint(current_pos.x(), current_pos.y() + widget.height())
                                
                                anim = QPropertyAnimation(widget, b"pos")
                                anim.setDuration(200)
                                anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                                anim.setStartValue(current_pos)
                                anim.setEndValue(target_pos)
                                animations.append(anim)
                
                # Start all animations
                for anim in animations:
                    anim.start()
                    
            except Exception as e:
                pass

            # remove the visual item
            taken = self.list_widget.takeItem(old_index)

            # insertion index in the shortened list should match the desired final index
            insert_index = new_index
            if insert_index < 0:
                insert_index = 0
            # clamp to current count (after removal it will be <= count)
            if insert_index > self.list_widget.count():
                insert_index = self.list_widget.count()

            # remove from internal playlist
            try:
                if path is not None and 0 <= old_index < len(self.playlist):
                    self.playlist.pop(old_index)
            except Exception:
                pass

            # insert at adjusted index
            try:
                name = None
                try:
                    name = item_ref.data(Qt.ItemDataRole.UserRole + 1)
                except Exception:
                    name = None
                if not name and widget:
                    try:
                        name = getattr(widget, '_text', None)
                    except Exception:
                        name = None

                # create a new visual item + widget to avoid reuse issues
                new_item = QListWidgetItem()
                if path:
                    new_item.setData(Qt.ItemDataRole.UserRole, path)
                if name:
                    new_item.setData(Qt.ItemDataRole.UserRole + 1, name)

                new_widget = None
                try:
                    display = name or (path and os.path.splitext(os.path.basename(path))[0]) or 'Item'
                    new_widget = PlaylistItemWidget(display, path, self, new_item)
                except Exception:
                    new_widget = None

                if new_widget:
                    new_item.setSizeHint(new_widget.sizeHint())
                    self.list_widget.insertItem(insert_index, new_item)
                    self.list_widget.setItemWidget(new_item, new_widget)
                else:
                    text = name or (path and os.path.splitext(os.path.basename(path))[0]) or 'Item'
                    new_item.setText(text)
                    self.list_widget.insertItem(insert_index, new_item)

                # update internal playlist order
                try:
                    if path:
                        self.playlist.insert(insert_index, path)
                except Exception:
                    pass
                    
                # Animate the moved item into place
                try:
                    if new_widget:
                        # Start with offset position
                        item_height = new_widget.height()
                        if new_index > old_index:
                            # Moving down - start from above
                            start_pos = QPoint(new_widget.x(), new_widget.y() - item_height)
                        else:
                            # Moving up - start from below
                            start_pos = QPoint(new_widget.x(), new_widget.y() + item_height)
                        
                        # Set initial position
                        new_widget.move(start_pos)
                        
                        # Animate to final position
                        final_pos = QPoint(new_widget.x(), new_widget.y() - (start_pos.y() - new_widget.y()))
                        
                        entrance_anim = QPropertyAnimation(new_widget, b"pos")
                        entrance_anim.setDuration(250)
                        entrance_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                        entrance_anim.setStartValue(start_pos)
                        entrance_anim.setEndValue(final_pos)
                        entrance_anim.start()
                except Exception as e:
                    pass
            except Exception as e:
                pass
        except Exception as e:
            pass

    def dedupe_playlist(self):
        try:
            seen = set()
            i = 0
            # iterate through visual list and remove any later duplicates, keeping first occurrence
            while i < self.list_widget.count():
                it = self.list_widget.item(i)
                try:
                    path = it.data(Qt.ItemDataRole.UserRole)
                except Exception:
                    path = None
                if path is None:
                    i += 1
                    continue
                if path in seen:
                    # remove visual item and corresponding playlist entry
                    self.list_widget.takeItem(i)
                    try:
                        if 0 <= i < len(self.playlist) and self.playlist[i] == path:
                            self.playlist.pop(i)
                        else:
                            # if playlist out-of-sync, attempt to remove first matching path
                            try:
                                self.playlist.remove(path)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    # do not increment i because list shifted
                else:
                    seen.add(path)
                    i += 1
            # persist changes
            try:
                self.save_playlist()
            except Exception:
                pass
        except Exception as e:
            pass

    def shuffle_playlist(self):
        try:
            if not self.playlist:
                return
            import random
            # remember currently playing file
            cur_path = None
            if 0 <= self.current_index < len(self.playlist):
                cur_path = self.playlist[self.current_index]

            # gather current items (path, name) preserving exact row order
            items = []
            for i in range(self.list_widget.count()):
                it = self.list_widget.item(i)
                try:
                    path = it.data(Qt.ItemDataRole.UserRole)
                except Exception:
                    path = None
                try:
                    name = it.data(Qt.ItemDataRole.UserRole + 1)
                except Exception:
                    name = None
                if path is not None:
                    items.append((path, name))

            # if too few items, nothing to animate
            if len(items) <= 1:
                return


            # Smooth animation: animate one overlay per row to the shuffled row positions,
            # then rebuild the list in the final order.
            try:
                from PyQt6.QtCore import QParallelAnimationGroup, QPoint, QEventLoop
                from PyQt6.QtGui import QPixmap
                from PyQt6.QtWidgets import QLabel

                count = self.list_widget.count()
                heights = []
                for i in range(count):
                    try:
                        h = self.list_widget.sizeHintForRow(i)
                        if not h or h <= 0:
                            item = self.list_widget.item(i)
                            w = self.list_widget.itemWidget(item)
                            h = w.sizeHint().height() if w is not None else item.sizeHint().height()
                    except Exception:
                        try:
                            item = self.list_widget.item(i)
                            w = self.list_widget.itemWidget(item)
                            h = w.sizeHint().height() if w is not None else item.sizeHint().height()
                        except Exception:
                            h = 24
                    heights.append(max(8, int(h)))

                y_positions = []
                y = 0
                for h in heights:
                    y_positions.append(y)
                    y += h

                overlays = []
                hidden_widgets = []
                viewport = self.list_widget.viewport()
                for i in range(count):
                    item = self.list_widget.item(i)
                    widget = None
                    try:
                        widget = self.list_widget.itemWidget(item)
                    except Exception:
                        widget = None

                    try:
                        if widget is not None:
                            pm = widget.grab()
                        else:
                            pm = QPixmap(viewport.width(), heights[i])
                            pm.fill(Qt.GlobalColor.transparent)
                    except Exception:
                        pm = QPixmap(viewport.width(), heights[i])
                        pm.fill(Qt.GlobalColor.transparent)

                    # Hide the real row widget during animation so we don't see
                    # a duplicate (original + overlay) at the same time.
                    try:
                        if widget is not None:
                            widget.setVisible(False)
                            hidden_widgets.append(widget)
                    except Exception:
                        pass

                    lbl = QLabel(viewport)
                    lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                    lbl.setPixmap(pm)
                    lbl.resize(pm.size())
                    lbl.move(0, y_positions[i])
                    lbl.show()
                    overlays.append((i, lbl, y_positions[i]))

                # Compute shuffled order by source indices; this works even when
                # multiple rows reference the same path.
                src_indices = list(range(len(items)))
                random.shuffle(src_indices)
                target_row_for_source = {src_idx: new_idx for new_idx, src_idx in enumerate(src_indices)}

                # Build final shuffled item payload.
                shuffled_items = [items[src_idx] for src_idx in src_indices]

                # animate overlays to their new positions
                group = QParallelAnimationGroup(self)
                for src_idx, lbl, old_y in overlays:
                    target_idx = target_row_for_source.get(src_idx, src_idx)
                    target_y = y_positions[target_idx] if 0 <= target_idx < len(y_positions) else old_y
                    anim = QPropertyAnimation(lbl, b'pos')
                    anim.setStartValue(QPoint(0, old_y))
                    anim.setEndValue(QPoint(0, int(target_y)))
                    anim.setDuration(400)
                    try:
                        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
                    except Exception:
                        pass
                    group.addAnimation(anim)

                # Wait for animation to finish before updating the list
                loop = QEventLoop()
                def _on_finished():
                    # remove overlays and rebuild the list in new order
                    try:
                        for _src, lbl, _oy in overlays:
                            try:
                                lbl.hide()
                                lbl.setParent(None)
                            except Exception:
                                pass
                    except Exception:
                        pass

                    # Restore any hidden source widgets before list clear/rebuild.
                    try:
                        for w in hidden_widgets:
                            try:
                                w.setVisible(True)
                            except Exception:
                                pass
                    except Exception:
                        pass

                    # rebuild visual list and internal playlist
                    self.list_widget.clear()
                    self.playlist = []
                    new_index = -1
                    for idx, (path, name) in enumerate(shuffled_items):
                        self.add_playlist_item(path, display_name=name)
                        if cur_path is not None and path == cur_path:
                            new_index = idx

                    if new_index != -1:
                        self.current_index = new_index
                        try:
                            self.list_widget.setCurrentRow(new_index)
                        except Exception:
                            pass
                    else:
                        self.current_index = -1

                    try:
                        self.save_playlist()
                    except Exception:
                        pass
                    loop.quit()

                group.finished.connect(_on_finished)
                group.start()
                loop.exec()
                return
            except Exception:
                # if animation fails for any reason, fall back to instant shuffle
                pass

            # fallback: instant shuffle (original behavior)
            random.shuffle(items)
            self.list_widget.clear()
            self.playlist = []
            new_index = -1
            for idx, (path, name) in enumerate(items):
                self.add_playlist_item(path, display_name=name)
                if cur_path is not None and path == cur_path:
                    new_index = idx

            if new_index != -1:
                self.current_index = new_index
                try:
                    self.list_widget.setCurrentRow(new_index)
                except Exception:
                    pass
            else:
                self.current_index = -1

            try:
                self.save_playlist()
            except Exception:
                pass
        except Exception as e:
            pass

    def save_playlist(self):
        try:
            # Persist playlist as list of objects with path and optional display name
            items = []
            count = self.list_widget.count()
            for i in range(count):
                it = self.list_widget.item(i)
                try:
                    path = it.data(Qt.ItemDataRole.UserRole)
                except Exception:
                    path = None
                try:
                    name = it.data(Qt.ItemDataRole.UserRole + 1)
                except Exception:
                    name = None
                try:
                    loop_flag = bool(it.data(Qt.ItemDataRole.UserRole + 2))
                except Exception:
                    loop_flag = False
                if path is None:
                    continue
                items.append({'path': path, 'name': name, 'loop': loop_flag})

            data = {'items': items}
            fn = os.path.join(os.path.expanduser('~'), '.music_island_playlist.json')
            with open(fn, 'w', encoding='utf-8') as f:
                import json
                json.dump(data, f)
        except Exception as e:
            pass

    def load_saved_playlist(self):
        try:
            fn = os.path.join(os.path.expanduser('~'), '.music_island_playlist.json')
            if not os.path.exists(fn):
                return
            import json
            with open(fn, 'r', encoding='utf-8') as f:
                data = json.load(f)
            items = data.get('items', [])
            valid_items = []  # Track items that actually exist
            missing_files = []  # Track missing files for cleanup
            
            for entry in items:
                p = entry.get('path')
                name = entry.get('name')
                loop_flag = entry.get('loop', False)
                if p and os.path.exists(p):
                    # add and set per-item loop flag
                    try:
                        self.add_playlist_item(p, display_name=name)
                        # set loop flag on the last-added item
                        try:
                            last_index = self.list_widget.count() - 1
                            if last_index >= 0:
                                it = self.list_widget.item(last_index)
                                try:
                                    it.setData(Qt.ItemDataRole.UserRole + 2, bool(loop_flag))
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        # Add to valid items list
                        valid_items.append(entry)
                    except Exception:
                        pass
                else:
                    # File doesn't exist - track for cleanup
                    if p:
                        missing_files.append(p)
            
            # Clean up theme colors for missing files
            for missing_file in missing_files:
                if missing_file in getattr(self, '_theme_colors', {}):
                    del self._theme_colors[missing_file]
            
            # If any files were missing, save the cleaned playlist
            if missing_files:
                # Update the data with only valid items
                cleaned_data = {'items': valid_items}
                
                # Save the cleaned playlist
                with open(fn, 'w', encoding='utf-8') as f:
                    json.dump(cleaned_data, f)
            
        except Exception as e:
            pass

    def _on_volume_changed(self, v: int):
        try:
            try:
                ctl = getattr(self, '_system_volume_controller', None)
                if ctl is not None and getattr(self, '_system_volume_linked', False) and ctl.available():
                    ctl.set_volume(int(max(0, min(100, v))))
            except Exception:
                pass
            self._apply_playback_volume(v)
        except Exception as e:
            pass

    def _playback_target_volume(self, slider_value: int = None) -> float:
        try:
            if slider_value is None:
                slider_value = self.volume.value() if hasattr(self, 'volume') else 70
        except Exception:
            slider_value = 70

        try:
            if getattr(self, '_system_volume_linked', False):
                return 1.0
        except Exception:
            pass

        try:
            slider_value = int(max(0, min(100, slider_value)))
            if slider_value == 0:
                return 0.0
            return max(0.0, min(1.0, (slider_value / 100.0) ** 1.5))
        except Exception:
            return 0.7

    def _apply_playback_volume(self, slider_value: int = None):
        try:
            volume = self._playback_target_volume(slider_value)
            try:
                if hasattr(self, 'audio') and self.audio is not None:
                    self.audio.setVolume(volume)
                elif hasattr(self, 'audio_output') and self.audio_output is not None:
                    self.audio_output.setVolume(volume)
            except Exception:
                pass
        except Exception:
            pass

    def _sync_volume_slider_from_system(self):
        try:
            ctl = getattr(self, '_system_volume_controller', None)
            if ctl is None or not getattr(self, '_system_volume_linked', False) or not ctl.available():
                return
            if not hasattr(self, 'volume') or self.volume is None:
                return
            sys_v = int(max(0, min(100, ctl.get_volume())))
            if self.volume.value() != sys_v:
                was_blocked = self.volume.blockSignals(True)
                try:
                    self.volume.setValue(sys_v)
                finally:
                    self.volume.blockSignals(was_blocked)
                self._apply_playback_volume(sys_v)
        except Exception:
            pass

    def _init_system_volume_sync(self):
        try:
            self._system_volume_controller = None
            self._system_volume_linked = False
            if sys.platform != 'win32' or SystemVolumeController is None:
                self._apply_playback_volume()
                return
            if not getattr(self, '_volume_sync_system', True):
                self._apply_playback_volume()
                return

            ctl = SystemVolumeController()
            if ctl is None or not ctl.available():
                self._apply_playback_volume()
                return

            self._system_volume_controller = ctl
            self._system_volume_linked = True

            if hasattr(self, 'volume') and self.volume is not None:
                sys_v = int(max(0, min(100, ctl.get_volume())))
                was_blocked = self.volume.blockSignals(True)
                try:
                    self.volume.setValue(sys_v)
                finally:
                    self.volume.blockSignals(was_blocked)
                self._apply_playback_volume(sys_v)

            poll = QTimer(self)
            poll.setInterval(250)
            poll.timeout.connect(self._sync_volume_slider_from_system)
            poll.start()
            self._system_volume_poll_timer = poll
        except Exception:
            self._system_volume_controller = None
            self._system_volume_linked = False
            self._apply_playback_volume()

    def delete_song(self, list_item):
        """Delete a song from the playlist with confirmation"""
        try:
            # Check if user has disabled confirmation
            dont_ask_again = getattr(self, '_delete_dont_ask_again', False)
            
            if not dont_ask_again:
                # Show confirmation dialog
                from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox
                from PyQt6.QtCore import Qt
                
                dlg = QDialog(self)
                dlg.setWindowTitle('Confirm Delete')
                dlg.setModal(True)
                dlg.setFixedSize(300, 150)
                layout = QVBoxLayout()
                
                # Get song name for the message
                row = self.list_widget.row(list_item)
                song_name = "Unknown Song"
                if row >= 0 and row < len(self.playlist):
                    try:
                        song_name = os.path.splitext(os.path.basename(self.playlist[row]))[0]
                    except Exception:
                        pass
                
                message = QLabel(f"Delete '{song_name}' from the library?")
                message.setWordWrap(True)
                layout.addWidget(message)
                
                # Checkbox for "Don't ask again"
                dont_ask_checkbox = QCheckBox("Continue and Don't Ask Again")
                layout.addWidget(dont_ask_checkbox)
                
                # Buttons
                button_layout = QHBoxLayout()
                delete_btn = QPushButton("Delete")
                cancel_btn = QPushButton("Cancel")
                button_layout.addWidget(delete_btn)
                button_layout.addWidget(cancel_btn)
                layout.addLayout(button_layout)
                
                dlg.setLayout(layout)
                
                def confirm_delete():
                    self._delete_dont_ask_again = dont_ask_checkbox.isChecked()
                    self._save_settings()  # Save the preference
                    self._actually_delete_song(list_item)
                    dlg.close()
                
                def cancel_delete():
                    dlg.close()
                
                delete_btn.clicked.connect(confirm_delete)
                cancel_btn.clicked.connect(cancel_delete)
                
                dlg.show()
            else:
                # User has disabled confirmation, delete directly
                self._actually_delete_song(list_item)
                
        except Exception as e:
            print(f"Error showing delete confirmation: {e}")

    def _actually_delete_song(self, list_item):
        """Actually perform the song deletion"""
        try:
            row = self.list_widget.row(list_item)
            if row >= 0 and row < len(self.playlist):
                # Stop playback if this is the current song
                if row == self.current_index:
                    try:
                        self.player.stop()
                        self.current_index = -1
                        self._set_song_text_with_font("No song.")
                        self.cover.set_cover(None)
                    except Exception:
                        pass
                
                # Remove from playlist and list widget
                removed_path = self.playlist.pop(row)
                self.list_widget.takeItem(row)
                
                # Adjust current_index if necessary
                if self.current_index > row:
                    self.current_index -= 1
                elif self.current_index == row:
                    # If we deleted the current song, try to play the next one
                    if self.playlist and self.current_index < len(self.playlist):
                        self.play_index(self.current_index)
                    else:
                        self.current_index = -1
                
                # Clean up theme color for removed song
                if removed_path in self._theme_colors:
                    del self._theme_colors[removed_path]
                
                # Save the updated playlist
                self.save_playlist()
                
        except Exception as e:
            print(f"Error deleting song: {e}")

    def _load_settings(self):
        """Load user settings from settings.json file"""
        try:
            import json
            loaded_song_colors = {}
            loaded_custom_covers = {}
            settings_file = get_config_path()
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    self._playback_mode = settings.get('playback_mode', 0)  # 0=Stop, 1=Loop, 2=Playlist
                    self._custom_font_enabled = settings.get('custom_font_enabled', True)
                    self._reflections_enabled = settings.get('reflections_enabled', True)
                    self._volume_sync_system = settings.get('volume_sync_system', True)
                    self._delete_dont_ask_again = settings.get('delete_dont_ask_again', False)
                    self._default_hue = settings.get('default_hue', 200)
                    self._default_saturation = settings.get('default_saturation', 70)
                    self._default_value = settings.get('default_value', 80)
                    self._tutorial_completed = settings.get('tutorial_completed', False)
                    self._hotkey_toggle_vk = settings.get('hotkey_toggle_vk', 0x78)
                    self._hotkey_drag_vk = settings.get('hotkey_drag_vk', 0x79)
                    self._hotkey_next_vk = settings.get('hotkey_next_vk', 0x21)
                    self._hotkey_prev_vk = settings.get('hotkey_prev_vk', 0x22)
                    # Migrate the previous built-in defaults to the new layout.
                    if self._hotkey_toggle_vk == 0x79 and self._hotkey_drag_vk == 0x7A:
                        self._hotkey_toggle_vk = 0x78
                        self._hotkey_drag_vk = 0x79
                    if self._hotkey_next_vk == 0x7B and self._hotkey_prev_vk == 0x78:
                        self._hotkey_next_vk = 0x21
                        self._hotkey_prev_vk = 0x22
                    try:
                        raw_covers = settings.get('song_custom_covers', {}) or {}
                        if isinstance(raw_covers, dict):
                            for p, img_path in raw_covers.items():
                                try:
                                    if isinstance(img_path, str) and img_path:
                                        loaded_custom_covers[p] = img_path
                                except Exception:
                                    pass
                    except Exception:
                        loaded_custom_covers = {}
                    try:
                        raw_colors = settings.get('song_theme_colors', {}) or {}
                        if isinstance(raw_colors, dict):
                            for p, hexval in raw_colors.items():
                                try:
                                    c = QColor(hexval)
                                    if c.isValid():
                                        loaded_song_colors[p] = c
                                except Exception:
                                    pass
                    except Exception:
                        loaded_song_colors = {}
            else:
                # Default settings
                self._playback_mode = 0  # Default to Stop mode
                self._custom_font_enabled = True  # Default to custom font on first launch
                self._reflections_enabled = True
                self._volume_sync_system = True
                self._delete_dont_ask_again = False
                self._default_hue = 200
                self._default_saturation = 70
                self._default_value = 80
                self._tutorial_completed = False  # Tutorial not completed on fresh install

            # _load_settings is called before _theme_colors is initialized in __init.
            # Store colors in a pending dict and merge after _theme_colors is created.
            try:
                if loaded_song_colors:
                    if hasattr(self, '_theme_colors') and isinstance(getattr(self, '_theme_colors'), dict):
                        self._theme_colors.update(loaded_song_colors)
                    else:
                        self._pending_theme_colors = dict(loaded_song_colors)
            except Exception:
                pass
            try:
                if loaded_custom_covers:
                    if hasattr(self, '_custom_covers') and isinstance(getattr(self, '_custom_covers'), dict):
                        self._custom_covers.update(loaded_custom_covers)
                    else:
                        self._pending_custom_covers = dict(loaded_custom_covers)
            except Exception:
                pass
        except Exception as e:
            self._playback_mode = 0  # Default to Stop mode
            self._custom_font_enabled = True  # Default to custom font on first launch
            self._reflections_enabled = True
            self._volume_sync_system = True
            self._delete_dont_ask_again = False
            self._default_hue = 200
            self._default_saturation = 70
            self._default_value = 80
            self._tutorial_completed = False
        
        # Apply font setting after loading
        try:
            self._apply_font_setting()
        except Exception as e:
            pass

    def _save_settings(self):
        """Save user settings to settings.json file"""
        try:
            import json
            song_theme_colors = {}
            try:
                for p, c in getattr(self, '_theme_colors', {}).items():
                    try:
                        song_theme_colors[p] = QColor(c).name()
                    except Exception:
                        pass
            except Exception:
                song_theme_colors = {}

            song_custom_covers = {}
            try:
                for p, img_path in getattr(self, '_custom_covers', {}).items():
                    try:
                        if isinstance(img_path, str) and img_path:
                            song_custom_covers[p] = img_path
                    except Exception:
                        pass
            except Exception:
                song_custom_covers = {}

            settings = {
                'playback_mode': getattr(self, '_playback_mode', 0),
                'custom_font_enabled': getattr(self, '_custom_font_enabled', True),
                'reflections_enabled': getattr(self, '_reflections_enabled', True),
                'volume_sync_system': getattr(self, '_volume_sync_system', True),
                'delete_dont_ask_again': getattr(self, '_delete_dont_ask_again', False),
                'default_hue': getattr(self, '_default_hue', 200),
                'default_saturation': getattr(self, '_default_saturation', 70),
                'default_value': getattr(self, '_default_value', 80),
                'tutorial_completed': getattr(self, '_tutorial_completed', False),
                'song_theme_colors': song_theme_colors,
                'song_custom_covers': song_custom_covers,
                'hotkey_toggle_vk': getattr(self, '_hotkey_toggle_vk', 0x78),
                'hotkey_drag_vk': getattr(self, '_hotkey_drag_vk', 0x79),
                'hotkey_next_vk': getattr(self, '_hotkey_next_vk', 0x21),
                'hotkey_prev_vk': getattr(self, '_hotkey_prev_vk', 0x22),
            }
            with open(get_config_path(), 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            pass

    def open_settings(self):
        """Open settings popup with loop and custom font options"""
        try:
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QGroupBox
            from PyQt6.QtCore import Qt

            dlg = QDialog(self)
            dlg.setWindowTitle('Settings')
            dlg.setModal(False)
            dlg.setFixedSize(350, 650)  # Height for all settings groups
            dlg.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            # Add theme-colored glass reflection to the dialog edges
            _player_ref = self
            _orig_paint = dlg.paintEvent
            def _glass_paint(event, _orig=_orig_paint, _dlg=dlg, _pl=_player_ref):
                _orig(event)
                if not getattr(_pl, '_reflections_enabled', True):
                    return
                try:
                    tc = QColor(getattr(_pl, '_theme_color', QColor('#1f1f23')))
                    r = QRectF(_dlg.rect())
                    if r.width() <= 4 or r.height() <= 4:
                        return
                    p = QPainter(_dlg)
                    p.setRenderHint(QPainter.RenderHint.Antialiasing)
                    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
                    edge_w = max(3.0, min(r.width(), r.height()) * 0.22)
                    alpha = 0.28
                    # top edge glow
                    gt = QLinearGradient(r.left(), r.top(), r.left(), r.top() + edge_w)
                    a0 = int(255 * alpha)
                    gt.setColorAt(0.0, QColor(tc.red(), tc.green(), tc.blue(), a0))
                    gt.setColorAt(0.35, QColor(tc.red(), tc.green(), tc.blue(), int(a0 * 0.42)))
                    gt.setColorAt(1.0, QColor(tc.red(), tc.green(), tc.blue(), 0))
                    p.fillRect(r, gt)
                    # bottom edge glow
                    gb = QLinearGradient(r.left(), r.bottom(), r.left(), r.bottom() - edge_w)
                    gb.setColorAt(0.0, QColor(tc.red(), tc.green(), tc.blue(), a0))
                    gb.setColorAt(0.35, QColor(tc.red(), tc.green(), tc.blue(), int(a0 * 0.42)))
                    gb.setColorAt(1.0, QColor(tc.red(), tc.green(), tc.blue(), 0))
                    p.fillRect(r, gb)
                    # left edge glow
                    gl = QLinearGradient(r.left(), r.top(), r.left() + edge_w, r.top())
                    gl.setColorAt(0.0, QColor(tc.red(), tc.green(), tc.blue(), a0))
                    gl.setColorAt(0.35, QColor(tc.red(), tc.green(), tc.blue(), int(a0 * 0.42)))
                    gl.setColorAt(1.0, QColor(tc.red(), tc.green(), tc.blue(), 0))
                    p.fillRect(r, gl)
                    # right edge glow
                    gr = QLinearGradient(r.right(), r.top(), r.right() - edge_w, r.top())
                    gr.setColorAt(0.0, QColor(tc.red(), tc.green(), tc.blue(), a0))
                    gr.setColorAt(0.35, QColor(tc.red(), tc.green(), tc.blue(), int(a0 * 0.42)))
                    gr.setColorAt(1.0, QColor(tc.red(), tc.green(), tc.blue(), 0))
                    p.fillRect(r, gr)
                    # subtle ambient light at top
                    ga = QLinearGradient(r.left(), r.top(), r.left(), r.bottom())
                    ga.setColorAt(0.0, QColor(255, 255, 255, int(255 * 0.06)))
                    ga.setColorAt(0.34, QColor(255, 255, 255, int(255 * 0.02)))
                    ga.setColorAt(1.0, QColor(255, 255, 255, 0))
                    p.fillRect(r, ga)
                    p.end()
                except Exception:
                    pass
            dlg.paintEvent = _glass_paint
            layout = QVBoxLayout()

            # Create group box for settings
            settings_group = QGroupBox("Playback Settings")
            settings_layout = QVBoxLayout()

            # Playback mode selection
            mode_group = QButtonGroup(self)
            
            # Stop mode radio button
            stop_radio = QRadioButton("Stop")
            stop_radio.setChecked(True)  # Default to Stop mode
            mode_group.addButton(stop_radio, 0)  # ID 0 = Stop
            settings_layout.addWidget(stop_radio)
            
            # Loop mode radio button
            loop_radio = QRadioButton("Loop")
            mode_group.addButton(loop_radio, 1)  # ID 1 = Loop
            settings_layout.addWidget(loop_radio)
            
            # Playlist mode radio button
            playlist_radio = QRadioButton("Playlist")
            mode_group.addButton(playlist_radio, 2)  # ID 2 = Playlist
            settings_layout.addWidget(playlist_radio)
            
            # Set current selection based on saved setting
            current_mode = getattr(self, '_playback_mode', 0)  # Default to Stop (0)
            if current_mode == 0:
                stop_radio.setChecked(True)
            elif current_mode == 1:
                loop_radio.setChecked(True)
            elif current_mode == 2:
                playlist_radio.setChecked(True)

            # Custom font checkbox
            font_checkbox = QCheckBox("Use Custom Font")
            current_font_setting = getattr(self, '_custom_font_enabled', False)
            font_checkbox.setChecked(current_font_setting)
            settings_layout.addWidget(font_checkbox)

            # Reflections checkbox
            reflections_checkbox = QCheckBox("Enable Reflections (uses more CPU/GPU)")
            reflections_checkbox.setChecked(getattr(self, '_reflections_enabled', True))
            settings_layout.addWidget(reflections_checkbox)

            # Volume sync checkbox
            volume_sync_checkbox = QCheckBox("Sync Volume to Windows Volume")
            volume_sync_checkbox.setChecked(getattr(self, '_volume_sync_system', True))
            settings_layout.addWidget(volume_sync_checkbox)

            settings_group.setLayout(settings_layout)
            layout.addWidget(settings_group)
            
            # Color settings group
            color_group = QGroupBox("Song Color")
            color_layout = QVBoxLayout()
            
            # Get current song's color or default
            current_song_color = None
            current_file_path = None
            try:
                if hasattr(self, 'current_index') and self.current_index >= 0 and self.current_index < len(self.playlist):
                    current_file_path = self.playlist[self.current_index]
                    if current_file_path in getattr(self, '_theme_colors', {}):
                        current_song_color = self._theme_colors[current_file_path]
            except Exception as e:
                pass
            
            # If no current song color, use default HSV values
            if current_song_color is not None:
                # Convert QColor to HSV
                h = int(current_song_color.hue())
                s = int(current_song_color.saturation() * 100 / 255)
                v = int(current_song_color.value() * 100 / 255)
            else:
                # Use default values
                h = getattr(self, '_default_hue', 200)
                s = getattr(self, '_default_saturation', 70)
                v = getattr(self, '_default_value', 80)
            
            # HSV Sliders
            hue_layout = QHBoxLayout()
            hue_layout.addWidget(QLabel("Hue:"))
            hue_slider = QSlider(Qt.Orientation.Horizontal)
            hue_slider.setRange(0, 359)
            hue_slider.setValue(h)
            hue_label = QLabel(str(hue_slider.value()))
            hue_layout.addWidget(hue_slider)
            hue_layout.addWidget(hue_label)
            color_layout.addLayout(hue_layout)
            
            saturation_layout = QHBoxLayout()
            saturation_layout.addWidget(QLabel("Saturation:"))
            saturation_slider = QSlider(Qt.Orientation.Horizontal)
            saturation_slider.setRange(0, 100)
            saturation_slider.setValue(s)
            saturation_label = QLabel(str(saturation_slider.value()))
            saturation_layout.addWidget(saturation_slider)
            saturation_layout.addWidget(saturation_label)
            color_layout.addLayout(saturation_layout)
            
            value_layout = QHBoxLayout()
            value_layout.addWidget(QLabel("Value:"))
            value_slider = QSlider(Qt.Orientation.Horizontal)
            value_slider.setRange(0, 100)
            value_slider.setValue(v)
            value_label = QLabel(str(value_slider.value()))
            value_layout.addWidget(value_slider)
            value_layout.addWidget(value_label)
            color_layout.addLayout(value_layout)
            
            # Color preview
            color_preview = QLabel()
            color_preview.setFixedHeight(40)
            _prev_c = QColor.fromHsv(hue_slider.value(), int(saturation_slider.value() * 255 / 100), int(value_slider.value() * 255 / 100))
            color_preview.setStyleSheet(f"background-color: {_prev_c.name()}; border: 1px solid #666;")
            color_layout.addWidget(color_preview)
            
            # Update color preview when sliders change
            def update_color_preview():
                h = hue_slider.value()
                s = saturation_slider.value()
                v = value_slider.value()
                _c = QColor.fromHsv(h, int(s * 255 / 100), int(v * 255 / 100))
                color_preview.setStyleSheet(f"background-color: {_c.name()}; border: 1px solid #666;")
                hue_label.setText(str(h))
                saturation_label.setText(str(s))
                value_label.setText(str(v))
            
            hue_slider.valueChanged.connect(update_color_preview)
            saturation_slider.valueChanged.connect(update_color_preview)
            value_slider.valueChanged.connect(update_color_preview)
            
            # Initialize preview
            update_color_preview()
            
            # Reset Color button inside the color group
            reset_color_btn = GlassButton("Reset Color", reflection_radius=6.0, reflection_intensity=0.18)
            reset_color_btn.setFixedHeight(32)
            reset_color_btn.setStyleSheet("QPushButton { background-color: rgba(0,0,0,180); color: white; border: none; border-radius: 0px; padding: 2px 4px; qproperty-alignment: AlignCenter; } QPushButton:hover { background-color: rgba(40,40,40,200); }")
            color_layout.addWidget(reset_color_btn)

            def reset_color():
                if current_file_path:
                    # Remove the existing color so _generate_initial_color re-derives it
                    if current_file_path in getattr(self, '_theme_colors', {}):
                        del self._theme_colors[current_file_path]
                    self._generate_initial_color(current_file_path)
                    new_col = self._theme_colors.get(current_file_path)
                    if new_col is not None:
                        self._set_theme_color_for_song(current_file_path, new_col)
                        # Update the HSV sliders to reflect the new color
                        qc = QColor(new_col)
                        hue_slider.setValue(max(0, qc.hue()))
                        saturation_slider.setValue(int(qc.saturation() * 100 / 255))
                        value_slider.setValue(int(qc.value() * 100 / 255))
                    self._save_settings()

            reset_color_btn.clicked.connect(reset_color)

            # Upload Cover button
            cover_btn_layout = QHBoxLayout()
            upload_cover_btn = GlassButton("Upload Cover", reflection_radius=6.0, reflection_intensity=0.18)
            upload_cover_btn.setFixedHeight(32)
            upload_cover_btn.setStyleSheet("QPushButton { background-color: rgba(0,0,0,180); color: white; border: none; border-radius: 0px; padding: 2px 4px; qproperty-alignment: AlignCenter; } QPushButton:hover { background-color: rgba(40,40,40,200); }")
            cover_btn_layout.addWidget(upload_cover_btn)
            remove_cover_btn = GlassButton("Remove Cover", reflection_radius=6.0, reflection_intensity=0.18)
            remove_cover_btn.setFixedHeight(32)
            remove_cover_btn.setStyleSheet("QPushButton { background-color: rgba(0,0,0,180); color: white; border: none; border-radius: 0px; padding: 2px 4px; qproperty-alignment: AlignCenter; } QPushButton:hover { background-color: rgba(40,40,40,200); }")
            cover_btn_layout.addWidget(remove_cover_btn)
            color_layout.addLayout(cover_btn_layout)

            # Show/hide remove button based on whether a custom cover exists
            has_custom = current_file_path and current_file_path in getattr(self, '_custom_covers', {})
            remove_cover_btn.setVisible(bool(has_custom))

            def upload_cover():
                if not current_file_path:
                    return
                from PyQt6.QtWidgets import QFileDialog
                img_path, _ = QFileDialog.getOpenFileName(
                    dlg, "Select Album Cover", "",
                    "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
                if not img_path:
                    return
                try:
                    # Determine covers directory under APPDATA
                    import hashlib, shutil
                    config_dir = os.path.dirname(get_config_path())
                    covers_dir = os.path.join(config_dir, 'covers')
                    os.makedirs(covers_dir, exist_ok=True)
                    # Generate a stable filename from the song path
                    h = hashlib.sha256(current_file_path.encode('utf-8')).hexdigest()[:16]
                    ext = os.path.splitext(img_path)[1].lower() or '.png'
                    dest = os.path.join(covers_dir, h + ext)
                    # Remove old cover file if extension changed
                    for old_ext in ('.png', '.jpg', '.jpeg', '.bmp', '.webp'):
                        old_path = os.path.join(covers_dir, h + old_ext)
                        if old_path != dest and os.path.exists(old_path):
                            try:
                                os.remove(old_path)
                            except Exception:
                                pass
                    shutil.copy2(img_path, dest)
                    self._custom_covers[current_file_path] = dest
                    try:
                        self._cover_art_cache.pop(current_file_path, None)
                    except Exception:
                        pass
                    self._save_settings()
                    # Reload cover art to show the new image
                    self.load_cover_art(current_file_path)
                    remove_cover_btn.setVisible(True)
                except Exception as e:
                    pass

            def remove_cover():
                if not current_file_path:
                    return
                try:
                    if current_file_path in getattr(self, '_custom_covers', {}):
                        old_path = self._custom_covers.pop(current_file_path)
                        try:
                            self._cover_art_cache.pop(current_file_path, None)
                        except Exception:
                            pass
                        # Delete the stored cover file
                        if isinstance(old_path, str) and os.path.exists(old_path):
                            try:
                                os.remove(old_path)
                            except Exception:
                                pass
                        self._save_settings()
                        # Reload cover to fall back to embedded/external art
                        self.load_cover_art(current_file_path)
                        remove_cover_btn.setVisible(False)
                except Exception as e:
                    pass

            upload_cover_btn.clicked.connect(upload_cover)
            remove_cover_btn.clicked.connect(remove_cover)

            color_group.setLayout(color_layout)
            layout.addWidget(color_group)

            # --- Hotkey settings group ---
            hotkey_group = QGroupBox("Hotkeys")
            hotkey_layout = QVBoxLayout()

            _pending_capture = {'target': None, 'timer': None, 'original_text': None, 'btn': None}

            toggle_vk = getattr(self, '_hotkey_toggle_vk', 0x79)
            drag_vk = getattr(self, '_hotkey_drag_vk', 0x7A)

            toggle_hk_layout = QHBoxLayout()
            toggle_hk_layout.addWidget(QLabel("Toggle (expand/shrink):"))
            toggle_hk_btn = GlassButton(self._vk_to_name(toggle_vk), reflection_radius=6.0, reflection_intensity=0.18)
            toggle_hk_btn.setStyleSheet("QPushButton { background-color: rgba(0,0,0,180); color: white; border: none; border-radius: 0px; padding: 6px; } QPushButton:hover { background-color: rgba(40,40,40,200); }")
            toggle_hk_layout.addWidget(toggle_hk_btn)
            hotkey_layout.addLayout(toggle_hk_layout)

            drag_hk_layout = QHBoxLayout()
            drag_hk_layout.addWidget(QLabel("Drag (hold to move):"))
            drag_hk_btn = GlassButton(self._vk_to_name(drag_vk), reflection_radius=6.0, reflection_intensity=0.18)
            drag_hk_btn.setStyleSheet("QPushButton { background-color: rgba(0,0,0,180); color: white; border: none; border-radius: 0px; padding: 6px; } QPushButton:hover { background-color: rgba(40,40,40,200); }")
            drag_hk_layout.addWidget(drag_hk_btn)
            hotkey_layout.addLayout(drag_hk_layout)

            def _cancel_capture():
                if _pending_capture['timer']:
                    _pending_capture['timer'].stop()
                    _pending_capture['timer'] = None
                btn = _pending_capture.get('btn')
                orig = _pending_capture.get('original_text')
                if btn and orig:
                    btn.setText(orig)
                _pending_capture['target'] = None
                _pending_capture['btn'] = None
                _pending_capture['original_text'] = None

            def _start_capture(target, btn):
                # Cancel any in-progress capture
                _cancel_capture()
                _pending_capture['target'] = target
                _pending_capture['btn'] = btn
                _pending_capture['original_text'] = btn.text()
                btn.setText("Press a key...")
                timer = QTimer(dlg)
                timer.setSingleShot(True)
                timer.timeout.connect(_cancel_capture)
                timer.start(3000)
                _pending_capture['timer'] = timer

            toggle_hk_btn.clicked.connect(lambda: _start_capture('toggle', toggle_hk_btn))
            drag_hk_btn.clicked.connect(lambda: _start_capture('drag', drag_hk_btn))

            next_vk_val = getattr(self, '_hotkey_next_vk', 0x21)
            prev_vk_val = getattr(self, '_hotkey_prev_vk', 0x22)

            next_hk_layout = QHBoxLayout()
            next_hk_layout.addWidget(QLabel("Next Song (global):"))
            next_hk_btn = GlassButton(self._vk_to_name(next_vk_val), reflection_radius=6.0, reflection_intensity=0.18)
            next_hk_btn.setStyleSheet("QPushButton { background-color: rgba(0,0,0,180); color: white; border: none; border-radius: 0px; padding: 6px; } QPushButton:hover { background-color: rgba(40,40,40,200); }")
            next_hk_layout.addWidget(next_hk_btn)
            hotkey_layout.addLayout(next_hk_layout)

            prev_hk_layout = QHBoxLayout()
            prev_hk_layout.addWidget(QLabel("Prev Song (global):"))
            prev_hk_btn = GlassButton(self._vk_to_name(prev_vk_val), reflection_radius=6.0, reflection_intensity=0.18)
            prev_hk_btn.setStyleSheet("QPushButton { background-color: rgba(0,0,0,180); color: white; border: none; border-radius: 0px; padding: 6px; } QPushButton:hover { background-color: rgba(40,40,40,200); }")
            prev_hk_layout.addWidget(prev_hk_btn)
            hotkey_layout.addLayout(prev_hk_layout)

            next_hk_btn.clicked.connect(lambda: _start_capture('next', next_hk_btn))
            prev_hk_btn.clicked.connect(lambda: _start_capture('prev', prev_hk_btn))

            # Install a key-capture event filter on the dialog
            class _HotkeyCaptureFilter(QObject):
                def __init__(self, parent, pending, player_ref):
                    super().__init__(parent)
                    self._pending = pending
                    self._player = player_ref

                def eventFilter(self, obj, event):
                    if event.type() == QEvent.Type.KeyPress and self._pending.get('target'):
                        vk = event.nativeVirtualKey()
                        if not vk or vk in (0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x10, 0x11, 0x12):
                            # Ignore bare modifier keys (Shift/Ctrl/Alt)
                            return True
                        target = self._pending['target']
                        self._pending['btn'].setText(self._player._vk_to_name(vk))
                        if target == 'toggle':
                            self._player._hotkey_toggle_vk = vk
                        elif target == 'drag':
                            self._player._hotkey_drag_vk = vk
                        elif target == 'next':
                            self._player._hotkey_next_vk = vk
                        elif target == 'prev':
                            self._player._hotkey_prev_vk = vk
                        if self._pending.get('timer'):
                            self._pending['timer'].stop()
                            self._pending['timer'] = None
                        self._pending['target'] = None
                        self._pending['btn'] = None
                        self._pending['original_text'] = None
                        return True
                    return False

            _capture_filter = _HotkeyCaptureFilter(dlg, _pending_capture, self)
            dlg.installEventFilter(_capture_filter)

            hotkey_group.setLayout(hotkey_layout)
            layout.addWidget(hotkey_group)

            # Buttons
            button_layout = QHBoxLayout()
            save_btn = GlassButton("Save", reflection_radius=6.0, reflection_intensity=0.18)
            save_btn.setStyleSheet("QPushButton { background-color: rgba(47,47,53,180); color: white; border: none; border-radius: 0px; padding: 6px; } QPushButton:hover { background-color: rgba(67,67,73,200); }")
            cancel_btn = GlassButton("Cancel", reflection_radius=6.0, reflection_intensity=0.18)
            cancel_btn.setStyleSheet("QPushButton { background-color: rgba(47,47,53,180); color: white; border: none; border-radius: 0px; padding: 6px; } QPushButton:hover { background-color: rgba(67,67,73,200); }")
            reset_btn = GlassButton("Factory Reset", reflection_radius=6.0, reflection_intensity=0.18)
            reset_btn.setStyleSheet("QPushButton { background-color: rgba(255,68,68,180); color: white; border: none; border-radius: 0px; padding: 6px; } QPushButton:hover { background-color: rgba(255,100,100,200); }")
            button_layout.addWidget(save_btn)
            button_layout.addWidget(cancel_btn)
            button_layout.addWidget(reset_btn)
            layout.addLayout(button_layout)

            dlg.setLayout(layout)

            def save_settings():
                self._playback_mode = mode_group.checkedId()
                self._custom_font_enabled = font_checkbox.isChecked()
                self._reflections_enabled = reflections_checkbox.isChecked()
                old_vol_sync = getattr(self, '_volume_sync_system', True)
                self._volume_sync_system = volume_sync_checkbox.isChecked()
                if old_vol_sync != self._volume_sync_system:
                    if self._volume_sync_system:
                        self._init_system_volume_sync()
                    else:
                        self._system_volume_linked = False
                        try:
                            t = getattr(self, '_system_volume_poll_timer', None)
                            if t is not None:
                                t.stop()
                        except Exception:
                            pass
                        self._apply_playback_volume()
                
                # Get HSV values from sliders
                new_hue = hue_slider.value()
                new_saturation = saturation_slider.value()
                new_value = value_slider.value()
                
                # Save default HSV values for future songs
                self._default_hue = new_hue
                self._default_saturation = new_saturation
                self._default_value = new_value
                
                
                # Apply color to current song if one exists
                if current_file_path:
                    try:
                        # Convert HSV to QColor
                        from PyQt6.QtGui import QColor
                        color = QColor.fromHsv(new_hue, int(new_saturation * 255 / 100), int(new_value * 255 / 100))
                        self._set_theme_color_for_song(current_file_path, color)
                    except Exception as e:
                        pass
                else:
                    pass
                
                self._save_settings()
                
                # Apply hotkey changes: update the global hotkey dict and restart the listener
                self._global_hotkeys['toggle']['vk'] = self._hotkey_toggle_vk
                self._global_hotkeys['drag']['vk'] = self._hotkey_drag_vk
                self._global_hotkeys['next']['vk'] = self._hotkey_next_vk
                self._global_hotkeys['prev']['vk'] = self._hotkey_prev_vk
                try:
                    self._stop_global_hotkey_listener()
                    self._start_global_hotkey_listener()
                except Exception:
                    pass
                
                # Apply font setting immediately
                self._apply_font_setting()
                
                # Force repaint so reflection toggle takes effect immediately
                self.update()
                
                dlg.close()

            def cancel_settings():
                dlg.close()

            def factory_reset():
                """Show confirmation dialog and perform factory reset"""
                try:
                    # Create confirmation dialog
                    confirm_dlg = QDialog(self)
                    confirm_dlg.setWindowTitle("Factory Reset Confirmation")
                    confirm_dlg.setModal(True)
                    confirm_dlg.setFixedSize(400, 200)
                    
                    confirm_layout = QVBoxLayout()
                    
                    # Warning message
                    warning_label = QLabel("Are you sure?")
                    warning_label.setStyleSheet("color: #ff4444; font-weight: bold;")
                    warning_label.setWordWrap(True)
                    confirm_layout.addWidget(warning_label)
                    
                    # Buttons
                    button_layout = QHBoxLayout()
                    confirm_btn = QPushButton("Reset Everything")
                    confirm_btn.setStyleSheet("QPushButton { background-color: #ff4444; color: white; font-weight: bold; }")
                    cancel_reset_btn = QPushButton("Cancel")
                    
                    button_layout.addWidget(cancel_reset_btn)
                    button_layout.addWidget(confirm_btn)
                    confirm_layout.addLayout(button_layout)
                    
                    confirm_dlg.setLayout(confirm_layout)
                    
                    def do_reset():
                        try:
                            # Delete settings file
                            import os
                            settings_file = get_config_path()
                            if os.path.exists(settings_file):
                                os.remove(settings_file)
                            
                            # Delete playlist file
                            playlist_file = resource_path('playlist.json')
                            if os.path.exists(playlist_file):
                                os.remove(playlist_file)
                            
                            # Clear current playlist
                            self.playlist.clear()
                            self.list_widget.clear()
                            self.current_index = -1
                            
                            # Reset all settings to defaults
                            self._playback_mode = 0  # Stop mode
                            self._custom_font_enabled = False  # Default to system font
                            self._reflections_enabled = True
                            self._delete_dont_ask_again = False
                            self._default_hue = 200
                            self._default_saturation = 70
                            self._default_value = 80
                            self._tutorial_completed = False  # Reset tutorial status
                            # Clear custom covers and delete stored files
                            try:
                                covers_dict = getattr(self, '_custom_covers', {})
                                for _p, _img in list(covers_dict.items()):
                                    try:
                                        if isinstance(_img, str) and os.path.exists(_img):
                                            os.remove(_img)
                                    except Exception:
                                        pass
                                self._custom_covers = {}
                                self._cover_art_cache = {}
                            except Exception:
                                self._custom_covers = {}
                                self._cover_art_cache = {}
                            # Reset hotkeys to defaults
                            self._hotkey_toggle_vk = 0x78
                            self._hotkey_drag_vk = 0x79
                            self._hotkey_next_vk = 0x21
                            self._hotkey_prev_vk = 0x22
                            self._global_hotkeys['toggle']['vk'] = 0x78
                            self._global_hotkeys['drag']['vk'] = 0x79
                            self._global_hotkeys['next']['vk'] = 0x21
                            self._global_hotkeys['prev']['vk'] = 0x22
                            try:
                                self._stop_global_hotkey_listener()
                                self._start_global_hotkey_listener()
                            except Exception:
                                pass
                            
                            # Save the reset state to prevent old settings from loading on restart
                            self._save_settings()
                            
                            # Apply default font
                            self._apply_font_setting()
                            
                            # Reset UI elements
                            try:
                                self._set_song_text_with_font("No song.")
                                self.cover.set_cover(None)
                                self.btn_play.set_shape("play")
                            except Exception as e:
                                pass
                            
                            
                        except Exception as e:
                            pass
                        
                        confirm_dlg.close()
                        dlg.close()
                    
                    def cancel_reset():
                        confirm_dlg.close()
                    
                    confirm_btn.clicked.connect(do_reset)
                    cancel_reset_btn.clicked.connect(cancel_reset)
                    
                    confirm_dlg.show()
                    
                except Exception as e:
                    pass

            save_btn.clicked.connect(save_settings)
            cancel_btn.clicked.connect(cancel_settings)
            reset_btn.clicked.connect(factory_reset)

            dlg.show()
        except Exception as e:
            print(f"Error opening settings: {e}")

    def _apply_font_setting(self):
        """Apply font setting to song label while preserving text color"""
        try:
            current_font_enabled = getattr(self, '_custom_font_enabled', False)
            
            # Get current text color to preserve it
            current_style = self.song_label.styleSheet()
            current_color = "white"  # Default fallback
            try:
                import re
                color_match = re.search(r'color:\s*([^;]+)', current_style)
                if color_match:
                    current_color = color_match.group(1).strip()
            except Exception:
                pass
            
            if current_font_enabled:
                font_path = resource_path("island.ttf")
                if os.path.exists(font_path):
                    font_id = QFontDatabase.addApplicationFont(font_path)
                    if font_id != -1:
                        font_families = QFontDatabase.applicationFontFamilies(font_id)
                        if font_families:
                            font_family = font_families[0]
                            self._font_family = font_family
                            # Apply font with preserved color
                            self.song_label.setStyleSheet(f"font-family: '{font_family}'; font-size: 23px; color: {current_color};")
                        else:
                            # Apply default font with preserved color
                            self.song_label.setStyleSheet(f"font-size: 23px; color: {current_color};")
                    else:
                        # Apply default font with preserved color
                        self.song_label.setStyleSheet(f"font-size: 23px; color: {current_color};")
                else:
                    # Apply default font with preserved color
                    self.song_label.setStyleSheet(f"font-size: 23px; color: {current_color};")
            else:
                # Use default font with preserved color
                self.song_label.setStyleSheet(f"font-size: 23px; color: {current_color};")
        except Exception as e:
            # Fallback - preserve color even on error
            try:
                current_style = self.song_label.styleSheet()
                import re
                color_match = re.search(r'color:\s*([^;]+)', current_style)
                if color_match:
                    current_color = color_match.group(1).strip()
                    self.song_label.setStyleSheet(f"font-size: 23px; color: {current_color};")
                else:
                    self.song_label.setStyleSheet("font-size: 23px;")
            except Exception:
                self.song_label.setStyleSheet("font-size: 23px;")

    def _create_smooth_animation(self, target, property_name, duration=300, easing=None):
        """Create a smooth property animation with default settings"""
        try:
            from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
            anim = QPropertyAnimation(target, property_name.encode())
            anim.setDuration(duration)
            if easing is None:
                try:
                    anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
                except Exception:
                    pass
            else:
                try:
                    anim.setEasingCurve(easing)
                except Exception:
                    pass
            return anim
        except Exception:
            return None

    def _animate_color_transition(self, target, start_color, end_color, duration=300):
        """Animate a color transition smoothly"""
        try:
            from PyQt6.QtCore import QPropertyAnimation, QVariantAnimation
            anim = QVariantAnimation()
            anim.setDuration(duration)
            anim.setStartValue(start_color)
            anim.setEndValue(end_color)
            
            def update_color(value):
                try:
                    if hasattr(target, 'setStyleSheet'):
                        # For widgets with stylesheets
                        if hasattr(target, '_base_stylesheet'):
                            # Update color in existing stylesheet
                            sheet = target._base_stylesheet
                            # This is a simplified approach - you may need to customize for specific widgets
                            target.setStyleSheet(sheet.replace('{color}', value.name()))
                except Exception:
                    pass
            
            anim.valueChanged.connect(update_color)
            anim.start()
            return anim
        except Exception:
            return None

    def _set_song_text_with_font(self, text):
        """Set song label text with proper font styling"""
        try:
            # Ensure font settings are loaded with correct defaults
            if not hasattr(self, '_custom_font_enabled'):
                self._custom_font_enabled = False  # Default to False, not True
            if not hasattr(self, '_font_family'):
                self._custom_font_enabled = False
            
            current_font_enabled = getattr(self, '_custom_font_enabled', False)
            current_theme_color = getattr(self, '_theme_color', QColor('#1f1f23'))
            # Use gradient-aware text color calculation
            text_color = self._calculate_text_color_for_gradient(current_theme_color)
            
            if current_font_enabled and hasattr(self, '_font_family'):
                stylesheet = f"font-family: '{self._font_family}'; font-size: 23px; color: {text_color};"
            else:
                stylesheet = f"font-size: 23px; color: {text_color};"
            
            self.song_label.setStyleSheet(stylesheet)
            self.song_label.setText(text)
        except Exception as e:
            # Fallback - set text without styling
            try:
                self.song_label.setText(text)
            except Exception:
                pass

    def _refresh_all_marquee_labels(self):
        try:
            if hasattr(self, 'song_label') and self.song_label is not None:
                self.song_label._update_timer()
        except Exception:
            pass
        try:
            if hasattr(self, 'list_widget') and self.list_widget is not None:
                for i in range(self.list_widget.count()):
                    try:
                        item = self.list_widget.item(i)
                        widget = self.list_widget.itemWidget(item)
                        label = getattr(widget, 'label', None)
                        if label is not None:
                            label._update_timer()
                    except Exception:
                        pass
        except Exception:
            pass

    def _get_display_name_for_file(self, file_path):
        """Get the custom display name for a file, or fallback to filename"""
        try:
            
            # First try to get the custom name from the playlist widget
            if hasattr(self, 'list_widget') and self.list_widget:
                for i in range(self.list_widget.count()):
                    item = self.list_widget.item(i)
                    if item:
                        try:
                            item_path = item.data(Qt.ItemDataRole.UserRole)
                            if item_path == file_path:
                                # Try to get custom display name
                                custom_name = item.data(Qt.ItemDataRole.UserRole + 1)
                                if custom_name:
                                    return custom_name
                                else:
                                    break
                        except Exception as e:
                            continue
            else:
                pass
            
            # Fallback to filename
            filename = os.path.splitext(os.path.basename(file_path))[0]
            return filename
        except Exception as e:
            return os.path.splitext(os.path.basename(file_path))[0]

    def _calculate_text_color(self, bg_color):
        """Calculate whether to use white or black text based on background brightness"""
        try:
            # Calculate relative luminance using the formula for sRGB
            r = bg_color.red() / 255.0
            g = bg_color.green() / 255.0
            b = bg_color.blue() / 255.0
            
            # Apply gamma correction
            r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
            g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
            b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
            
            # Calculate luminance
            luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
            
            # Use white text for dark backgrounds, black for light backgrounds
            # Threshold around 0.5 (50% luminance)
            return "white" if luminance < 0.5 else "black"
        except Exception:
            return "white"  # Default to white if calculation fails

    def _calculate_text_color_for_gradient(self, base_color):
        """Calculate text color based on the actual gradient appearance, not just base color"""
        try:
            # Convert base color to HSV to understand how gradient will affect it
            h = base_color.hueF()
            s = base_color.saturationF()
            v = base_color.valueF()
            
            # The gradient creates variations in value (brightness)
            # We need to consider the brightest and darkest parts of the gradient
            
            # Typical gradient value range: from base_value * 0.3 to base_value * 1.3
            # But let's be more conservative and consider realistic ranges
            min_value = max(0.1, v * 0.4)   # Darkest part of gradient
            max_value = min(1.0, v * 1.2)   # Brightest part of gradient
            
            # Calculate luminance for both extremes
            def hsv_to_luminance(h, s, v):
                # Convert HSV to RGB
                c = v * s
                x = c * (1 - abs((h / 60) % 2 - 1))
                m = v - c
                
                if h < 60:
                    r, g, b = c, x, 0
                elif h < 120:
                    r, g, b = x, c, 0
                elif h < 180:
                    r, g, b = 0, c, x
                elif h < 240:
                    r, g, b = 0, x, c
                elif h < 300:
                    r, g, b = x, 0, c
                else:
                    r, g, b = c, 0, x
                
                r, g, b = r + m, g + m, b + m
                
                # Apply gamma correction
                r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
                g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
                b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
                
                # Calculate luminance
                return 0.2126 * r + 0.7152 * g + 0.0722 * b
            
            min_luminance = hsv_to_luminance(h, s, min_value)
            max_luminance = hsv_to_luminance(h, s, max_value)
            avg_luminance = (min_luminance + max_luminance) / 2
            
            # If the gradient has very bright parts, use black text
            # If the gradient is mostly dark, use white text
            # We're more conservative about using black text since bright gradients are more problematic
            text_color = "black" if max_luminance > 0.7 and avg_luminance > 0.4 else "white"
            
            
            return text_color
        except Exception as e:
            # Fallback to simple calculation
            return self._calculate_text_color(base_color)

    def _update_song_text_color(self, bg_color):
        """Update the song label text color based on background with smooth transition"""
        try:
            # Use gradient-aware text color calculation
            text_color = self._calculate_text_color_for_gradient(bg_color)
            # Get the actual font setting, not a default
            current_font_enabled = getattr(self, '_custom_font_enabled', False)
            
            # Get current color for smooth transition
            current_style = self.song_label.styleSheet()
            current_color = "white"  # Default fallback
            
            try:
                # Extract current color from stylesheet
                import re
                color_match = re.search(r'color:\s*([^;]+)', current_style)
                if color_match:
                    current_color = color_match.group(1).strip()
            except Exception:
                pass
            
            # Create new stylesheet based on actual font setting
            if current_font_enabled and hasattr(self, '_font_family'):
                new_style = f"font-family: '{self._font_family}'; font-size: 23px; color: {text_color};"
            else:
                new_style = f"font-size: 23px; color: {text_color};"
            
            # Animate the color transition
            try:
                from PyQt6.QtGui import QColor
                start_qcolor = QColor(current_color) if current_color != "white" else QColor(255, 255, 255)
                end_qcolor = QColor(text_color) if text_color != "white" else QColor(255, 255, 255)
                
                self._animate_color_transition(self.song_label, start_qcolor, end_qcolor, 200)
            except Exception:
                pass
            
            # Apply the new style
            self.song_label.setStyleSheet(new_style)
        except Exception as e:
            pass

    def _hotkey_display_text(self):
        # Returns a string like 'F10', 'Ctrl+Alt+K', etc.
        setting = self._hotkey_setting
        if not setting:
            return 'F10'
        vk = setting.get('vk', 0x79)
        mod = setting.get('mod', 0)
        # Map vk to key name
        key_names = {
            0x70: 'F1', 0x71: 'F2', 0x72: 'F3', 0x73: 'F4', 0x74: 'F5', 0x75: 'F6',
            0x76: 'F7', 0x77: 'F8', 0x78: 'F9', 0x79: 'F10', 0x7A: 'F11', 0x7B: 'F12',
        }
        name = key_names.get(vk)
        if not name:
            if 0x41 <= vk <= 0x5A:
                name = chr(vk)
            else:
                name = f'VK_{vk:X}'
        mod_names = []
        if mod & 0x1:
            mod_names.append('Alt')
        if mod & 0x2:
            mod_names.append('Ctrl')
        if mod & 0x4:
            mod_names.append('Shift')
        if mod & 0x8:
            mod_names.append('Win')
        if mod_names:
            return '+'.join(mod_names) + '+' + name
        else:
            return name

    @staticmethod
    def _vk_to_name(vk):
        """Return a human-readable name for a Windows virtual-key code."""
        _names = {
            0x08: 'Backspace', 0x09: 'Tab', 0x0D: 'Enter', 0x1B: 'Escape',
            0x20: 'Space', 0x21: 'Page Up', 0x22: 'Page Down',
            0x23: 'End', 0x24: 'Home', 0x25: 'Left', 0x26: 'Up',
            0x27: 'Right', 0x28: 'Down', 0x2C: 'Print Screen',
            0x2D: 'Insert', 0x2E: 'Delete', 0x13: 'Pause',
            0x14: 'Caps Lock', 0x90: 'Num Lock', 0x91: 'Scroll Lock',
            0x70: 'F1', 0x71: 'F2', 0x72: 'F3', 0x73: 'F4',
            0x74: 'F5', 0x75: 'F6', 0x76: 'F7', 0x77: 'F8',
            0x78: 'F9', 0x79: 'F10', 0x7A: 'F11', 0x7B: 'F12',
            0xC0: '`', 0xBD: '-', 0xBB: '=', 0xDB: '[', 0xDD: ']',
            0xDC: '\\', 0xBA: ';', 0xDE: "'", 0xBC: ',', 0xBE: '.',
            0xBF: '/',
        }
        n = _names.get(vk)
        if n:
            return n
        if 0x41 <= vk <= 0x5A:
            return chr(vk)
        if 0x30 <= vk <= 0x39:
            return chr(vk)
        if 0x60 <= vk <= 0x69:
            return f'Num {vk - 0x60}'
        return f'Key 0x{vk:02X}'

    def _set_theme_color_for_song(self, file_path, color):
        if not isinstance(color, QColor):
            return
        self._theme_colors[file_path] = QColor(color)
        self._theme_color = QColor(color)
        
        # Update slider styles to match new theme color
        self._update_slider_styles()
        
        # Update song text color based on new theme color
        self._update_song_text_color(color)
        
        # update settings button color to match new theme
        try:
            try:
                tc = QColor(self._theme_color)
                theme_rgba = f"rgba({tc.red()},{tc.green()},{tc.blue()},128)"
                hover_rgba = f"rgba({min(255, tc.red()+20)},{min(255, tc.green()+20)},{min(255, tc.blue()+20)},160)"
            except Exception:
                theme_rgba = 'rgba(47,47,53,128)'
                hover_rgba = 'rgba(67,67,73,160)'

            if getattr(self, 'settings_btn', None) is not None:
                try:
                    self.settings_btn.setStyleSheet(
                        f"QPushButton{{background:{theme_rgba};border:none;border-radius:0px;color:white;}}"
                        f"QPushButton:hover{{background:{hover_rgba};}}"
                    )
                except Exception:
                    pass

            if getattr(self, 'drag_btn', None) is not None:
                try:
                    self.drag_btn.setStyleSheet(
                        f"QPushButton{{background:{theme_rgba};border:none;border-radius:0px;}}"
                        f"QPushButton:hover{{background:{hover_rgba};}}"
                    )
                except Exception:
                    pass
        except Exception:
            pass
        # update borders of UI elements to match theme color
        self._update_ui_borders()

    def _update_ui_borders(self):
        """Keep controls borderless so reflection highlights are the only edge accent."""
        try:
            try:
                theme_hex = self._theme_color.name()
                tc = QColor(self._theme_color)
                theme_rgba50 = f"rgba({tc.red()},{tc.green()},{tc.blue()},128)"
                theme_rgba_hover = f"rgba({tc.red()},{tc.green()},{tc.blue()},165)"
            except Exception:
                theme_hex = '#4a90e2'
                theme_rgba50 = 'rgba(74,144,226,128)'
                theme_rgba_hover = 'rgba(74,144,226,165)'

            for btn_name in ('btn_prev', 'btn_play', 'btn_next', 'btn_shuffle'):
                btn = getattr(self, btn_name, None)
                if btn is None:
                    continue
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(47, 47, 53, 128);
                        border-radius: 0px;
                        border: none;
                    }
                    QPushButton:hover {
                        background-color: rgba(68, 68, 68, 128);
                    }
                """)

            if hasattr(self, 'import_btn'):
                self.import_btn.setStyleSheet("""
                    QPushButton {
                        background: rgba(47, 47, 53, 128);
                        border: none;
                        border-radius: 0px;
                        padding: 8px;
                        color: white;
                        font-size: 14px;
                        text-align: left;
                    }
                    QPushButton:hover {
                        background: rgba(67, 67, 73, 128);
                        border: none;
                    }
                    QPushButton:pressed {
                        background: rgba(37, 37, 43, 128);
                        border: none;
                    }
                """)

            if hasattr(self, 'drag_btn'):
                self.drag_btn.setStyleSheet(
                    f"QPushButton{{background:{theme_rgba50};border:none;border-radius:0px;}}"
                    f"QPushButton:hover{{background:{theme_rgba_hover};}}"
                )

            if hasattr(self, 'settings_btn'):
                self.settings_btn.setStyleSheet(
                    f"QPushButton{{background:{theme_rgba50};border:none;border-radius:0px;color:white;}}"
                    f"QPushButton:hover{{background:{theme_rgba_hover};}}"
                )

            if hasattr(self, 'list_widget'):
                sheet = """
                    QListWidget {
                        background: rgba(47, 47, 53, 128);
                        border: none;
                        border-radius: 0px;
                        padding: 0px;
                        font-size: 14px;
                    }
                    QListWidget::item {
                        padding: 2px;
                        border-bottom: 1px solid rgba(255, 255, 255, 10);
                        min-height: 20px;
                    }
                    QListWidget::item:selected {
                        background: rgba(255, 255, 255, 20);
                    }
                    QScrollBar:vertical {
                        background: rgba(255,255,255,10);
                        width: 12px;
                        margin: 2px;
                        border: none;
                    }
                    QScrollBar::handle:vertical {
                        background: {theme_rgba50};
                        min-height: 24px;
                        border-radius: 0px;
                    }
                    QScrollBar::handle:vertical:hover {
                        background: {theme_rgba_hover};
                        border: 2px solid rgba(255,255,255,40);
                    }
                    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                        height: 0px;
                        border: none;
                        background: transparent;
                    }
                    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                        background: transparent;
                    }
                    QScrollBar:horizontal {
                        background: rgba(255,255,255,10);
                        height: 12px;
                        margin: 2px;
                        border: none;
                    }
                    QScrollBar::handle:horizontal {
                        background: {theme_rgba50};
                        min-width: 24px;
                        border-radius: 0px;
                    }
                    QScrollBar::handle:horizontal:hover {
                        background: {theme_rgba_hover};
                        border: 2px solid rgba(255,255,255,40);
                    }
                    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                        width: 0px;
                        border: none;
                        background: transparent;
                    }
                    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                        background: transparent;
                    }
                """
                self.list_widget.setStyleSheet(
                    sheet.replace('{theme_hex}', theme_hex)
                         .replace('{theme_rgba50}', theme_rgba50)
                         .replace('{theme_rgba_hover}', theme_rgba_hover)
                )
        except Exception:
            pass

    def _ensure_theme_color_for_song(self, file_path):
        if file_path in self._theme_colors:
            self._theme_color = QColor(self._theme_colors[file_path])
            self.update()
            try:
                self._update_slider_styles()
            except Exception:
                pass
            return

        hue = random.random()
        # ensure generated random theme colors have saturation=42 and luminance ~26 (out of 255)
        sat = 42.0 / 255.0
        lightness = 26.0 / 255.0
        c = QColor.fromHslF(hue, sat, lightness)
        self._set_theme_color_for_song(file_path, c)

    # ---------- Cover ----------
    def _cover_cache_signature(self, file_path):
        try:
            custom_path = getattr(self, '_custom_covers', {}).get(file_path)
            if custom_path and isinstance(custom_path, str) and os.path.exists(custom_path):
                try:
                    stamp = os.path.getmtime(custom_path)
                except Exception:
                    stamp = 0.0
                return ('custom', custom_path, stamp)
        except Exception:
            pass
        try:
            stamp = os.path.getmtime(file_path)
        except Exception:
            stamp = 0.0
        return ('track', file_path, stamp)

    def _crop_cover_square(self, pixmap):
        try:
            if not isinstance(pixmap, QPixmap) or pixmap.isNull():
                return None
            w = pixmap.width()
            h = pixmap.height()
            if w <= 0 or h <= 0:
                return None
            if w > h:
                side = h
                x = max(0, (w - side) // 2)
                return pixmap.copy(x, 0, side, side)
            return pixmap
        except Exception:
            return None

    def _extract_cover_art_pixmap(self, file_path):
        # Check for user-uploaded custom cover first.
        try:
            custom_path = getattr(self, '_custom_covers', {}).get(file_path)
            if custom_path and isinstance(custom_path, str) and os.path.exists(custom_path):
                pm = self._crop_cover_square(QPixmap(custom_path))
                if pm is not None:
                    return pm
        except Exception:
            pass

        try:
            tags = ID3(file_path)
            for tag in tags.values():
                if isinstance(tag, APIC):
                    pix = QPixmap()
                    pix.loadFromData(tag.data)
                    pm = self._crop_cover_square(pix)
                    if pm is not None:
                        return pm
                    break

            d = os.path.dirname(file_path) or '.'
            base = os.path.splitext(os.path.basename(file_path))[0]
            candidates = [base + ext for ext in ('.jpg', '.png', '.jpeg')]
            for candidate in candidates:
                fn = os.path.join(d, candidate)
                if os.path.exists(fn):
                    pm = self._crop_cover_square(QPixmap(fn))
                    if pm is not None:
                        return pm
        except Exception:
            pass
        return None

    def load_cover_art(self, file_path):
        cover_pix = None
        try:
            sig = self._cover_cache_signature(file_path)
            cached = getattr(self, '_cover_art_cache', {}).get(file_path)
            if isinstance(cached, tuple) and len(cached) == 2 and cached[0] == sig:
                cover_pix = cached[1]
            else:
                cover_pix = self._extract_cover_art_pixmap(file_path)
                self._cover_art_cache[file_path] = (sig, cover_pix)
        except Exception:
            cover_pix = None

        if cover_pix is not None:
            self.cover.set_cover(cover_pix)
            try:
                if hasattr(self, 'bottom_widget') and self.bottom_widget is not None:
                    self.bottom_widget.update()
            except Exception:
                pass

            if file_path in self._theme_colors:
                self._set_theme_color_for_song(file_path, self._theme_colors[file_path])
            else:
                try:
                    img = cover_pix.toImage()
                    w2 = img.width()
                    h2 = img.height()
                    cx = max(0, min(w2 - 1, w2 // 2))
                    cy = max(0, min(h2 - 1, h2 // 2))
                    dx = int(w2 * 0.35)
                    dy = int(h2 * 0.35)
                    samples = [
                        img.pixelColor(max(0, min(w2 - 1, cx - dx)), max(0, min(h2 - 1, cy - dy))),
                        img.pixelColor(max(0, min(w2 - 1, cx + dx)), max(0, min(h2 - 1, cy - dy))),
                        img.pixelColor(max(0, min(w2 - 1, cx - dx)), max(0, min(h2 - 1, cy + dy))),
                        img.pixelColor(max(0, min(w2 - 1, cx + dx)), max(0, min(h2 - 1, cy + dy))),
                    ]
                    r = sum(c.red() for c in samples) // 4
                    g = sum(c.green() for c in samples) // 4
                    b = sum(c.blue() for c in samples) // 4
                    self._set_theme_color_for_song(file_path, QColor(r, g, b))
                except Exception:
                    self._ensure_theme_color_for_song(file_path)
            return

        # nothing found — clear cover and fall back to theme gradient
        self.cover.set_cover(None)
        try:
            if hasattr(self, 'bottom_widget') and self.bottom_widget is not None:
                # clear any cached blurred pixmap so stale imagery doesn't appear
                try:
                    if hasattr(self.bottom_widget, '_cache'):
                        self.bottom_widget._cache['pixmap'] = None
                        self.bottom_widget._cache['blurred'] = None
                        self.bottom_widget._cache['size'] = None
                except Exception:
                    pass
                self.bottom_widget.update()
        except Exception:
            pass
        self._ensure_theme_color_for_song(file_path)

    # ---------- Playback helpers (restored simplified implementations) ----------
    def play_selected(self, item):
        self.play_index(self.list_widget.row(item))

    def play_index(self, index):
        if index < 0 or index >= len(self.playlist):
            return
        # Debounce rapid play_index calls to prevent resource exhaustion
        import time as _time
        now = _time.monotonic()
        if now - getattr(self, '_last_play_index_time', 0) < 0.15 and index == getattr(self, '_last_play_index_req', -1):
            return
        self._last_play_index_time = now
        self._last_play_index_req = index
        file_path = self.playlist[index]
        
        # record current index so other UI code knows which track is active
        try:
            self.current_index = index
        except Exception:
            pass
        try:
            self._refresh_all_marquee_labels()
        except Exception:
            pass
            
        # try to read duration from file metadata so UI updates immediately for files without quick media signals
        dur_ms = 0
        try:
            try:
                from mutagen.mp3 import MP3
                info = MP3(file_path).info
                dur_ms = int(getattr(info, 'length', 0) * 1000)
            except Exception:
                from mutagen import File as MutagenFile
                f = MutagenFile(file_path)
                dur_ms = int(getattr(getattr(f, 'info', None), 'length', 0) * 1000) if f is not None else 0
        except Exception:
            dur_ms = 0

        # Reset duration and seek bar before loading new song
        self._duration_ms = 0
        try:
            self.seek_slider.setRange(0, 0)
            self.time_left.setText("0:00")
            self.time_right.setText("0:00")
        except Exception:
            pass

        # Restore duration from file metadata if we read it
        try:
            if dur_ms and dur_ms > 0:
                try:
                    self._on_duration_changed(dur_ms)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            # initiate crossfade if currently playing, otherwise switch immediately
            self._start_crossfade(file_path, index)
        except Exception as e:
            try:
                self.player.setSource(QUrl.fromLocalFile(file_path))
                self.player.play()
            except Exception as e2:
                pass

        try:
            self._fade_in_song_ui()
            # song label and cover will be updated when crossfade finishes; set label now
            try:
                self._set_song_text_with_font(self._get_display_name_for_file(file_path))
            except Exception:
                pass

            # Load the target cover after the song UI reset so it is not hidden at 0 opacity.
            if not getattr(self, '_crossfade_timer', None):
                try:
                    self.load_cover_art(file_path)
                    self._fade_in_cover()
                except Exception:
                    pass
            else:
                try:
                    self.load_cover_art(file_path)
                    self.cover_opacity.setOpacity(1.0)
                except Exception:
                    pass
        except Exception:
            pass

    def toggle_play(self):
        try:
            if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.player.pause()
            else:
                if self.current_index == -1 and self.playlist:
                    self.play_index(0)
                elif self.current_index >= 0 and self.current_index < len(self.playlist):
                    # After EndOfMedia, Qt6 needs a source reset to play again
                    try:
                        ms = self.player.mediaStatus()
                    except Exception:
                        ms = None
                    if ms == QMediaPlayer.MediaStatus.EndOfMedia or ms == QMediaPlayer.MediaStatus.NoMedia:
                        self.play_index(self.current_index)
                    else:
                        self.player.play()
                else:
                    self.player.play()
        except Exception:
            pass

    def next_track(self):
        if self.playlist:
            self.play_index((self.current_index + 1) % len(self.playlist))

    def prev_track(self):
        if self.playlist:
            self.play_index((self.current_index - 1) % len(self.playlist))

    def _start_crossfade(self, file_path: str, target_index: int):
        try:
            # if nothing is currently playing, just switch immediately
            try:
                playing = (self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
            except Exception:
                playing = False

            target_vol = self._playback_target_volume()

            if not playing or getattr(self, 'current_index', -1) == -1:
                try:
                    # immediate switch — stop and clear source to reset Qt6 EndOfMedia state
                    self.player.stop()
                    self.player.setSource(QUrl())
                    self.player.setSource(QUrl.fromLocalFile(file_path))
                    self.player.play()
                    try:
                        self.audio.setVolume(target_vol)
                    except Exception:
                        pass
                    self.current_index = target_index
                    try:
                        self._set_song_text_with_font(self._get_display_name_for_file(file_path))
                        self.load_cover_art(file_path)
                    except Exception:
                        pass
                    # Force button to pause since we just started playback
                    try:
                        self.btn_play.set_shape("pause")
                    except Exception:
                        pass
                except Exception:
                    pass
                return

            # if a crossfade is already running, finish it first
            if getattr(self, '_crossfade_timer', None) is not None:
                try:
                    self._finish_crossfade(self._crossfade_target_index)
                except Exception:
                    pass

            import time
            # prepare new player/audio
            new_audio = QAudioOutput()
            new_player = QMediaPlayer()
            new_player.setAudioOutput(new_audio)
            try:
                new_audio.setVolume(0.0)
            except Exception:
                pass
            try:
                new_player.setSource(QUrl.fromLocalFile(file_path))
            except Exception:
                pass
            # start playback of incoming track muted
            try:
                new_player.play()
            except Exception:
                pass

            # attach probe to new player if available
            try:
                if hasattr(self, '_attach_probe'):
                    try:
                        self._attach_probe(new_player)
                    except Exception:
                        pass
            except Exception:
                pass

            # store crossfade state
            self._crossfade_from_player = self.player
            self._crossfade_from_audio = self.audio
            self._crossfade_to_player = new_player
            self._crossfade_to_audio = new_audio
            self._crossfade_start_time = time.time()
            self._crossfade_target_index = target_index
            self._crossfade_duration_ms = 500

            # start timer to update volumes
            try:
                from PyQt6.QtCore import QTimer
                timer = QTimer(self)
                timer.setInterval(16)
                timer.timeout.connect(self._update_crossfade)
                timer.start()
                self._crossfade_timer = timer
            except Exception:
                # fallback: immediate finish
                try:
                    self._finish_crossfade(target_index)
                except Exception:
                    pass
        except Exception as e:
            pass

    def _update_crossfade(self):
        try:
            import time
            if not getattr(self, '_crossfade_timer', None):
                return
            start = getattr(self, '_crossfade_start_time', None)
            if start is None:
                return
            elapsed = (time.time() - start) * 1000.0
            dur = max(1.0, float(getattr(self, '_crossfade_duration_ms', 500)))
            t = min(1.0, elapsed / dur)

            from_audio = getattr(self, '_crossfade_from_audio', None)
            to_audio = getattr(self, '_crossfade_to_audio', None)
            if from_audio is not None:
                try:
                    start_vol = getattr(self, '_crossfade_from_start_vol', None)
                    if start_vol is None:
                        start_vol = from_audio.volume()
                        self._crossfade_from_start_vol = start_vol
                    from_audio.setVolume(max(0.0, start_vol * (1.0 - t)))
                except Exception:
                    pass
            if to_audio is not None:
                try:
                    to_audio.setVolume(max(0.0, self._playback_target_volume() * t))
                except Exception:
                    pass

            if t >= 1.0:
                try:
                    self._finish_crossfade(self._crossfade_target_index)
                except Exception:
                    pass
        except Exception as e:
            pass

    def _finish_crossfade(self, target_index: int):
        try:
            # stop timer
            try:
                if getattr(self, '_crossfade_timer', None) is not None:
                    try:
                        self._crossfade_timer.stop()
                    except Exception:
                        pass
                self._crossfade_timer = None
            except Exception:
                pass

            from_player = getattr(self, '_crossfade_from_player', None)
            from_audio = getattr(self, '_crossfade_from_audio', None)
            to_player = getattr(self, '_crossfade_to_player', None)
            to_audio = getattr(self, '_crossfade_to_audio', None)

            target_vol = self._playback_target_volume()

            # ensure final volumes
            try:
                if from_audio is not None:
                    from_audio.setVolume(0.0)
            except Exception:
                pass
            try:
                if to_audio is not None:
                    to_audio.setVolume(target_vol)
            except Exception:
                pass

            # stop and cleanup old player
            try:
                if from_player is not None and from_player is not to_player:
                    try:
                        from_player.stop()
                    except Exception:
                        pass
                    try:
                        from_player.setSource(QUrl())
                    except Exception:
                        pass
                    try:
                        from_player.deleteLater()
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                if from_audio is not None and from_audio is not to_audio:
                    try:
                        from_audio.deleteLater()
                    except Exception:
                        pass
            except Exception:
                pass

            # adopt new player as main
            try:
                if to_player is not None:
                    # disconnect old signals
                    try:
                        getattr(self, 'player', None).durationChanged.disconnect(self._on_duration_changed)
                    except Exception:
                        pass
                    try:
                        getattr(self, 'player', None).positionChanged.disconnect(self._on_position_changed)
                    except Exception:
                        pass
                    try:
                        getattr(self, 'player', None).mediaStatusChanged.disconnect(self._on_media_status_changed)
                    except Exception:
                        pass
                    try:
                        getattr(self, 'player', None).playbackStateChanged.disconnect(self._on_playback_state_changed)
                    except Exception:
                        pass

                    self.player = to_player
                    self.audio = to_audio
                    self.audio_output = to_audio

                    try:
                        self.player.durationChanged.connect(self._on_duration_changed)
                    except Exception:
                        pass
                    try:
                        # refresh UI immediately in case the incoming player already has duration available
                        dur = getattr(self.player, 'duration', None)
                        if callable(dur):
                            try:
                                self._on_duration_changed(self.player.duration())
                            except Exception:
                                pass
                        else:
                            try:
                                self._on_duration_changed(int(getattr(self.player, 'duration', 0) or 0))
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        self.player.positionChanged.connect(self._on_position_changed)
                    except Exception:
                        pass
                    try:
                        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
                    except Exception:
                        pass
                    try:
                        self.player.playbackStateChanged.connect(self._on_playback_state_changed)
                    except Exception:
                        pass
                    # The new player is already in PlayingState so
                    # playbackStateChanged won't re-fire.  Force the button.
                    try:
                        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                            self.btn_play.set_shape("pause")
                    except Exception:
                        pass

            except Exception:
                pass

            # reset crossfade fields
            self._crossfade_from_player = None
            self._crossfade_from_audio = None
            self._crossfade_to_player = None
            self._crossfade_to_audio = None
            self._crossfade_start_time = None
            self._crossfade_from_start_vol = None
            self._crossfade_target_index = None

            # finalize index and UI
            try:
                if isinstance(target_index, int) and 0 <= target_index < len(self.playlist):
                    self.current_index = target_index
                    fp = self.playlist[target_index]
                    try:
                        self._set_song_text_with_font(self._get_display_name_for_file(fp))
                    except Exception:
                        pass
                    try:
                        if not getattr(self.cover, 'cover_pixmap', None):
                            self.load_cover_art(fp)
                        self.cover_opacity.setOpacity(1.0)
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception as e:
            pass

    def _on_duration_changed(self, dur: int):
        self._duration_ms = dur
        try:
            # QMediaPlayer duration is in milliseconds, but the seek bar should use seconds for long tracks
            seconds = max(0, int(dur / 1000))
            self.seek_slider.setRange(0, seconds)
            self.time_right.setText(self._format_time(dur))
        except Exception:
            pass

    def _on_position_changed(self, pos: int):

        # Convert position from ms to seconds for the slider
        seconds = int(pos / 1000)
        if not self._seeking:
            try:
                self.seek_slider.setValue(seconds)
            except Exception:
                pass

        left_text = self._format_time(pos)
        if self._time_left_mode and self._duration_ms:
            left_text = "-" + self._format_time(self._duration_ms - pos)

        try:
            self.time_left.setText(left_text)
            if self._duration_ms:
                self.time_right.setText(self._format_time(self._duration_ms))
        except Exception:
            pass

        # ── Primary end-of-track detection ──
        # positionChanged is the most reliable signal on Qt6/Windows.
        # When position reaches within 500 ms of duration (or overshoots),
        # trigger loop/playlist handling immediately.  Stop-mode (0) is
        # left alone so the player finishes naturally.
        try:
            dur = self._duration_ms
            if dur > 0 and pos >= dur - 500:
                self._near_track_end = True
                if getattr(self, '_playback_mode', 0) != 0:
                    self._handle_end_of_track()
            else:
                self._near_track_end = False
                # Re-arm end-of-track detection once we see a position
                # that is clearly NOT near the end.  This avoids re-arming
                # in PlayingState where a stale near-end positionChanged
                # from the old source could immediately re-trigger (loop bug).
                if dur > 0 and pos < dur - 2000:
                    self._end_of_track_handled = False
        except Exception:
            pass

    def _handle_end_of_track(self):
        """Shared handler for end-of-track (called from EndOfMedia or StoppedState backup)."""
        if getattr(self, '_end_of_track_handled', False):
            return
        self._end_of_track_handled = True
        playback_mode = getattr(self, '_playback_mode', 0)
        if playback_mode == 1:  # Loop
            idx = getattr(self, 'current_index', -1)
            if 0 <= idx < len(self.playlist):
                QTimer.singleShot(100, lambda i=idx: self.play_index(i))
            else:
                pass
        elif playback_mode == 2:  # Playlist
            if self.playlist:
                ni = (getattr(self, 'current_index', 0) + 1) % len(self.playlist)
                QTimer.singleShot(100, lambda i=ni: self.play_index(i))
            else:
                pass
        else:
            pass

    def _on_audio_outputs_changed(self):
        """Switch all active QAudioOutput instances to the new default device."""
        try:
            new_dev = QMediaDevices.defaultAudioOutput()
            if not new_dev.isNull():
                try:
                    self.audio.setDevice(new_dev)
                except Exception:
                    pass
                # Also update the crossfade player if one exists
                try:
                    xf_audio = getattr(self, '_crossfade_to_audio', None)
                    if xf_audio is not None:
                        xf_audio.setDevice(new_dev)
                except Exception:
                    pass
                # Re-acquire the system volume endpoint for the new device
                try:
                    if getattr(self, '_system_volume_linked', False) and SystemVolumeController is not None:
                        ctl = SystemVolumeController()
                        if ctl.available():
                            self._system_volume_controller = ctl
                except Exception:
                    pass
        except Exception:
            pass

    def _on_media_status_changed(self, status):
        try:
            if status == QMediaPlayer.MediaStatus.EndOfMedia:
                self._handle_end_of_track()
        except Exception as e:
            pass

    def _on_playback_state_changed(self, state):
        """Single source of truth for play/pause icon — always matches actual player state."""
        try:
            if state == QMediaPlayer.PlaybackState.PlayingState:
                self.btn_play.set_shape("pause")
            else:
                self.btn_play.set_shape("play")
        except Exception:
            pass
        # Also refresh hover play icon on the cover widget
        try:
            if hasattr(self, 'cover'):
                self.cover._refresh_hover_play_icon()
        except Exception:
            pass
        # Refresh slider colors (gray when idle, themed when playing)
        try:
            self._update_slider_styles()
        except Exception:
            pass
        try:
            self._refresh_all_marquee_labels()
        except Exception:
            pass
        # Backup end-of-track detection: when the player reaches
        # StoppedState and _near_track_end was set by positionChanged,
        # handle end-of-track even if EndOfMedia never fired.
        try:
            if state == QMediaPlayer.PlaybackState.StoppedState:
                if getattr(self, '_near_track_end', False):
                    self._near_track_end = False
                    self._handle_end_of_track()
        except Exception:
            pass

    def _on_seek_pressed(self):
        self._seeking = True

    def _on_seek_released(self):
        self._seeking = False
        try:
            # Convert slider value (seconds) to milliseconds for player
            slider_seconds = self.seek_slider.value()
            player_ms = slider_seconds * 1000
            self.player.setPosition(player_ms)
        except Exception as e:
            pass

    def _on_seek_moved(self, v: int):
        # Update time display while seeking, but don't update player position yet
        try:
            left_text = self._format_time(v * 1000)
            if self._time_left_mode and self._duration_ms:
                left_text = "-" + self._format_time(self._duration_ms - (v * 1000))
            self.time_left.setText(left_text)
        except Exception:
            pass

    def _animate_to_size(self, w: int, h: int, lock_fixed: bool = False):
        start = self.geometry()
        end = self.geometry()
        end.setWidth(w)
        end.setHeight(h)

        if self._mode_anim is not None:
            try:
                self._mode_anim.stop()
            except Exception:
                pass

        self._mode_anim = QPropertyAnimation(self, b"geometry")
        self._mode_anim.setDuration(220)
        # set easing curve using QEasingCurve instance to satisfy PyQt6
        try:
            self._mode_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type.OutCubic))
        except Exception:
            try:
                self._mode_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            except Exception:
                pass
        self._mode_anim.setStartValue(start)
        self._mode_anim.setEndValue(end)

        if lock_fixed:
            def _lock():
                try:
                    self.setFixedSize(w, h)
                except Exception:
                    pass
            try:
                self._mode_anim.finished.connect(_lock)
            except Exception:
                pass
        else:
            try:
                self.setMinimumSize(0, 0)
                self.setMaximumSize(9999, 9999)
            except Exception:
                pass

        try:
            self._mode_anim.start()
        except Exception:
            pass

    def _animate_widget_opacity(self, widget, target_opacity, duration=300):
        """Animate widget opacity smoothly"""
        try:
            if not widget:
                return None
            
            # Get or create opacity effect
            if not hasattr(widget, '_opacity_effect'):
                widget._opacity_effect = QGraphicsOpacityEffect(widget)
                widget.setGraphicsEffect(widget._opacity_effect)
            
            # Create animation
            anim = self._create_smooth_animation(widget._opacity_effect, b"opacity", duration=duration)
            if anim:
                anim.setStartValue(widget._opacity_effect.opacity())
                anim.setEndValue(target_opacity)
                anim.start()
                return anim
        except Exception:
            # Fallback: set opacity directly
            try:
                if hasattr(widget, '_opacity_effect'):
                    widget._opacity_effect.setOpacity(target_opacity)
            except Exception:
                pass
        return None

    def _animate_widget_show(self, widget, duration=300):
        """Smoothly show a widget"""
        try:
            if widget:
                widget.show()
                return self._animate_widget_opacity(widget, 1.0, duration)
        except Exception:
            pass
        return None

    def _animate_widget_hide(self, widget, duration=300):
        """Smoothly hide a widget"""
        try:
            if widget:
                anim = self._animate_widget_opacity(widget, 0.0, duration)
                if anim:
                    # Hide widget after animation completes
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(duration, lambda: widget.hide())
                else:
                    widget.hide()
                return anim
        except Exception:
            pass
        return None

    def _fade_in_song_ui(self):
        try:
            # Stop any existing fade animations
            if hasattr(self, '_fade_anim') and self._fade_anim:
                try:
                    for anim in self._fade_anim:
                        if anim:
                            anim.stop()
                except Exception:
                    pass

            self.song_opacity.setOpacity(0.0)
            # Keep cover opacity at 0 — it will be animated separately once the
            # pixmap is loaded (see _fade_in_cover called from load_cover_art).
            self.cover_opacity.setOpacity(0.0)

            # Animate only the song label; cover fades in when image is ready.
            a1 = self._create_smooth_animation(self.song_opacity, b"opacity", duration=400)
            if a1:
                a1.setStartValue(0.0)
                a1.setEndValue(1.0)

            if a1:
                self._fade_anim = (a1,)
                a1.start()
            else:
                # Fallback
                a1 = QPropertyAnimation(self.song_opacity, b"opacity")
                a1.setDuration(400)
                a1.setEasingCurve(QEasingCurve.Type.OutCubic)
                a1.setStartValue(0.0)
                a1.setEndValue(1.0)
                self._fade_anim = (a1,)
                a1.start()
        except Exception:
            pass

    def _fade_in_cover(self):
        """Animate cover_opacity 0 → 1.  Called right after load_cover_art sets
        the pixmap so the cover fades in at the same moment the art becomes
        visible rather than ~500 ms before."""
        try:
            # Stop any previous cover fade to avoid conflicts
            prev = getattr(self, '_cover_fade_anim', None)
            if prev is not None:
                try:
                    prev.stop()
                except Exception:
                    pass
            a2 = self._create_smooth_animation(self.cover_opacity, b"opacity", duration=450)
            if a2:
                a2.setStartValue(0.0)
                a2.setEndValue(1.0)
                # Store reference so the animation isn't garbage-collected before
                # it finishes (local variables are not kept alive by Qt).
                self._cover_fade_anim = a2
                a2.start()
            else:
                a2 = QPropertyAnimation(self.cover_opacity, b"opacity")
                a2.setDuration(450)
                a2.setEasingCurve(QEasingCurve.Type.OutCubic)
                a2.setStartValue(0.0)
                a2.setEndValue(1.0)
                self._cover_fade_anim = a2
                a2.start()
        except Exception:
            # Hard fallback: just make the cover fully visible immediately
            try:
                self.cover_opacity.setOpacity(1.0)
            except Exception:
                pass

    def _format_time(self, ms: int) -> str:
        if ms < 0:
            ms = 0
        s = ms // 1000
        m = s // 60
        s = s % 60
        return f"{m}:{s:02d}"

    def _toggle_time_mode(self, event):
        self._time_left_mode = not self._time_left_mode
        try:
            self._on_position_changed(self.player.position())
        except Exception:
            pass

    def _on_close_clicked(self):
        try:
            pass
        except Exception:
            pass
        try:
            self.close()
        except Exception:
            pass

    def _cleanup_before_exit(self):
        try:
            if getattr(self, '_edge_sampler', None) is not None:
                self._edge_sampler.stop()
        except Exception:
            pass
        try:
            self._stop_global_hotkey_listener()
        except Exception:
            pass
        # Clean up any in-progress crossfade
        try:
            if getattr(self, '_crossfade_timer', None) is not None:
                self._crossfade_timer.stop()
                self._crossfade_timer = None
        except Exception:
            pass
        try:
            for attr in ('_crossfade_from_player', '_crossfade_to_player'):
                p = getattr(self, attr, None)
                if p is not None and p is not getattr(self, 'player', None):
                    try:
                        p.stop()
                    except Exception:
                        pass
                    try:
                        p.deleteLater()
                    except Exception:
                        pass
            for attr in ('_crossfade_from_audio', '_crossfade_to_audio'):
                a = getattr(self, attr, None)
                if a is not None and a is not getattr(self, 'audio', None):
                    try:
                        a.deleteLater()
                    except Exception:
                        pass
            self._crossfade_from_player = None
            self._crossfade_from_audio = None
            self._crossfade_to_player = None
            self._crossfade_to_audio = None
        except Exception:
            pass
        # Clean up audio probes
        try:
            for probe in getattr(self, '_audio_probes', []):
                try:
                    probe.setSource(None)
                except Exception:
                    pass
                try:
                    probe.deleteLater()
                except Exception:
                    pass
            self._audio_probes = []
        except Exception:
            pass
        try:
            self._save_settings()
        except Exception:
            pass
        try:
            self.save_playlist()
        except Exception:
            pass

    def _write_reverse_pcm_to_wav(self, pcm_bytes, sample_rate, channels, sample_size):
        try:
            bytes_per_frame = max(1, (int(sample_size) // 8) * int(channels))
            usable = len(pcm_bytes) - (len(pcm_bytes) % bytes_per_frame)
            if usable < bytes_per_frame * 4:
                return None

            chunk = pcm_bytes[:usable]
            n_frames = len(chunk) // bytes_per_frame
            rev_chunks = [chunk[i * bytes_per_frame:(i + 1) * bytes_per_frame]
                          for i in range(n_frames)]
            rev_chunks.reverse()
            reversed_pcm = b''.join(rev_chunks)

            import wave as _wave, tempfile as _tempfile
            _fd, tmp_path = _tempfile.mkstemp(suffix='.wav')
            os.close(_fd)
            with _wave.open(tmp_path, 'wb') as wf:
                wf.setnchannels(int(channels))
                wf.setsampwidth(max(1, int(sample_size) // 8))
                wf.setframerate(int(sample_rate))
                wf.writeframes(reversed_pcm)
            return tmp_path
        except Exception:
            return None

    def _apply_slowdown_to_wav(self, wav_path, output_sec=2.5, end_rate=0.25):
        """Bake a gradual turntable-stop slowdown into a WAV file.
        Pitch starts at original (1.0x) and linearly drops to end_rate."""
        try:
            import wave as _wave, array as _array
            with _wave.open(wav_path, 'rb') as wf:
                ch = wf.getnchannels()
                sw = wf.getsampwidth()
                fr = wf.getframerate()
                nf = wf.getnframes()
                raw = wf.readframes(nf)
            if nf < 100 or sw not in (2, 4):
                return wav_path
            tc = 'h' if sw == 2 else 'i'
            inp = _array.array(tc, raw)
            out_frames = int(output_sec * fr)
            out = _array.array(tc)
            inv = 1.0 / max(1, out_frames - 1)
            last = nf - 1
            # Build a source-position curve where speed(t) = 1.0 - (1.0 - end_rate)*t
            # Integrating: src_pos(t) = t - 0.5*(1.0 - end_rate)*t^2
            # scaled so the full source is consumed.
            max_src = 1.0 - 0.5 * (1.0 - end_rate)  # total integral at t=1
            for i in range(out_frames):
                t = i * inv
                src_norm = (t - 0.5 * (1.0 - end_rate) * t * t) / max_src
                src_f = min(max(0.0, src_norm), 1.0) * last
                src_i = min(int(src_f), last)
                frac = src_f - src_i
                src_n = min(src_i + 1, last)
                b0 = src_i * ch
                b1 = src_n * ch
                # Fade out over the last 80% of the output.
                fade = max(0.0, min(1.0, (1.0 - t) / 0.8))
                for c in range(ch):
                    out.append(int((inp[b0 + c] * (1.0 - frac) + inp[b1 + c] * frac) * fade))
            with _wave.open(wav_path, 'wb') as wf:
                wf.setnchannels(ch)
                wf.setsampwidth(sw)
                wf.setframerate(fr)
                wf.writeframes(out.tobytes())
            return wav_path
        except Exception:
            return wav_path

    def _decode_reverse_close_clip(self, target_ms=1000):
        try:
            src = self.player.source()
            if src is None or not src.isLocalFile():
                return None
            src_path = src.toLocalFile()
            if not src_path or not os.path.exists(src_path):
                return None

            current_pos_ms = max(0, int(self.player.position()))
            if current_pos_ms <= 0:
                return None

            start_ms = max(0, current_pos_ms - int(target_ms))

            # --- Try ffmpeg first (reliable – can seek in compressed files) ---
            try:
                import shutil, subprocess, tempfile as _tf
                _ffmpeg = shutil.which('ffmpeg')
                if _ffmpeg:
                    dur_sec = target_ms / 1000.0
                    st_sec = max(0.0, current_pos_ms / 1000.0 - dur_sec)
                    _fd, _tmp = _tf.mkstemp(suffix='.wav')
                    os.close(_fd)
                    _cmd = [
                        _ffmpeg, '-y', '-loglevel', 'error',
                        '-ss', f'{st_sec:.3f}', '-t', f'{dur_sec:.3f}',
                        '-i', src_path,
                        '-af', 'areverse',
                        '-ar', '44100', '-ac', '2',
                        '-f', 'wav', _tmp,
                    ]
                    _kw = dict(capture_output=True, timeout=4)
                    if sys.platform == 'win32':
                        _kw['creationflags'] = 0x08000000  # CREATE_NO_WINDOW
                    subprocess.run(_cmd, **_kw)
                    if os.path.exists(_tmp) and os.path.getsize(_tmp) > 200:
                        return _tmp
                    try:
                        os.remove(_tmp)
                    except Exception:
                        pass
            except Exception:
                pass

            # --- Fallback: QAudioDecoder ---
            # Grab the FIRST target_ms of the file (delivered almost instantly)
            # rather than seeking to current position (which would time out).
            start_ms = 0
            current_pos_ms = int(target_ms)
            from PyQt6.QtCore import QEventLoop, QTimer
            from PyQt6.QtMultimedia import QAudioDecoder

            decoder = QAudioDecoder(self)
            # Force int16 output so wave module and _apply_slowdown_to_wav work.
            from PyQt6.QtMultimedia import QAudioFormat
            fmt16 = QAudioFormat()
            fmt16.setSampleRate(44100)
            fmt16.setChannelCount(2)
            try:
                fmt16.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            except Exception:
                pass
            decoder.setAudioFormat(fmt16)
            decoder.setSource(QUrl.fromLocalFile(src_path))

            state = {
                'pcm': bytearray(),
                'sample_rate': 44100,
                'channels': 2,
                'sample_size': 16,
                'done': False,
            }

            def _to_ms(raw):
                try:
                    value = int(raw)
                except Exception:
                    return 0
                if value > 1000000:
                    return int(value / 1000)
                return value

            def _trim_tail():
                try:
                    bytes_per_frame = max(1, (state['sample_size'] // 8) * state['channels'])
                    max_bytes = int(state['sample_rate'] * (int(target_ms) / 1000.0) * bytes_per_frame)
                    if len(state['pcm']) > max_bytes:
                        del state['pcm'][:len(state['pcm']) - max_bytes]
                except Exception:
                    pass

            def _mark_done():
                state['done'] = True
                try:
                    decoder.stop()
                except Exception:
                    pass

            def _on_buffer_ready():
                try:
                    while decoder.bufferAvailable():
                        buf = decoder.read()
                        if not buf or not buf.isValid():
                            continue

                        try:
                            fmt = buf.format()
                            state['sample_rate'] = int(fmt.sampleRate()) or state['sample_rate']
                            state['channels'] = int(fmt.channelCount()) or state['channels']
                            try:
                                state['sample_size'] = int(fmt.bytesPerSample()) * 8 or state['sample_size']
                            except Exception:
                                state['sample_size'] = int(fmt.sampleSize()) or state['sample_size']
                        except Exception:
                            pass

                        try:
                            data = bytes(buf.data())
                        except Exception:
                            try:
                                data = bytes(buf.constData())
                            except Exception:
                                data = b''
                        if not data:
                            continue

                        bytes_per_frame = max(1, (state['sample_size'] // 8) * state['channels'])
                        start_time_ms = _to_ms(buf.startTime())
                        duration_time_ms = _to_ms(buf.duration())
                        if duration_time_ms <= 0 and state['sample_rate'] > 0:
                            duration_time_ms = int((buf.frameCount() / float(state['sample_rate'])) * 1000.0)
                        end_time_ms = start_time_ms + max(0, duration_time_ms)

                        if end_time_ms and end_time_ms <= start_ms:
                            continue

                        if start_time_ms < start_ms and duration_time_ms > 0:
                            skip_ratio = min(1.0, max(0.0, (start_ms - start_time_ms) / float(duration_time_ms)))
                            skip_bytes = int(len(data) * skip_ratio)
                            skip_bytes -= (skip_bytes % bytes_per_frame)
                            data = data[skip_bytes:]

                        if end_time_ms and end_time_ms > current_pos_ms and duration_time_ms > 0:
                            keep_ratio = min(1.0, max(0.0, (current_pos_ms - start_time_ms) / float(duration_time_ms)))
                            keep_bytes = int(len(data) * keep_ratio)
                            keep_bytes -= (keep_bytes % bytes_per_frame)
                            data = data[:keep_bytes]

                        if data:
                            state['pcm'].extend(data)
                            _trim_tail()

                        if end_time_ms and end_time_ms >= current_pos_ms:
                            _mark_done()
                            break
                except Exception:
                    _mark_done()

            loop = QEventLoop(self)
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(loop.quit)

            try:
                decoder.bufferReady.connect(_on_buffer_ready)
                decoder.finished.connect(loop.quit)
                decoder.error.connect(loop.quit)
            except Exception:
                pass

            decoder.start()
            timer.start(2500)
            loop.exec()

            try:
                timer.stop()
            except Exception:
                pass
            try:
                decoder.stop()
            except Exception:
                pass
            try:
                decoder.deleteLater()
            except Exception:
                pass

            if not state['pcm']:
                return None

            return self._write_reverse_pcm_to_wav(
                bytes(state['pcm']),
                state['sample_rate'],
                state['channels'],
                state['sample_size'],
            )
        except Exception:
            return None

    def _start_close_animation(self):
        if getattr(self, '_closing_in_progress', False):
            return
        self._closing_in_progress = True

        try:
            app = QApplication.instance()
            if app is not None:
                self._close_quit_on_last_window_closed = bool(app.quitOnLastWindowClosed())
                app.setQuitOnLastWindowClosed(False)
        except Exception:
            self._close_quit_on_last_window_closed = None

        duration_ms = 500
        start_rect = self.geometry()
        center = start_rect.center()
        end_w, end_h = 120, 120
        end_x = int(center.x() - end_w / 2)
        end_y = int(center.y() - end_h / 2)
        end_rect = QRect(end_x, end_y, end_w, end_h)

        try:
            if self._close_anim is not None:
                self._close_anim.stop()
        except Exception:
            pass

        try:
            self._close_anim = QPropertyAnimation(self, b"geometry")
            self._close_anim.setDuration(duration_ms)
            try:
                self._close_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type.InOutSine))
            except Exception:
                pass
            self._close_anim.setStartValue(start_rect)
            try:
                self._close_anim.setKeyValueAt(0.12, start_rect)
            except Exception:
                pass
            self._close_anim.setEndValue(end_rect)
        except Exception:
            self._close_anim = None

        # Fade window opacity.
        try:
            if self._close_opacity_anim is not None:
                self._close_opacity_anim.stop()
        except Exception:
            pass
        try:
            self._close_opacity_anim = QPropertyAnimation(self, b"windowOpacity")
            self._close_opacity_anim.setDuration(duration_ms)
            try:
                self._close_opacity_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type.InOutSine))
            except Exception:
                pass
            self._close_opacity_anim.setStartValue(max(0.0, float(self.windowOpacity())))
            try:
                self._close_opacity_anim.setKeyValueAt(0.15, max(0.0, float(self.windowOpacity())))
                self._close_opacity_anim.setKeyValueAt(0.60, 0.35)
            except Exception:
                pass
            self._close_opacity_anim.setEndValue(0.0)
        except Exception:
            self._close_opacity_anim = None

        # --- Close sound: reverse + slowdown via ffmpeg + winsound ---
        audio_duration_ms = 1000
        playing = False
        try:
            playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        except Exception:
            playing = False
        if not playing:
            try:
                playing = self.player.position() > 0 and self.player.source().isLocalFile()
            except Exception:
                playing = False

        close_sound_playing = False
        if playing:
            try:
                cur_vol = 1.0
                active_audio = None
                try:
                    active_audio = (self.player.audioOutput() or
                                    getattr(self, 'audio_output', None) or
                                    getattr(self, 'audio', None))
                    cur_vol = float(active_audio.volume()) if active_audio else 1.0
                except Exception:
                    pass

                src = self.player.source()
                src_path = src.toLocalFile() if src and src.isLocalFile() else None
                pos_ms = max(0, int(self.player.position()))

                if src_path and os.path.exists(src_path) and pos_ms > 200:
                    import shutil, subprocess, tempfile as _tf
                    _ffmpeg = shutil.which('ffmpeg')
                    if not _ffmpeg:
                        # Fallback to known install location.
                        for _candidate in [
                            os.path.expanduser(r'~\ffmpeg-2026-04-01-git-eedf`8f0165-full_build\bin\ffmpeg.exe'),
                        ]:
                            if os.path.isfile(_candidate):
                                _ffmpeg = _candidate
                                break
                    if _ffmpeg:
                        clip_sec = 1.5
                        pos_sec = pos_ms / 1000.0
                        st_sec = max(0.0, pos_sec - clip_sec)
                        out_sec = audio_duration_ms / 1000.0
                        _fd, _tmp = _tf.mkstemp(suffix='.wav')
                        os.close(_fd)
                        # Use atrim in the filter graph (not input -ss) so
                        # areverse gets all the frames it needs.
                        # asetrate to slow down pitch, aresample back to 44100,
                        # atrim to limit length, afade to fade out.
                        rough_seek = max(0.0, st_sec - 3.0)
                        trim_start = st_sec - rough_seek
                        trim_end = pos_sec - rough_seek
                        _cmd = [
                            _ffmpeg, '-y', '-loglevel', 'error',
                            '-ss', f'{rough_seek:.3f}',
                            '-i', src_path,
                            '-af', (
                                f'atrim={trim_start:.3f}:{trim_end:.3f},'
                                f'asetpts=PTS-STARTPTS,'
                                f'areverse,'
                                f'aecho=0.8:0.7:60|120:0.4|0.2,'
                                f'volume={min(cur_vol, 1.0):.2f}'
                            ),
                            '-ar', '44100', '-ac', '2',
                            '-sample_fmt', 's16',
                            '-f', 'wav', _tmp,
                        ]
                        _kw = dict(capture_output=True, timeout=5)
                        if sys.platform == 'win32':
                            _kw['creationflags'] = 0x08000000
                        subprocess.run(_cmd, **_kw)
                        if os.path.exists(_tmp) and os.path.getsize(_tmp) > 1000:
                            # Bake gradual turntable-stop into the WAV
                            # (pitch starts ~1.2x high, drops to near-zero).
                            self._apply_slowdown_to_wav(
                                _tmp, output_sec=out_sec, end_rate=0.25)
                            self._rev_tmp = _tmp
                            # Mute and pause the real player.
                            try:
                                if active_audio:
                                    active_audio.setVolume(0.0)
                                self.player.pause()
                            except Exception:
                                pass
                            # Play with winsound (bypasses Qt multimedia).
                            import winsound
                            winsound.PlaySound(
                                _tmp,
                                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
                            )
                            close_sound_playing = True
                        else:
                            try:
                                os.remove(_tmp)
                            except Exception:
                                pass
            except Exception:
                close_sound_playing = False
        if playing and not close_sound_playing:
            try:
                if self._close_audio_anim is not None:
                    self._close_audio_anim.stop()
            except Exception:
                pass
            try:
                active_audio = (self.player.audioOutput() or
                                getattr(self, 'audio_output', None) or
                                getattr(self, 'audio', None))
                start_vol = float(active_audio.volume()) if active_audio else 1.0
                self._close_audio_anim = QVariantAnimation(self)
                self._close_audio_anim.setDuration(duration_ms)
                self._close_audio_anim.setStartValue(0.0)
                self._close_audio_anim.setEndValue(1.0)

                def _on_fallback_step(v):
                    try:
                        t = max(0.0, min(1.0, float(v)))
                        if active_audio:
                            active_audio.setVolume(max(0.0, start_vol * (1.0 - t)))
                    except Exception:
                        pass

                self._close_audio_anim.valueChanged.connect(_on_fallback_step)
                self._close_audio_anim.start()
            except Exception:
                pass

        def _finish_close():
            # Stop winsound if still going.
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
            # Clean up temp file.
            try:
                rt = getattr(self, '_rev_tmp', None)
                if rt:
                    try:
                        os.remove(rt)
                    except Exception:
                        pass
                    self._rev_tmp = None
            except Exception:
                pass
            # Restore quit setting.
            try:
                app = QApplication.instance()
                if app is not None and self._close_quit_on_last_window_closed is not None:
                    app.setQuitOnLastWindowClosed(bool(self._close_quit_on_last_window_closed))
            except Exception:
                pass
            self._close_quit_on_last_window_closed = None
            # Pause main player.
            try:
                self.player.pause()
            except Exception:
                pass
            self._cleanup_before_exit()
            self._allow_close = True
            try:
                QApplication.quit()
            except Exception:
                try:
                    self.close()
                except Exception:
                    pass

        # Quit after the audio finishes (or after visual anim if no close sound).
        quit_delay = audio_duration_ms if close_sound_playing else duration_ms
        QTimer.singleShot(quit_delay + 200, _finish_close)

        # Start visual animations.
        try:
            if self._close_anim is not None:
                self._close_anim.start()
        except Exception:
            pass
        try:
            if self._close_opacity_anim is not None:
                self._close_opacity_anim.start()
        except Exception:
            pass

    def closeEvent(self, event):
        try:
            if getattr(self, '_allow_close', False):
                event.accept()
                return
        except Exception:
            pass

        try:
            event.ignore()
        except Exception:
            pass
        self._start_close_animation()

    def paintEvent(self, event):
        # When shrunk/small, don't draw any background (fully transparent)
        if not self.expanded:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        r = self.rect()
        rf = QRectF(r)
        path = _chamfered_path(QRectF(r), 20.0, chamfer_tl=False)
        # apply an automatic brightness multiplier (set by animation) so
        # the gradient subtly fades in/out based on an internal phase
        try:
            # Determine playing state
            playing = False
            if hasattr(self, 'player') and self.player is not None:
                try:
                    playing = (self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
                except Exception:
                    playing = (getattr(self, 'current_index', -1) != -1)

            # Smooth pause/play fade: _pause_fade_progress 0=playing, 1=paused
            # Updated every paintEvent frame (driven by _auto_grad_timer at ~60 Hz)
            if not hasattr(self, '_pause_fade_progress'):
                self._pause_fade_progress = 0.0 if playing else 1.0

            fade_speed = 0.04  # ~0.65 s transition at 60 fps
            if not playing:
                self._pause_fade_progress = min(1.0, self._pause_fade_progress + fade_speed)
            else:
                self._pause_fade_progress = max(0.0, self._pause_fade_progress - fade_speed)

            fade = self._pause_fade_progress

            # Blend live auto-brightness with paused target (50 %)
            bmul_playing = getattr(self, '_auto_brightness', 1.0)
            bmul_paused = 0.5 * bmul_playing
            bmul = bmul_playing + (bmul_paused - bmul_playing) * fade

            # Beat pulse drives colour instead of raw volume energy
            live_beat = max(0.0, min(1.0, getattr(self, '_beat_pulse', 0.0)))
            low_e  = live_beat * (1.0 - fade)
            high_e = low_e

            base_orig = QColor(self._theme_color)
            react = max(0.0, float(getattr(self, '_volume_reactivity', 1.0))) * 5.0

            low_mul  = bmul * (1.0 + 1.8 * low_e  * react)
            high_mul = bmul * (1.0 + 1.8 * high_e * react)

            rr1 = min(255, max(0, int(base_orig.red()   * low_mul)))
            gg1 = min(255, max(0, int(base_orig.green() * low_mul)))
            bb1 = min(255, max(0, int(base_orig.blue()  * low_mul)))

            rr2 = min(255, max(0, int(base_orig.red()   * high_mul)))
            gg2 = min(255, max(0, int(base_orig.green() * high_mul)))
            bb2 = min(255, max(0, int(base_orig.blue()  * high_mul)))

            glass_a = int(max(40, min(220, getattr(self, '_expanded_glass_alpha', 128))))
            col1 = QColor(rr1, gg1, bb1, glass_a)
            col2 = QColor(rr2, gg2, bb2, glass_a)
        except Exception:
            glass_a = int(max(40, min(220, getattr(self, '_expanded_glass_alpha', 128))))
            col1 = QColor(self._theme_color.red(), self._theme_color.green(), self._theme_color.blue(), glass_a)
            col2 = QColor(0, 0, 0, glass_a)

        sx = rf.left() + (rf.width() * (0.35 + self._grad_offset.x()))
        sy = rf.top() + (rf.height() * (0.35 + self._grad_offset.y()))
        ex = rf.right() - (rf.width() * (0.35 - self._grad_offset.x()))
        ey = rf.bottom() - (rf.height() * (0.35 - self._grad_offset.y()))
        grad = QLinearGradient(QPointF(sx, sy), QPointF(ex, ey))
        grad.setColorAt(0.0, col1)
        grad.setColorAt(1.0, col2)

        painter.fillPath(path, grad)
        try:
            _paint_glass_reflections(self, painter, radius=12.0, intensity=0.40)
        except Exception:
            pass
        painter.end()

    def dark_style(self):
        return """
        QWidget {
            background-color: transparent;
            color: white;
            font-family: Segoe UI;
        }
        QListWidget {
            background-color: #2a2a30;
            border-radius: 0px;
        }
        """

    # ---------- Automatic gradient animation helpers ----------
    def _start_auto_gradient(self):
        import random, time
        # choose an initial random target offset (x,y) in the same coordinate scale
        self._auto_grad_target = QPointF((random.random() - 0.5) * 0.24, (random.random() - 0.5) * 0.24)
        self._auto_brightness_base = 0.82
        self._auto_brightness_amp = 0.36
        self._auto_grad_period = random.uniform(6.0, 12.0)
        self._auto_phase_start = time.time()
        self._auto_brightness = 1.0
        self._auto_last_update = time.time()

        # timer for smooth updates (~60Hz)
        try:
            self._auto_grad_timer = QTimer(self)
            self._auto_grad_timer.setInterval(16)
            self._auto_grad_timer.timeout.connect(self._update_auto_gradient)
            self._auto_grad_timer.start()
        except Exception:
            pass

        # schedule the first random target pick
        try:
            QTimer.singleShot(int(random.uniform(5000, 12000)), self._pick_new_grad_target)
        except Exception:
            pass

    def _pick_new_grad_target(self):
        import random, time
        try:
            self._auto_grad_target = QPointF((random.random() - 0.5) * 0.24, (random.random() - 0.5) * 0.24)
            # pick a new fade period as well so the rhythm feels organic
            self._auto_grad_period = random.uniform(6.0, 12.0)
            self._auto_phase_start = time.time()
        except Exception:
            pass

        # schedule next target pick
        try:
            QTimer.singleShot(int(random.uniform(2500, 6000)), self._pick_new_grad_target)
        except Exception:
            pass

    def _update_auto_gradient(self):
        import time, math
        try:
            now = time.time()
            mono_now = time.monotonic()
            last = getattr(self, '_auto_last_update', now)
            dt = max(0.0, now - last)
            self._auto_last_update = now

            # time-constant based smoothing (frame-rate independent)
            tau = 0.12
            alpha = 1.0 - math.exp(-dt / tau) if tau > 0 else 1.0

            cur = getattr(self, '_grad_offset', QPointF(0.0, 0.0))
            tgt = getattr(self, '_auto_grad_target', QPointF(0.0, 0.0))
            nx = cur.x() + (tgt.x() - cur.x()) * alpha
            ny = cur.y() + (tgt.y() - cur.y()) * alpha
            self._grad_offset = QPointF(nx, ny)

            # brightness target follows a sinusoid; scale amplitude by current audio volume
            elapsed = now - getattr(self, '_auto_phase_start', now)
            period = max(0.1, getattr(self, '_auto_grad_period', 4.0))
            phase = 2.0 * math.pi * (elapsed / period)
            base = getattr(self, '_auto_brightness_base', 0.82)
            amp = getattr(self, '_auto_brightness_amp', 0.36)
            # determine current playback volume (0.0-1.0) if available
            try:
                vol = 1.0
                if hasattr(self, 'audio') and self.audio is not None:
                    try:
                        vol = float(self.audio.volume())
                    except Exception:
                        vol = 1.0
                vol = max(0.0, min(1.0, vol))
            except Exception:
                vol = 1.0
            # scale the amplitude by volume and reactivity so quieter playback yields subtler gradients
            react = max(0.0, float(getattr(self, '_volume_reactivity', 1.0)))
            target_b = base + (amp * vol * react) * (0.5 * (1.0 + math.sin(phase)))

            tau_b = 0.25
            alpha_b = 1.0 - math.exp(-dt / tau_b) if tau_b > 0 else 1.0
            self._auto_brightness = getattr(self, '_auto_brightness', 1.0) + (target_b - getattr(self, '_auto_brightness', 1.0)) * alpha_b

            try:
                if getattr(self, 'expanded', False):
                    self.update()
                else:
                    # In small mode, trigger the cover widget to repaint so the
                    # audio-reactive glow animates even when the main window is transparent.
                    try:
                        if hasattr(self, 'cover') and self.cover is not None:
                            self.cover.update()
                    except Exception:
                        pass
            except Exception:
                pass

            # Decay beat pulse (half-life ~140 ms so colours snap back quickly)
            try:
                bp = getattr(self, '_beat_pulse', 0.0)
                if bp > 0.0:
                    # tau = 0.14 s  →  decay factor per frame
                    decay = math.exp(-dt / 0.14) if dt > 0 else 1.0
                    self._beat_pulse = max(0.0, bp * decay)
            except Exception:
                pass

            # Keep pulsing on the predicted beat grid once BPM confidence is high enough.
            try:
                bpm = max(0, int(getattr(self, '_current_bpm', 0) or 0))
                confidence = max(0.0, min(1.0, float(getattr(self, '_bpm_confidence', 0.0))))
                phase_time = float(getattr(self, '_bpm_phase_time', 0.0))
                if bpm > 0 and confidence >= 0.24 and phase_time > 0.0:
                    beat_period = 60.0 / float(bpm)
                    nearest_beat = phase_time + round((mono_now - phase_time) / beat_period) * beat_period
                    window = max(0.03, min(0.08, (dt * 1.9) + 0.02))
                    last_predict = float(getattr(self, '_bpm_last_predict', 0.0))
                    if abs(mono_now - nearest_beat) <= window and (mono_now - last_predict) >= max(0.18, beat_period * 0.45):
                        self._bpm_last_predict = mono_now
                        self._beat_pulse = max(getattr(self, '_beat_pulse', 0.0), 0.42 + (0.48 * confidence))
            except Exception:
                pass

            # Update BPM label every ~500 ms
            try:
                last_bpm_upd = getattr(self, '_last_bpm_label_update', 0.0)
                if mono_now - last_bpm_upd >= 0.5:
                    self._last_bpm_label_update = mono_now
                    bpm = self._compute_bpm()
                    self._current_bpm = bpm
                    if hasattr(self, 'bpm_label') and self.bpm_label is not None:
                        if bpm > 0 and self.current_index >= 0:
                            self.bpm_label.setText(f"{bpm} BPM")
                        else:
                            self.bpm_label.setText("")
            except Exception:
                pass
        except Exception:
            pass

    def _fold_bpm_guess(self, bpm: float, min_bpm: int = 72, max_bpm: int = 176) -> float:
        try:
            bpm = float(bpm)
            if bpm <= 0.0:
                return 0.0
            while bpm < min_bpm:
                bpm *= 2.0
            while bpm > max_bpm:
                bpm *= 0.5
            if bpm < min_bpm or bpm > max_bpm:
                return 0.0
            return bpm
        except Exception:
            return 0.0

    def _register_bpm_onset(self, when: float, strength: float):
        try:
            onsets = list(getattr(self, '_bpm_onsets', []))
            strength = max(0.0, float(strength))
            bpm = max(0.0, float(getattr(self, '_current_bpm', 0)))
            beat_period = (60.0 / bpm) if bpm > 0.0 else 0.5
            min_gap = max(0.18, min(0.42, beat_period * 0.45))

            if onsets and (when - onsets[-1][0]) < min_gap:
                if strength > onsets[-1][1]:
                    onsets[-1] = (when, strength)
                else:
                    return
            else:
                onsets.append((when, strength))

            while onsets and (when - onsets[0][0]) > 12.0:
                onsets.pop(0)
            self._bpm_onsets = onsets

            phase_time = float(getattr(self, '_bpm_phase_time', 0.0))
            if bpm > 0.0 and phase_time > 0.0:
                predicted_period = 60.0 / bpm
                nearest = phase_time + round((when - phase_time) / predicted_period) * predicted_period
                if abs(when - nearest) <= max(0.08, predicted_period * 0.18):
                    self._bpm_phase_time = nearest + (when - nearest) * 0.35
                else:
                    self._bpm_phase_time = when
            else:
                self._bpm_phase_time = when

            self._beat_pulse = max(getattr(self, '_beat_pulse', 0.0), min(1.0, 0.55 + strength * 0.35))
        except Exception:
            pass

    def _process_bpm_frame(self, when: float, raw_low: float, band_energies=None):
        try:
            prev_low = float(getattr(self, '_bpm_prev_energy', 0.0))
            low_floor = float(getattr(self, '_bpm_low_floor', raw_low))
            floor_alpha = 0.025 if raw_low >= low_floor else 0.07
            low_floor = (1.0 - floor_alpha) * low_floor + floor_alpha * raw_low
            self._bpm_low_floor = low_floor

            flux = max(0.0, raw_low - prev_low)
            if band_energies is not None:
                prev_bands = getattr(self, '_bpm_prev_band_energies', None)
                if prev_bands is not None and len(prev_bands) == len(band_energies):
                    flux = 0.0
                    for index, band in enumerate(band_energies):
                        previous = float(prev_bands[index])
                        diff = float(band) - previous
                        if diff > 0.0:
                            weight = 1.35 if index == 0 else (1.15 if index == 1 else 0.9)
                            flux += (diff / (max(1e-4, previous) + 0.015)) * weight
                self._bpm_prev_band_energies = [float(band) for band in band_energies]

            flux_floor = float(getattr(self, '_bpm_flux_floor', flux))
            flux_floor = (0.88 * flux_floor) + (0.12 * flux)
            self._bpm_flux_floor = flux_floor

            transient = max(0.0, raw_low - max(low_floor * 0.92, prev_low * 0.82))
            onset_strength = max(0.0, flux - max(0.08, flux_floor * 1.10))
            onset_strength += transient * 3.5

            if raw_low >= max(0.018, low_floor * 0.72) and onset_strength >= 0.11:
                self._register_bpm_onset(when, onset_strength)

            self._bpm_prev_energy = raw_low
        except Exception:
            pass

    def _compute_bpm(self) -> int:
        """Estimate BPM from recent weighted onsets and keep the strongest plausible tempo."""
        try:
            import math
            import time

            onsets = getattr(self, '_bpm_onsets', [])
            if len(onsets) < 4:
                self._bpm_confidence = 0.0
                return 0

            min_bpm = 72
            max_bpm = 176
            now = float(onsets[-1][0])
            scores = {}

            for start_index, (start_time, start_strength) in enumerate(onsets[:-1]):
                if start_strength <= 0.0:
                    continue
                for end_time, end_strength in onsets[start_index + 1:]:
                    dt = float(end_time - start_time)
                    if dt < 0.25 or dt > 2.4:
                        continue

                    folded = self._fold_bpm_guess(60.0 / dt, min_bpm=min_bpm, max_bpm=max_bpm)
                    if folded <= 0.0:
                        continue

                    pair_strength = max(0.05, min(float(start_strength), float(end_strength)))
                    recency = 1.0 - min(0.45, (now - float(end_time)) / 16.0)

                    for candidate in (int(folded), int(round(folded)), int(folded) + 1):
                        if candidate < min_bpm or candidate > max_bpm:
                            continue
                        error = abs(candidate - folded)
                        weight = pair_strength * recency * max(0.0, 1.0 - (error / 2.5))
                        if weight <= 0.0:
                            continue

                        prior = max(
                            math.exp(-((candidate - 96.0) / 14.0) ** 2),
                            math.exp(-((candidate - 112.0) / 12.0) ** 2),
                            math.exp(-((candidate - 128.0) / 10.0) ** 2),
                            math.exp(-((candidate - 140.0) / 12.0) ** 2),
                        )
                        scores[candidate] = scores.get(candidate, 0.0) + (weight * (0.96 + 0.12 * prior))

            if not scores:
                self._bpm_confidence = 0.0
                return 0

            previous_bpm = int(getattr(self, '_current_bpm', 0) or 0)
            if previous_bpm > 0:
                for candidate in list(scores.keys()):
                    diff = abs(candidate - previous_bpm)
                    if diff <= 6:
                        scores[candidate] *= 1.0 + max(0.0, 0.22 - (diff * 0.03))

            ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
            best_bpm, best_score = ranked[0]
            runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
            total_score = sum(scores.values()) + 1e-6
            separation = (best_score - runner_up) / max(best_score, 1e-6)
            share = best_score / total_score
            coverage = min(1.0, len(onsets) / 8.0)
            confidence = max(0.0, min(1.0, (share * 2.2) + (separation * 0.45) + (coverage * 0.2) - 0.15))
            self._bpm_confidence = confidence

            if confidence < 0.28:
                if previous_bpm > 0 and (time.monotonic() - now) <= 1.6:
                    return previous_bpm
                return 0

            if previous_bpm > 0 and abs(best_bpm - previous_bpm) <= 3:
                best_bpm = int(round((previous_bpm * 0.65) + (best_bpm * 0.35)))

            return int(best_bpm)
        except Exception:
            self._bpm_confidence = 0.0
            return 0

    def _on_audio_buffer_probed(self, buffer):
        try:
            import time as _time

            # process QAudioBuffer to estimate energy below/above 300Hz
            try:
                fmt = buffer.format()
                sample_rate = int(fmt.sampleRate())
                channels = int(fmt.channelCount())
                sample_size = int(fmt.sampleSize())
            except Exception:
                sample_rate = 44100
                channels = 2
                sample_size = 16

            # get raw bytes
            try:
                data = bytes(buffer.data())
            except Exception:
                try:
                    data = bytes(buffer.constData())
                except Exception:
                    data = None

            if not data:
                return

            # prefer numpy FFT if available
            try:
                import numpy as np
                if sample_size == 16:
                    arr = np.frombuffer(data, dtype=np.int16)
                elif sample_size == 32:
                    arr = np.frombuffer(data, dtype=np.int32)
                else:
                    arr = np.frombuffer(data, dtype=np.int16)

                if channels > 1 and arr.size % channels == 0:
                    arr = arr.reshape(-1, channels).mean(axis=1)

                # normalize
                denom = float(32768 if sample_size == 16 else (2**31))
                if denom == 0:
                    denom = 32768.0
                arrf = arr.astype(np.float32) / denom

                band_energies = None
                if arrf.size < 8:
                    # too small for FFT
                    rms = float(np.sqrt(np.mean(arrf * arrf))) if arrf.size else 0.0
                    raw_low = raw_high = rms
                else:
                    # compute real FFT and power spectrum
                    freqs = np.fft.rfftfreq(arrf.size, d=1.0 / sample_rate)
                    mags = np.abs(np.fft.rfft(arrf))
                    total = mags.sum() + 1e-12

                    sub_mask = (freqs >= 35.0) & (freqs < 90.0)
                    bass_mask = (freqs >= 90.0) & (freqs < 180.0)
                    low_mid_mask = (freqs >= 180.0) & (freqs < 360.0)
                    presence_mask = (freqs >= 360.0) & (freqs < 1400.0)

                    sub_energy = float(mags[sub_mask].sum() / total)
                    bass_energy = float(mags[bass_mask].sum() / total)
                    low_mid_energy = float(mags[low_mid_mask].sum() / total)
                    presence_energy = float(mags[presence_mask].sum() / total)

                    band_energies = (sub_energy, bass_energy, low_mid_energy)
                    raw_low = (sub_energy * 0.42) + (bass_energy * 0.43) + (low_mid_energy * 0.15)
                    raw_high = presence_energy

                prev_low = float(getattr(self, '_low_energy', 0.0))
                prev_high = float(getattr(self, '_high_energy', 0.0))
                low_alpha = 0.42 if raw_low >= prev_low else 0.12
                high_alpha = 0.34 if raw_high >= prev_high else 0.10
                self._low_energy = prev_low + (raw_low - prev_low) * low_alpha
                self._high_energy = prev_high + (raw_high - prev_high) * high_alpha

                self._process_bpm_frame(_time.monotonic(), raw_low, band_energies)

                # --- Rolling PCM buffer for close animation ---
                try:
                    buf = self._pcm_rolling_buffer
                    self._pcm_fmt = (sample_rate, channels, sample_size)
                    buf.extend(data)
                    bytes_per_frame = max(1, (sample_size // 8) * channels)
                    max_bytes = int(sample_rate * 1.5 * bytes_per_frame)
                    if len(buf) > max_bytes:
                        del buf[:len(buf) - max_bytes]
                except Exception:
                    pass

                return
            except Exception:
                pass

            # fallback: approximate energy from RMS and split by heuristic
            try:
                import struct, math
                if sample_size == 16:
                    fmt = '<' + 'h' * (len(data) // 2)
                    vals = struct.unpack(fmt, data[: (len(data) // 2) * 2])
                    arrf = [v / 32768.0 for v in vals]
                else:
                    # coarse fallback
                    arrf = [b / 255.0 for b in data]

                rms = math.sqrt(sum(x * x for x in arrf) / max(1, len(arrf)))
                raw_low = raw_high = rms
                prev_low = float(getattr(self, '_low_energy', 0.0))
                prev_high = float(getattr(self, '_high_energy', 0.0))
                low_alpha = 0.42 if raw_low >= prev_low else 0.12
                high_alpha = 0.34 if raw_high >= prev_high else 0.10
                self._low_energy = prev_low + (raw_low - prev_low) * low_alpha
                self._high_energy = prev_high + (raw_high - prev_high) * high_alpha
                self._process_bpm_frame(_time.monotonic(), raw_low)

                # PCM buffer (fallback path)
                try:
                    buf = self._pcm_rolling_buffer
                    self._pcm_fmt = (sample_rate, channels, sample_size)
                    buf.extend(data)
                    bytes_per_frame = max(1, (sample_size // 8) * channels)
                    max_bytes = int(sample_rate * 1.5 * bytes_per_frame)
                    if len(buf) > max_bytes:
                        del buf[:len(buf) - max_bytes]
                except Exception:
                    pass
            except Exception:
                pass
        except Exception:
            pass

    def _slider_style_gray(self) -> str:
        """Gray/inactive slider style used when no song is loaded."""
        return """
        QSlider::groove:horizontal {
            height: 6px;
            background: rgba(255,255,255,12);
            border: none;
            border-radius: 0px;
        }
        QSlider::groove:vertical {
            width: 6px;
            background: rgba(255,255,255,12);
            border: none;
            border-radius: 0px;
        }
        QSlider::handle:horizontal {
            background: rgba(128,128,128,100);
            width: 14px;
            margin: -6px 0;
            border-radius: 0px;
        }
        QSlider::handle:vertical {
            background: rgba(128,128,128,100);
            height: 14px;
            margin: 0 -6px;
            border-radius: 0px;
        }
        QSlider::handle:horizontal:hover, QSlider::handle:vertical:hover {
            background: rgba(160,160,160,130);
            border: 2px solid rgba(255,255,255,25);
        }
        """

    def _slider_style_for_color(self, col: QColor) -> str:
        try:
            # ensure QColor
            c = QColor(col)
            rgba50 = f'rgba({c.red()},{c.green()},{c.blue()},128)'
            rgba65 = f'rgba({c.red()},{c.green()},{c.blue()},165)'
        except Exception:
            rgba50 = 'rgba(74,144,226,128)'
            rgba65 = 'rgba(74,144,226,165)'
        # common handle style; use radius and remove default focus outline
        style = f"""
        QSlider::groove:horizontal {{
            height: 6px;
            background: rgba(255,255,255,18);
            border: none;
            border-radius: 0px;
        }}
        QSlider::groove:vertical {{
            width: 6px;
            background: rgba(255,255,255,18);
            border: none;
            border-radius: 0px;
        }}
        QSlider::handle:horizontal {{
            background: {rgba50};
            width: 14px;
            margin: -6px 0; /* center handle */
            border-radius: 0px;
        }}
        QSlider::handle:vertical {{
            background: {rgba50};
            height: 14px;
            margin: 0 -6px; /* center handle */
            border-radius: 0px;
        }}
        QSlider::handle:horizontal:hover, QSlider::handle:vertical:hover {{
            background: {rgba65};
            border: 2px solid rgba(255,255,255,40);
        }}
        """
        return style

    def _update_slider_styles(self):
        try:
            has_song = getattr(self, 'current_index', -1) >= 0 and getattr(self, 'playlist', [])
            if has_song:
                col = getattr(self, '_theme_color', None) or QColor('#4a90e2')
                ss = self._slider_style_for_color(col)
            else:
                ss = self._slider_style_gray()
            try:
                if hasattr(self, 'seek_slider'):
                    self.seek_slider.setStyleSheet(ss)
            except Exception:
                pass
            try:
                if hasattr(self, 'volume'):
                    self.volume.setStyleSheet(ss)
            except Exception:
                pass
        except Exception:
            pass


if __name__ == '__main__':
    # ---------- RUN ----------
    # Force Qt to use the native Windows media backend so that an ffmpeg
    # installation on PATH doesn't hijack Qt6's multimedia pipeline.
    os.environ.setdefault('QT_MULTIMEDIA_BACKEND', 'windows')
    app = QApplication(sys.argv)
    player = MiniMusicPlayer()
    player.show()

    # Play startup sound (startup.mp3) located next to this script, if present.
    try:
        startup_path = resource_path('startup.mp3')
        if os.path.exists(startup_path):
            # attach to player so objects are kept alive for duration of playback
            player.startup_audio = QAudioOutput()
            player.startup_player = QMediaPlayer()
            try:
                # match main player volume if available, but reduce to 60%
                main_vol = getattr(player, 'audio').volume()
                player.startup_audio.setVolume(main_vol * 0.6)
            except Exception:
                pass
            player.startup_player.setAudioOutput(player.startup_audio)
            try:
                player.startup_player.setSource(QUrl.fromLocalFile(resource_path('startup.mp3')))
                player.startup_player.play()
            except Exception:
                pass
    except Exception:
        pass

    sys.exit(app.exec())
