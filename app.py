import csv
import io
import os
import re
import time
import shutil
import secrets
import sqlite3
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, Response, abort, flash, g, jsonify, redirect,
                   render_template, request, session, url_for)
from PIL import Image, ImageOps
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
EKSTENSI_OK = {"jpg", "jpeg", "png", "webp"}


# ---------- Konfigurasi & keamanan dasar ----------
def ambil_secret_key():
    """Pakai SECRET_KEY dari environment; jika tidak ada, buat acak sekali lalu simpan."""
    kunci = os.environ.get("SECRET_KEY")
    if kunci:
        return kunci
    path = os.path.join(BASE_DIR, "secret.key")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    kunci = secrets.token_hex(32)
    with open(path, "w", encoding="utf-8") as f:
        f.write(kunci)
    return kunci


app = Flask(__name__)
app.config["SECRET_KEY"] = ambil_secret_key()
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # total upload maks 200 MB
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"        # mencegah serangan CSRF lintas situs
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("HTTPS") == "1"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
app.config["TEMPLATES_AUTO_RELOAD"] = True

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
# Disarankan: isi ADMIN_PASS_HASH (lihat catatan). ADMIN_PASS teks biasa tetap
# didukung agar kode lama berjalan, tetapi langsung di-hash di memori.
ADMIN_PASS_HASH = os.environ.get("ADMIN_PASS_HASH")
if not ADMIN_PASS_HASH:
    ADMIN_PASS_HASH = generate_password_hash(os.environ.get("ADMIN_PASS", "admin123"))
    print("PERINGATAN: ADMIN_PASS_HASH belum diatur. Ganti password admin sebelum dipublikasikan.")

HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]

FIELD_TEKS = [
    "panggilan_pria", "panggilan_wanita", "nama_pria", "nama_wanita",
    "ortu_pria", "ortu_wanita", "tanggal_acara",
    "akad_tempat", "akad_alamat", "akad_waktu",
    "resepsi_tempat", "resepsi_alamat", "resepsi_waktu",
    "maps_url", "kutipan", "sumber_kutipan",
    "kalimat_pembuka", "kalimat_rsvp", "kalimat_hadiah", "kalimat_penutup",
    "bank", "no_rekening", "atas_nama",
    "kado_penerima", "kado_telepon", "kado_alamat",
    "bank2", "no_rekening2", "atas_nama2",
]
# Kolom yang ditambahkan setelah versi pertama (dimigrasi otomatis di init_db)
KOLOM_BARU = ["sumber_kutipan", "kalimat_pembuka", "kalimat_rsvp",
              "kalimat_hadiah", "kalimat_penutup",
              "kado_penerima", "kado_telepon", "kado_alamat",
              "bank2", "no_rekening2", "atas_nama2"]
# Batas panjang input per kolom (bawaan 200 karakter)
BATAS = {"kutipan": 600, "kalimat_pembuka": 600, "kalimat_rsvp": 600,
         "kalimat_hadiah": 600, "kalimat_penutup": 400,
         "maps_url": 500, "akad_alamat": 300, "resepsi_alamat": 300,
         "kado_alamat": 300}


# ---------- Pembatas laju (rate limit) sederhana, disimpan di memori ----------
# (jumlah kiriman maksimal, dalam berapa detik) per alamat IP untuk satu undangan.
# Dibuat longgar karena banyak tamu memakai satu IP yang sama (WiFi gedung, jaringan seluler).
BATAS_RSVP = (20, 600)
_catatan = defaultdict(deque)


def sudah_penuh(kunci, maks, detik):
    q = _catatan[kunci]
    batas = time.time() - detik
    while q and q[0] < batas:
        q.popleft()
    if not q:
        _catatan.pop(kunci, None)
    return len(q) >= maks


def catat(kunci):
    _catatan[kunci].append(time.time())


# ---------- Database ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def tutup_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        with open(os.path.join(BASE_DIR, "schema.sql"), encoding="utf-8") as f:
            db.executescript(f.read())
        # Migrasi: tambahkan kolom baru pada database lama bila belum ada
        ada = {r[1] for r in db.execute("PRAGMA table_info(undangan)")}
        for kolom in KOLOM_BARU:
            if kolom not in ada:
                db.execute(f"ALTER TABLE undangan ADD COLUMN {kolom} TEXT")


