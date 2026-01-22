@echo off
setlocal enabledelayedexpansion

:: --- KONFIGURACE ---
set "USER=Doomnick"
set "REPO=Performance-Analyzer"
set "ZIP_NAME=app_package.zip"
set "EXE_NAME=Performance Analyzer.exe"
set "HASH_FILE=file_hashes.txt"

echo ===========================================
echo    AKTUALIZACE SYSTEMU PERFORMANCE ANALYZER
echo ===========================================

:: 1. Počkáme, až se aplikace Performance Analyzer úplně ukončí
timeout /t 3 /nobreak > nul

:: 2. Stáhneme nejnovější verzi ZIPu z GitHub Releases
echo [1/4] Stahuji aktualizacni balicek...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/%USER%/%REPO%/releases/latest/download/%ZIP_NAME%' -OutFile '%ZIP_NAME%'"

if not exist "%ZIP_NAME%" (
    echo [CHYBA] Nepodarilo se stahnout aktualizaci. Zkontrolujte pripojeni.
    pause
    exit
)

:: 3. Čištění starých souborů (kromě dat a updateru)
echo [2/4] Pripravuji slozku...
:: Smažeme vše kromě reportů, výsledků, temp_plots a updaterů
for /d %%i in (*) do (
    if /i not "%%i"=="reporty" if /i not "%%i"=="vysledky" if /i not "%%i"=="temp_plots" rd /s /q "%%i"
)
for %%i in (*) do (
    if /i not "%%i"=="update.bat" if /i not "%%i"=="%ZIP_NAME%" if /i not "%%i"=="last_check_time.txt" del /q "%%i"
)

:: 4. Rozbalení nového ZIPu
echo [3/4] Instaluji novou verzi...
:: Windows 10/11 mají příkaz tar v základu
tar -xf "%ZIP_NAME%"

:: 5. Úklid a aktualizace HASH_FILE
echo [4/4] Dokoncuji instalaci...
del "%ZIP_NAME%"

:: Získáme SHA z GitHubu znovu pro uložení do local_sha, aby aplikace věděla, že je aktuální
for /f "delims=" %%S in ('powershell -Command "(Invoke-RestMethod -Uri 'https://api.github.com/repos/%USER%/%REPO%/contents/app.py').sha"') do set "REMOTE_SHA=%%S"
echo app.py: !REMOTE_SHA!> "%HASH_FILE%"

echo ===========================================
echo    AKTUALIZACE DOKONCENA!
echo ===========================================
timeout /t 2 > nul

:: Restartujeme přímo EXE
start "" "%EXE_NAME%"
exit