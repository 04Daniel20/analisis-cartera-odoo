@echo off
REM ============================================================
REM  Actualizacion automatica del dataset - la firma
REM  Daniel Castillo
REM
REM  Que hace:
REM    Ejecuta el script de extraccion y deja constancia en un log.
REM    Pensado para correr desatendido desde el Programador de tareas.
REM ============================================================

cd /d C:\proyecto-datos

REM Marca de tiempo para el log
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set dt=%%I
set FECHA=%dt:~0,4%-%dt:~4,2%-%dt:~6,2%_%dt:~8,2%%dt:~10,2%

echo. >> log_actualizacion.txt
echo ============================================ >> log_actualizacion.txt
echo EJECUCION: %FECHA% >> log_actualizacion.txt
echo ============================================ >> log_actualizacion.txt

python 05_extraccion_dataset.py >> log_actualizacion.txt 2>&1

if %ERRORLEVEL% EQU 0 (
    echo RESULTADO: OK >> log_actualizacion.txt
) else (
    echo RESULTADO: ERROR - codigo %ERRORLEVEL% >> log_actualizacion.txt
)

REM Si quieres ver la ventana al probarlo a mano, descomenta la linea siguiente:
REM pause