# ---------- Helper ----------
def slugify(teks):
    return re.sub(r"[^a-z0-9]+", "-", teks.lower()).strip("-")[:50]


def gambar_valid(file):
    """Periksa isi file (bukan hanya ekstensi): JPEG, PNG, atau WEBP."""
    kepala = file.stream.read(12)
    file.stream.seek(0)
    return (kepala.startswith(b"\xff\xd8\xff")
            or kepala.startswith(b"\x89PNG\r\n\x1a\n")
            or (kepala[:4] == b"RIFF" and kepala[8:12] == b"WEBP"))


def simpan_foto(file, slug):
    """Simpan foto ke static/uploads/<slug>/ (dikecilkan otomatis) dan kembalikan path relatifnya."""
    if not file or not file.filename or "." not in file.filename:
        return None
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in EKSTENSI_OK or not gambar_valid(file):
        return None
    folder = os.path.join(UPLOAD_DIR, slug)
    os.makedirs(folder, exist_ok=True)
    nama = f"{secrets.token_hex(6)}.jpg"
    try:
        img = Image.open(file.stream)
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((1600, 1600))
        img.save(os.path.join(folder, nama), "JPEG", quality=85, optimize=True)
    except Exception:
        return None
    return f"uploads/{slug}/{nama}"


def ambil_form():
    data = {f: request.form.get(f, "").strip()[:BATAS.get(f, 200)] for f in FIELD_TEKS}
    if data["maps_url"] and not data["maps_url"].startswith(("http://", "https://")):
        data["maps_url"] = ""
    return data


def sama(a, b):
    return secrets.compare_digest(a.encode(), b.encode())


def _parse(v):
    try:
        return datetime.strptime(v, "%Y-%m-%dT%H:%M")
    except (ValueError, TypeError):
        return None


@app.template_filter("tgl_id")
def tgl_id(v):
    d = _parse(v)
    return f"{HARI[d.weekday()]}, {d.day} {BULAN[d.month - 1]} {d.year}" if d else ""

@app.template_filter("tgl_hari_bulan")
def tgl_hari_bulan(v):
    d = _parse(v)
    return f"{d.day:02d} {BULAN[d.month - 1][:3].upper()}" if d else ""


@app.template_filter("tgl_tahun")
def tgl_tahun(v):
    d = _parse(v)
    return str(d.year) if d else ""

@app.template_filter("wa_nomor")
def wa_nomor(v):
    """Ubah nomor telepon (08xx / +62xx) jadi format wa.me (62xx)."""
    d = re.sub(r"\D", "", v or "")
    if d.startswith("0"):
        d = "62" + d[1:]
    return d

@app.template_filter("sisa_hari")
def sisa_hari(v):
    """Jumlah hari menuju acara (0 jika sudah lewat atau tanggal belum diisi)."""
    d = _parse(v)
    return max(0, (d.date() - datetime.now().date()).days) if d else 0


@app.context_processor
def inject_bulan():
    return dict(BULAN=BULAN)

@app.template_filter("tgl_pendek")
def tgl_pendek(v):
    d = _parse(v)
    return f"{d.day:02d} . {d.month:02d} . {d.year}" if d else ""


def login_required(f):
    @wraps(f)
    def bungkus(*a, **kw):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*a, **kw)
    return bungkus


