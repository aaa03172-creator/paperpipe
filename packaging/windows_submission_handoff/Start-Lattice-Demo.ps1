$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PAPERPIPE_SUBMISSION_DEMO_BUNDLE = "1"
$env:PAPERPIPE_CLOUD_ADAPTER = "mock"
$env:PAPERPIPE_CLOUD_METADATA_STORE = "memory"
$env:PAPERPIPE_CLOUD_DOWNSTREAM_REGISTRY_STORE = "memory"
$env:PAPERPIPE_SUBMISSION_DEMO_BUNDLE_DIR = Join-Path $Root "submission_demo"
$env:PAPERPIPE_DEMO_EXPECTED_PAPER_ID = "cloudpdf_lab_001_fe476330a3bd"
$env:PAPERPIPE_DEMO_SEARCH_QUERY = "amyloid"
$env:LATTICE_START_PATH = "/ui/papers/cloudpdf_lab_001_fe476330a3bd?source=cloud"
$NativeExe = Join-Path $Root "Lattice.exe"
$FallbackExe = Join-Path $Root "lattice.exe"
if (Test-Path $NativeExe) {
    & $NativeExe
} else {
    & $FallbackExe start --host 127.0.0.1 --port 8046
}
