/* =====================================================
   main.js - Interaksi undangan digital
   ===================================================== */
(function () {
  "use strict";

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var kurangGerak = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var cover = $("#cover");
  var btnBuka = $("#btn-buka");
  var audio = $("#musik");
  var btnMusik = $("#btn-musik");
  var sudahBuka = false;

  /* ---------- Pecah teks jadi huruf untuk animasi bertahap ---------- */
  function siapkanAnimasiHuruf() {
    $$("[data-anim-huruf]").forEach(function (el) {
      var teks = el.textContent;
      el.textContent = "";
      teks.split("").forEach(function (huruf, i) {
        var span = document.createElement("span");
        span.className = "huruf";
        span.style.transitionDelay = (i * 35) + "ms";
        span.textContent = huruf === " " ? "\u00A0" : huruf;
        el.appendChild(span);
      });
    });
  }

  /* ---------- Muncul saat scroll (berurutan lewat --urut di CSS) ---------- */
  function mulaiReveal() {
    var items = $$(".muncul, .fade");
    if (!("IntersectionObserver" in window)) {
      items.forEach(function (el) { el.classList.add("tampak"); });
      $$(".huruf").forEach(function (el) { el.classList.add("tampak"); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add("tampak");
          $$(".huruf", e.target).forEach(function (h) { h.classList.add("tampak"); });
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.15, rootMargin: "0px 0px -6% 0px" });
    items.forEach(function (el) { io.observe(el); });

    // Elemen huruf yang tidak berada di dalam .muncul (misal cover) dipicu langsung
    $$("[data-anim-huruf]:not(.muncul)").forEach(function (el) {
      $$(".huruf", el).forEach(function (h) { h.classList.add("tampak"); });
    });
  }

  /* ---------- Musik ---------- */
  var musikSedangMain = false;
  var jedaOtomatis = false;

  function sembunyikanMusik() {
    if (btnMusik) btnMusik.style.display = "none";
  }

  function putarMusik() {
    if (!audio) return;
    audio.volume = 0.7;
    var p = audio.play();
    if (p && p.catch) {
      p.catch(function (err) {
        if (err && err.name === "NotSupportedError") sembunyikanMusik();
      });
    }
  }

  if (audio) {
    audio.addEventListener("play", function () {
      musikSedangMain = true;
      if (btnMusik) btnMusik.classList.add("main");
    });
    audio.addEventListener("pause", function () {
      musikSedangMain = false;
      if (btnMusik) btnMusik.classList.remove("main");
    });
    var sumber = $("source", audio);
    if (sumber) sumber.addEventListener("error", sembunyikanMusik);
  }

  if (btnMusik) {
    btnMusik.addEventListener("click", function () {
      if (!audio) return;
      if (musikSedangMain) audio.pause(); else putarMusik();
    });
  }

  document.addEventListener("visibilitychange", function () {
    if (!audio || !sudahBuka) return;
    if (document.hidden && musikSedangMain) {
      jedaOtomatis = true;
      audio.pause();
    } else if (!document.hidden && jedaOtomatis) {
      jedaOtomatis = false;
      putarMusik();
    }
  });

  /* ---------- Kelopak jatuh (dikurung di #kelopak-area) ---------- */
  function mulaiKelopak() {
    if (kurangGerak) return;
    var area = document.getElementById("kelopak-area") || document.body;
    var jumlah = window.innerWidth < 600 ? 10 : 16;
    for (var i = 0; i < jumlah; i++) {
      var k = document.createElement("span");
      var ukuran = 10 + Math.random() * 10;
      k.className = "kelopak";
      k.setAttribute("aria-hidden", "true");
      k.style.width = ukuran + "px";
      k.style.height = ukuran * 1.3 + "px";
      k.style.left = Math.random() * 100 + "%";
      k.style.animationDuration = 10 + Math.random() * 9 + "s";
      k.style.animationDelay = Math.random() * 9 + "s";
      k.style.setProperty("--geser", (Math.random() * 180 - 90) + "px");
      area.appendChild(k);
    }
  }

  /* ---------- Buka undangan (versi sederhana, tanpa gerbang) ---------- */
  function bukaUndangan() {
    if (sudahBuka) return;
    sudahBuka = true;
    cover.classList.add("terbuka");
    cover.setAttribute("aria-hidden", "true");
    document.body.classList.remove("terkunci");
    window.scrollTo(0, 0);
    if (btnMusik) btnMusik.style.display = "flex";
    putarMusik();
    setTimeout(mulaiReveal, 300);
    setTimeout(mulaiKelopak, 500);
  }
  if (btnBuka) btnBuka.addEventListener("click", bukaUndangan);

  /* ---------- Navigasi aktif mengikuti scroll ---------- */
  var tautan = $$("#nav-melayang a");
  function setAktif(id) {
    tautan.forEach(function (a) {
      a.classList.toggle("aktif", a.getAttribute("href") === "#" + id);
    });
  }
  if ("IntersectionObserver" in window) {
    var ioNav = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) setAktif(e.target.id); });
    }, { rootMargin: "-45% 0px -45% 0px" });
    tautan.forEach(function (a) {
      var s = $(a.getAttribute("href"));
      if (s) ioNav.observe(s);
    });
  }
  tautan.forEach(function (a) {
    a.addEventListener("click", function () { setAktif(a.getAttribute("href").slice(1)); });
  });
  setAktif("beranda");

  /* ---------- Paralaks latar ---------- */
  var menunggu = false;
  window.addEventListener("scroll", function () {
    if (menunggu || kurangGerak) return;
    menunggu = true;
    window.requestAnimationFrame(function () {
      document.documentElement.style.setProperty("--py", String(window.scrollY));
      menunggu = false;
    });
  }, { passive: true });

  /* ---------- Hitung mundur ---------- */
  var hitung = $("#hitung");
  if (hitung && hitung.dataset.tanggal) {
    var target = new Date(hitung.dataset.tanggal).getTime();
    var el = {
      hari: $('[data-u="hari"]', hitung), jam: $('[data-u="jam"]', hitung),
      menit: $('[data-u="menit"]', hitung), detik: $('[data-u="detik"]', hitung)
    };
    var tick = function () {
      var s = Math.max(0, Math.floor((target - Date.now()) / 1000));
      if (isNaN(target)) s = 0;
      var judulHitung = $("#judul-hitung");
      if (judulHitung && !isNaN(target) && target <= Date.now()) {
        judulHitung.textContent = "Hari Bahagia Telah Tiba";
      }
      el.hari.textContent = Math.floor(s / 86400);
      el.jam.textContent = Math.floor((s % 86400) / 3600);
      el.menit.textContent = Math.floor((s % 3600) / 60);
      el.detik.textContent = s % 60;
    };
    tick();
    setInterval(tick, 1000);
  }

  /* ---------- Tombol hadiah ---------- */
  var btnGift = $("#btn-gift");
  var giftIsi = $("#gift-isi");
  if (btnGift && giftIsi) {
    btnGift.addEventListener("click", function () {
      var buka = giftIsi.classList.toggle("terbuka");
      btnGift.setAttribute("aria-expanded", String(buka));
      btnGift.textContent = buka ? "Sembunyikan Gift" : "Tampilkan Gift";
    });
  }

  /* ---------- Salin nomor rekening dan alamat kado ---------- */
  $$(".btn-salin").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var teks = btn.dataset.nomor || "";
      var selesai = function () {
        btn.classList.add("tersalin");
        setTimeout(function () { btn.classList.remove("tersalin"); }, 2000);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(teks).then(selesai, function () { salinCadangan(teks); selesai(); });
      } else {
        salinCadangan(teks);
        selesai();
      }
    });
  });
  function salinCadangan(teks) {
    var t = document.createElement("textarea");
    t.value = teks;
    t.style.position = "fixed";
    t.style.opacity = "0";
    document.body.appendChild(t);
    t.select();
    try { document.execCommand("copy"); } catch (e) { /* diabaikan */ }
    document.body.removeChild(t);
  }

  /* ---------- Simpan ke kalender (Google Calendar) ---------- */
  var btnKal = $("#btn-kalender");
  if (btnKal) {
    btnKal.addEventListener("click", function () {
      var mulai = new Date(btnKal.dataset.mulai);
      if (isNaN(mulai.getTime())) return;
      var selesai = new Date(mulai.getTime() + 4 * 3600 * 1000);
      var p = function (n) { return String(n).padStart(2, "0"); };
      var fmt = function (d) {
        return d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + "T" +
               p(d.getHours()) + p(d.getMinutes()) + "00";
      };
      var url = "https://calendar.google.com/calendar/render?action=TEMPLATE" +
        "&text=" + encodeURIComponent(btnKal.dataset.judul || "Pernikahan") +
        "&dates=" + fmt(mulai) + "/" + fmt(selesai) +
        "&location=" + encodeURIComponent(btnKal.dataset.lokasi || "");
      window.open(url, "_blank", "noopener");
    });
  }

  /* ---------- Lightbox galeri ---------- */
  var lightbox = $("#lightbox");
  if (lightbox) {
    var gambarBesar = $("img", lightbox);
    $$(".galeri img").forEach(function (img) {
      img.addEventListener("click", function () {
        gambarBesar.src = img.src;
        gambarBesar.alt = img.alt;
        lightbox.style.display = "flex";
      });
    });
    var tutup = function () { lightbox.style.display = "none"; gambarBesar.src = ""; };
    lightbox.addEventListener("click", tutup);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") tutup(); });
  }

  /* ---------- Kirim form (RSVP dan ucapan) ---------- */
  function kirim(form, payload, pesanEl, sukses) {
    var tombol = $('button[type="submit"]', form);
    var labelAwal = tombol.textContent;
    tombol.disabled = true;
    tombol.textContent = "Mengirim...";
    pesanEl.style.color = "";
    pesanEl.textContent = "";
    fetch(form.dataset.url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
      .then(function (res) {
        return res.json().then(function (d) { return { ok: res.ok && d.ok, d: d }; });
      })
      .then(function (r) {
        if (!r.ok) throw new Error((r.d && r.d.pesan) || "Gagal mengirim.");
        sukses(r.d);
      })
      .catch(function (err) {
        pesanEl.style.color = "#a33a40";
        pesanEl.textContent = err.message === "Failed to fetch"
          ? "Gagal mengirim. Periksa koneksi Anda dan coba lagi."
          : err.message;
      })
      .then(function () {
        tombol.textContent = labelAwal;
        setTimeout(function () { tombol.disabled = false; }, 3000);
      });
  }

  var formRsvp = $("#form-rsvp");
  if (formRsvp) {
    formRsvp.addEventListener("submit", function (e) {
      e.preventDefault();
      var f = formRsvp.elements;
      var pilih = $('input[name="kehadiran"]:checked', formRsvp);
      var pesan = $("#pesan-rsvp");
      if (!pilih) {
        pesan.style.color = "#a33a40";
        pesan.textContent = "Pilih konfirmasi kehadiran.";
        return;
      }
      kirim(formRsvp, {
        nama: f.nama.value, jumlah: f.jumlah.value,
        kehadiran: pilih.value, website: f.website.value
      }, pesan, function (d) {
        pesan.style.color = "";
        pesan.textContent = "Terima kasih, " + d.nama + ". Konfirmasi Anda sudah kami terima.";
        formRsvp.reset();
      });
    });
  }

  var formUcapan = $("#form-ucapan");
  if (formUcapan) {
    formUcapan.addEventListener("submit", function (e) {
      e.preventDefault();
      var f = formUcapan.elements;
      var pesan = $("#pesan-ucapan");
      kirim(formUcapan, {
        nama: f.nama.value, ucapan: f.ucapan.value,
        kehadiran: "ucapan", jumlah: 1, website: f.website.value
      }, pesan, function (d) {
        var kartu = document.createElement("article");
        kartu.className = "ucapan";
        var nama = document.createElement("strong");
        nama.textContent = d.nama;
        var isi = document.createElement("p");
        isi.textContent = d.ucapan;
        kartu.appendChild(nama);
        kartu.appendChild(isi);
        var daftar = $("#daftar-ucapan");
        daftar.insertBefore(kartu, daftar.firstChild);
        pesan.style.color = "";
        pesan.textContent = "Terima kasih atas ucapan dan doa Anda.";
        f.ucapan.value = "";
      });
    });
  }

  siapkanAnimasiHuruf();
})();