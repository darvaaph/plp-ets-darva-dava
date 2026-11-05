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
from crud.analyzer import analyze_statement


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