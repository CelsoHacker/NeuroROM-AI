# -*- coding: utf-8 -*-
"""
================================================================================
FORENSIC UI INTEGRATION - MÉTODO ATUALIZADO
================================================================================
Método on_engine_detection_complete EXPANDIDO para exibir:
- Plataforma
- Engine
- Ano Estimado
- Compressão (+ Entropia)
- Confiança

Este arquivo contém o código de substituição para o método existente.

IMPORTANTE: Integrar no interface_tradutor_final.py
================================================================================
"""

def on_engine_detection_complete_TIER1(self, detection_result):
    """
    Handler chamado quando detecção TIER 1 termina (thread-safe via signal).

    NOVO: Exibe informações forenses completas:
    - Plataforma
    - Engine
    - Ano Estimado
    - Compressão (Status via Entropia)
    - Confiança (Nível calculado)

    Args:
        detection_result: Dicionário com resultados da detecção forense
    """
    try:
        # Armazena resultado
        self.detected_engine = detection_result

        # ================================================================
        # EXTRAÇÃO DE INFORMAÇÕES FORENSES
        # ================================================================
        engine_type = detection_result.get('type', 'UNKNOWN')
        platform = detection_result.get('platform', 'Unknown')
        engine = detection_result.get('engine', 'Unknown')
        notes = detection_result.get('notes', '')

        # NOVOS CAMPOS TIER 1
        year_estimate = detection_result.get('year_estimate', None)
        compression = detection_result.get('compression', 'N/A')
        confidence = detection_result.get('confidence', 'N/A')
        entropy = detection_result.get('entropy', 0.0)
        warnings = detection_result.get('warnings', [])
        recommendations = detection_result.get('recommendations', [])

        # NOVOS CAMPOS TIER 1 ADVANCED (Contextual Fingerprinting)
        contextual_patterns = detection_result.get('contextual_patterns', [])
        architecture_inference = detection_result.get('architecture_inference', None)

        # NOVOS CAMPOS DEEP FINGERPRINTING (RAIO-X)
        deep_analysis = detection_result.get('deep_analysis', None)

        # ================================================================
        # EXTRAÇÃO DE INFORMAÇÕES DO DEEP ANALYSIS (SE DISPONÍVEL)
        # ================================================================
        game_year_from_deep = None
        architecture_from_deep = None
        features_from_deep = []
        pattern_count_from_deep = 0

        if deep_analysis:
            game_year_from_deep = deep_analysis.get('game_year', None)
            architecture_from_deep = deep_analysis.get('architecture_hints', [])
            features_from_deep = deep_analysis.get('feature_icons', [])
            pattern_count_from_deep = len(deep_analysis.get('patterns_found', []))

        # ================================================================
        # ESCOLHA DE EMOJI E COR POR TIPO
        # ================================================================
        type_emoji_map = {
            'ROM': ("🎮", "Console ROM", "#4CAF50"),
            'PC_GAME': ("💻", "PC Game", "#2196F3"),
            'PC_GENERIC': ("💻", "PC Executável", "#64B5F6"),
            'INSTALLER': ("⚠️", "INSTALADOR", "#FF9800"),
            'ARCHIVE': ("📦", "Arquivo Compactado", "#9C27B0"),
            'ERROR': ("❌", "Erro", "#FF5722"),
            'UNKNOWN': ("❓", "Desconhecido", "#757575"),
            'GENERIC': ("📄", "Arquivo Genérico", "#FF9800")
        }

        type_emoji, type_text, color = type_emoji_map.get(
            engine_type,
            ("📄", "Arquivo Genérico", "#FF9800")
        )

        # ================================================================
        # MONTAGEM DA MENSAGEM EXPANDIDA
        # ================================================================
        detection_text = f"{type_emoji} <b>Detectado:</b> {type_text}<br>"
        detection_text += f"<b>📍 Plataforma:</b> {platform}<br>"
        detection_text += f"<b>⚙️ Engine:</b> {engine}<br>"

        # Ano Estimado
        if year_estimate:
            detection_text += f"<b>📅 Ano Estimado:</b> {year_estimate}<br>"
        else:
            detection_text += f"<b>📅 Ano Estimado:</b> <i>Não detectado</i><br>"

        # Compressão + Entropia
        detection_text += f"<b>🔧 Compressão:</b> {compression}<br>"

        # Confiança
        detection_text += f"<b>🎯 Confiança:</b> {confidence}<br>"

        # Arquitetura Inferida (NOVO - TIER 1 ADVANCED)
        if architecture_inference:
            arch_name = architecture_inference.get('architecture', 'N/A')
            game_type = architecture_inference.get('game_type', 'N/A')
            year_range = architecture_inference.get('year_range', 'N/A')
            based_on = architecture_inference.get('based_on', 'N/A')

            detection_text += f"<br><b>🏗️ Arquitetura Detectada:</b> {arch_name}<br>"
            detection_text += f"<b>📊 Tipo de Jogo:</b> {game_type}<br>"
            detection_text += f"<b>📅 Período:</b> {year_range}<br>"
            detection_text += f"<small><i>Baseado em: {based_on}</i></small><br>"

        # Padrões Contextuais Encontrados (NOVO - TIER 1 ADVANCED)
        if contextual_patterns:
            detection_text += f"<br><b>🎯 Padrões Contextuais:</b> {len(contextual_patterns)} encontrados<br>"
            for pattern in contextual_patterns[:3]:  # Mostrar até 3 padrões
                pattern_desc = pattern.get('description', 'N/A')
                detection_text += f"<small>• {pattern_desc}</small><br>"

        # Deep Analysis - Raio-X do Jogo Dentro do Instalador (NOVO - DEEP FINGERPRINTING)
        if pattern_count_from_deep > 0:
            detection_text += f"<br><b>🔬 RAIO-X DO INSTALADOR:</b> {pattern_count_from_deep} padrões do jogo detectados<br>"

            # Mostrar arquitetura inferida do jogo
            if architecture_from_deep:
                arch_name = architecture_from_deep[0]
                detection_text += f"<b>🏗️ Jogo Detectado:</b> {arch_name}<br>"

            # Mostrar ano do jogo (não do instalador)
            if game_year_from_deep:
                detection_text += f"<b>📅 Ano do Jogo:</b> {game_year_from_deep}<br>"

            # Mostrar features detectadas
            if features_from_deep:
                detection_text += f"<br><b>🎮 Features Encontradas no Jogo:</b><br>"
                for feature in features_from_deep[:5]:  # Mostrar até 5 features
                    detection_text += f"<small>• {feature}</small><br>"

        # Notas técnicas (opcional)
        if notes:
            detection_text += f"<br><small><i>{notes}</i></small>"

        # ================================================================
        # AVISOS E RECOMENDAÇÕES (SE HOUVER)
        # ================================================================
        if warnings:
            detection_text += "<br><br><b>⚠️ AVISOS:</b><br>"
            for warning in warnings:
                detection_text += f"<small>{warning}</small><br>"

        if recommendations:
            detection_text += "<br><b>💡 RECOMENDAÇÕES:</b><br>"
            for rec in recommendations:
                detection_text += f"<small>{rec}</small><br>"

        # ================================================================
        # ATUALIZAÇÃO DA UI (THREAD-SAFE)
        # ================================================================
        self.engine_detection_label.setText(detection_text)
        self.engine_detection_label.setStyleSheet(
            f"""
            color: {color};
            background: #1e1e1e;
            padding: 12px;
            border-radius: 6px;
            border-left: 4px solid {color};
            font-size: 10pt;
            """
        )
        self.engine_detection_label.setVisible(True)

        # ================================================================
        # LOG EXPANDIDO
        # ================================================================
        self.log(f"🎯 Detectado: {type_text} | {platform}")
        self.log(f"📋 Engine: {engine}")

        if year_estimate:
            self.log(f"📅 Ano: {year_estimate}")

        self.log(f"🔧 Compressão: {compression}")
        self.log(f"🎯 Confiança: {confidence}")

        # Log de avisos
        for warning in warnings:
            self.log(warning)

        # ================================================================
        # SINCRONIZAÇÃO DO COMBOBOX DE PLATAFORMA
        # ================================================================
        platform_code = detection_result.get('platform_code')
        if platform_code and platform_code != 'INSTALLER' and platform_code != 'ARCHIVE':
            self.sync_platform_combobox(platform_code)

    except Exception as e:
        error_msg = f"⚠️ Erro ao processar detecção: {e}"
        self.log(error_msg)

        # Mostra erro genérico
        self.engine_detection_label.setText(
            f"❌ <b>Erro na Análise Forense</b><br>"
            f"<small>{error_msg}</small>"
        )
        self.engine_detection_label.setStyleSheet(
            "color:#FF5722;background:#1e1e1e;padding:10px;border-radius:5px;"
        )
        self.engine_detection_label.setVisible(True)


