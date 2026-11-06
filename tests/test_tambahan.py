"""Test tambahan buatan kelompok.

Isi dengan:
1. Satu test regresi untuk setiap bug yang kalian perbaiki (gagal sebelum perbaikan,
   lulus sesudahnya). Beri nama yang menjelaskan bug-nya.
2. Lima test kasus tepi, masing-masing dengan komentar singkat mengapa kasus itu berisiko.
"""
import pytest
from crud.lexer import TokenType as T, tokenize
from crud.parser import parse_sql
from crud import ast_nodes as ast
from crud.resolver import Resolver
from crud.analyzer import analyze_statement, column_usage
from crud.cli import main


def test_regresi_bug1_keyword_huruf_kecil():
    toks = tokenize("select id from t where aktif = 1")
    assert toks[0].type == T.KEYWORD and toks[0].value == "SELECT"
    assert toks[2].type == T.KEYWORD and toks[2].value == "FROM"
    assert toks[4].type == T.KEYWORD and toks[4].value == "WHERE"
    
def test_regresi_bug2_escape_kutip_ganda_dalam_string():
    toks = tokenize("SELECT 'O''Brien' FROM t")
    assert toks[1].type == T.STRING and toks[1].value == "O'Brien"
    assert sum(t.type == T.STRING for t in toks) == 1
    
def test_regresi_bug3_and_lebih_kuat_dari_or():
    """SPESIFIKASI.md 3.1: a = 1 OR (b = 2 AND c = 3), bukan (a OR b) AND c."""
    script = parse_sql("SELECT id FROM t WHERE a = 1 OR b = 2 AND c = 3;")
    assert script.errors == [], script.errors
    where = script.statements[0].where
    assert where.op == "OR"            # OR jadi root (derajat terendah)
    assert where.right.op == "AND"     # kelompok AND jadi anak kanan OR
    assert where.left.op == "="        # a = 1 di kiri OR

def test_tepi_campuran_and_or_urutan_terbalik():
    """Kasus tepi: AND dulu baru OR - kelompok AND harus mengikat lebih erat
    di sisi kiri, bukan terbawa ke kanan. Risiko: salah menentukan sisi anak."""
    script = parse_sql("SELECT id FROM t WHERE a = 1 AND b = 2 OR c = 3;")
    where = script.statements[0].where
    assert where.op == "OR" and where.left.op == "AND" and where.right.op == "="
    
def test_regresi_bug4_alias_delete_tidak_bocor():
    """SPESIFIKASI.md 4.5: scope DELETE harus ditutup sebelum statement berikutnya.

    Sebelum perbaikan, 's.id' di SELECT kedua salah resolve ke 'sesi' warisan
    DELETE dan tidak ada diagnostic sama sekali.
    """
    script = parse_sql("DELETE FROM sesi s WHERE s.id = 1; SELECT s.id FROM pengguna u;")
    assert script.errors == []
    diags = Resolver().resolve_script(script)
    second = [c for c in ast.iter_nodes(script.statements[1])
              if isinstance(c, ast.ColumnRef)]
    assert second[0].resolved is None
    assert [d.level for d in diags] == ["error"]
    assert "'s'" in diags[0].message
    
def test_tepi_delete_dengan_subquery_tetap_resolve_alias_luar():
    """Kasus tepi: subquery di WHERE membuka/menutup scope sendiri, lalu alias
    DELETE harus tetap terlihat sesudahnya. Risiko: _pop() diletakkan terlalu awal."""
    script = parse_sql(
        "DELETE FROM sesi s "
        "WHERE s.id IN (SELECT p.sesi_id FROM pengguna p) AND s.aktif = 0;")
    diags = Resolver().resolve_script(script)
    cols = {(c.qualifier, c.name): c.resolved
            for c in ast.iter_nodes(script) if isinstance(c, ast.ColumnRef)}
    assert cols[("s", "id")] == "sesi"
    assert cols[("p", "sesi_id")] == "pengguna"
    assert cols[("s", "aktif")] == "sesi"
    assert diags == []

def test_regresi_bug5_operator_tidak_sama_dengan():
    toks = tokenize("SELECT id FROM t WHERE a <> 1")
    ops = [t.value for t in toks if t.type == T.OP]
    assert ops == ["<>"]

def test_regresi_bug6_panic_mode_lanjut_ke_statement_berikutnya():
    sql = """
    SELECT id FROM pelanggan;
    SELECT id nama, FROM pesanan;
    UPDATE produk SET stok = 1;
    """
    script = parse_sql(sql)
    assert len(script.errors) == 1
    assert len(script.statements) == 2

