# buat_aset.py - bikin aset bunga dari karangan-atas.webp
# Jalankan dari folder proyek: python buat_aset.py
from PIL import Image

im = Image.open("static/img/karangan-atas.webp").convert("RGBA")
w, h = im.size

# 1. buket-samping.webp: separuh kiri karangan (dipakai di pojok section)
kiri = im.crop((0, 0, w // 2, h))
kiri = kiri.crop(kiri.getbbox())
kiri.save("static/img/buket-samping.webp", "WEBP", quality=90)

# 2. anggrek-pojok.webp: kelompok anggrek kiri, bagian atas dibuat memudar
a = im.crop((0, 130, 372, 491))
a = a.crop(a.getbbox())
alpha = a.getchannel("A")
pudar = int(a.height * 0.16)
px = alpha.load()
for y in range(pudar):
    f = y / pudar
    for x in range(a.width):
        px[x, y] = int(px[x, y] * f)
a.putalpha(alpha)
a.save("static/img/anggrek-pojok.webp", "WEBP", quality=90)
print("selesai")