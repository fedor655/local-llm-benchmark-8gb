# -*- coding: utf-8 -*-
"""GPU-рендер Мандельброта на torch. Одинаков для ноута/4090/H100 -> честное сравнение.
Ноут: pip install torch --index-url https://download.pytorch.org/whl/cu121
Запуск: python mandelbrot_gpu.py"""
import time, sys
import torch

if not torch.cuda.is_available():
    print("CUDA недоступна — torch не видит GPU"); sys.exit(1)
dev = 'cuda'
name = torch.cuda.get_device_name(0)

W, H = 6000, 4000
MAX_ITER = 500
cx, cy, half_w = -0.75, 0.0, 1.75
half_h = half_w * H / W
xmin, xmax = cx - half_w, cx + half_w
ymin, ymax = cy - half_h, cy + half_h


def render():
    x = torch.linspace(xmin, xmax, W, device=dev)
    y = torch.linspace(ymin, ymax, H, device=dev)
    cr = x.unsqueeze(0).expand(H, W)
    ci = y.unsqueeze(1).expand(H, W)
    zr = torch.zeros((H, W), device=dev)
    zi = torch.zeros((H, W), device=dev)
    nit = torch.zeros((H, W), device=dev)
    alive = torch.ones((H, W), device=dev, dtype=torch.bool)
    for i in range(MAX_ITER):
        zr2 = zr * zr - zi * zi + cr
        zi2 = 2 * zr * zi + ci
        zr = torch.where(alive, zr2, zr)
        zi = torch.where(alive, zi2, zi)
        esc = alive & (zr * zr + zi * zi > 4.0)
        nit = torch.where(esc, torch.full_like(nit, float(i)), nit)
        alive = alive & ~esc
    return nit, alive


render(); torch.cuda.synchronize()          # прогрев (компиляция ядер)
t0 = time.time()
nit, alive = render()
torch.cuda.synchronize()
dt = time.time() - t0
thru = W * H * MAX_ITER / dt / 1e9
print(f"GPU: {name}")
print(f"{W}x{H}, {MAX_ITER} итераций -> {dt*1000:.0f} мс  ({thru:.1f} млрд итер-пикселей/с)")

try:
    from PIL import Image
    v = (nit * 0.15).cpu()
    r = 0.5 + 0.5 * torch.cos(v + 4.1)
    g = 0.5 + 0.5 * torch.cos(v + 4.1 + 0.9)
    b = 0.5 + 0.5 * torch.cos(v + 4.1 + 1.7)
    img = torch.stack([r, g, b], -1)
    img[alive.cpu()] = 0
    arr = (img.clamp(0, 1) * 255).byte().numpy()
    Image.fromarray(arr, 'RGB').save('/tmp/mandelbrot_gpu.png', optimize=True)
    print("картинка -> /tmp/mandelbrot_gpu.png")
except Exception as e:
    print("картинку не сохранил:", e)
