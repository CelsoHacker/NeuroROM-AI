from pathlib import Path

from core.auto_text_auditor import AutoTextAuditor


def _write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_auto_text_auditor_gera_artefatos_e_remove_lixo(tmp_path: Path):
    crc = "DE9F8517"
    by_offset = tmp_path / f"{crc}_only_safe_text_by_offset.txt"
    _write_lines(
        by_offset,
        [
            "[0x001000] Hello there",
            "[0x001010] Ko&",
            "[0x001020] Chn.Mail",
            "[0x001030] Oh... please...",
            "[0x001040] Hello there",
        ],
    )

    auditor = AutoTextAuditor(purity_min_score=95, keep_suspects=False)
    result = auditor.audit(by_offset_path=str(by_offset), stage_dir=str(tmp_path), crc32=crc)

    assert Path(result["report_json_path"]).exists()
    assert Path(result["report_txt_path"]).exists()
    assert Path(result["suspects_path"]).exists()
    assert Path(result["errors_path"]).exists()
    assert Path(result["pure_path"]).exists()

    pure_lines = Path(result["pure_path"]).read_text(encoding="utf-8").splitlines()
    assert "Hello there" in pure_lines
    assert "Oh... please..." in pure_lines
    assert "Ko&" not in pure_lines
    assert "Chn.Mail" not in pure_lines
    assert result["error"] >= 1
    assert result["suspect"] >= 1
    assert result["duplicate_text_removed"] >= 1


def test_auto_text_auditor_keep_suspects_preserva_linhas_duvidosas(tmp_path: Path):
    crc = "DE9F8517"
    by_offset = tmp_path / f"{crc}_only_safe_text_by_offset.txt"
    _write_lines(
        by_offset,
        [
            "[0x001000] Chn.Mail",
            "[0x001010] Mys.Robe",
            "[0x001020] Axe 'n Ale",
        ],
    )

    auditor = AutoTextAuditor(
        purity_min_score=70,
        keep_suspects=True,
        fail_on_suspect=False,
    )
    result = auditor.audit(by_offset_path=str(by_offset), stage_dir=str(tmp_path), crc32=crc)

    pure_lines = Path(result["pure_path"]).read_text(encoding="utf-8").splitlines()
    assert "Chn.Mail" in pure_lines
    assert "Mys.Robe" in pure_lines
    assert "Axe 'n Ale" in pure_lines
    assert result["suspect"] >= 2
    assert result["error"] == 0
    assert result["passed"] is True


def test_auto_text_auditor_score_e_pass_consistentes(tmp_path: Path):
    crc = "DE9F8517"
    by_offset = tmp_path / f"{crc}_only_safe_text_by_offset.txt"
    _write_lines(
        by_offset,
        [
            "[0x001000] Lord British",
            "[0x001010] Oh... please...",
            "[0x001020] Energy type?",
        ],
    )

    auditor = AutoTextAuditor(purity_min_score=98, keep_suspects=False)
    result = auditor.audit(by_offset_path=str(by_offset), stage_dir=str(tmp_path), crc32=crc)

    assert result["error"] == 0
    assert result["suspect"] == 0
    assert result["purity_score"] == 100
    assert result["passed"] is True


def test_auto_text_auditor_marca_fragmento_caps_como_suspeito(tmp_path: Path):
    crc = "DE9F8517"
    by_offset = tmp_path / f"{crc}_only_safe_text_by_offset.txt"
    _write_lines(
        by_offset,
        [
            "[0x001000] GEOFFREY",
            "[0x001010] OFFREY",
            "[0x001020] ENUS",
            "[0x001030] NAME",
        ],
    )

    auditor = AutoTextAuditor(purity_min_score=90, keep_suspects=False)
    result = auditor.audit(by_offset_path=str(by_offset), stage_dir=str(tmp_path), crc32=crc)

    pure_lines = Path(result["pure_path"]).read_text(encoding="utf-8").splitlines()
    assert "GEOFFREY" in pure_lines
    assert "NAME" in pure_lines
    assert "OFFREY" not in pure_lines
    assert "ENUS" not in pure_lines
    assert result["suspect"] >= 2


