# Generalização de Qualidade para PS1/N64/SNES/GBA

## Escopo reutilizável já existente
- `core/semantic_quality_gate.py`: gate semântico por segmento (flags fortes, score e bloqueio).
- `core/qa_gate_runtime.py`: QA pós-tradução com:
  - checks técnicos/semânticos
  - `coverage_incomplete_false`
  - loop de saneamento semântico automático
- `core/safe_reinserter.py`: gate técnico + visual + linguístico + semântico, inventário por ROM e artifacts por CRC32.

## Camada de perfil adicionada
- `core/quality_profile_manager.py`:
  - resolução hierárquica de perfil
  - merge incremental: `default -> console -> family -> crc -> override`
  - normalização de `register_policy`, thresholds semânticos e glossary.

## Perfis-base adicionados
- `profiles/quality/default.json`
- `profiles/quality/consoles/ps1.json`
- `profiles/quality/consoles/n64.json`
- `profiles/quality/consoles/snes.json`
- `profiles/quality/consoles/gba.json`

## O que virou configurável por perfil
- política de registro (`register_policy`)
- thresholds semânticos (`min_semantic_score_standard/strict`)
- número de rounds de saneamento (`autofix_max_rounds`)
- glossário/nomes próprios por console/família/CRC

## Adaptações por console (incrementais)
- PS1/N64/GBA/SNES usam a mesma arquitetura de gates.
- Diferenças de vocabulário/termos fixos ficam em perfil (sem hardcode no núcleo).
- Ajustes específicos de jogo (nomes próprios, terminologia de UI) devem ir em:
  - `profiles/quality/families/<family>.json`
  - `profiles/quality/crc/<CRC32>.json`

## Compatibilidade preservada
- Sem renomear interfaces públicas.
- Fluxo atual continua válido quando perfil não existe (fallback seguro).
- Artifacts e checks permanecem padrão do núcleo:
  - inventário por ROM
  - `coverage_incomplete`
  - gates técnico/visual/linguístico/semântico
  - bloqueio real por segmento

