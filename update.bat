@echo off
setlocal enabledelayedexpansion

set "USER=Doomnick"
set "REPO=Performance-Analyzer"
set "HASH_FILE=file_hashes.txt"
set "FILES=app.py;app.py processor.py;processor.py master_engine.py;master_engine.py graphics_engine.py;graphics_engine.py report_generator.py;report_generator.py templates/report_template.html;templates/report_template.html"

echo ===========================================
echo   PROBIHA AKTUALIZACE... Prosim cekejte.
echo ===========================================

:: Krátká pauza pro uvolnění souborů Pythonem
timeout /t 2 >nul

for %%A in (%FILES%) do (
    for /f "tokens=1,2 delims=;" %%B in ("%%A") do (
        set "R_PATH=%%B" & set "L_PATH=%%C"
        
        :: Stažení SHA a souboru
        for /f "delims=" %%S in ('powershell -Command "(Invoke-RestMethod -UseBasicParsing -Uri 'https://api.github.com/repos/%USER%/%REPO%/contents/!R_PATH!').sha"') do set "REMOTE_SHA=%%S"
        
        echo Aktualizuji: !L_PATH!
        for %%D in (!L_PATH!) do if not exist "%%~dpD" mkdir "%%~dpD"
        powershell -Command "Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/%USER%/%REPO%/main/!R_PATH!' -OutFile '!L_PATH!'"
        
        :: Zápis nového SHA
        type "%HASH_FILE%" | findstr /V /C:"!R_PATH!:" > "%HASH_FILE%.tmp" 2>nul
        echo !R_PATH!: !REMOTE_SHA!>> "%HASH_FILE%.tmp"
        move /y "%HASH_FILE%.tmp" "%HASH_FILE%" >nul
    )
)

echo.
echo Hotovo! Restartuji aplikaci...
start "" "Spustit.bat"
exit