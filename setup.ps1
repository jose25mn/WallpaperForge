# setup.ps1 — configura o ambiente WallpaperForge no Windows 11
# Uso: cd d:\Projetos\WallpaperForge && .\setup.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== WallpaperForge Setup ===" -ForegroundColor Cyan
Write-Host ""

# ── 1. Verificar Python 3.11+ ─────────────────────────────────────────────────
$python = "python"
$ver = & $python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
if (-not $?) {
    Write-Host "ERRO: Python não encontrado. Instale Python 3.11+ e adicione ao PATH." -ForegroundColor Red
    exit 1
}
$parts = $ver.Split(".")
if ([int]$parts[0] -lt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -lt 11)) {
    Write-Host "ERRO: Python $ver detectado. É necessário 3.11+." -ForegroundColor Red
    exit 1
}
Write-Host "Python $ver ok" -ForegroundColor Green

# ── 2. Criar venv ─────────────────────────────────────────────────────────────
if (-not (Test-Path ".venv")) {
    Write-Host "Criando ambiente virtual .venv..." -ForegroundColor Yellow
    & $python -m venv .venv
    Write-Host "venv criada." -ForegroundColor Green
} else {
    Write-Host ".venv já existe, pulando criação." -ForegroundColor DarkGray
}

$pip = ".\.venv\Scripts\pip.exe"

# ── 3. Instalar dependências ──────────────────────────────────────────────────
Write-Host ""
Write-Host "Instalando dependências (isso pode demorar na primeira vez)..." -ForegroundColor Yellow
& $pip install --upgrade pip --quiet
& $pip install -e ".[dev]"
Write-Host "Dependências instaladas." -ForegroundColor Green

# ── 4. Criar diretórios de trabalho ──────────────────────────────────────────
foreach ($dir in @("work/raw", "work/filtered", "output/_rejeitadas", "bin", "config", "logs")) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force $dir | Out-Null
    }
}
Write-Host "Diretórios criados." -ForegroundColor Green

# ── 5. Baixar Real-ESRGAN (Vulkan) ────────────────────────────────────────────
$realesrganExe = "bin\realesrgan-ncnn-vulkan.exe"
if (-not (Test-Path $realesrganExe)) {
    Write-Host ""
    Write-Host "Baixando Real-ESRGAN ncnn-vulkan..." -ForegroundColor Yellow
    try {
        $apiUrl  = "https://api.github.com/repos/xinntao/Real-ESRGAN/releases/latest"
        $headers = @{ "User-Agent" = "WallpaperForge-Setup/1.0" }
        $release = Invoke-RestMethod -Uri $apiUrl -Headers $headers

        $asset = $release.assets | Where-Object { $_.name -like "*windows*" } | Select-Object -First 1
        if ($null -eq $asset) {
            throw "Nenhum asset Windows encontrado na release."
        }

        $zipPath = "bin\realesrgan_win.zip"
        Write-Host "Baixando $($asset.name) ($([math]::Round($asset.size/1MB, 1)) MB)..." -ForegroundColor DarkGray
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath

        Write-Host "Extraindo..." -ForegroundColor DarkGray
        Expand-Archive -Path $zipPath -DestinationPath "bin\" -Force
        Remove-Item $zipPath -Force

        # Mover exe para raiz de bin\ se estiver em subpasta
        $found = Get-ChildItem "bin\" -Recurse -Filter "realesrgan-ncnn-vulkan.exe" | Select-Object -First 1
        if ($found -and $found.FullName -ne (Resolve-Path $realesrganExe -ErrorAction SilentlyContinue)) {
            Copy-Item $found.FullName "bin\" -Force
        }

        Write-Host "Real-ESRGAN baixado com sucesso." -ForegroundColor Green
    } catch {
        Write-Host "Aviso: não foi possível baixar Real-ESRGAN automaticamente." -ForegroundColor Red
        Write-Host "Baixe manualmente em: https://github.com/xinntao/Real-ESRGAN/releases" -ForegroundColor Yellow
        Write-Host "Coloque realesrgan-ncnn-vulkan.exe em: $(Resolve-Path 'bin\')" -ForegroundColor Yellow
    }
} else {
    Write-Host "Real-ESRGAN já presente em $realesrganExe." -ForegroundColor DarkGray
}

# ── Conclusão ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Setup concluído! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Para usar:" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\activate"
Write-Host "  python -m wallpaperforge monitors"
Write-Host "  python -m wallpaperforge --help"
Write-Host ""
