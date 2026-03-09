from core.final_qa import evaluate_reinsertion_qa


def _base_kwargs():
    return {
        "console": "SMS",
        "rom_crc32": "DE9F8517",
        "rom_size": 524288,
        "stats": {"TRUNC": 0, "BLOCKED": 0},
        "checks": {"input_match": True, "ordering": True, "emulator_smoke": True},
        "limitations": [],
        "compression_policy": {"mode": "none"},
        "translation_input": {"path": "x.jsonl"},
        "require_manual_emulator": False,
    }


def test_qa_visual_gate_fails_when_displayed_skip_or_english_residual():
    kwargs = _base_kwargs()
    kwargs["evidence"] = {
        "not_translated_count": 0,
        "same_as_source_phrase_count": 0,
        "english_likely_count": 0,
        "rom_vs_translated_mismatch_count": 0,
        "placeholder_fail_count": 0,
        "terminator_missing_count": 0,
        "suspicious_non_pt_count": 0,
        "unchanged_equal_src_count": 0,
        "displayed_trace_skip_displayed_count": 2,
        "displayed_trace_english_residual_count": 1,
    }

    qa = evaluate_reinsertion_qa(**kwargs)

    assert qa["overall_pass"] is False
    assert "displayed_trace_skip_displayed_zero" in qa["required_failed"]
    assert "displayed_trace_english_residual_zero" in qa["required_failed"]


def test_qa_visual_gate_passes_when_visual_counts_are_zero():
    kwargs = _base_kwargs()
    kwargs["evidence"] = {
        "not_translated_count": 0,
        "same_as_source_phrase_count": 0,
        "english_likely_count": 0,
        "rom_vs_translated_mismatch_count": 0,
        "placeholder_fail_count": 0,
        "terminator_missing_count": 0,
        "suspicious_non_pt_count": 0,
        "unchanged_equal_src_count": 0,
        "displayed_trace_skip_displayed_count": 0,
        "displayed_trace_english_residual_count": 0,
    }

    qa = evaluate_reinsertion_qa(**kwargs)

    assert qa["overall_pass"] is True
    assert "displayed_trace_skip_displayed_zero" not in qa["required_failed"]
    assert "displayed_trace_english_residual_zero" not in qa["required_failed"]
