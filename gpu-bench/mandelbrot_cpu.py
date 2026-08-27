# -*- coding: utf-8 -*-
"""Мега-рендер множества Мандельброта: numpy + гладкая (smooth) раскраска."""
import numpy as np
from PIL import Image
import time

W, H = 6000, 4000          # 24 мегапикселя
MAX_ITER = 500

# полный вид, аспект подогнан под 3:2 без искажений
cx, cy = -0.75, 0.0
half_w = 1.75
half_h = half_w * H / W
xmin, xmax = cx - half_w, cx + half_w
ymin, ymax = cy - half_h, cy + half_h

t0 = time.time()
x = np.linspace(xmin, xmax, W, dtype=np.float64)
y = np.linspace(ymin, ymax, H, dtype=np.float64)
C = x[None, :] + 1j * y[:, None]
Z = np.zeros_like(C)
nu = np.zeros(C.shape, dtype=np.float64)   # smooth iteration count
alive = np.ones(C.shape, dtype=bool)

for i in range(MAX_ITER):
    Z[alive] = Z[alive] * Z[alive] + C[alive]
    esc = alive & (Z.real * Z.real + Z.imag * Z.imag > 4.0)
    if esc.any():
        az = np.abs(Z[esc])
        nu[esc] = i + 1 - np.log(np.log(az)) / np.log(2)
    alive &= ~esc
    if not alive.any():
        break

# гладкая циклическая палитра
v = nu * 0.15
r = 0.5 + 0.5 * np.cos(v + 4.1)
g = 0.5 + 0.5 * np.cos(v + 4.1 + 0.9)
b = 0.5 + 0.5 * np.cos(v + 4.1 + 1.7)
img = np.stack([r, g, b], axis=-1)
img[alive] = 0.0                            # внутри множества — чёрный
out = (np.clip(img, 0, 1) * 255).astype(np.uint8)

Image.fromarray(out, 'RGB').save('/tmp/mandelbrot.png', optimize=True)
print(f'готово: {W}x{H}, {MAX_ITER} итераций, {time.time()-t0:.1f} c -> /tmp/mandelbrot.png')
