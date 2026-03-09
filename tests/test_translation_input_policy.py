from pathlib import Path

from interface import interface_tradutor_final as ui


class _DummyPrepareWindow:
    _auto_prepare_translation_after_extraction = ui.MainWindow._auto_prepare_translation_after_extraction
    _infer_crc32_from_filename = ui.MainWindow._infer_crc32_from_filename

    def __init__(self, stage_dir: Path, extracted_file: Path, crc: str):
        self.stage_dir = str(stage_dir)
        self.current_output_dir = str(stage_dir.parent)
        self.current_rom_crc32 = crc
        self.extracted_file = str(extracted_file)
        self.optimized_file = None
        self._advanced_jsonl_confirmed_path = "stale-value"
        self._auto_prepared_extracted_path = ""
        self.logs: list[str] = []
        self.update_called = False

    def _maybe_auto_run_runtime_dyn_after_extraction(self, _path: str):
        return None

    def _get_stage_dir(self, stage: str, output_dir: str | None = None):
        if stage == "extracao":
            return self.stage_dir
        return None

    def _update_action_states(self):
        self.update_called = True

    def log(self, message: str):
        self.logs.append(str(message))


class _DummyAdvancedConfirmWindow:
    _is_advanced_jsonl_input = ui.MainWindow._is_advanced_jsonl_input
    _normalize_path_key = ui.MainWindow._normalize_path_key
    _is_advanced_jsonl_confirmed = ui.MainWindow._is_advanced_jsonl_confirmed
    _confirm_advanced_jsonl_translation = ui.MainWindow._confirm_advanced_jsonl_translation
    _resolve_tilemap_jsonl_for_translation = ui.MainWindow._resolve_tilemap_jsonl_for_translation

    def __init__(self):
        self._advanced_jsonl_confirmed_path = ""
        self.logs: list[str] = []

    def tr(self, key: str) -> str:
        return key

    def log(self, message: str):
        self.logs.append(str(message))


class _DummyQualityGateWindow:
    _parse_optional_int_gate = ui.MainWindow._parse_optional_int_gate
    _normalize_for_match = ui.MainWindow._normalize_for_match
    _get_translation_gate_min_ratio = ui.MainWindow._get_translation_gate_min_ratio
    _find_companion_translated_txt_for_gate = ui.MainWindow._find_companion_translated_txt_for_gate
    _compute_translation_completion_gate = ui.MainWindow._compute_translation_completion_gate
    _evaluate_reinsertion_preflight_gate = ui.MainWindow._evaluate_reinsertion_preflight_gate

    def __init__(self):
        self._translation_coverage_cache = {}
        self.current_rom_crc32 = "DE9F8517"
        self.current_output_dir = None
        self.translated_file = None
        self.translation_source_path: str | None = None
        self.logs: list[str] = []

    def log(self, message: str):
        self.logs.append(str(message))

    def tr(self, key: str) -> str:
        return key

    def _resolve_crc_root_from_path(self, _file_path: str):
        return None

    def _get_stage_dir(self, _stage: str, _output_dir: str | None = None):
        return None

    def _infer_crc32_from_filename(self, _file_path: str):
        return "DE9F8517"

    def _translated_file_matches_current_rom(self, _file_path: str):
        return True, "DE9F8517"

    def _rom_requires_jsonl_reinsert(self):
        return True

    def _compute_jsonl_reinsertion_coverage_gate(self, _translated_jsonl_path: str):
        return {
            "pure_jsonl_path": "dummy",
            "expected_safe_total": 3,
            "translated_total": 3,
            "matched_total": 3,
            "coverage_ratio": 1.0,
        }

    def _find_translation_source_txt_for_gate(self, _translated_path: str):
        return self.translation_source_path


def test_auto_prepare_prefere_safe_e_promove_para_optimized(tmp_path: Path):
    crc = "DE9F8517"
    stage_dir = tmp_path / "1_extracao"
    stage_dir.mkdir(parents=True, exist_ok=True)

    pure_jsonl = stage_dir / f"{crc}_pure_text.jsonl"
    pure_jsonl.write_text('{"type":"meta"}\n', encoding="utf-8")

    safe_txt = stage_dir / f"{crc}_only_safe_text.txt"
    safe_txt.write_text("Linha segura 1\nLinha segura 2\n", encoding="utf-8")

    dummy = _DummyPrepareWindow(stage_dir=stage_dir, extracted_file=pure_jsonl, crc=crc)
    dummy._auto_prepare_translation_after_extraction()

    expected_optimized = stage_dir / f"{crc}_pure_text_optimized.txt"
    assert dummy.update_called is True
    assert dummy.optimized_file == str(expected_optimized)
    assert expected_optimized.exists()
    assert expected_optimized.read_text(encoding="utf-8") == safe_txt.read_text(encoding="utf-8")
    assert dummy._advanced_jsonl_confirmed_path == ""


