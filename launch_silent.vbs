' FalconEYE AI Arpeggio Generator — Silent Launcher
' Launches the Python backend server with NO visible console window.
' Logs are written to backend\server.log
'
' (c) 2026 FalconEYE Software Dev

Dim WshShell, fso, projectDir, venvPython, backendDir, logFile

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Resolve project directory (where this .vbs lives)
projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
venvPython = projectDir & "\venv\Scripts\pythonw.exe"
backendDir = projectDir & "\backend"
logFile = backendDir & "\server.log"

' Fallback to python.exe in venv if pythonw doesn't exist
If Not fso.FileExists(venvPython) Then
    venvPython = projectDir & "\venv\Scripts\python.exe"
End If

' Verify python exists
If Not fso.FileExists(venvPython) Then
    MsgBox "Python virtual environment not found." & vbCrLf & vbCrLf & _
           "Please run build_and_run.bat first to set up the environment.", _
           vbExclamation, "FalconEYE AI Arpeggio Generator"
    WScript.Quit 1
End If

' Build the command — run launcher.py silently, redirect output to log
Dim cmd
cmd = """" & venvPython & """ """ & backendDir & "\launcher.py"" > """ & logFile & """ 2>&1"

' Launch hidden (0 = hidden window, False = don't wait)
WshShell.Run cmd, 0, False

' Brief pause then open browser
WScript.Sleep 2500

' Open the web UI
WshShell.Run "http://localhost:8765", 1, False
