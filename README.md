# WallpaperForge

Coleta imagens de uma obra na internet, deixa você escolher as que quer, faz upscale para 4K e exporta wallpapers no tamanho exato de cada monitor.

## Pré-requisitos

- Windows 11
- Python 3.11+
- GPU NVIDIA (recomendado) — o upscaler usa Vulkan, então qualquer GPU com suporte funciona

## Instalação

```powershell
cd d:\Projetos\WallpaperForge
.\setup.ps1
.\.venv\Scripts\activate
```

O `setup.ps1` cria a venv, instala as dependências e tenta baixar o binário do Real-ESRGAN automaticamente.

## Uso rápido

```powershell
# Listar monitores detectados
python -m wallpaperforge monitors

# Pipeline completo (coleta → filtro → seleção → upscale → crop)
python -m wallpaperforge all --query "Violet Evergarden" --limit 200

# Com URL de galeria, sem interface gráfica
python -m wallpaperforge all --url https://wallhaven.cc/tag/... --no-ui

# Rodar etapas separadas
python -m wallpaperforge scrape --query "Makoto Shinkai"
python -m wallpaperforge filter
python -m wallpaperforge select
python -m wallpaperforge upscale --model realesrgan-x4plus
python -m wallpaperforge crop
```

## Estrutura do projeto

```
WallpaperForge/
├── wallpaperforge/         # Código-fonte
│   ├── __main__.py         # Entry point
│   ├── monitors.py         # Detecção de monitores
│   ├── scraper.py          # Coleta de imagens
│   ├── filter.py           # Filtros automáticos
│   ├── ui.py               # Interface de seleção (PySide6)
│   ├── upscale.py          # Upscale via Real-ESRGAN
│   ├── crop.py             # Corte por monitor
│   └── utils/
│       ├── config.py       # Leitura de settings.toml
│       └── log.py          # Logging estruturado
├── config/
│   ├── settings.toml       # Configuração editável
│   └── monitors.json       # Gerado na primeira execução
├── work/
│   ├── raw/                # Imagens brutas do scraper
│   ├── filtered/           # Imagens após filtros
│   └── selection.json      # Seleção salva pela UI
├── output/
│   ├── Monitor_1_2560x1440/
│   ├── Monitor_2_1920x1080/
│   └── _rejeitadas/
├── bin/                    # Binário Real-ESRGAN
├── logs/                   # Logs de cada execução
├── tests/
├── pyproject.toml
└── setup.ps1
```

## Configuração de monitores

Na primeira execução, `config/monitors.json` é gerado automaticamente. Você pode adicionar monitores manualmente:

```json
[
  {
    "name": "\\.\DISPLAY1", "width": 2560, "height": 1440,
    "x": 0, "y": 0, "is_primary": true,
    "dpi_x": 96, "dpi_y": 96, "scale_factor": 1.0, "manual": false
  },
  {
    "name": "Monitor Futuro", "width": 3840, "height": 2160,
    "x": 2560, "y": 0, "is_primary": false,
    "dpi_x": 144, "dpi_y": 144, "scale_factor": 1.5, "manual": true
  }
]
```

## Configuração geral

Edite `config/settings.toml` para ajustar limiares sem tocar no código:

```toml
[filter]
min_side = 1100          # descarta imagens menores
hash_distance = 5        # tolerância para duplicatas

[upscale]
model = "realesrgan-x4plus-anime"   # ou "realesrgan-x4plus" para arte realista
tile_size = 256                      # mantém uso de VRAM abaixo de 4 GB
```

## Rodar testes

```powershell
pytest
# ou com cobertura:
pytest --cov=wallpaperforge --cov-report=term-missing
```

## Saída

```
output/
  Monitor_1_2560x1440/   ← wallpapers prontos para o monitor 1
  Monitor_2_1920x1080/   ← wallpapers prontos para o monitor 2
  _rejeitadas/           ← imagens que não tinham resolução suficiente
  relatorio.json         ← estatísticas de cada etapa
```
