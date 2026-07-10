# Packaging

Use the PowerShell build script to create a directly runnable Windows exe:

```powershell
.\build_exe.ps1
```

The default output is:

```text
dist\MixerSpectrumDemo.exe
```

The script copies the local Python Tcl/Tk runtime into `runtime_tcl`, then runs
PyInstaller with `pyinstaller_runtime_hook.py` so the packaged Tkinter app can
find `init.tcl` after extraction.

To rebuild with a different executable name:

```powershell
.\build_exe.ps1 -AppName MixerSpectrumDemoDev
```

Generated directories such as `build`, `dist`, and `runtime_tcl` can be deleted
and recreated by running the script again.
