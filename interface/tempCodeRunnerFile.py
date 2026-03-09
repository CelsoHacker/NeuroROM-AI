            self.current_process = subprocess.Popen(cmd, shell=True)

            self.extract_progress_bar.setValue(50)
            self.extract_status_label.setText(self.tr("status_processing"))

            # 3. CRIA O MONITOR (O Segredo para não travar)
            self.v9_timer = QTimer()
            self.v9_timer.timeout.connect(self.check_v9_status)
            self.v9_timer.start(1000)  # Verifica a cada 1 segundo (1000ms)

        except Exception as e:
            self.log(f"[ERROR] Erro ao lançar: {_sanitize_error(e)}")

    def check_v9_status(self):
        """Verifica se o processo de extração terminou e lê o relatório para o log."""
        if hasattr(self, "current_process") and self.current_process.poll() is not None:
            self.v9_timer.stop()
            self.extract_progress_bar.setValue(100)
            self.extract_status_label.setText(self.tr("status_done"))

            # --- LÓGICA DE RECUPERAÇÃO DE RESULTADOS (NEUTRAL) ---
            rom_dir = os.path.dirname(self.original_rom_path)
            crc32_id = getattr(self, "_extraction_crc32", None)
            if not crc32_id:
                crc32_id = _crc32_file(self.original_rom_path)

            # Report file com naming neutro (CRC32)
            report_file = os.path.join(rom_dir, f"{crc32_id}_report.txt")

            # Verifica qual extrator foi usado e procura o arquivo correto
            extractor_type = getattr(self, "_current_extractor_type", "fast_clean")

            # Lista de possíveis arquivos de saída - prioriza CRC32, fallback legacy
            possible_outputs = [
                # Novos nomes neutros (CRC32)
                os.path.join(rom_dir, f"{crc32_id}_pure_text.jsonl"),
                os.path.join(rom_dir, f"{crc32_id}_extracted.txt"),
            ]

            extracted_file = None
            for candidate in possible_outputs:
                if os.path.exists(candidate):
                    extracted_file = candidate
                    break

            # 1. Tenta ler o RELATÓRIO para o Log da direita
            if os.path.exists(report_file):
                self.log("=" * 40)
                self.log("📋 RESUMO DA EXTRAÇÃO:")
                try:
                    with open(report_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip() and not line.startswith("#"):
                                self.log(f"  {line.strip()}")
                except Exception as e:
                    self.log(f"[WARN] Erro ao ler relatório: {_sanitize_error(e)}")
                self.log("=" * 40)

            # 2. Tenta mostrar uma prévia das strings no log
            if extracted_file:
                self.extracted_file = extracted_file
                self.current_rom_crc32 = crc32_id
                output_dir = self._organize_crc32_outputs(
                    rom_dir, crc32_id, stage="extracao"
                )
                if output_dir:
                    self.log(
                        self.tr("outputs_organized_message").format(
                            folder=self._get_stage_dir("extracao", output_dir) or output_dir
                        )
                    )
                    self._set_extracted_from_output_dir(output_dir, crc32_id)
                    self._apply_max_extraction(
                        self.original_rom_path, output_dir, crc32_id
