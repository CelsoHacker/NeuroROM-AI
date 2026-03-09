# RELATÓRIO DE AUDITORIA — ROM Translation Framework

Data: 29/01/2026  
Auditor: Codex (engenheiro sênior, QA e segurança)

## Visão geral
O projeto é funcional, porém não estava “vendável” por riscos críticos de reinserção (corromper ROM silenciosamente), ausência de modo estrito/dry‑run, falta de escrita atômica e ausência de relatório de reinserção. Também havia vazamento de chave de API em script de exemplo.

Status após hardening P0:
- Reinserção SMS agora valida limites, gera backups incrementais, grava de forma atômica, cria `reinsert_report.json`, oferece `--strict` e `--dry-run`.
- Vazamento de API key removido.
- Testes mínimos adicionados e pytest corrigido para rodar sem erros.

## Resultado de setup e execução
- Entry point: `main.py` (GUI).
- Requisitos: `requirements.txt` presente. Adicionado `requirements-dev.txt`.
- Python suportado: 3.10+ (documentado).
- Fluxo real validado (SMS):
  - ROM: `ROMs/Master System/Mickey.sms` (CRC32 953F42E1).
  - Reinserção via CLI gerou `Mickey_PTBR.sms`, backup `.bak` e relatório JSON.

## Linters / formatadores / type check
Executados conforme solicitado:
- **ruff**: falhou com muitos erros (inclui arquivos com sintaxe inválida, e.g. `audit_mapping_items_sms.py`).
- **black --check**: falhou (arquivos com sintaxe inválida + dezenas de arquivos desformatados).
- **isort --check-only**: falhou em dezenas de arquivos.
- **mypy**: falhou por erro de sintaxe em `core/translation_engine.py:117`.

Observação: há arquivos `*.py` com conteúdo que não é Python válido (ex.: here‑string de PowerShell), o que impede Black/Ruff/Mypy.

## Testes (pytest)
- `pytest -q`: **15 passed**, 5 warnings (funções de teste retornando `bool` em `tests/test_sms_relocation_v2.py`).

## Achados críticos (P0) — corrigidos
1) **Reinserção podia corromper ROM sem validações e sem escrita atômica**  
   - Arquivo: `core/sega_reinserter.py` (linhas ~258+, ~332+).  
   - Correções:
     - Validação de offset, max_len, terminator e ponteiros (`_validate_entry`).  
     - Truncagem padrão com aviso (e `--strict` para abortar).  
     - Escrita atômica, checksums e relatório JSON.  
   - Referência: `core/sega_reinserter.py:103`, `core/sega_reinserter.py:258`, `core/sega_reinserter.py:663`.

2) **Faltava backup incremental obrigatório**  
   - Correção: backups `.bak`, `.bak2...` via utilitário dedicado.  
   - Referência: `utils/rom_io.py:22`, `core/sega_reinserter.py:521`.

3) **Ausência de modo `--strict` e `--dry-run`**  
   - Correção: novos parâmetros no core e CLI.  
   - Referência: `core/sega_reinserter.py:258`, `tools/reinsert_sms_cli.py:32`.

4) **Vazamento de API key em script**  
   - Arquivo: `tools/dev_scripts/create_test_file.py:16`.  
   - Correção: substituído por placeholder `SUA_API_KEY_AQUI`.

5) **Reinserção com realocação (SMS) sem validações básicas**  
   - Arquivo: `core/sms_relocation_v1.py:358`.  
   - Correção: validações de offset/max_len/terminator e escrita atômica opcional.

## Achados P1 (melhorias importantes)
1) **Arquivos `.py` com sintaxe inválida quebram tooling**  
   - `audit_mapping_items_sms.py` (here‑string PowerShell).  
   - `core/translation_engine.py` (string literal inválida).  
   - Impacto: impede Black/Ruff/Mypy → custo alto de manutenção.

2) **Ferramentas que escrevem ROM sem hardening**  
   - `core/nes_injector_pro.py`, `core/sms_injector_pro.py`, `core/sms_patcher.py` ainda gravam sem backup/atômico/relatório.
   - Recomendação: aplicar `utils/rom_io.py` nesses fluxos.

3) **Logging excessivo e prints soltos**  
   - Muitos módulos com prints diretos; recomenda‑se log centralizado.

## Achados P2 (melhorias de qualidade)
1) **Warnings de pytest**  
   - `tests/test_sms_relocation_v2.py` retorna `bool` em testes.

2) **Style/Imports**  
   - Muitos arquivos fora de padrão (Black/Isort).

## Checklist “Vendável”
### A) Instalação e Execução
✅ README com passos básicos  
✅ requirements.txt presente  
✅ entrypoint (`main.py`)  
➕ `requirements-dev.txt` criado  
⚠️ CLI geral não existe; criada CLI específica para reinserção SMS

### B) Robustez e Integridade (crítico)
✅ Backup incremental automático  
✅ Checksums antes/depois  
✅ Validação de offsets / tamanho / terminator  
✅ Escrita atômica  
✅ `--dry-run` e `--strict`  
✅ Relatório `reinsert_report.json`

### C) Qualidade do Código
⚠️ Base grande e monolítica; refatoração necessária (P1/P2)

### D) Segurança e Privacidade
✅ Removido vazamento de API key em script  
⚠️ Documentos antigos exibem exemplos com chaves (placeholders)

### E) Performance
⚠️ Sem perfil geral; melhorias pontuais recomendadas (P2)

## Roadmap de correções
### P0 (bloqueadores) — concluído
- Hardening de reinserção SMS com backup, validações, checksums, escrita atômica, report, strict/dry‑run.
- Remoção de chave exposta.
- Testes mínimos de reinserção e correção do pytest.

### P1 (curto prazo: 1–2 semanas)
- Corrigir arquivos `.py` inválidos (ex.: `audit_mapping_items_sms.py`, `core/translation_engine.py`).
- Aplicar hardening em `nes_injector_pro.py`, `sms_injector_pro.py`, `sms_patcher.py`.
- Introduzir logger único e padronizar mensagens de erro.

### P2 (médio prazo: 3–6 semanas)
- Refatorar módulos monolíticos em camadas (extractors/reinserters/io/utils/cli).
- Padronizar código com Black/Isort e reduzir warnings do pytest.
- Tipagem gradual (mypy com baseline).

## Changelog (principais mudanças implementadas)
- Hardening de reinserção SMS (`core/sega_reinserter.py`).
- Utilitários de I/O de ROM (`utils/rom_io.py`).
- Hardening básico em `core/sms_relocation_v1.py`.
- CLI `tools/reinsert_sms_cli.py`.
- Testes `tests/test_sega_reinserter_hardening.py`.
- README atualizado e `requirements-dev.txt`.

## Conclusão
O projeto agora passa no critério crítico “não corromper ROM silenciosamente” para o fluxo SMS.  
Ainda não está 100% vendável para um público amplo enquanto houver arquivos inválidos e falta de padronização de linting, mas os bloqueadores P0 foram resolvidos.
