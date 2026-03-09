#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mini-teste manual para validar loader JSONL do sega_reinserter.
Uso: python tools/test_jsonl_loader.py [arquivo.jsonl]
"""
__test__ = False  # Evita coleta pelo pytest (arquivo é um tool manual)
import sys
import json
from pathlib import Path

# Adiciona core ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_jsonl_loader(jsonl_path: str):
    """Testa carregamento de JSONL traduzido."""
    path = Path(jsonl_path)
    if not path.exists():
        print(f"[ERRO] Arquivo não encontrado: {jsonl_path}")
        return False

    print(f"[INFO] Testando: {path.name}")
    print("=" * 60)

    # Carrega linhas brutas
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    lines = [l.strip() for l in lines if l.strip()]
    print(f"[INFO] Total de linhas: {len(lines)}")

    # Conta campos relevantes
    count_total = 0
    count_with_text_dst = 0
    count_with_id = 0
    loaded_keys = []

    for line in lines:
        try:
            obj = json.loads(line)
            count_total += 1

            if obj.get("text_dst"):
                count_with_text_dst += 1

            if obj.get("id") is not None:
                count_with_id += 1

            # Simula lógica do _load_jsonl
            text = (obj.get("text_dst") or obj.get("translation") or
                    obj.get("translated_text") or obj.get("translated") or
                    obj.get("text"))

            if isinstance(text, str) and text.strip():
                off = obj.get("offset", 0)
                if isinstance(off, str):
                    s = off.strip()
                    try:
                        off = int(s, 16) if s.lower().startswith("0x") else int(s)
                    except ValueError:
                        off = 0

                if obj.get("id") is not None:
                    key = str(obj["id"])
                else:
                    key = obj.get("key") or f"0x{off:X}"

                loaded_keys.append(key)

        except json.JSONDecodeError:
            continue

    print(f"[INFO] Entradas JSON válidas: {count_total}")
    print(f"[INFO] Com text_dst: {count_with_text_dst}")
    print(f"[INFO] Com id: {count_with_id}")
    print(f"[INFO] Traduções carregáveis: {len(loaded_keys)}")
    print()

    if loaded_keys:
        print("[INFO] Primeiras 5 chaves:")
        for k in loaded_keys[:5]:
            print(f"       - {k}")
    else:
        print("[WARN] Nenhuma tradução carregável encontrada!")
        print("[HINT] Verifique se o JSONL tem campos: text_dst, translation, translated_text, ou text")

    print("=" * 60)

    # Testa com o loader real
    try:
        from core.sega_reinserter import SegaReinserter

        class FakeReinserter(SegaReinserter):
            def __init__(self):
                self._core = None
                self.stats = {}

        fake = FakeReinserter()
        # Chama _load_jsonl diretamente
        from core.sega_reinserter import SegaMasterSystemReinserter
        fake._core = SegaMasterSystemReinserter()
        result = fake._load_jsonl(path)

        print(f"[TEST] Loader real retornou: {len(result)} traduções")
        if result:
            print("[OK] Loader funcionando corretamente!")
            return True
        else:
            print("[FAIL] Loader retornou vazio!")
            return False

    except Exception as e:
        print(f"[ERRO] Falha ao testar loader: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Tenta arquivo padrão
        default = Path(__file__).parent.parent / "core" / "953F42E1_translated.jsonl"
        if not default.exists():
            # Procura em outros lugares
            for p in Path(__file__).parent.parent.rglob("*_translated.jsonl"):
                default = p
                break

        if default.exists():
            test_jsonl_loader(str(default))
        else:
            print("Uso: python tools/test_jsonl_loader.py <arquivo.jsonl>")
            print("     ou coloque 953F42E1_translated.jsonl em core/")
    else:
        test_jsonl_loader(sys.argv[1])
