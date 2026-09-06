param([string]$Typst = 'typst')
$ErrorActionPreference = 'Stop'
$reportRoot = Split-Path -Parent $PSScriptRoot

python "$PSScriptRoot/make_figures.py"
if ($LASTEXITCODE -ne 0) { throw 'Figure generation failed' }
python "$PSScriptRoot/check_figures.py"
if ($LASTEXITCODE -ne 0) { throw 'Figure preservation checks failed' }
foreach ($reportName in @('report_nbody', 'report_pyflate', 'report_appendix')) {
    & $Typst compile --root $reportRoot "$PSScriptRoot/$reportName.typ" "$reportRoot/$reportName.pdf"
    if ($LASTEXITCODE -ne 0) { throw "Typst failed: $reportName" }
    pdftotext -layout -enc UTF-8 "$reportRoot/$reportName.pdf" "$reportRoot/$reportName.txt"
    if ($LASTEXITCODE -ne 0) { throw "Text export failed: $reportName" }
    Write-Output "Built $reportName.pdf and $reportName.txt"
}
