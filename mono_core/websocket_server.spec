# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_all

hidden_jaraco = collect_submodules('jaraco')
datas_pv, binaries_pv, hiddenimports_pv = collect_all('pvporcupine')
datas_silero, binaries_silero, hiddenimports_silero = collect_all('silero_vad')

a = Analysis(
    ['websocket_server.py'],
    pathex=[],
    binaries=binaries_pv + binaries_silero,
    datas=[
        ('core/config.json', 'core'),
        ('RealtimeSTT/assets', 'RealtimeSTT/assets'),
    ] + datas_pv + datas_silero,
    # pkg_resources 在新版本 setuptools 下依赖 jaraco.*，需要显式打包
    hiddenimports=[
        'jaraco', 
        'jaraco.text',
        'scipy._lib.array_api_compat.numpy.fft',
        'scipy._lib.array_api_compat.numpy.linalg',
        'scipy._lib.array_api_compat.numpy.random',
        'scipy._lib.array_api_compat.numpy.testing',
        'silero_vad.data',
        'importlib_resources',
    ] + hidden_jaraco + hiddenimports_pv + hiddenimports_silero,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 移除 excludes=['pkg_resources']，尝试让 PyInstaller 正常打包 pkg_resources 及其依赖
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='websocket_server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