def test_auto_prepare_fallback_jsonl_quando_nao_ha_safe(tmp_path: Path):
    crc = "DE9F8517"
    stage_dir = tmp_path / "1_extracao"
    stage_dir.mkdir(parents=True, exist_ok=True)

    pure_jsonl = stage_dir / f"{crc}_pure_text.jsonl"
    pure_jsonl.write_text('{"type":"meta"}\n', encoding="utf-8")

    dummy = _DummyPrepareWindow(stage_dir=stage_dir, extracted_file=pure_jsonl, crc=crc)
    dummy._auto_prepare_translation_after_extraction()

    assert dummy.optimized_file == str(pure_jsonl)
    assert any("fallback bruto" in msg.lower() for msg in dummy.logs)


def test_jsonl_direto_exige_allow_advanced(tmp_path: Path):
    dummy = _DummyAdvancedConfirmWindow()
    jsonl_path = tmp_path / "input_pure_text.jsonl"
    jsonl_path.write_text("{}\n", encoding="utf-8")
    txt_path = tmp_path / "input_pure_text_optimized.txt"
    txt_path.write_text("ok\n", encoding="utf-8")

    assert dummy._resolve_tilemap_jsonl_for_translation(str(jsonl_path), allow_advanced=False) is None
    assert dummy._resolve_tilemap_jsonl_for_translation(str(txt_path), allow_advanced=True) is None
    assert dummy._resolve_tilemap_jsonl_for_translation(str(jsonl_path), allow_advanced=True) == str(jsonl_path)


def test_confirmacao_jsonl_sem_confirmar_bloqueia(monkeypatch, tmp_path: Path):
    dummy = _DummyAdvancedConfirmWindow()
    jsonl_path = str((tmp_path / "DE9F8517_pure_text.jsonl").resolve())

    monkeypatch.setattr(
        ui.QMessageBox,
        "warning",
        lambda *args, **kwargs: ui.QMessageBox.StandardButton.No,
    )

    assert dummy._confirm_advanced_jsonl_translation(jsonl_path) is False
    assert dummy._advanced_jsonl_confirmed_path == ""


def test_confirmacao_jsonl_com_confirmacao_permite(monkeypatch, tmp_path: Path):
    dummy = _DummyAdvancedConfirmWindow()
    jsonl_path = str((tmp_path / "DE9F8517_pure_text.jsonl").resolve())

    monkeypatch.setattr(
        ui.QMessageBox,
        "warning",
        lambda *args, **kwargs: ui.QMessageBox.StandardButton.Yes,
    )

    assert dummy._confirm_advanced_jsonl_translation(jsonl_path) is True
    assert dummy._advanced_jsonl_confirmed_path == dummy._normalize_path_key(jsonl_path)
    assert any("jsonl direto confirmado" in msg.lower() for msg in dummy.logs)