@app.after_request
def header_keamanan(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("X-Robots-Tag", "noindex, nofollow")  # undangan bersifat privat
    if request.path.startswith(("/admin", "/customer")):
        resp.headers["Referrer-Policy"] = "no-referrer"  # token tidak bocor lewat Referer
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.errorhandler(404)
def tidak_ada(e):
    return ("<h1 style='font-family:serif;text-align:center;margin-top:20vh'>"
            "Halaman tidak ditemukan</h1>"), 404


# ---------- Halaman publik ----------
@app.route("/")
def beranda():
    return redirect(url_for("admin_dashboard"))


@app.route("/u/<slug>")
def halaman_undangan(slug):
    """Satu link umum untuk semua tamu. Parameter ?to= dari link lama diabaikan."""
    db = get_db()
    u = db.execute("SELECT * FROM undangan WHERE slug = ?", (slug,)).fetchone()
    if u is None:
        abort(404)
    ucapan = db.execute(
        "SELECT nama, kehadiran, ucapan FROM rsvp "
        "WHERE undangan_id = ? AND ucapan != '' ORDER BY id DESC LIMIT 100",
        (u["id"],)).fetchall()
    galeri = [p for p in (u["galeri"] or "").split(",") if p]
    return render_template("undangan.html", u=u, ucapan=ucapan, galeri=galeri)


@app.route("/u/<slug>/rsvp", methods=["POST"])
def kirim_rsvp(slug):
    db = get_db()
    u = db.execute("SELECT id FROM undangan WHERE slug = ?", (slug,)).fetchone()
    if u is None:
        return jsonify(ok=False, pesan="Undangan tidak ditemukan."), 404
    d = request.get_json(silent=True) or {}
    if d.get("website"):  # honeypot: kolom tersembunyi hanya diisi bot
        return jsonify(ok=True, nama="", kehadiran="", ucapan="")

    kunci = f"rsvp:{slug}:{request.remote_addr}"
    if sudah_penuh(kunci, BATAS_RSVP[0], BATAS_RSVP[1]):
        return jsonify(ok=False, pesan="Terlalu banyak pengiriman. Coba lagi beberapa menit lagi."), 429

    nama = (d.get("nama") or "").strip()[:60]
    kehadiran = d.get("kehadiran")
    ucapan = (d.get("ucapan") or "").strip()[:500]
    try:
        jumlah = max(1, min(int(d.get("jumlah") or 1), 10))
    except (TypeError, ValueError):
        jumlah = 1
    if not nama:
        return jsonify(ok=False, pesan="Nama wajib diisi."), 400
    if kehadiran not in ("hadir", "tidak_hadir", "ragu", "ucapan"):
        return jsonify(ok=False, pesan="Pilih konfirmasi kehadiran."), 400
    if kehadiran == "ucapan" and not ucapan:
        return jsonify(ok=False, pesan="Ucapan wajib diisi."), 400

    db.execute(
        "INSERT INTO rsvp (undangan_id, nama, kehadiran, jumlah, ucapan) VALUES (?,?,?,?,?)",
        (u["id"], nama, kehadiran, jumlah, ucapan))
    db.commit()
    catat(kunci)
    return jsonify(ok=True, nama=nama, kehadiran=kehadiran, ucapan=ucapan)


# ---------- Dashboard customer (mempelai) ----------
def ringkasan(rows):
    return {
        "hadir": sum(1 for r in rows if r["kehadiran"] == "hadir"),
        "tidak": sum(1 for r in rows if r["kehadiran"] == "tidak_hadir"),
        "ragu": sum(1 for r in rows if r["kehadiran"] == "ragu"),
        "orang": sum(r["jumlah"] for r in rows if r["kehadiran"] == "hadir"),
        "ucapan": sum(1 for r in rows if r["ucapan"]),
        "total": len(rows),
    }


def aman_csv(v):
    """Cegah formula injection saat CSV dibuka di Excel."""
    v = "" if v is None else str(v)
    return "'" + v if v[:1] in ("=", "+", "-", "@") else v


def buat_csv(u, rows):
    label = {"hadir": "Hadir", "tidak_hadir": "Tidak hadir",
             "ragu": "Belum pasti", "ucapan": "Ucapan"}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Nama", "Status", "Jumlah", "Ucapan", "Waktu"])
    for r in rows:
        w.writerow([aman_csv(r["nama"]), label.get(r["kehadiran"], ""), r["jumlah"],
                    aman_csv(r["ucapan"]), r["dibuat"]])
    data = "\ufeff" + buf.getvalue()  # BOM agar Excel membaca UTF-8
    return Response(data, mimetype="text/csv; charset=utf-8", headers={
        "Content-Disposition": f"attachment; filename=rsvp-{u['slug']}.csv"})


@app.route("/customer/<slug>/<token>")
def customer_view(slug, token):
    db = get_db()
    u = db.execute(
        "SELECT * FROM undangan WHERE slug = ? AND customer_token = ?",
        (slug, token)).fetchone()
    if u is None:
        abort(404)
    rows = db.execute(
        "SELECT * FROM rsvp WHERE undangan_id = ? ORDER BY id DESC", (u["id"],)
    ).fetchall()
    base_url = url_for("halaman_undangan", slug=u["slug"], _external=True)
    export_url = url_for("customer_export", slug=u["slug"], token=token)
    return render_template("customer_dashboard.html", u=u, rows=rows,
                           ringkas=ringkasan(rows), base_url=base_url,
                           export_url=export_url)


@app.route("/customer/<slug>/<token>/export.csv")
def customer_export(slug, token):
    db = get_db()
    u = db.execute(
        "SELECT * FROM undangan WHERE slug = ? AND customer_token = ?",
        (slug, token)).fetchone()
    if u is None:
        abort(404)
    rows = db.execute(
        "SELECT * FROM rsvp WHERE undangan_id = ? ORDER BY id DESC", (u["id"],)).fetchall()
    return buat_csv(u, rows)


# ---------- Admin (superadmin / kamu) ----------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        kunci = f"login:{request.remote_addr}"
        if sudah_penuh(kunci, 5, 300):
            flash("Terlalu banyak percobaan. Coba lagi dalam 5 menit.")
            return render_template("admin_login.html"), 429
        user_ok = sama(request.form.get("username", ""), ADMIN_USER)
        pass_ok = check_password_hash(ADMIN_PASS_HASH, request.form.get("password", ""))
        if user_ok and pass_ok:
            session.clear()
            session["admin"] = True
            session.permanent = True
            return redirect(url_for("admin_dashboard"))
        catat(kunci)
        flash("Username atau password salah.")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@login_required
def admin_dashboard():
    daftar = get_db().execute(
        "SELECT u.*, "
        "(SELECT COUNT(*) FROM rsvp r WHERE r.undangan_id = u.id) AS total_rsvp, "
        "(SELECT COALESCE(SUM(r.jumlah), 0) FROM rsvp r "
        " WHERE r.undangan_id = u.id AND r.kehadiran = 'hadir') AS total_hadir "
        "FROM undangan u ORDER BY u.id DESC").fetchall()
    total = {
        "undangan": len(daftar),
        "rsvp": sum(d["total_rsvp"] for d in daftar),
        "hadir": sum(d["total_hadir"] for d in daftar),
    }
    return render_template("admin_dashboard.html", daftar=daftar, total=total)


@app.route("/admin/baru", methods=["GET", "POST"])
@login_required
def admin_baru():
    if request.method == "POST":
        db = get_db()
        slug = slugify(request.form.get("slug", ""))
        if not slug:
            flash("Slug tidak valid.")
            return render_template("admin_form.html", u=request.form, mode="baru")
        if db.execute("SELECT 1 FROM undangan WHERE slug = ?", (slug,)).fetchone():
            flash("Slug sudah dipakai, gunakan yang lain.")
            return render_template("admin_form.html", u=request.form, mode="baru")

        data = ambil_form()
        data["slug"] = slug
        data["customer_token"] = secrets.token_urlsafe(16)  # 128 bit acak
        data["foto_cover"] = simpan_foto(request.files.get("foto_cover"), slug)
        data["foto_pria"] = simpan_foto(request.files.get("foto_pria"), slug)
        data["foto_wanita"] = simpan_foto(request.files.get("foto_wanita"), slug)
        data["galeri"] = ",".join(
            p for p in (simpan_foto(f, slug) for f in request.files.getlist("galeri")) if p)

        kolom = list(data.keys())
        db.execute(
            f"INSERT INTO undangan ({', '.join(kolom)}) VALUES ({', '.join('?' * len(kolom))})",
            [data[k] for k in kolom])
        db.commit()
        flash("Undangan berhasil dibuat.")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_form.html", u={}, mode="baru")


@app.route("/admin/<int:uid>/edit", methods=["GET", "POST"])
@login_required
def admin_edit(uid):
    db = get_db()
    u = db.execute("SELECT * FROM undangan WHERE id = ?", (uid,)).fetchone()
    if u is None:
        abort(404)
    if request.method == "POST":
        data = ambil_form()
        for kolom in ("foto_cover", "foto_pria", "foto_wanita"):
            baru = simpan_foto(request.files.get(kolom), u["slug"])
            data[kolom] = baru or u[kolom]
        galeri = [] if request.form.get("hapus_galeri") else \
            [p for p in (u["galeri"] or "").split(",") if p]
        galeri += [p for p in (simpan_foto(f, u["slug"])
                               for f in request.files.getlist("galeri")) if p]
        data["galeri"] = ",".join(galeri)
        set_sql = ", ".join(f"{k} = ?" for k in data)
        db.execute(f"UPDATE undangan SET {set_sql} WHERE id = ?", [*data.values(), uid])
        db.commit()
        flash("Perubahan disimpan.")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_form.html", u=u, mode="edit")


@app.route("/admin/<int:uid>")
@login_required
def admin_detail(uid):
    db = get_db()
    u = db.execute("SELECT * FROM undangan WHERE id = ?", (uid,)).fetchone()
    if u is None:
        abort(404)
    rows = db.execute("SELECT * FROM rsvp WHERE undangan_id = ? ORDER BY id DESC", (uid,)).fetchall()
    base_url = url_for("halaman_undangan", slug=u["slug"], _external=True)
    customer_url = url_for("customer_view", slug=u["slug"], token=u["customer_token"], _external=True)
    return render_template("admin_detail.html", u=u, rows=rows, ringkas=ringkasan(rows),
                           base_url=base_url, customer_url=customer_url)


@app.route("/admin/<int:uid>/export.csv")
@login_required
def admin_export(uid):
    db = get_db()
    u = db.execute("SELECT * FROM undangan WHERE id = ?", (uid,)).fetchone()
    if u is None:
        abort(404)
    rows = db.execute("SELECT * FROM rsvp WHERE undangan_id = ? ORDER BY id DESC", (uid,)).fetchall()
    return buat_csv(u, rows)


@app.route("/admin/<int:uid>/rsvp/<int:rid>/hapus", methods=["POST"])
@login_required
def admin_hapus_rsvp(uid, rid):
    """Hapus satu konfirmasi atau ucapan (misalnya spam)."""
    db = get_db()
    db.execute("DELETE FROM rsvp WHERE id = ? AND undangan_id = ?", (rid, uid))
    db.commit()
    flash("Data konfirmasi dihapus.")
    return redirect(url_for("admin_detail", uid=uid))


@app.route("/admin/<int:uid>/token-baru", methods=["POST"])
@login_required
def admin_token_baru(uid):
    """Buat ulang link customer (misalnya jika link lama bocor)."""
    db = get_db()
    if db.execute("SELECT 1 FROM undangan WHERE id = ?", (uid,)).fetchone() is None:
        abort(404)
    db.execute("UPDATE undangan SET customer_token = ? WHERE id = ?",
               (secrets.token_urlsafe(16), uid))
    db.commit()
    flash("Link customer dibuat ulang. Link lama sudah tidak berlaku.")
    return redirect(url_for("admin_detail", uid=uid))


@app.route("/admin/<int:uid>/hapus", methods=["POST"])
@login_required
def admin_hapus(uid):
    db = get_db()
    u = db.execute("SELECT slug FROM undangan WHERE id = ?", (uid,)).fetchone()
    if u:
        db.execute("DELETE FROM rsvp WHERE undangan_id = ?", (uid,))
        db.execute("DELETE FROM undangan WHERE id = ?", (uid,))
        db.commit()
        shutil.rmtree(os.path.join(UPLOAD_DIR, u["slug"]), ignore_errors=True)
    flash("Undangan dihapus.")
    return redirect(url_for("admin_dashboard"))


init_db()

if __name__ == "__main__":
    # Mode debug hanya lewat FLASK_DEBUG=1 dan dikunci ke localhost
    # (debugger Werkzeug berbahaya bila terbuka di jaringan).
    # Untuk menguji dari HP di WiFi yang sama: jalankan tanpa FLASK_DEBUG.
    debug = os.environ.get("FLASK_DEBUG") == "1"
    host = "127.0.0.1" if debug else os.environ.get("HOST", "0.0.0.0")
    app.run(debug=debug, host=host, port=5000)
