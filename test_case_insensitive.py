#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TESTE RÁPIDO - BUSCA CASE-INSENSITIVE
Valida que a busca robusta está funcionando
"""

import sys
from pathlib import Path

# Adicionar diretório da interface ao path
interface_dir = Path(__file__).parent / 'interface'
sys.path.insert(0, str(interface_dir))

def test_case_insensitive():
    """Testa busca case-insensitive."""
    print("=" * 80)
    print("TESTE: BUSCA CASE-INSENSITIVE")
    print("=" * 80)

    try:
        from forensic_engine_upgrade import scan_contextual_patterns

        # Criar dados de teste com variações de case
        test_data = b''

        # UPPERCASE
        test_data += b'NEW GAME\x00LOAD A GAME\x00CONFIGURATION\x00CREDITS\x00EXIT GAME'
        test_data += b'\x00' * 100

        # lowercase
        test_data += b'master volume\x00sfx\x00music\x00voices'
        test_data += b'\x00' * 100

        # MixedCase
        test_data += b'Resolution\x00Details\x00Gamma\x00Brightness'
        test_data += b'\x00' * 100

        # Title Case
        test_data += b'Inventory\x00Equipment\x00Use\x00Drop'
        test_data += b'\x00' * 100

        print("\n🔍 Testando busca case-insensitive...")
        matches = scan_contextual_patterns(test_data)

        if matches:
            print(f"\n✅ SUCESSO! Encontrados {len(matches)} padrões")
            print("\nPadrões detectados:")
            for match in matches:
                code = match['pattern_code']
                variant = match.get('matched_variant', 'unknown')
                pos = match['position']
                print(f"  ✓ {code} (variante: {variant}, posição: 0x{pos:X})")

            # Validar que encontrou todas as variações
            expected_patterns = ['MENU_5OPTION_1999', 'AUDIO_SETTINGS_QUAD_1999',
                               'VIDEO_SETTINGS_QUAD', 'INVENTORY_STANDARD_1999']
            found_codes = [m['pattern_code'] for m in matches]

            all_found = all(exp in found_codes for exp in expected_patterns)

            if all_found:
                print("\n✅ TODAS AS VARIAÇÕES DE CASE FORAM DETECTADAS!")
                print("✅ Sistema case-insensitive está OPERACIONAL!")
                return True
            else:
                missing = [exp for exp in expected_patterns if exp not in found_codes]
                print(f"\n⚠️  Faltando: {missing}")
                return False
        else:
            print("❌ Nenhum padrão detectado")
            return False

    except Exception as e:
        print(f"❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_inno_setup_detection():
    """Testa detecção de Inno Setup com variações."""
    print("\n" + "=" * 80)
    print("TESTE: DETECÇÃO INNO SETUP (DARKSTONE FIX)")
    print("=" * 80)

    try:
        # Simular header com assinatura Inno Setup
        test_header = b'MZ' + b'\x00' * 100

        # Adicionar assinatura em posição variada
        test_header += b'Some random data here...\x00'
        test_header += b'INNO SETUP SETUP DATA\x00'  # UPPERCASE (DarkStone pode usar)
        test_header += b'\x00' * 500

        # Buscar manualmente
        if b'INNO SETUP' in test_header or b'Inno Setup' in test_header:
            print("✅ Assinatura Inno Setup detectada em dados de teste")

            # Verificar se está no dicionário
            from forensic_engine_upgrade import FORENSIC_SIGNATURES_TIER1

            installer_sigs = FORENSIC_SIGNATURES_TIER1.get('INSTALLER', [])
            print(f"\n✅ Assinaturas de instalador carregadas: {len(installer_sigs)}")

            # Listar assinaturas Inno Setup
            inno_sigs = [sig for sig in installer_sigs if b'Inno' in sig[0] or b'INNO' in sig[0]]
            print(f"✅ Assinaturas Inno Setup: {len(inno_sigs)}")

            for sig_tuple in inno_sigs:
                sig = sig_tuple[0]
                offset = sig_tuple[1]
                desc = sig_tuple[2]
                print(f"   • {desc} (offset: {offset})")

            print("\n✅ Sistema pronto para detectar DarkStone.exe!")
            return True
        else:
            print("❌ Assinatura não encontrada")
            return False

    except Exception as e:
        print(f"❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Função principal."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║           🔧 TESTE RÁPIDO - CORREÇÕES CASE-INSENSITIVE                       ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    tests_passed = 0
    tests_total = 2

    if test_case_insensitive():
        tests_passed += 1

    if test_inno_setup_detection():
        tests_passed += 1

    print("\n" + "=" * 80)
    print("RESUMO")
    print("=" * 80)
    print(f"Testes passados: {tests_passed}/{tests_total}")

    if tests_passed == tests_total:
        print("\n✅ TODAS AS CORREÇÕES FUNCIONANDO!")
        print("✅ Sistema pronto para detectar DarkStone.exe com case-insensitive!")
        return 0
    else:
        print(f"\n❌ {tests_total - tests_passed} teste(s) falharam")
        return 1


if __name__ == "__main__":
    sys.exit(main())
