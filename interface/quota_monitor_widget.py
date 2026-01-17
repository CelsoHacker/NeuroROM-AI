"""
Widget de Monitoramento de Quota para Google Gemini API
========================================================

Widget customtkinter para exibir status da quota em tempo real
"""

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from typing import Optional, Callable
import threading
import time


class QuotaMonitorWidget(ctk.CTkFrame):
    """Widget para monitorar uso da API Gemini em tempo real"""

    def __init__(self, parent, quota_manager=None, **kwargs):
        """
        Inicializa widget de monitoramento

        Args:
            parent: Widget pai (tkinter)
            quota_manager: Instância de GeminiQuotaManager
            **kwargs: Argumentos para CTkFrame
        """
        super().__init__(parent, **kwargs)

        self.quota_manager = quota_manager
        self.auto_update_enabled = True
        self.update_interval = 5000  # 5 segundos
        self.update_thread: Optional[threading.Thread] = None

        self._setup_ui()
        self._start_auto_update()

    def _setup_ui(self):
        """Configura interface do widget"""

        # Título
        title_label = ctk.CTkLabel(
            self,
            text="📊 Status da API Gemini",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        title_label.pack(pady=(10, 5), padx=10, anchor="w")

        # Frame de estatísticas
        stats_frame = ctk.CTkFrame(self)
        stats_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Grid de estatísticas
        row = 0

        # Uso diário
        ctk.CTkLabel(
            stats_frame,
            text="Uso Diário:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=row, column=0, sticky="w", padx=10, pady=5)

        self.daily_usage_label = ctk.CTkLabel(
            stats_frame,
            text="0/20 (0%)",
            font=ctk.CTkFont(size=12)
        )
        self.daily_usage_label.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Barra de progresso
        self.progress_bar = ctk.CTkProgressBar(
            stats_frame,
            width=300,
            height=15
        )
        self.progress_bar.grid(row=row, column=0, columnspan=2, padx=10, pady=5, sticky="ew")
        self.progress_bar.set(0)
        row += 1

        # Requisições restantes
        ctk.CTkLabel(
            stats_frame,
            text="Restantes:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=row, column=0, sticky="w", padx=10, pady=5)

        self.remaining_label = ctk.CTkLabel(
            stats_frame,
            text="20 requisições",
            font=ctk.CTkFont(size=12)
        )
        self.remaining_label.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Tempo até reset
        ctk.CTkLabel(
            stats_frame,
            text="Reset em:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=row, column=0, sticky="w", padx=10, pady=5)

        self.reset_time_label = ctk.CTkLabel(
            stats_frame,
            text="--h --m",
            font=ctk.CTkFont(size=12)
        )
        self.reset_time_label.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Última requisição
        ctk.CTkLabel(
            stats_frame,
            text="Última requisição:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=row, column=0, sticky="w", padx=10, pady=5)

        self.last_request_label = ctk.CTkLabel(
            stats_frame,
            text="Nunca",
            font=ctk.CTkFont(size=12)
        )
        self.last_request_label.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Taxa de sucesso (última hora)
        ctk.CTkLabel(
            stats_frame,
            text="Taxa de sucesso:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=row, column=0, sticky="w", padx=10, pady=5)

        self.success_rate_label = ctk.CTkLabel(
            stats_frame,
            text="100%",
            font=ctk.CTkFont(size=12)
        )
        self.success_rate_label.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Configurar grid weights
        stats_frame.grid_columnconfigure(1, weight=1)

        # Separador
        separator = ttk.Separator(self, orient='horizontal')
        separator.pack(fill='x', padx=10, pady=10)

        # Botões de controle
        button_frame = ctk.CTkFrame(self)
        button_frame.pack(fill="x", padx=10, pady=5)

        self.refresh_button = ctk.CTkButton(
            button_frame,
            text="🔄 Atualizar",
            command=self.refresh_stats,
            width=120
        )
        self.refresh_button.pack(side="left", padx=5)

        self.auto_update_switch = ctk.CTkSwitch(
            button_frame,
            text="Auto-atualizar",
            command=self._toggle_auto_update
        )
        self.auto_update_switch.pack(side="left", padx=5)
        self.auto_update_switch.select()  # Inicia ativo

        # Status indicator
        self.status_indicator = ctk.CTkLabel(
            button_frame,
            text="🟢",
            font=ctk.CTkFont(size=20)
        )
        self.status_indicator.pack(side="right", padx=5)

    def set_quota_manager(self, quota_manager):
        """Define/atualiza quota manager"""
        self.quota_manager = quota_manager
        self.refresh_stats()

    def refresh_stats(self):
        """Atualiza estatísticas exibidas"""
        if not self.quota_manager:
            self._show_unavailable()
            return

        try:
            stats = self.quota_manager.get_stats()

            # Uso diário
            daily_used = stats['daily_used']
            daily_limit = stats['daily_limit']
            usage_percent = stats['usage_percent']

            self.daily_usage_label.configure(
                text=f"{daily_used}/{daily_limit} ({usage_percent:.0f}%)"
            )

            # Barra de progresso
            self.progress_bar.set(usage_percent / 100)

            # Cor da barra baseada em uso
            if usage_percent < 50:
                color = "#4CAF50"  # Verde
                indicator = "🟢"
            elif usage_percent < 80:
                color = "#FF9800"  # Laranja
                indicator = "🟡"
            else:
                color = "#F44336"  # Vermelho
                indicator = "🔴"

            self.progress_bar.configure(progress_color=color)
            self.status_indicator.configure(text=indicator)

            # Restantes
            remaining = stats['daily_remaining']
            self.remaining_label.configure(
                text=f"{remaining} {'requisição' if remaining == 1 else 'requisições'}"
            )

            # Tempo até reset
            hours = int(stats['hours_until_reset'])
            minutes = int((stats['hours_until_reset'] - hours) * 60)
            self.reset_time_label.configure(text=f"{hours}h {minutes}m")

            # Última requisição
            last_req = stats.get('last_request')
            if last_req:
                from datetime import datetime
                dt = datetime.fromisoformat(last_req)
                time_str = dt.strftime("%H:%M:%S")
                self.last_request_label.configure(text=time_str)
            else:
                self.last_request_label.configure(text="Nunca")

            # Taxa de sucesso
            success_rate = stats.get('success_rate_last_hour', 100)
            self.success_rate_label.configure(text=f"{success_rate:.0f}%")

        except Exception as e:
            print(f"❌ Erro ao atualizar stats: {e}")
            self._show_error()

    def _show_unavailable(self):
        """Mostra estado de indisponível"""
        self.daily_usage_label.configure(text="N/A")
        self.progress_bar.set(0)
        self.remaining_label.configure(text="Sistema não disponível")
        self.reset_time_label.configure(text="--")
        self.last_request_label.configure(text="--")
        self.success_rate_label.configure(text="--")
        self.status_indicator.configure(text="⚫")

    def _show_error(self):
        """Mostra estado de erro"""
        self.status_indicator.configure(text="⚠️")

    def _start_auto_update(self):
        """Inicia atualização automática"""
        if self.auto_update_enabled:
            self.refresh_stats()
            self.after(self.update_interval, self._start_auto_update)

    def _toggle_auto_update(self):
        """Alterna auto-atualização"""
        self.auto_update_enabled = not self.auto_update_enabled

        if self.auto_update_enabled:
            self._start_auto_update()

    def destroy(self):
        """Cleanup ao destruir widget"""
        self.auto_update_enabled = False
        super().destroy()


# ============================================================================
# JANELA STANDALONE DE MONITORAMENTO
# ============================================================================

class QuotaMonitorWindow(ctk.CTkToplevel):
    """Janela standalone para monitorar quota"""

    def __init__(self, parent=None, quota_manager=None):
        """
        Inicializa janela de monitoramento

        Args:
            parent: Janela pai (opcional)
            quota_manager: Instância de GeminiQuotaManager
        """
        super().__init__(parent)

        self.title("Monitor de Quota - Google Gemini API")
        self.geometry("450x400")
        self.resizable(False, False)

        # Widget de monitoramento
        self.monitor_widget = QuotaMonitorWidget(
            self,
            quota_manager=quota_manager
        )
        self.monitor_widget.pack(fill="both", expand=True, padx=10, pady=10)

        # Botão fechar
        close_button = ctk.CTkButton(
            self,
            text="Fechar",
            command=self.destroy,
            width=100
        )
        close_button.pack(pady=10)

        # Centralizar janela
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (450 // 2)
        y = (self.winfo_screenheight() // 2) - (400 // 2)
        self.geometry(f"450x400+{x}+{y}")

    def set_quota_manager(self, quota_manager):
        """Define quota manager"""
        self.monitor_widget.set_quota_manager(quota_manager)


# ============================================================================
# FUNÇÃO HELPER PARA ABRIR MONITOR
# ============================================================================

def open_quota_monitor(quota_manager=None):
    """
    Abre janela de monitoramento de quota

    Args:
        quota_manager: Instância de GeminiQuotaManager
    """
    # Criar janela root se não existir
    try:
        root = ctk.CTk()
        root.withdraw()  # Esconde janela principal
    except:
        root = None

    window = QuotaMonitorWindow(root, quota_manager)
    window.mainloop()


# ============================================================================
# TESTE STANDALONE
# ============================================================================

if __name__ == "__main__":
    # Teste do widget
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    try:
        from core.quota_manager import get_quota_manager
        quota_mgr = get_quota_manager()
    except:
        quota_mgr = None
        print("⚠️ QuotaManager não disponível - teste com valores simulados")

    open_quota_monitor(quota_mgr)