def test_regresi_bug7_shadowing_alias_subquery_menimpa_luar():
    """SPESIFIKASI.md 4.3: qualifier dicari dari scope terdalam ke luar (shadowing).

    Jika outer query dan inner subquery sama-sama memakai alias 'x',
    kolom di dalam subquery harus di-resolve ke tabel milik subquery (inner),
    bukan tabel milik outer query.
    """
    sql = """
    SELECT x.id FROM pelanggan x
    WHERE x.id IN (SELECT x.pelanggan_id FROM pesanan x WHERE x.total > 500000);
    """
    script = parse_sql(sql)
    assert script.errors == []
    diags = Resolver().resolve_script(script)
    assert diags == []

    cols = [c for c in ast.iter_nodes(script) if isinstance(c, ast.ColumnRef)]
    # Outer query: x.id -> pelanggan
    assert cols[0].resolved == "pelanggan"
    assert cols[1].resolved == "pelanggan"
    # Inner subquery: x.pelanggan_id dan x.total harus merujuk ke pesanan, bukan pelanggan
    assert cols[2].resolved == "pesanan"
    assert cols[3].resolved == "pesanan"
    
def test_regresi_bug8_subquery_update_dibaca_bukan_diubah():
    """SPESIFIKASI.md 5: subquery di UPDATE selalu R, target tetap U.

    Sebelum perbaikan, analyzer meneruskan op 'U' ke _collect() sehingga
    'pelanggan' di dalam subquery ikut dicap Update.
    """
    script = parse_sql(
        "UPDATE pesanan SET status = 'BATAL' "
        "WHERE pelanggan_id IN (SELECT id FROM pelanggan WHERE diblokir = 1);")
    assert script.errors == []
    assert analyze_statement(script.statements[0]) == {
        "pesanan": {"U"}, "pelanggan": {"R"}}
    
def test_tepi_subquery_di_set_update_dibaca():
    """Kasus tepi: subquery di SET juga wajib R dan berasal dari pemanggilan
    _collect() yang berbeda dari WHERE. Risiko: hanya satu jalur yang diperbaiki."""
    script = parse_sql(
        "UPDATE pesanan SET total = (SELECT SUM(total) FROM arsip) WHERE id = 1;")
    assert script.errors == []
    assert analyze_statement(script.statements[0]) == {
        "pesanan": {"U"}, "arsip": {"R"}}

def test_tepi_komentar_blok_berisi_bintang_dan_baris_baru():
    """Kasus tepi: komentar blok multi-baris yang memuat karakter '*' di dalamnya
    tidak boleh salah dianggap sebagai penutup komentar. Risiko: komentar tertutup prematur."""
    sql = "/* komentar * dengan * bintang \n dan baris baru **/ SELECT 1;"
    toks = tokenize(sql)
    assert toks[0].value == "SELECT" and toks[0].line == 2

def test_tepi_kolom_tanpa_qualifier_ambigu_dua_tabel():
    """Kasus tepi: kolom tanpa qualifier pada query dengan 2 tabel (JOIN)
    wajib menghasilkan warning 'ambigu tanpa skema' dan resolved tetap None.
    Risiko: resolver salah menebak atau mengabaikan ambiguitas."""
    script = parse_sql("SELECT id FROM pelanggan p JOIN pesanan o ON p.id = o.pelanggan_id;")
    diags = Resolver().resolve_script(script)
    col = [c for c in ast.iter_nodes(script.statements[0])
           if isinstance(c, ast.ColumnRef) and c.qualifier is None][0]
    assert col.resolved is None
    assert any("ambigu tanpa skema" in d.message for d in diags)

def test_regresi_bug9_left_outer_join():
    """SPESIFIKASI.md Bagian 3: join = [ "INNER" | "LEFT" [ "OUTER" ] ] "JOIN" ...
    Kata kunci OUTER bersifat opsional setelah LEFT dan tidak boleh menyebabkan ParseError.
    """
    sql = "SELECT c.id, a.kota FROM crm.pelanggan c LEFT OUTER JOIN crm.alamat a ON a.pelanggan_id = c.id;"
    script = parse_sql(sql)
    assert script.errors == [], script.errors
    stmt = script.statements[0]
    assert len(stmt.joins) == 1
    assert stmt.joins[0].kind == "LEFT"
    assert stmt.joins[0].source.name == "crm.alamat"
    assert stmt.joins[0].source.alias == "a"
    
