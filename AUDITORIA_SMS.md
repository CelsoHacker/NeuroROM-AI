# Auditoria rapida - SMS (Master System)

## O que esta acontecendo
O erro **"UniversalMasterSystemExtractor ..."** aparece quando o Python esta
importando **uma versao errada** do modulo do extrator.

O motivo mais comum (especialmente no Windows) e quando existem arquivos
duplicados com extensao dupla, por exemplo:
- `MASTER_SYSTEM_UNIVERSAL_EXTRACTOR.py.py`
- `MASTER_SYSTEM_UNIVERSAL_EXTRACTOR_OLD.py.py`

Com a opcao "ocultar extensoes" ligada, esses arquivos parecem iguais no
Explorer, e acaba ficando facil substituir o arquivo errado.

## Arquivos que DEVEM existir no core
Mantenha somente:
- `core/MASTER_SYSTEM_UNIVERSAL_EXTRACTOR.py`
- `core/MASTER_SYSTEM_COMPLETE_DATABASE.py`

Pode deletar sem medo:
- qualquer `MASTER_SYSTEM_UNIVERSAL_EXTRACTOR*.py.py`
- qualquer `*_OLD*.py*`
- qualquer `*_API_COMPAT*.py*`
- a pasta `core/__pycache__` (isso e so cache compilado do Python)

## Como confirmar 100% (sem achismo)
Ao iniciar o sistema, o console vai mostrar:
- `[DEBUG] UniversalMasterSystemExtractor carregado de: ...`

Se o caminho apontar para o `core/MASTER_SYSTEM_UNIVERSAL_EXTRACTOR.py`, ta certo.

## Script de limpeza
Rode:
- `python tools/sms_cleanup.py`

Ele remove duplicados e o `__pycache__`.
