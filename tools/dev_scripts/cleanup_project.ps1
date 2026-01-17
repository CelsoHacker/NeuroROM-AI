# ========================================
# SCRIPT DE LIMPEZA AUTOMÁTICA
# ROM Translation Framework V5
# ========================================

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  LIMPEZA AUTOMÁTICA DO PROJETO" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$basePath = "rom-translation-framework"

# Verifica se está na pasta correta
if (-not (Test-Path $basePath)) {
    Write-Host "❌ ERRO: Execute este script na pasta PROJETO_V5_OFICIAL" -ForegroundColor Red
    Write-Host "   Pasta atual: $(Get-Location)" -ForegroundColor Yellow
    exit 1
}

# Contador de arquivos deletados
$deletedCount = 0

Write-Host "[1/10] 🗑️  Removendo cache Python..." -ForegroundColor Yellow
$pycache = Get-ChildItem -Path $basePath -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
foreach ($dir in $pycache) {
    Remove-Item $dir.FullName -Recurse -Force
    $deletedCount++
    Write-Host "  ✓ Removido: $($dir.FullName)" -ForegroundColor Gray
}

$pyc = Get-ChildItem -Path $basePath -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
foreach ($file in $pyc) {
    Remove-Item $file.FullName -Force
    $deletedCount++
}
Write-Host "  ✅ Cache Python removido ($($pycache.Count + $pyc.Count) itens)`n" -ForegroundColor Green

Write-Host "[2/10] 🗑️  Removendo backups de teste..." -ForegroundColor Yellow
$backups = Get-ChildItem -Path $basePath -Recurse -Filter "*.backup_*" -ErrorAction SilentlyContinue
foreach ($file in $backups) {
    Remove-Item $file.FullName -Force
    $deletedCount++
    Write-Host "  ✓ Removido: $($file.Name)" -ForegroundColor Gray
}
Write-Host "  ✅ Backups removidos ($($backups.Count) arquivos)`n" -ForegroundColor Green

Write-Host "[3/10] 🗑️  Removendo duplicatas em core/..." -ForegroundColor Yellow
$coreDuplicates = @(
    "$basePath\core\gemini_translator.py",
    "$basePath\core\parallel_translator.py",
    "$basePath\core\translation_engine.py",
    "$basePath\core\translator_engine.py"
)
foreach ($file in $coreDuplicates) {
    if (Test-Path $file) {
        Remove-Item $file -Force
        $deletedCount++
        Write-Host "  ✓ Removido: $(Split-Path $file -Leaf)" -ForegroundColor Gray
    }
}
Write-Host "  ✅ Duplicatas core/ removidas`n" -ForegroundColor Green

Write-Host "[4/10] 🗑️  Removendo arquivos obsoletos em interface/..." -ForegroundColor Yellow
$interfaceObsolete = @(
    "$basePath\interface\gui_translator.py",
    "$basePath\interface\pointer_scanner.py",
    "$basePath\interface\memory_mapper.py",
    "$basePath\interface\generic_snes_extractor.py",
    "$basePath\interface\integration_patch.py",
    "$basePath\interface\tempCodeRunnerFile.py"
)
foreach ($file in $interfaceObsolete) {
    if (Test-Path $file) {
        Remove-Item $file -Force
        $deletedCount++
        Write-Host "  ✓ Removido: $(Split-Path $file -Leaf)" -ForegroundColor Gray
    }
}
Write-Host "  ✅ Obsoletos interface/ removidos`n" -ForegroundColor Green

Write-Host "[5/10] 🗑️  Removendo duplicatas em utils/..." -ForegroundColor Yellow
$utilsDuplicates = @(
    "$basePath\utils\license_guard.py",
    "$basePath\utils\cuda_optimizer.py"
)
foreach ($file in $utilsDuplicates) {
    if (Test-Path $file) {
        Remove-Item $file -Force
        $deletedCount++
        Write-Host "  ✓ Removido: $(Split-Path $file -Leaf)" -ForegroundColor Gray
    }
}
Write-Host "  ✅ Duplicatas utils/ removidas`n" -ForegroundColor Green

Write-Host "[6/10] 🗑️  Removendo documentação obsoleta..." -ForegroundColor Yellow
$docsObsolete = @(
    "$basePath\docs\7_DAY_ROADMAP.md",
    "$basePath\docs\BUG_FIX_DELIVERY.md",
    "$basePath\docs\CHANGELOG.md",
    "$basePath\docs\COMPLETE_GUIDE.txt",
    "$basePath\docs\GUIA_TESTES_LEGAL_SEGURO.md",
    "$basePath\docs\LAUNCH_STRATEGY.md",
    "$basePath\docs\MANUAL_USO.md",
    "$basePath\docs\PROJECT_ANALYSIS_REPORT.md",
    "$basePath\docs\README.txt",
    "$basePath\docs\RELATORIO_CORRECOES.md",
    "$basePath\docs\SOLUCAO_LEGAL_E_SEGURA.md",
    "$basePath\docs\TECHNICAL_MANUAL.txt"
)
foreach ($file in $docsObsolete) {
    if (Test-Path $file) {
        Remove-Item $file -Force
        $deletedCount++
        Write-Host "  ✓ Removido: $(Split-Path $file -Leaf)" -ForegroundColor Gray
    }
}
Write-Host "  ✅ Documentação obsoleta removida`n" -ForegroundColor Green

