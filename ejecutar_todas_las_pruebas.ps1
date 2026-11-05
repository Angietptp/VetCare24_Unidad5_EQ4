<#
  Corre todas las pruebas de la Unidad 5:
    1) Laboratorio: entorno virtual, Ruff y pytest con cobertura (minimo 80 %).
    2) VetCare 24: pruebas dentro de Docker Compose (requiere Docker Desktop abierto).

  Uso (desde la raiz del repositorio):
    powershell -ExecutionPolicy Bypass -File .\ejecutar_todas_las_pruebas.ps1
  Opciones:
    -SoloLaboratorio   omite VetCare 24
    -SoloVetCare       omite el laboratorio
#>
param([switch]$SoloLaboratorio, [switch]$SoloVetCare)

$ErrorActionPreference = "Continue"
$raiz = $PSScriptRoot
$resumen = @()

function Paso($titulo) { Write-Host "`n=== $titulo ===" -ForegroundColor Cyan }

if (-not $SoloVetCare) {
    Paso "LABORATORIO"
    Push-Location (Join-Path $raiz "01_LABORATORIO_U5\laboratorio_U5")
    if (-not (Test-Path ".venv")) { py -m venv .venv }
    & .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt
    & .\.venv\Scripts\python.exe -m ruff check src tests
    $ruff = $LASTEXITCODE
    & .\.venv\Scripts\python.exe -m pytest -v --cov=src --cov-report=term-missing --cov-report=html --cov-fail-under=80
    $pytest = $LASTEXITCODE
    Pop-Location
    $resumen += [pscustomobject]@{ Proyecto = "Laboratorio"; Ruff = $(if ($ruff -eq 0) {"OK"} else {"FALLA"}); Pruebas = $(if ($pytest -eq 0) {"OK"} else {"FALLA"}) }
}

if (-not $SoloLaboratorio) {
    Paso "VETCARE 24 (Docker)"
    Push-Location (Join-Path $raiz "02_PIA_VETCARE24")
    if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
    docker compose --profile tests build tests
    docker compose --profile tests run --rm tests
    $docker = $LASTEXITCODE
    Pop-Location
    $resumen += [pscustomobject]@{ Proyecto = "VetCare 24"; Ruff = "(en el CI)"; Pruebas = $(if ($docker -eq 0) {"OK"} else {"FALLA"}) }
}

Paso "RESUMEN"
$resumen | Format-Table -AutoSize
