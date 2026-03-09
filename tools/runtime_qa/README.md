# Runtime QA Universal

Módulo opcional para:

1. `AutoProbe` guiado por seeds do `{CRC32}_pure_text.jsonl` (sem scan cego).
2. `Runtime Trace + Autoplay` com artefatos auditáveis.
3. Captura dinâmica por `NameTable/VRAM` (BizHawk) com reconstrução via tilemap/fontmap.
4. Diff de cobertura `runtime_texts vs static_only_safe_text_by_offset`.
5. Integração com QA existente via `runtime_qa_step.py`.

## Scripts principais

- `generate_probe_bizhawk.py`
- `generate_trace_autoplay_bizhawk.py`
- `generate_dyn_capture_bizhawk.py`
- `generate_probe_libretro.py`
- `generate_trace_autoplay_libretro.py`
- `analyze_probe_hits.py`
- `runtime_qa_step.py`
- `dyn_text_pipeline.py`

## Fluxo rápido (exemplo)

1. Gerar probe:
   - BizHawk: `python tools/runtime_qa/generate_probe_bizhawk.py --pure-jsonl ...`
   - Libretro: `python tools/runtime_qa/generate_probe_libretro.py --pure-jsonl ... --core-path ... --rom-path ...`
2. Executar script gerado e obter `{CRC32}_probe_hits.jsonl`.
3. Analisar hits:
   - `python tools/runtime_qa/analyze_probe_hits.py --probe-hits ...`
4. Gerar trace+autoplay:
   - BizHawk: `python tools/runtime_qa/generate_trace_autoplay_bizhawk.py --pure-jsonl ... --hook-profile ...`
   - Libretro: `python tools/runtime_qa/generate_trace_autoplay_libretro.py --pure-jsonl ... --hook-profile ... --core-path ... --rom-path ...`
5. Executar script gerado e obter `{CRC32}_runtime_trace.jsonl`.
6. Integrar RuntimeQA:
   - `python tools/runtime_qa/runtime_qa_step.py --runtime-trace ... --translated-jsonl ... --mapping-json ...`

## Captura dinâmica (BizHawk)

1. Gerar script Lua dinâmico:
   - `python tools/runtime_qa/generate_dyn_capture_bizhawk.py --pure-jsonl ... --fontmap-json ...`
   - `fontmap-json` recomendado: `glyph_hash(FNV-1a 32 dos 32 bytes do tile) -> char`
2. Executar no EmuHawk e gerar:
   - `{CRC32}_dyn_text_log_raw*.jsonl`
3. Pós-processar e gerar artefatos finais:
   - `{CRC32}_dyn_text_log.jsonl`
   - `{CRC32}_dyn_text_unique.txt`
   - `{CRC32}_coverage_diff_report.txt`
   - listas `missing_from_runtime` e `missing_from_static`
   - `{CRC32}_dyn_fontmap_bootstrap.json` (hashes desconhecidos para bootstrap)
   - `{CRC32}_unknown_glyphs.jsonl` (hash + exemplos de contexto/pattern)
   - `{CRC32}_unknown_glyphs.png` (grade 8x8 dos tiles desconhecidos)

## Rodadas de mapeamento manual (novo)

Para reduzir rapidamente `?` no runtime-dyn, use o assistente de rodadas:

```powershell
python tools/runtime_qa/dyn_fontmap_rounds.py `
  --bootstrap "C:\...\DE9F8517_dyn_fontmap_bootstrap.json" `
  --dyn-unique "C:\...\DE9F8517_dyn_text_unique.txt" `
  --dyn-log "C:\...\DE9F8517_dyn_text_log.jsonl" `
  --mapping-json "C:\...\DE9F8517_dyn_fontmap_round_template_top100.json" `
  --top-n 100 `
  --template-top-n 100
```

Saídas principais:
- `{CRC32}_dyn_fontmap_top{N}.csv` (priorização por hits + contexto + pattern + grupo)
- `{CRC32}_dyn_fontmap_groups_top{N}.csv` (clusters de similaridade/duplicatas)
- `{CRC32}_dyn_fontmap_round_template_top{N}.json` (template para preencher)
- `{CRC32}_dyn_text_unique_preview.txt` (preview parcial com mapeamento aplicado)
- `{CRC32}_dyn_fontmap_round_report.json` (métricas: resolvidos/faltando/cobertura por hits)

## Saídas

- `{CRC32}_runtime_displayed_text_trace.jsonl`
- `{CRC32}_runtime_missing_displayed_text.jsonl`
- `{CRC32}_runtime_coverage_summary.json`
- `{CRC32}_dyn_text_log.jsonl`
- `{CRC32}_dyn_text_unique.txt`
- `{CRC32}_unknown_glyphs.jsonl`
- `{CRC32}_unknown_glyphs.png`
- `{CRC32}_coverage_diff_report.txt`
- Injeção opcional de bloco `RUNTIME_TRACE` em `proof/report`.

## Execução no Windows (EmuHawk)

Use o orquestrador com caminho já configurado do EmuHawk:

```powershell
python tools/runtime_qa/ui_orchestrator.py `
  --mode max `
  --runner bizhawk `
  --path-emuhawk "C:\...\BizHawk-2.11-win-x64\EmuHawk.exe" `
  --rom "C:\...\game.sms" `
  --pure-jsonl "C:\...\DE9F8517_pure_text.jsonl" `
  --translated-jsonl "C:\...\DE9F8517_translated_fixed_ptbr.jsonl" `
  --mapping-json "C:\...\DE9F8517_reinsertion_mapping.json" `
  --runtime-dir "C:\...\DE9F8517\runtime" `
  --runtime-dyn-enabled 1 `
  --runtime-dyn-input-explorer 1 `
  --runtime-dyn-savestate-bfs 1 `
  --runtime-dyn-fontmap-json "C:\...\fontmap_glyph_hash_to_char.json" `
  --runtime-static-only-safe-by-offset "C:\...\DE9F8517_only_safe_text_by_offset.txt"
```
