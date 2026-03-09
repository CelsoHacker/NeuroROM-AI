# apply_neutral_patch.ps1
# Patch cirúrgico: remove os.path.basename(...) do log "Iniciando extração" nos 2 arquivos que você encontrou.
# - Faz backup .bak
# - Substitui apenas a linha do log
# - Verifica se ainda sobra algum "Iniciando extração:" com basename
#
# Compatível com Windows PowerShell 5.1

param(
  [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"

$files = @(
  (Join-Path -Path $ProjectRoot -ChildPath "interface\interface_tradutor_final.py")
  (Join-Path -Path $ProjectRoot -ChildPath "interface\interface_tradutor_final_NEUTRAL.py")
)

$pattern = 'self\.log\(\s*f"\[START\]\s+Iniciando extração:\s*\{os\.path\.basename\(\s*self\.original_rom_path\s*\)\}"\s*\)'
$replacement = 'self.log("[START] Iniciando extração (identificação por CRC32/ROM_SIZE no report)")'

foreach ($f in $files) {
  if (!(Test-Path $f)) {
    Write-Host "[WARN] Arquivo não encontrado: $f"
    continue
  }

  $bak = "$f.bak"
  if (!(Test-Path $bak)) {
    Copy-Item $f $bak
    Write-Host "[OK] Backup criado: $bak"
  } else {
    Write-Host "[INFO] Backup já existe: $bak"
  }

  $content = Get-Content $f -Raw -Encoding UTF8
  $new = [regex]::Replace($content, $pattern, $replacement)

  if ($new -eq $content) {
    Write-Host "[INFO] Nenhuma substituição feita em: $f (talvez já esteja neutro, ou a linha difere)."
  } else {
    Set-Content -Path $f -Value $new -Encoding UTF8
    Write-Host "[OK] Patch aplicado em: $f"
  }
}

Write-Host ""
Write-Host "== Verificação (ocorrências de 'Iniciando extração:' em .py) =="
Get-ChildItem -Path $ProjectRoot -Recurse -Filter "*.py" |
  Select-String -Pattern "Iniciando extração:" -SimpleMatch |
  ForEach-Object { "$($_.Path):$($_.LineNumber):$($_.Line.Trim())" }

Write-Host ""
Write-Host "[DONE] Se aparecer alguma linha ainda com basename, copie aqui o trecho exato e eu ajusto o regex."
