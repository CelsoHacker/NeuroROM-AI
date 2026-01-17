# NEUROROM AI V6.0 PRO SUITE
## Universal ROM & PC Game Translation Framework

<div align="center">

**AI-Powered ROM & Game Translation for Classic and Modern Platforms**

**Developed by Celso - Solo Developer | 2026**

[Quick Start](#-quick-start) | [Documentation](docs/) | [Examples](examples/)

</div>

---

## Features

### KERNEL V9.5 ENGINE
- Hardware Detection (HiROM/LoROM via $FFD5)
- Sequential Finder (Auto-detect character tables)
- Pointer Scavenger (16/24-bit pointer tables)
- Dynamic Text Allocator with Repointing
- Checksum Fixer (Auto-recalculate $FFDE-$FFFF)

### Multi-Platform Support
- **Console ROMs**: SNES, NES, Genesis/Mega Drive, Master System, PS1, N64, GBA
- **PC Games**: Unity, Unreal Engine, RPG Maker, GameMaker, DOS games
- **File Formats**: .sfc, .smc, .nes, .bin, .iso, .exe, .dll, and more

### AI Translation
- Google Gemini API (online, high quality)
- Ollama (offline, unlimited, free)
- Hybrid mode with automatic fallback
- Batch translation with quota management

### Professional Tools
- Forensic Scanner with engine fingerprinting
- DTE/MTE compression solver
- Graphics Lab for tile editing
- Runtime Text Capture Engine (RTCE)
- Safe reinsertion with automatic backups

---

## Quick Start

### Prerequisites
- Python 3.10+
- Windows 10/11 (primary), Linux/macOS (experimental)

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/neurorom-ai.git
cd neurorom-ai

# Install dependencies
pip install -r requirements.txt

# Launch application
python main.py
```

### Optional Dependencies

For full functionality:
```bash
# Image processing and OCR
pip install opencv-python pillow pytesseract

# Machine learning features
pip install scikit-learn joblib

# Install Tesseract OCR (Windows)
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
```

---

## Project Structure

```
rom-translation-framework/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── core/                   # Core extraction and translation engines
│   ├── ultimate_extractor_v9.py    # Kernel V9.5 engine
│   ├── forensic_scanner.py         # File analysis
│   ├── gemini_translator.py        # AI translation
│   └── ...
├── interface/              # PyQt6 GUI application
│   ├── interface_tradutor_final.py # Main window
│   ├── gui_tabs/                   # Tab modules
│   └── ...
├── rtce_core/              # Runtime Text Capture Engine
├── tools/                  # Utility scripts
├── utils/                  # Helper functions
├── examples/               # Usage examples
├── docs/                   # Documentation
├── i18n/                   # Interface translations (16 languages)
└── config/                 # Configuration files
```

---

## Translation Pipeline

1. **Detection**: Automatic platform and engine identification
2. **Extraction**: Text extraction with pointer mapping
3. **Optimization**: Deduplication and filtering (up to 80% reduction)
4. **Translation**: AI-powered translation with context awareness
5. **Reinsertion**: Safe insertion with backup and validation

---

## Supported Platforms

| Platform | Extraction | Translation | Reinsertion |
|----------|------------|-------------|-------------|
| SNES     | Full       | Full        | Full        |
| NES      | Full       | Full        | Full        |
| Genesis  | Full       | Full        | Partial     |
| PS1      | Full       | Full        | Partial     |
| GBA      | Full       | Full        | Partial     |
| PC Games | Full       | Full        | Full        |

---

## Configuration

### API Keys

Set your Gemini API key as environment variable:
```bash
export GEMINI_API_KEY="your-api-key-here"
```

Or configure in the application settings.

### Offline Translation (Ollama)

1. Install Ollama: https://ollama.ai
2. Pull a model: `ollama pull gemma:2b`
3. Select "Offline Mode" in the application

---

## Tech Stack

- **Language**: Python 3.10+
- **GUI**: PyQt6
- **AI APIs**: Google Gemini, Ollama
- **ML**: scikit-learn, NumPy, Pandas
- **Image Processing**: OpenCV, Pillow, Tesseract
- **Architecture**: Multi-threaded with QThread

---

## License

Proprietary software. All rights reserved.

---

## Support

For issues and questions, please check the [documentation](docs/) or open an issue.

---

**NEUROROM AI V6.0 PRO SUITE**
**Made for ROM hackers and game translators**

Developed by Celso | 2026
