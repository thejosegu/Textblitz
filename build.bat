@echo off
setlocal enabledelayedexpansion

set LOGFILE=%~dp0build.log
echo. > "%LOGFILE%"

echo ============================================
echo  Blitztext Build
echo ============================================
echo.

:: PyInstaller
echo [1/2] Erstelle Blitztext.exe ...
python -m PyInstaller blitztext.spec --noconfirm --upx-dir "%~dp0" >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo.
    echo FEHLER: Build fehlgeschlagen. Details in build.log
    pause
    exit /b 1
)
echo     OK

:: faster-whisper + av in dist\libs\ installieren
echo.
echo [2/2] Installiere faster-whisper + av nach dist\libs\ ...
if exist "%~dp0dist\libs\" rmdir /S /Q "%~dp0dist\libs"
mkdir "%~dp0dist\libs"

python -m pip install faster-whisper ctranslate2 tokenizers av --no-deps ^
    --target "%~dp0dist\libs" --upgrade >> "%LOGFILE%" 2>&1
python -m pip install huggingface_hub filelock packaging tqdm ^
    requests urllib3 certifi charset-normalizer idna fsspec --no-deps ^
    --target "%~dp0dist\libs" --upgrade >> "%LOGFILE%" 2>&1

if errorlevel 1 (
    echo     WARNUNG: Installation fehlgeschlagen - lokaler Modus nicht verfuegbar.
    echo     Details in build.log
) else (
    echo     OK
)

echo.
echo ============================================
echo  Fertig: dist\Blitztext.exe
echo ============================================
echo.
if exist "%~dp0dist\whisper\model.bin" (
    echo   Whisper-Modell:  dist\whisper\ OK
) else (
    echo   Whisper-Modell:  FEHLT - dist\whisper\model.bin manuell ablegen
)
echo   Einstellungen:   dist\config.json ^(auto-erstellt^)
echo   Build-Log:       build.log
echo.
pause
