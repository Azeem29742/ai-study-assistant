$ErrorActionPreference = "Continue"

$API = "http://127.0.0.1:8000"
$passed = 0
$failed = 0

function Test-Check {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    try {
        & $Action
        Write-Host "[PASS] $Name" -ForegroundColor Green
        $script:passed++
    }
    catch {
        Write-Host "[FAIL] $Name" -ForegroundColor Red
        Write-Host "       $($_.Exception.Message)" -ForegroundColor Yellow
        $script:failed++
    }
}

Write-Host ""
Write-Host "========================================"
Write-Host " AI STUDY ASSISTANT - AUTOMATED QA"
Write-Host "========================================"
Write-Host ""

Test-Check "Backend status" {
    $r = Invoke-RestMethod "$API/ai/status"
    if ($r.status -ne "ok") { throw "Backend status was not ok" }
}

Test-Check "Sessions API" {
    $r = Invoke-RestMethod "$API/ai/sessions"
    if ($r.status -ne "success") { throw "Sessions API failed" }
}

Test-Check "Standalone chats API" {
    $r = Invoke-RestMethod "$API/ai/chats?session_id=__standalone_chats__"
    if ($r.status -ne "success") { throw "Standalone chats API failed" }
}

Test-Check "Documents API" {
    $r = Invoke-RestMethod "$API/ai/documents"
    if ($null -eq $r.documents -or $null -eq $r.document_count) { throw "Documents response is invalid" }
}

Test-Check "Projects API" {
    $r = Invoke-RestMethod "$API/ai/projects"
    if ($r.status -ne "success") { throw "Projects API failed" }
}

Test-Check "Default session chats" {
    $r = Invoke-RestMethod "$API/ai/chats?session_id=default"
    if ($r.status -ne "success") { throw "Default session chats failed" }
}

Test-Check "Cover letter session chats" {
    $r = Invoke-RestMethod "$API/ai/chats?session_id=cover%20letter"
    if ($r.status -ne "success") { throw "Cover letter session chats failed" }
}

Test-Check "Chat history endpoint" {
    $sessions = Invoke-RestMethod "$API/ai/sessions"
    $chatId = $null

    foreach ($s in $sessions.sessions) {
        $chats = Invoke-RestMethod "$API/ai/chats?session_id=$([uri]::EscapeDataString($s.session_id))"

        if ($chats.chats -and $chats.chats.Count -gt 0) {
            $chatId = $chats.chats[0].chat_id
            break
        }
    }

    if (-not $chatId) {
        throw "No chat available for history test"
    }

    $r = Invoke-RestMethod "$API/ai/chat-history?chat_id=$([uri]::EscapeDataString($chatId))"

    if ($r.status -ne "success") {
        throw "Chat history request failed"
    }
}

Test-Check "Frontend production build" {
    Push-Location $PSScriptRoot

    try {
        $output = npm run build 2>&1

        if ($LASTEXITCODE -ne 0) {
            throw "npm run build failed"
        }
    }
    finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "========================================"
Write-Host " QA RESULT"
Write-Host "========================================"
Write-Host "Passed: $passed"
Write-Host "Failed: $failed"
Write-Host ""

if ($failed -eq 0) {
    Write-Host "ALL AUTOMATED TESTS PASSED" -ForegroundColor Green
    exit 0
}
else {
    Write-Host "SOME TESTS FAILED" -ForegroundColor Red
    exit 1
}

