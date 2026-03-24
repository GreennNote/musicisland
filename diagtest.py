import sys, importlib, traceback

# Test dxcam
print('Testing dxcam...')
try:
    dxcam = importlib.import_module('dxcam')
    cam = dxcam.create(output_color='RGB')
    print('  dxcam.create() returned:', cam)
    if cam is not None:
        frame = cam.grab()
        print('  grab() returned:', type(frame), '/', frame)
except Exception as e:
    print('  dxcam FAILED:', e)

# Test mss
print('Testing mss...')
try:
    mss = importlib.import_module('mss')
    sct = mss.mss()
    shot = sct.grab({'left': 0, 'top': 0, 'width': 100, 'height': 100})
    print('  mss shot type:', type(shot))
    print('  has .rgb:', hasattr(shot, 'rgb'))
    if hasattr(shot, 'rgb'):
        print('  shot.rgb type:', type(shot.rgb), 'len:', len(shot.rgb))
    print('  shot.width=%s, shot.height=%s' % (shot.width, shot.height))
    # Check raw bytes
    raw = bytes(shot.rgb)
    print('  first 12 bytes (rgb):', list(raw[:12]))
except Exception as e:
    print('  mss FAILED:', e)
    traceback.print_exc()

# Test win32gdi
print('Testing win32gdi...')
try:
    import ctypes
    import ctypes.wintypes as wt
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    l, t, w, h = 0, 0, 10, 10
    hdesktop = user32.GetDesktopWindow()
    hdc = user32.GetDC(hdesktop)
    mem_dc = gdi32.CreateCompatibleDC(hdc)
    hbm = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old_bm = gdi32.SelectObject(mem_dc, hbm)
    gdi32.BitBlt(mem_dc, 0, 0, w, h, hdc, l, t, 0x00CC0020)
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
    bmi.biHeight = -h
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0
    buf = (ctypes.c_char * (w * h * 4))()
    gdi32.GetDIBits(mem_dc, hbm, 0, h, buf, ctypes.byref(bmi), 0)
    gdi32.SelectObject(mem_dc, old_bm)
    gdi32.DeleteObject(hbm)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(hdesktop, hdc)
    raw = list(bytes(buf)[:12])
    print('  win32gdi capture OK, first 12 bytes (BGRA):', raw)
except Exception as e:
    print('  win32gdi FAILED:', e)
    traceback.print_exc()
