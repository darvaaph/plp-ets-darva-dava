# Log Penggunaan AI

Catat setiap penggunaan AI atau coding agent yang memengaruhi kode atau laporan.

| No | Siapa | Prompt / tugas (ringkas) | Hasil: diterima, diubah, atau ditolak | Alasan | Cara verifikasi |
| --- | --- | --- | --- | --- | --- |
| 1 | Darva | Memahami arsitektur pipeline *Crafting Interpreters*, menganalisis kegagalan awal pytest, serta mengidentifikasi gejala dan akar masalah 8 bug tersembunyi. | Diterima dengan modifikasi | Alur pembagian kerja disesuaikan menjadi pair programming bertahap (Driver & Navigator) dengan branch Git terpisah. | Menjalankan `python -m pytest` (5 failed baseline), mengecek output AST pada `data/sample/audit.sql --ast`, dan mencocokkan dengan `SPESIFIKASI.md`. |
| 2 | Dava | Tahap observasi Jam ke-1: memastikan posisi branch `dava_plp`, lalu memverifikasi gejala Bug 5-8 langsung dari kode sebelum menyentuh perbaikan apa pun; menulis draf laporan Bug 5-8 ke `docs/LAPORAN_BUG.md`. | Diterima | Gejala keempat bug dibuktikan dengan eksekusi kode, bukan tebakan, supaya laporan bisa dipertahankan saat demo individual. | Menjalankan `tokenize()` pada query `<>`, `python -m crud.cli data/sample/campuran_error.sql`, resolve pola subquery `data/sample/audit.sql` baris 12-14, dan `analyze_statement()` pada UPDATE; lalu dicocokkan dengan SPESIFIKASI.md bagian 2.5, 4.3, 5, dan 6. |

**Refleksi (3-5 kalimat).** (Akan diisi di akhir Jam ke-6 setelah seluruh evaluasi selesai).
