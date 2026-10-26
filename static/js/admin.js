/* =====================================================
   admin.js - Interaksi dashboard admin dan customer
   ===================================================== */
(function () {
  "use strict";

  /* ---------- Salin teks ke clipboard (tombol dengan data-salin) ---------- */
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

  document.querySelectorAll("[data-salin]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var teks = btn.dataset.salin;
      var awal = btn.dataset.label || btn.textContent;
      btn.dataset.label = awal;
      var selesai = function () {
        btn.textContent = "Tersalin";
        setTimeout(function () { btn.textContent = awal; }, 1800);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(teks).then(selesai, function () {
          salinCadangan(teks);
          selesai();
        });
      } else {
        salinCadangan(teks);
        selesai();
      }
    });
  });

  /* ---------- Tombol WhatsApp (data-wa berisi link undangan) ---------- */
  document.querySelectorAll("[data-wa]").forEach(function (a) {
    var pesan = "Dengan penuh sukacita, kami mengundang Anda ke pernikahan kami. " +
      "Detail acara ada pada undangan digital berikut:\n" + a.dataset.wa +
      "\n\nTerima kasih.";
    a.href = "https://wa.me/?text=" + encodeURIComponent(pesan);
  });

  /* ---------- Konfirmasi sebelum aksi berbahaya (data-konfirmasi) ---------- */
  document.querySelectorAll("form[data-konfirmasi]").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      if (!window.confirm(f.dataset.konfirmasi)) e.preventDefault();
    });
  });

  /* ---------- Filter tabel RSVP berdasarkan status ---------- */
  var tombolFilter = document.querySelectorAll(".filter button");
  var baris = document.querySelectorAll("#tabel-rsvp tbody tr[data-status]");
  var kosongFilter = document.getElementById("kosong-filter");
  tombolFilter.forEach(function (b) {
    b.addEventListener("click", function () {
      tombolFilter.forEach(function (x) { x.classList.remove("aktif"); });
      b.classList.add("aktif");
      var pilih = b.dataset.filter;
      var tampil = 0;
      baris.forEach(function (tr) {
        var cocok = pilih === "semua" || tr.dataset.status === pilih;
        tr.style.display = cocok ? "" : "none";
        if (cocok) tampil++;
      });
      if (kosongFilter) kosongFilter.style.display = tampil ? "none" : "block";
    });
  });
})();