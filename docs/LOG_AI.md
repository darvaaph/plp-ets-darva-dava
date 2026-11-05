# Log Penggunaan AI

Catat setiap penggunaan AI atau coding agent yang memengaruhi kode atau laporan.

| No | Siapa | Prompt / tugas (ringkas) | Hasil: diterima, diubah, atau ditolak | Alasan | Cara verifikasi |
| --- | --- | --- | --- | --- | --- |
| 1 | Darva | Memahami arsitektur pipeline *Crafting Interpreters*, menganalisis kegagalan awal pytest, serta mengidentifikasi gejala dan akar masalah 8 bug tersembunyi. | Diterima dengan modifikasi | Alur pembagian kerja disesuaikan menjadi pair programming bertahap (Driver & Navigator) dengan branch Git terpisah. | Menjalankan `python -m pytest` (5 failed baseline), mengecek output AST pada `data/sample/audit.sql --ast`, dan mencocokkan dengan `SPESIFIKASI.md`. |

**Refleksi (3-5 kalimat).** (Akan diisi di akhir Jam ke-6 setelah seluruh evaluasi selesai).