Write-Host "[7/10] 🗑️  Removendo PDF grande (4MB)..." -ForegroundColor Yellow
$pdf = "$basePath\MANUAL_USO.pdf"
if (Test-Path $pdf) {
    $pdfSize = (Get-Item $pdf).Length / 1MB
    Remove-Item $pdf -Force
    $deletedCount++
    Write-Host "  ✓ Removido: MANUAL_USO.pdf ($($pdfSize.ToString('0.0')) MB)" -ForegroundColor Gray
}
Write-Host "  ✅ PDF removido`n" -ForegroundColor Green

Write-Host "[8/10] 🗑️  Limpando arquivos de teste dummy_pc_game..." -ForegroundColor Yellow
$dummyFiles = @(
    "$basePath\dummy_pc_game\extracted_texts_pc.json",
    "$basePath\dummy_pc_game\test_translations.json"
)
foreach ($file in $dummyFiles) {
    if (Test-Path $file) {
        Remove-Item $file -Force
        $deletedCount++
        Write-Host "  ✓ Removido: $(Split-Path $file -Leaf)" -ForegroundColor Gray
    }
}
$dummyOutput = "$basePath\dummy_pc_game\translation_output"
if (Test-Path $dummyOutput) {
    Remove-Item $dummyOutput -Recurse -Force
    $deletedCount++
    Write-Host "  ✓ Removido: translation_output/" -ForegroundColor Gray
}
Write-Host "  ✅ Dummy game limpo`n" -ForegroundColor Green

Write-Host "[9/10] 🗑️  Removendo outputs de teste em ROMs/..." -ForegroundColor Yellow
$romOutputs = Get-ChildItem -Path "$basePath\ROMs\Super Nintedo" -Filter "*_extracted_texts.txt" -ErrorAction SilentlyContinue
$romOutputs += Get-ChildItem -Path "$basePath\ROMs\Super Nintedo" -Filter "*_optimized.txt" -ErrorAction SilentlyContinue
$romOutputs += Get-ChildItem -Path "$basePath\ROMs\Super Nintedo" -Filter "*_translated.txt" -ErrorAction SilentlyContinue
foreach ($file in $romOutputs) {
    Remove-Item $file.FullName -Force
    $deletedCount++
    Write-Host "  ✓ Removido: $($file.Name)" -ForegroundColor Gray
}
Write-Host "  ✅ Outputs ROM removidos ($($romOutputs.Count) arquivos)`n" -ForegroundColor Green

Write-Host "[10/10] 🗑️  Removendo pastas vazias..." -ForegroundColor Yellow
$scriptsPrincipais = "$basePath\Scripts principais"
if (Test-Path $scriptsPrincipais) {
    $items = Get-ChildItem $scriptsPrincipais -ErrorAction SilentlyContinue
    if ($items.Count -eq 0) {
        Remove-Item $scriptsPrincipais -Force
        $deletedCount++
        Write-Host "  ✓ Removido: Scripts principais/ (vazia)" -ForegroundColor Gray
    }
}
Write-Host "  ✅ Pastas vazias removidas`n" -ForegroundColor Green

# Resumo final
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  ✅ LIMPEZA CONCLUÍDA COM SUCESSO" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Total de itens removidos: $deletedCount" -ForegroundColor White
Write-Host "  Espaço liberado: ~4-6 MB" -ForegroundColor White
Write-Host "`n  Próximo passo:" -ForegroundColor Yellow
Write-Host "  Leia PROJETO_CLEANUP_GUIDE.md para detalhes" -ForegroundColor Yellow
Write-Host "========================================`n" -ForegroundColor Cyan

# Pergunta sobre ROMs
Write-Host "⚠️  ATENÇÃO - ROMs Detectadas!" -ForegroundColor Yellow
Write-Host "   Seu projeto contém ROMs em:" -ForegroundColor White
Write-Host "   $basePath\ROMs\`n" -ForegroundColor White

$response = Read-Host "   Deseja MANTER as ROMs (apenas para uso local)? (S/N)"
if ($response -eq "N" -or $response -eq "n") {
    Write-Host "`n   Removendo ROMs..." -ForegroundColor Yellow
    Remove-Item "$basePath\ROMs\Super Nintedo\*.smc" -Force -ErrorAction SilentlyContinue
    Remove-Item "$basePath\ROMs\Playstation 1\*.bin" -Force -ErrorAction SilentlyContinue

    Write-Host "   ✅ ROMs removidas" -ForegroundColor Green
    Write-Host "   ⚠️  Lembre-se de adicionar ROMs/ ao .gitignore`n" -ForegroundColor Yellow
} else {
    Write-Host "`n   ✅ ROMs mantidas (apenas para uso pessoal)" -ForegroundColor Green
    Write-Host "   ⚠️  NÃO compartilhe este projeto com as ROMs!`n" -ForegroundColor Red
}

Write-Host "Pressione qualquer tecla para sair..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
