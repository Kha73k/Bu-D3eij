; bud3eij.iss - Inno Setup script for the Bu D3eij feature-selective installer.
;
; STATUS: UNVERIFIED - written by construction, not yet compiled/installed in this
; environment. Compile with Inno Setup 6 (ISCC.exe) AFTER running installer\build.ps1
; to stage installer\build\. Test on a clean Windows VM (no Python, no model cache).
;
; Flow: component page (Core forced + optional Marquee/Vanguard/Sonara) -> a PyTorch
; CPU/CUDA page (shown only if a torch feature is picked, defaulted by GPU detection)
; -> copy the staged Python + app source -> run bootstrap.py to pip-install the
; selection -> create the shortcut. ML model weights download on first tool use.

#define AppName "Bu D3eij"
#define AppVersion "4.4.0"
#define Publisher "Kha73k"
#define AppURL "https://github.com/Kha73k/Bu-D3eij"

[Setup]
AppId={{B7D3E1A0-1F2C-4B5A-9C6D-BUD3EIJ00001}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#Publisher}
AppPublisherURL={#AppURL}
WizardStyle=modern
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
SetupIconFile=..\AppLogo.ico
OutputDir=dist
OutputBaseFilename=BuD3eij-Setup
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Per-user by default (no admin needed); the user can elevate for a machine-wide install.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Messages]
; Tell the user up front that a setup window will appear after the wizard, so the
; pip-install console reads as an expected, safe step rather than something scary.
WelcomeLabel2=This will install [name/ver] on your computer.%n%nAfter the wizard copies the app, a small "Bu D3eij - Setup" window will open and install the parts you choose. It downloads the components the app needs and sets them up on this PC - nothing of yours is uploaded. That step is normal and can take a few minutes; please let it finish.%n%nIt's recommended that you close all other applications before continuing.

[Types]
Name: "full"; Description: "All features"
Name: "compact"; Description: "Core only"
Name: "custom"; Description: "Custom"; Flags: iscustom

[Components]
Name: "core";     Description: "Core - File Converter, Nexus, YouTube, ASCII Art";        Types: full compact custom; Flags: fixed
Name: "marquee";  Description: "Marquee - Background Remover, Upscaler, Image to Prompt (PyTorch)"; Types: full
Name: "vanguard"; Description: "Vanguard - AI Text Detector, Text Extraction, Font ID";   Types: full
Name: "sonara";   Description: "Sonara - Audio Stem Splitter (PyTorch)";                   Types: full

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
; The staged folder (installer\build\) holds the standalone Python + all app source.
; Shipping all source is cheap; the feature selection only changes which pip packages
; bootstrap.py installs. (Run installer\build.ps1 first.)
Source: "build\*"; DestDir: "{app}"; Excludes: "_cache\*"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app.py"""; WorkingDir: "{app}"; IconFilename: "{app}\AppLogo.ico"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app.py"""; WorkingDir: "{app}"; IconFilename: "{app}\AppLogo.ico"; Tasks: desktopicon

[Run]
; "Launch Bu D3eij" checkbox on the final wizard page (checked by default).
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app.py"""; WorkingDir: "{app}"; Description: "Launch {#AppName}"; Flags: postinstall nowait skipifsilent

[Code]
var
  GpuPage: TInputOptionWizardPage;

function HasNvidia(): Boolean;
var
  ResultCode: Integer;
begin
  // nvidia-smi.exe ships with the NVIDIA driver (usually on PATH in System32).
  Result := Exec('nvidia-smi', '-L', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

procedure InitializeWizard();
begin
  GpuPage := CreateInputOptionPage(wpSelectComponents,
    'PyTorch build', 'Choose the compute backend for the AI tools.',
    'Marquee and Sonara use PyTorch. CPU works on any PC; CUDA is much faster but ' +
    'needs an NVIDIA GPU and is a larger download.',
    True, False);
  GpuPage.Add('CPU  (recommended - works on any PC)');
  GpuPage.Add('CUDA 12.6  (NVIDIA GPU - much faster)');
  if HasNvidia() then
    GpuPage.SelectedValueIndex := 1
  else
    GpuPage.SelectedValueIndex := 0;
end;

function NeedsTorch(): Boolean;
begin
  Result := WizardIsComponentSelected('marquee') or WizardIsComponentSelected('sonara');
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  // Only ask about CPU/CUDA when a torch-dependent feature is selected.
  if (PageID = GpuPage.ID) then
    Result := not NeedsTorch()
  else
    Result := False;
end;

function GetFeatures(): String;
var
  s: String;
begin
  s := '';
  if WizardIsComponentSelected('marquee')  then s := s + 'marquee,';
  if WizardIsComponentSelected('vanguard') then s := s + 'vanguard,';
  if WizardIsComponentSelected('sonara')   then s := s + 'sonara,';
  if (Length(s) > 0) and (s[Length(s)] = ',') then
    s := Copy(s, 1, Length(s) - 1);
  Result := s;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  Torch, Args: String;
begin
  if CurStep = ssPostInstall then
  begin
    if NeedsTorch() and (GpuPage.SelectedValueIndex = 1) then
      Torch := 'cuda'
    else
      Torch := 'cpu';
    Args := 'bootstrap.py --features "' + GetFeatures() + '" --torch ' + Torch +
            ' --reqs-dir "' + ExpandConstant('{app}\requirements') + '"';
    // SW_SHOW: the user watches the branded "Bu D3eij - Setup" console (bootstrap.py)
    // explain itself and show pip's progress (this can take minutes / GBs).
    if not Exec(ExpandConstant('{app}\python\python.exe'), Args, ExpandConstant('{app}'),
                SW_SHOW, ewWaitUntilTerminated, ResultCode) then
      MsgBox('Bu D3eij could not start its component setup. Please run the ' +
             'installer again.', mbError, MB_OK)
    else if ResultCode <> 0 then
      MsgBox('Bu D3eij could not finish setting up its components (code ' +
             IntToStr(ResultCode) + ').' + #13#10#13#10 +
             'This is almost always a temporary network problem - please check ' +
             'your internet connection and run the installer again.', mbError, MB_OK);
  end;
end;