# ================================================================
# EXEMPLO DE SAÍDA ESPERADA NA INTERFACE:
# ================================================================
"""
⚠️ Detectado: INSTALADOR
📍 Plataforma: Instalador (Instalador Inno Setup)
⚙️ Engine: Instalador Inno Setup
📅 Ano Estimado: 1999
🔧 Compressão: Alta compressão detectada (Entropia: 7.82)
🎯 Confiança: Alta

🔬 RAIO-X DO INSTALADOR: 8 padrões do jogo detectados
🏗️ Jogo Detectado: Action-RPG ou RPG Turn-Based
📅 Ano do Jogo: 1999

🎮 Features Encontradas no Jogo:
• 📊 Sistema de Atributos (STR/DEX/INT)
• ⬆️ Sistema de Níveis/Experiência
• 🎮 Menu Principal
• ⚔️ Sistema de Combate
• 🎒 Sistema de Inventário

⚠️ AVISOS:
⚠️ Este arquivo é um INSTALADOR, não o jogo em si
⚠️ Você não pode extrair textos diretamente de instaladores

💡 RECOMENDAÇÕES:
🏗️ JOGO DETECTADO: Action-RPG ou RPG Turn-Based
💡 SOLUÇÃO: Execute o instalador para instalar o jogo
💡 Depois, selecione o executável do jogo (.exe) na pasta de instalação
💡 Exemplo: C:\Games\[NomeDoJogo]\game.exe
"""