def test_auto_text_auditor_falha_quando_suspeito_e_modo_estrito(tmp_path: Path):
    crc = "DE9F8517"
    by_offset = tmp_path / f"{crc}_only_safe_text_by_offset.txt"
    _write_lines(
        by_offset,
        [
            "[0x001000] Chn.Mail",
            "[0x001010] Lord British",
        ],
    )

    auditor_strict = AutoTextAuditor(
        purity_min_score=90,
        keep_suspects=False,
        fail_on_suspect=True,
    )
    strict_result = auditor_strict.audit(
        by_offset_path=str(by_offset), stage_dir=str(tmp_path), crc32=crc
    )
    assert strict_result["suspect"] >= 1
    assert strict_result["passed"] is False
    assert strict_result["fail_reason"] == "suspects_present"

    auditor_lenient = AutoTextAuditor(
        purity_min_score=50,
        keep_suspects=False,
        fail_on_suspect=False,
    )
    lenient_result = auditor_lenient.audit(
        by_offset_path=str(by_offset), stage_dir=str(tmp_path), crc32=crc
    )
    assert lenient_result["passed"] is True


def test_auto_text_auditor_bloqueia_padroes_estranhos_de_tabela(tmp_path: Path):
    crc = "DE9F8517"
    by_offset = tmp_path / f"{crc}_only_safe_text_by_offset.txt"
    _write_lines(
        by_offset,
        [
            "[0x001000] I J",
            "[0x001010] ABCDE H",
            "[0x001020] FIREBALL A F",
            "[0x001030] XIYiJZj",
            "[0x001040] Lord British",
        ],
    )

    auditor = AutoTextAuditor(
        purity_min_score=90,
        keep_suspects=False,
        fail_on_suspect=True,
    )
    result = auditor.audit(by_offset_path=str(by_offset), stage_dir=str(tmp_path), crc32=crc)

    pure_lines = Path(result["pure_path"]).read_text(encoding="utf-8").splitlines()
    assert "Lord British" in pure_lines
    assert "I J" not in pure_lines
    assert "ABCDE H" not in pure_lines
    assert "FIREBALL A F" not in pure_lines
    assert "XIYiJZj" not in pure_lines
    assert (int(result["suspect"]) + int(result["error"])) >= 4
    assert result["passed"] is False


def test_auto_text_auditor_repara_fragmento_de_prefixo_com_rom(tmp_path: Path):
    crc = "DE9F8517"
    by_offset = tmp_path / f"{crc}_only_safe_text_by_offset.txt"
    _write_lines(
        by_offset,
        [
            "[0x000101] CK PEARL",
            "[0x000120] Lord British",
        ],
    )

    rom = bytearray(b"\x00" * 0x1200)
    rom[0x100:0x10B] = b"BLACK PEARL"
    rom[0x10B] = 0x00
    rom_path = tmp_path / "test.sms"
    rom_path.write_bytes(bytes(rom))

    auditor = AutoTextAuditor(
        purity_min_score=90,
        keep_suspects=False,
        fail_on_suspect=False,
    )
    result = auditor.audit(
        by_offset_path=str(by_offset),
        stage_dir=str(tmp_path),
        crc32=crc,
        rom_path=str(rom_path),
    )

    pure_lines = Path(result["pure_path"]).read_text(encoding="utf-8").splitlines()
    assert "BLACK PEARL" in pure_lines
    assert "CK PEARL" not in pure_lines
    assert int(result["prefix_repaired"]) >= 1


def test_auto_text_auditor_remove_fragmentos_duros_e_repara_prefixo_caps(tmp_path: Path):
    crc = "DE9F8517"
    by_offset = tmp_path / f"{crc}_only_safe_text_by_offset.txt"
    _write_lines(
        by_offset,
        [
            "[0x001001] !shonest",
            "[0x001020] HOriginal version by",
            "[0x001040] s would you like to sell?",
            "[0x001064] ITUALITY OM",
            "[0x001080] Lord British",
        ],
    )

    rom = bytearray(b"\x00" * 0x1200)
    rom[0x1060:0x106F] = b"SPIRITUALITY OM"
    rom[0x106F] = 0x00
    rom_path = tmp_path / "test.sms"
    rom_path.write_bytes(bytes(rom))

    auditor = AutoTextAuditor(
        purity_min_score=90,
        keep_suspects=False,
        fail_on_suspect=False,
    )
    result = auditor.audit(
        by_offset_path=str(by_offset),
        stage_dir=str(tmp_path),
        crc32=crc,
        rom_path=str(rom_path),
    )

    pure_lines = Path(result["pure_path"]).read_text(encoding="utf-8").splitlines()
    assert "Lord British" in pure_lines
    assert "Original version by" in pure_lines
    assert "SPIRITUALITY OM" in pure_lines
    assert "!shonest" not in pure_lines
    assert "s would you like to sell?" not in pure_lines
    assert int(result["prefix_repaired"]) >= 1
