# Build Notes

## Windows developer setup

```bat
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m app.main --demo
```

## Build an EXE

Run this on a Windows machine. PyInstaller does not cross-build a real Windows `.exe` from macOS.

```bat
build_exe.bat
```

The script installs dependencies, runs tests, builds the app, smoke-tests the generated executable with `--demo`, and creates:

```text
dist\ProductAnalyzer.exe
```

The `ProductAnalyzer.spec` file is configured for PyInstaller and includes the bundled demo inputs from `data/input`. For production packaging, add signing, installer creation, and customer-specific data locations.

## Build a macOS DMG

```bash
./build_dmg.sh
```

The script builds `dist/ProductAnalyzer.app` from `ProductAnalyzerMac.spec`, then creates `dist/ProductAnalyzer-mac.dmg`. In the frozen macOS app, bundled demo inputs are read from the app resources and generated outputs are written to `~/Documents/ProductAnalyzer/output`.
