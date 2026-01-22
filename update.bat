@echo off
setlocal enabledelayedexpansion

:: --- KONFIGURACE ---
set "USER=Doomnick"
set "REPO=Performance-Analyzer"
set "ZIP_NAME=app_package.zip"
set "EXE_NAME=Performance Analyzer.exe"
set "HASH_FILE=file_hashes.txt"

echo ===================================================
echo     AKTUALIZACE: %EXE_NAME%
echo ===================================================

:: 1. Pauza pro uvolnění souborů aplikací
echo [1/5] Cekam na ukonceni aplikace...
timeout /t 3 /nobreak > nul

:: 2. Rychlé stahování přes curl
echo [2/5] Stahuji aktualizacni balicek...
curl -L "https://github.com/%USER%/%REPO%/releases/latest/download/%ZIP_NAME%" -o "%ZIP_NAME%"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [CHYBA] Stahovani selhalo. Zkontrolujte internet.
    pause
    exit
)

:: 3. Čištění staré verze
echo [3/5] Odstranuji starou verzi...
if exist "_internal" rd /s /q "_internal"
if exist "templates" rd /s /q "templates"

:: Whitelist: Smažeme soubory, zachováme data a updater
for %%i in (*) do (
    if /i not "%%i"=="update.bat" if /i not "%%i"=="%ZIP_NAME%" if /i not "%%i"=="reporty" if /i not "%%i"=="vysledky" if /i not "%%i"=="last_check_time.txt" if /i not "%%i"=="file_hashes.txt" del /q "%%i"
)

:: 4. Rozbalení balíčku
echo [4/5] Instaluji nove soubory...
tar -xf "%ZIP_NAME%"
if %ERRORLEVEL% neq 0 (
    echo [CHYBA] Rozbaleni se nezdarilo.
    pause
    exit
)

:: 5. Úklid a zápis SHA
echo [5/5] Dokoncovani...
del "%ZIP_NAME%"

:: Zápis nové verze SHA (Silent režim)
for /f "delims=" %%S in ('powershell -Command "$ProgressPreference = 'SilentlyContinue'; (Invoke-RestMethod -Uri 'https://api.github.com/repos/%USER%/%REPO%/contents/app.py').sha"') do set "REMOTE_SHA=%%S"
echo app.py: !REMOTE_SHA!> "%HASH_FILE%"

echo.
echo Aktualizace uspesna! Spoustim aplikaci a zalamuji CMD...
timeout /t 1 > nul

:: Spuštění nové verze
start "" "%EXE_NAME%"

:: --- OKAMŽITÉ UKONČENÍ A SMAZÁNÍ UPDATERU ---
:: Tento řádek smaže soubor update.bat z disku a okamžitě zavře okno CMD
(goto) 2>nul & del "%~f0" & exit