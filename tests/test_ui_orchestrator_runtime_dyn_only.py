from pathlib import Path

from tools.runtime_qa import ui_orchestrator


def test_run_orchestrator_runtime_dyn_only_skips_probe_and_uses_runtime_dyn_dir(
    tmp_path: Path, monkeypatch
):
    rom_path = tmp_path / "game.sms"
    rom_path.write_bytes(b"\x00\x01")
    pure_jsonl = tmp_path / "DE9F8517_pure_text.jsonl"
    pure_jsonl.write_text('{"type":"meta","rom_crc32":"DE9F8517","rom_size":2}\n', encoding="utf-8")
    emuhawk = tmp_path / "EmuHawk.exe"
    emuhawk.write_text("stub", encoding="utf-8")

    dyn_called_runtime_dirs: list[Path] = []
    log_lines: list[str] = []

    def _probe_should_not_run(*_args, **_kwargs):
        raise AssertionError("AutoProbe não deveria ser executado em runtime-dyn-only.")

    def _fake_dyn_capture(*_args, **kwargs):
        out_dir = Path(kwargs["runtime_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        dyn_called_runtime_dirs.append(out_dir)
        dyn_log = out_dir / "DE9F8517_dyn_text_log_raw_dyn.jsonl"
        dyn_log.write_text('{"type":"meta"}\n', encoding="utf-8")
        return {
            "dyn_capture_script_path": str(out_dir / "DE9F8517_dyn_capture_dyn.lua"),
            "dyn_capture_config_path": str(out_dir / "DE9F8517_runtime_dyn_capture_config.json"),
            "dyn_text_log_path": str(dyn_log),
        }

    monkeypatch.setattr(ui_orchestrator, "_run_probe_bizhawk", _probe_should_not_run)
    monkeypatch.setattr(ui_orchestrator, "_run_probe_libretro", _probe_should_not_run)
    monkeypatch.setattr(ui_orchestrator, "_run_dyn_capture_bizhawk", _fake_dyn_capture)
    monkeypatch.setattr(ui_orchestrator, "discover_static_only_safe_by_offset", lambda **_kwargs: None)
    monkeypatch.setattr(
        ui_orchestrator,
        "process_dynamic_capture",
        lambda **_kwargs: {
            "dyn_text_log_path": _kwargs["dyn_log_input_path"],
            "dyn_text_unique_path": str(Path(_kwargs["out_dir"]) / "DE9F8517_dyn_text_unique.txt"),
            "fontmap_bootstrap_path": "",
            "unknown_glyphs_jsonl_path": "",
            "unknown_glyphs_png_path": "",
            "coverage": {},
        },
    )
    monkeypatch.setattr(ui_orchestrator, "compute_crc32", lambda _path: "DE9F8517")

    result = ui_orchestrator.run_orchestrator(
        mode="auto",
        rom_path=rom_path,
        pure_jsonl=pure_jsonl,
        translated_jsonl=tmp_path / "missing_translated.jsonl",
        mapping_json=tmp_path / "missing_mapping.json",
        runtime_dir=tmp_path / "runtime",
        report_txt=None,
        proof_json=None,
        report_json=None,
        path_emuhawk=emuhawk,
        libretro_runner=None,
        libretro_core=None,
        timeout_probe_s=60,
        timeout_trace_s=60,
        runtime_scenarios_enabled=[],
        max_iterations=1,
        plateau_rounds=1,
        runner_mode="bizhawk",
        platform_hint="master_system",
        runtime_dyn_enabled=True,
        runtime_dyn_only=True,
        runtime_dyn_fontmap_json=None,
        runtime_dyn_input_explorer=False,
        runtime_dyn_savestate_bfs=False,
        runtime_static_only_safe_by_offset=None,
        logger=lambda _msg: log_lines.append(str(_msg)),
    )

    assert dyn_called_runtime_dirs, "dyn_capture não foi executado."
    assert dyn_called_runtime_dirs[0].name == "2_runtime_dyn"
    assert result["status"] == "PASS"
    assert str(result["runtime_dyn_dir"]).endswith("2_runtime_dyn")
    assert "_dyn_text_" in str(result["artifacts"]["dyn_text_log"])
    assert any("dyn capture finished" in line for line in log_lines)
    assert any("postprocess finished" in line for line in log_lines)
    assert any(str((tmp_path / "runtime" / "2_runtime_dyn").resolve()) in line for line in log_lines)
