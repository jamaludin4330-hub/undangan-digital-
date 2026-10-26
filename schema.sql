CREATE TABLE IF NOT EXISTS undangan (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT UNIQUE NOT NULL,
  customer_token TEXT UNIQUE,
  panggilan_pria TEXT, panggilan_wanita TEXT,
  nama_pria TEXT, nama_wanita TEXT,
  ortu_pria TEXT, ortu_wanita TEXT,
  tanggal_acara TEXT,
  akad_tempat TEXT, akad_alamat TEXT, akad_waktu TEXT,
  resepsi_tempat TEXT, resepsi_alamat TEXT, resepsi_waktu TEXT,
  maps_url TEXT,
  kutipan TEXT, sumber_kutipan TEXT,
  kalimat_pembuka TEXT, kalimat_rsvp TEXT, kalimat_hadiah TEXT, kalimat_penutup TEXT,
  bank TEXT, no_rekening TEXT, atas_nama TEXT,
  foto_cover TEXT, foto_pria TEXT, foto_wanita TEXT, galeri TEXT,
  dibuat TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rsvp (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  undangan_id INTEGER NOT NULL,
  nama TEXT NOT NULL,
  kehadiran TEXT NOT NULL,
  jumlah INTEGER DEFAULT 1,
  ucapan TEXT DEFAULT '',
  dibuat TEXT DEFAULT CURRENT_TIMESTAMP
);