param([string]$Typst = 'typst')
$ErrorActionPreference = 'Stop'
$reportRoot = Split-Path -Parent $PSScriptRoot

python "$PSScriptRoot/make_figures.py"
if ($LASTEXITCODE -ne 0) { throw 'Figure generation failed' }
python "$PSScriptRoot/check_figures.py"
if ($LASTEXITCODE -ne 0) { throw 'Figure preservation checks failed' }
# xpdf's pdftotext has -table (keeps table rows intact); poppler's does not.
$txtMode = if ((cmd /c "pdftotext -h 2>&1" | Out-String) -match '-table') { '-table' } else { '-layout' }
foreach ($reportName in @('report_nbody', 'report_pyflate', 'report_appendix')) {
    & $Typst compile --root $reportRoot "$PSScriptRoot/$reportName.typ" "$reportRoot/$reportName.pdf"
    if ($LASTEXITCODE -ne 0) { throw "Typst failed: $reportName" }
    pdftotext $txtMode -enc UTF-8 "$reportRoot/$reportName.pdf" "$reportRoot/$reportName.txt"
    if ($LASTEXITCODE -ne 0) { throw "Text export failed: $reportName" }
    Write-Output "Built $reportName.pdf and $reportName.txt"
}
python "$PSScriptRoot/check_txt_tables.py"
if ($LASTEXITCODE -ne 0) { throw 'Text-export table checks failed' }
