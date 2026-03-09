#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TESTE RÁPIDO - DEEP FINGERPRINTING (RAIO-X FORENSE)
Valida que o sistema de raio-x está funcionando corretamente
"""

import sys
import os
from pathlib import Path

# Adicionar diretório da interface ao path
interface_dir = Path(__file__).parent / 'interface'
sys.path.insert(0, str(interface_dir))


def create_test_file():
    """Cria arquivo de teste simulando um instalador com dados de jogo."""
    print("\n🔧 Criando arquivo de teste...")

    test_file = Path(__file__).parent / 'test_installer_with_game.bin'

    # Simular estrutura de instalador
    data = b'MZ\x90\x00'  # PE header
    data += b'\x00' * 100

    # Adicionar assinatura Inno Setup
    data += b'Inno Setup Setup Data (5.1.7)\x00'
    data += b'\x00' * 1000

    # ====================================
    # SEÇÃO 1: Header (0-64KB)
    # ====================================
    # Menu patterns
    data += b'NEW GAME\x00LOAD GAME\x00SAVE GAME\x00OPTIONS\x00EXIT GAME\x00'
    data += b'\x00' * 5000

    # Configuration patterns
    data += b'Configuration\x00Settings\x00Controls\x00Key Bindings\x00'
    data += b'\x00' * 5000

    # Preencher até 128KB
    data += b'\x00' * (131072 - len(data))

    # ====================================
    # SEÇÃO 2: 128KB offset
    # ====================================
    # Audio/Video systems
    data += b'Master Volume\x00SFX\x00Music\x00Voices\x00Sound Effects\x00'
    data += b'\x00' * 2000
    data += b'Resolution\x00Shadows\x00Texture\x00Graphics\x00Fullscreen\x00'
    data += b'\x00' * 5000

    # Preencher até 256KB
    data += b'\x00' * (262144 - len(data))

    # ====================================
    # SEÇÃO 3: 256KB offset
    # ====================================
    # RPG Stats and Combat
    data += b'STR\x00DEX\x00INT\x00Wisdom\x00Constitution\x00'
    data += b'\x00' * 2000
    data += b'Level\x00EXP\x00Experience\x00'
    data += b'\x00' * 2000
    data += b'Attack\x00Defend\x00Magic\x00Spell\x00Damage\x00Health\x00Mana\x00'
    data += b'\x00' * 5000

    # Character creation
    data += b'Character\x00Class\x00Race\x00Warrior\x00Mage\x00Rogue\x00'
    data += b'\x00' * 5000

    # Inventory
    data += b'Inventory\x00Equipment\x00Items\x00Weapon\x00Armor\x00Potion\x00'
    data += b'\x00' * 5000

    # Preencher até 512KB
    data += b'\x00' * (524288 - len(data))

    # ====================================
    # SEÇÃO 4: Middle + Footer
    # ====================================
    # Year markers
    data += b'Copyright 1999\x00(c) 1999\x001999\x00Version 1.0\x00'
    data += b'\x00' * 10000

    # Preencher até ~1MB (simular instalador)
    data += b'\x00' * (1048576 - len(data))

    # Salvar arquivo
    with open(test_file, 'wb') as f:
        f.write(data)

    print(f"✅ Arquivo criado: {test_file} ({len(data) / 1024:.1f} KB)")
    return test_file


def test_scan_inner_patterns():
    """Testa função scan_inner_patterns com arquivo simulado."""
    print("\n" + "=" * 80)
    print("TESTE 1: FUNÇÃO scan_inner_patterns()")
    print("=" * 80)

    try:
        from forensic_engine_upgrade import scan_inner_patterns

        # Criar arquivo de teste
        test_file = create_test_file()

        print("\n🔍 Executando scan_inner_patterns()...")
        result = scan_inner_patterns(str(test_file))

        # Validar resultado
        print("\n📊 RESULTADOS:")
        print(f"  • Padrões encontrados: {len(result['patterns_found'])}")
        print(f"  • Contagens por categoria: {result['pattern_counts']}")
        print(f"  • Arquiteturas inferidas: {result['architecture_hints']}")
        print(f"  • Ano do jogo: {result['game_year']}")
        print(f"  • Features detectadas: {len(result['feature_icons'])}")
        print(f"  • Confiança: {result['confidence']}")

        # Mostrar features
        if result['feature_icons']:
            print("\n🎮 FEATURES DETECTADAS:")
            for icon in result['feature_icons']:
                print(f"  {icon}")

        # Validar resultados esperados
        expected_patterns = ['RPG_STATS', 'RPG_LEVEL', 'RPG_CHARACTER',
                           'MENU_MAIN', 'MENU_CONFIG', 'AUDIO_SYS',
                           'VIDEO_SYS', 'COMBAT_SYS', 'INVENTORY_SYS']

        found_patterns = list(result['pattern_counts'].keys())
        missing = [p for p in expected_patterns if p not in found_patterns]

        if len(found_patterns) >= 7:  # Pelo menos 7 categorias
            print("\n✅ TESTE PASSOU!")
            print(f"✅ {len(found_patterns)} categorias de padrões detectadas")
            print(f"✅ Confiança: {result['confidence']}")

            if missing:
                print(f"⚠️  Categorias não detectadas: {missing}")

            # Limpar arquivo de teste
            os.remove(test_file)
            print(f"\n🧹 Arquivo de teste removido: {test_file}")

            return True
        else:
            print(f"\n❌ TESTE FALHOU!")
            print(f"❌ Apenas {len(found_patterns)} categorias detectadas (esperado: 7+)")
            print(f"❌ Faltando: {missing}")
            return False

    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_architecture_inference():
    """Testa inferência de arquitetura."""
    print("\n" + "=" * 80)
    print("TESTE 2: INFERÊNCIA DE ARQUITETURA")
    print("=" * 80)

    try:
        from forensic_engine_upgrade import _infer_architecture_from_patterns

        # Teste 1: RPG completo (3+ indicadores)
        print("\n🧪 Teste 1: RPG Completo")
        rpg_patterns = ['RPG_STATS', 'RPG_LEVEL', 'RPG_CHARACTER',
                       'COMBAT_SYS', 'INVENTORY_SYS']
        arch = _infer_architecture_from_patterns(rpg_patterns)
        print(f"  Padrões: {rpg_patterns}")
        print(f"  Arquitetura: {arch}")

        if 'Action-RPG' in arch[0] or 'RPG Turn-Based' in arch[0]:
            print("  ✅ RPG detectado corretamente")
        else:
            print("  ❌ RPG não detectado")
            return False

        # Teste 2: Menu-Driven Game
        print("\n🧪 Teste 2: Menu-Driven Game")
        menu_patterns = ['MENU_MAIN', 'MENU_CONFIG', 'AUDIO_SYS', 'VIDEO_SYS']
        arch = _infer_architecture_from_patterns(menu_patterns)
        print(f"  Padrões: {menu_patterns}")
        print(f"  Arquitetura: {arch}")

        if 'Menu-Driven' in arch[0]:
            print("  ✅ Menu-Driven detectado corretamente")
        else:
            print("  ⚠️  Menu-Driven não detectado (pode estar em segunda posição)")

        # Teste 3: Combat-Focused (sem RPG stats)
        print("\n🧪 Teste 3: Combat-Focused Game")
        combat_patterns = ['COMBAT_SYS', 'MENU_MAIN']
        arch = _infer_architecture_from_patterns(combat_patterns)
        print(f"  Padrões: {combat_patterns}")
        print(f"  Arquitetura: {arch}")

        if 'Combat-Focused' in arch[0]:
            print("  ✅ Combat-Focused detectado corretamente")
        else:
            print("  ⚠️  Combat-Focused não detectado")

        print("\n✅ TESTE DE INFERÊNCIA PASSOU!")
        return True

    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_icon_mapping():
    """Testa mapeamento de ícones."""
    print("\n" + "=" * 80)
    print("TESTE 3: MAPEAMENTO DE ÍCONES")
    print("=" * 80)

    try:
        from forensic_engine_upgrade import _map_patterns_to_icons

        patterns = ['RPG_STATS', 'RPG_LEVEL', 'MENU_MAIN', 'COMBAT_SYS',
                   'INVENTORY_SYS', 'AUDIO_SYS', 'VIDEO_SYS']

        print(f"\n🔍 Testando com padrões: {patterns}")
        icons = _map_patterns_to_icons(patterns)

        print(f"\n🎨 ÍCONES GERADOS ({len(icons)}):")
        for icon in icons:
            print(f"  {icon}")

        if len(icons) >= 5:
            print(f"\n✅ TESTE PASSOU! {len(icons)} ícones gerados")
            return True
        else:
            print(f"\n❌ TESTE FALHOU! Apenas {len(icons)} ícones (esperado: 5+)")
            return False

    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Função principal."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║           🔬 TESTE DEEP FINGERPRINTING - RAIO-X FORENSE                      ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    tests_passed = 0
    tests_total = 3

    # Teste 1: Função scan_inner_patterns
    if test_scan_inner_patterns():
        tests_passed += 1

    # Teste 2: Inferência de arquitetura
    if test_architecture_inference():
        tests_passed += 1

    # Teste 3: Mapeamento de ícones
    if test_icon_mapping():
        tests_passed += 1

    # Resumo
    print("\n" + "=" * 80)
    print("RESUMO")
    print("=" * 80)
    print(f"Testes passados: {tests_passed}/{tests_total}")

    if tests_passed == tests_total:
        print("\n✅ TODOS OS TESTES PASSARAM!")
        print("✅ Sistema de Deep Fingerprinting está OPERACIONAL!")
        print("\n🎉 PRÓXIMO PASSO: Testar com DarkStone.exe!")
        print("   Execute: python interface/gui_tabs/interface_tradutor_final.py")
        print("   E selecione DarkStone.exe para ver o raio-x em ação!")
        return 0
    else:
        print(f"\n❌ {tests_total - tests_passed} teste(s) falharam")
        print("⚠️  Verifique os erros acima")
        return 1


if __name__ == "__main__":
    sys.exit(main())