def test_regresi_bug10_insert_select_berkurung():
    """SPESIFIKASI.md 3: INSERT ... (SELECT ...) adalah bentuk sah.

    Sebelum perbaikan, token '(' tertinggal sehingga parser melempar
    ParseError 'diharapkan VALUES atau SELECT, ditemukan '('.
    """
    script = parse_sql("INSERT INTO arsip (SELECT id, total FROM pesanan);")
    assert script.errors == []
    stmt = script.statements[0]
    assert stmt.columns == []
    assert stmt.query is not None


def test_regresi_bug10_insert_select_berkurung_dengan_kolom():
    """Varian kedua: kurung daftar kolom diikuti kurung subquery.

    Risiko: '(' kedua bisa dikira awal daftar kolom lagi.
    """
    script = parse_sql("INSERT INTO arsip (id, total) (SELECT id, total FROM pesanan);")
    assert script.errors == []
    stmt = script.statements[0]
    assert stmt.columns == ["id", "total"]
    assert stmt.query is not None

def test_regresi_bug11_cli_error_resolver_exit_code(tmp_path, capsys):
    """Error resolver harus membuat CLI keluar dengan kode 1.

    Sebelum perbaikan, diagnostik hanya dicetak ke stderr dan main()
    tetap mengembalikan 0.
    """
    path = tmp_path / "alias_salah.sql"
    path.write_text("SELECT s.id FROM pengguna u;", encoding="utf-8")
    code = main([str(path), "--out", str(tmp_path / "matrix.csv")])
    assert code == 1
    assert "tidak terdefinisi" in capsys.readouterr().err


def test_tepi_cli_warning_tetap_exit_code_nol(tmp_path):
    """Kasus tepi: warning ambigu bukan error fatal.

    Risiko: perbaikan terlalu kasar dengan menganggap semua diagnostics gagal.
    """
    path = tmp_path / "ambigu.sql"
    path.write_text("SELECT nama FROM pelanggan p, pesanan o;", encoding="utf-8")
    code = main([str(path), "--out", str(tmp_path / "matrix.csv")])
    assert code == 0


def test_tepi_column_usage_lengkap_semua_statement():
    """Kasus tepi: API publik column_usage(stmt) wajib mengembalikan triple
    (tabel, kolom, operasi) untuk seluruh jenis statement (SELECT, INSERT, UPDATE, DELETE)
    sesuai SPESIFIKASI.md bagian 7 dan 8.

    Risiko: jika resolver belum dijalankan atau ada node ekspresi yang terlewat,
    triple kolom yang dihasilkan tidak lengkap atau kolom tidak teresolusi.
    """
    # 1. SELECT dengan JOIN dan WHERE
    script_sel = parse_sql(
        "SELECT p.nama, o.total FROM pelanggan p JOIN pesanan o "
        "ON p.id = o.pelanggan_id WHERE p.aktif = 1;")
    Resolver().resolve_script(script_sel)
    cols_sel = column_usage(script_sel.statements[0])
    assert cols_sel == {
        ("pelanggan", "nama", "R"),
        ("pesanan", "total", "R"),
        ("pelanggan", "id", "R"),
        ("pesanan", "pelanggan_id", "R"),
        ("pelanggan", "aktif", "R"),
    }

    # 2. INSERT ... VALUES (kolom target adalah C)
    script_ins = parse_sql("INSERT INTO log (user_id, aksi) VALUES (1, 'login');")
    Resolver().resolve_script(script_ins)
    cols_ins = column_usage(script_ins.statements[0])
    assert cols_ins == {
        ("log", "user_id", "C"),
        ("log", "aksi", "C"),
    }

    # 3. UPDATE (kolom assignment adalah U, kolom di ekspresi & WHERE adalah R)
    script_upd = parse_sql(
        "UPDATE produk SET stok = stok - 1 WHERE id = 10 AND status = 'aktif';")
    Resolver().resolve_script(script_upd)
    cols_upd = column_usage(script_upd.statements[0])
    assert cols_upd == {
        ("produk", "stok", "U"),
        ("produk", "stok", "R"),
        ("produk", "id", "R"),
        ("produk", "status", "R"),
    }

    # 4. DELETE (kolom di WHERE adalah R)
    script_del = parse_sql("DELETE FROM sesi s WHERE s.kedaluwarsa < 1000;")
    Resolver().resolve_script(script_del)
    cols_del = column_usage(script_del.statements[0])
    assert cols_del == {
        ("sesi", "kedaluwarsa", "R"),
    }
