<#
.SYNOPSIS
    Generates a preview text file from a pure_text.jsonl extraction file.

.DESCRIPTION
    Reads {CRC32}_pure_text.jsonl and generates {CRC32}_preview.txt in the same directory.
    Each line shows: [ID] 0xOFFSET max=<max_len_bytes> | <text_src>

    This is a read-only utility - it does NOT modify any existing pipeline files.

.PARAMETER crc
    The CRC32 hash of the ROM (e.g., "B519E833"). Required unless -jsonlPath is used.

.PARAMETER consoleFolder
    The console subfolder under ROMs/ (default: "Master System")

.PARAMETER jsonlPath
    Direct path to a {CRC32}_pure_text.jsonl file. If provided, -crc/-consoleFolder are ignored
    (CRC32 is inferred from filename if not explicitly provided).

.EXAMPLE
    .\make_preview_from_jsonl.ps1 -crc B519E833

.EXAMPLE
    .\make_preview_from_jsonl.ps1 -crc B519E833 -consoleFolder "Master System"

.EXAMPLE
    .\make_preview_from_jsonl.ps1 -jsonlPath ".\ROMs\Master System\B519E833_pure_text.jsonl"

.NOTES
    Author: ROM Translation Framework
    This utility only reads JSONL and writes preview - no modifications to mapping/reinsertion.
#>

param(
    [Parameter(Mandatory=$false)]
    [string]$crc,

    [Parameter(Mandatory=$false)]
    [string]$consoleFolder = "Master System",

    [Parameter(Mandatory=$false)]
    [string]$jsonlPath
)

# Determine paths based on mode
if ($jsonlPath) {
    # Mode: direct jsonlPath
    if (-not (Test-Path $jsonlPath)) {
        Write-Error "JSONL file not found: $jsonlPath"
        exit 1
    }
    $jsonlFile = Resolve-Path $jsonlPath
    $outputDir = Split-Path -Parent $jsonlFile
    $fileName = Split-Path -Leaf $jsonlFile

    # Infer CRC from filename if not provided
    if (-not $crc) {
        if ($fileName -match '^([0-9A-Fa-f]{8})_pure_text\.jsonl$') {
            $crc = $Matches[1]
        } else {
            Write-Error "Cannot infer CRC32 from filename '$fileName'. Provide -crc or use standard naming: {CRC32}_pure_text.jsonl"
            exit 1
        }
    }
    $previewFile = Join-Path $outputDir "${crc}_preview.txt"
} else {
    # Mode: traditional -crc / -consoleFolder
    if (-not $crc) {
        Write-Error "Missing -crc. Provide -crc or use -jsonlPath."
        exit 1
    }
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $projectRoot = Split-Path -Parent $scriptDir
    $romsDir = Join-Path $projectRoot "ROMs"
    $consolePath = Join-Path $romsDir $consoleFolder
    $jsonlFile = Join-Path $consolePath "${crc}_pure_text.jsonl"
    $previewFile = Join-Path $consolePath "${crc}_preview.txt"

    if (-not (Test-Path $jsonlFile)) {
        Write-Error "JSONL file not found: $jsonlFile"
        exit 1
    }
}

Write-Host "Reading: $jsonlFile"

# Read and process JSONL
$lines = Get-Content $jsonlFile -Encoding UTF8
$previewLines = @()

foreach ($line in $lines) {
    if ([string]::IsNullOrWhiteSpace($line)) {
        continue
    }

    try {
        $item = $line | ConvertFrom-Json

        $id = $item.id
        $offset = $item.offset
        $maxLen = $item.max_len_bytes
        $textSrc = $item.text_src

        # Format: [0001] 0xOFFSET max=<max_len_bytes> | <text_src>
        $idFormatted = $id.ToString().PadLeft(4, '0')
        $previewLine = "[${idFormatted}] ${offset} max=${maxLen} | ${textSrc}"

        $previewLines += $previewLine
    }
    catch {
        Write-Warning "Failed to parse line: $line"
    }
}

# Write preview file
$previewLines | Out-File -FilePath $previewFile -Encoding UTF8

Write-Host "Generated: $previewFile"
Write-Host "Total items: $($previewLines.Count)"
