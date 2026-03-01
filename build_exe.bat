@echo off
chcp 65001 >nul
echo ============================================
echo   PoENavi - exe Build
echo ============================================
echo.

REM Install dependencies
pip install pyinstaller PySide6 pynput keyboard opencv-python-headless numpy 2>nul

REM Build
pyinstaller --noconfirm --onedir --windowed ^
    --name "PoENavi" ^
    --add-data "icon.jpg;." ^
    --add-data "config.json;." ^
    --add-data "guide_data.json;." ^
    --add-data "monster_levels.json;." ^
    --add-data "assets;assets" ^
    --add-data "maps;maps" ^
    --hidden-import "PySide6.QtWidgets" ^
    --hidden-import "PySide6.QtCore" ^
    --hidden-import "PySide6.QtGui" ^
    --hidden-import "pynput" ^
    --hidden-import "pynput.keyboard" ^
    --hidden-import "pynput.keyboard._win32" ^
    --hidden-import "keyboard" ^
    --hidden-import "cv2" ^
    --hidden-import "numpy" ^
    --exclude-module "PySide6.Qt3DAnimation" ^
    --exclude-module "PySide6.Qt3DCore" ^
    --exclude-module "PySide6.Qt3DExtras" ^
    --exclude-module "PySide6.Qt3DInput" ^
    --exclude-module "PySide6.Qt3DLogic" ^
    --exclude-module "PySide6.Qt3DRender" ^
    --exclude-module "PySide6.QtBluetooth" ^
    --exclude-module "PySide6.QtCharts" ^
    --exclude-module "PySide6.QtDataVisualization" ^
    --exclude-module "PySide6.QtDesigner" ^
    --exclude-module "PySide6.QtHelp" ^
    --exclude-module "PySide6.QtLocation" ^
    --exclude-module "PySide6.QtMultimedia" ^
    --exclude-module "PySide6.QtMultimediaWidgets" ^
    --exclude-module "PySide6.QtNetworkAuth" ^
    --exclude-module "PySide6.QtNfc" ^
    --exclude-module "PySide6.QtOpenGL" ^
    --exclude-module "PySide6.QtOpenGLWidgets" ^
    --exclude-module "PySide6.QtPdf" ^
    --exclude-module "PySide6.QtPdfWidgets" ^
    --exclude-module "PySide6.QtPositioning" ^
    --exclude-module "PySide6.QtQml" ^
    --exclude-module "PySide6.QtQuick" ^
    --exclude-module "PySide6.QtQuick3D" ^
    --exclude-module "PySide6.QtQuickWidgets" ^
    --exclude-module "PySide6.QtRemoteObjects" ^
    --exclude-module "PySide6.QtScxml" ^
    --exclude-module "PySide6.QtSensors" ^
    --exclude-module "PySide6.QtSerialBus" ^
    --exclude-module "PySide6.QtSerialPort" ^
    --exclude-module "PySide6.QtSpatialAudio" ^
    --exclude-module "PySide6.QtSql" ^
    --exclude-module "PySide6.QtStateMachine" ^
    --exclude-module "PySide6.QtSvg" ^
    --exclude-module "PySide6.QtSvgWidgets" ^
    --exclude-module "PySide6.QtTest" ^
    --exclude-module "PySide6.QtTextToSpeech" ^
    --exclude-module "PySide6.QtUiTools" ^
    --exclude-module "PySide6.QtWebChannel" ^
    --exclude-module "PySide6.QtWebEngine" ^
    --exclude-module "PySide6.QtWebEngineCore" ^
    --exclude-module "PySide6.QtWebEngineWidgets" ^
    --exclude-module "PySide6.QtWebSockets" ^
    --exclude-module "PySide6.QtXml" ^
    --exclude-module "tkinter" ^
    --exclude-module "unittest" ^
    --exclude-module "email" ^
    --exclude-module "http" ^
    --exclude-module "xml" ^
    main.py

echo.
if exist dist\PoENavi\PoENavi.exe (
    echo BUILD SUCCESS!
    echo    exe is in: dist\PoENavi
    echo    Zip the dist\PoENavi\ folder to distribute
) else (
    echo BUILD FAILED. Check errors above.
)
echo.
pause