def test_translation_completion_gate_jsonl_detecta_unchanged_e_missing(tmp_path: Path):
    dummy = _DummyQualityGateWindow()
    translated_jsonl = tmp_path / "DE9F8517_translated.jsonl"
    translated_jsonl.write_text(
        "\n".join(
            [
                '{"type":"meta","rom_crc32":"DE9F8517","rom_size":524288}',
                '{"id":1,"offset":"0x000001","text_src":"Hello","text_dst":"Ola","reinsertion_safe":true}',
                '{"id":2,"offset":"0x000002","text_src":"World","text_dst":"World","reinsertion_safe":true}',
                '{"id":3,"offset":"0x000003","text_src":"Bye","text_dst":"","reinsertion_safe":true}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    info = dummy._compute_translation_completion_gate(str(translated_jsonl), write_report=False)
    assert info["mode"] == "jsonl"
    assert info["total_candidates"] == 3
    assert info["effective_translated"] == 1
    assert info["unchanged"] == 1
    assert info["missing"] == 1
    assert info["pending"] == 2
    assert round(float(info["ratio"]), 4) == round(1 / 3, 4)


def test_reinsertion_gate_bloqueia_quando_traducao_abaixo_de_100(tmp_path: Path):
    dummy = _DummyQualityGateWindow()
    translated_jsonl = tmp_path / "DE9F8517_translated.jsonl"
    translated_jsonl.write_text(
        "\n".join(
            [
                '{"type":"meta","rom_crc32":"DE9F8517","rom_size":524288}',
                '{"id":1,"offset":"0x000001","text_src":"Hello","text_dst":"Ola","reinsertion_safe":true}',
                '{"id":2,"offset":"0x000002","text_src":"World","text_dst":"World","reinsertion_safe":true}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    ok, reason = dummy._evaluate_reinsertion_preflight_gate(str(translated_jsonl))
    assert ok is False
    assert "Cobertura efetiva" in reason


def test_reinsertion_gate_libera_quando_traducao_atinge_100(tmp_path: Path):
    dummy = _DummyQualityGateWindow()
    translated_jsonl = tmp_path / "DE9F8517_translated.jsonl"
    translated_jsonl.write_text(
        "\n".join(
            [
                '{"type":"meta","rom_crc32":"DE9F8517","rom_size":524288}',
                '{"id":1,"offset":"0x000001","text_src":"Hello","text_dst":"Ola","reinsertion_safe":true}',
                '{"id":2,"offset":"0x000002","text_src":"World","text_dst":"Mundo","reinsertion_safe":true}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    ok, reason = dummy._evaluate_reinsertion_preflight_gate(str(translated_jsonl))
    assert ok is True
    assert reason == ""


def test_translation_completion_gate_ignora_nomes_proprios_na_cobertura(tmp_path: Path):
    dummy = _DummyQualityGateWindow()
    translated_jsonl = tmp_path / "DE9F8517_translated.jsonl"
    translated_jsonl.write_text(
        "\n".join(
            [
                '{"type":"meta","rom_crc32":"DE9F8517","rom_size":524288}',
                '{"id":1,"offset":"0x000001","text_src":"KARAMEIKOS","text_dst":"KARAMEIKOS","reinsertion_safe":true}',
                '{"id":2,"offset":"0x000002","text_src":"a ranger","text_dst":"a ranger","reinsertion_safe":true}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    info = dummy._compute_translation_completion_gate(str(translated_jsonl), write_report=False)
    assert info["non_translatable_skipped"] == 1
    assert info["total_candidates"] == 1
    assert info["pending"] == 1


def test_translation_completion_gate_ignora_fontes_tecnicas_jsonl(tmp_path: Path):
    dummy = _DummyQualityGateWindow()
    translated_jsonl = tmp_path / "DE9F8517_translated.jsonl"
    translated_jsonl.write_text(
        "\n".join(
            [
                '{"type":"meta","rom_crc32":"DE9F8517","rom_size":524288}',
                '{"id":1,"offset":"0x000001","text_src":"a ranger","text_dst":"um patrulheiro","reinsertion_safe":true,"source":"POINTER"}',
                '{"id":2,"offset":"0x000002","text_src":"Ta ranger","text_dst":"Ta ranger","reinsertion_safe":true,"source":"SCRIPT_OPCODE_AUTO"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    info = dummy._compute_translation_completion_gate(str(translated_jsonl), write_report=False)
    assert info["total_candidates"] == 1
    assert info["effective_translated"] == 1
    assert info["pending"] == 0
    assert info["non_translatable_skipped"] == 1


def test_reinsertion_gate_jsonl_usa_txt_companheiro_para_cobertura(tmp_path: Path):
    dummy = _DummyQualityGateWindow()
    source_txt = tmp_path / "DE9F8517_pure_text_optimized.txt"
    source_txt.write_text("a ranger\n", encoding="utf-8")
    dummy.translation_source_path = str(source_txt)

    translated_txt = tmp_path / "DE9F8517_pure_text_translated.txt"
    translated_txt.write_text("um patrulheiro\n", encoding="utf-8")

    translated_jsonl = tmp_path / "DE9F8517_translated.jsonl"
    translated_jsonl.write_text(
        "\n".join(
            [
                '{"type":"meta","rom_crc32":"DE9F8517","rom_size":524288}',
                '{"id":1,"offset":"0x000001","text_src":"a ranger","text_dst":"a ranger","reinsertion_safe":true,"source":"POINTER"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    ok, reason = dummy._evaluate_reinsertion_preflight_gate(str(translated_jsonl))
    assert ok is True
    assert reason == ""
