# Builds a signed release APK at android\dist\HealthScale.apk
# Downloads a JDK 17 and the Android SDK into %LOCALAPPDATA% when they are missing.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$AndroidDir = $PSScriptRoot
$DistDir = Join-Path $AndroidDir "dist"
$KeystoreDir = Join-Path $AndroidDir "keystore"
$SdkRoot = Join-Path $env:LOCALAPPDATA "Android\Sdk"
$JdkRoot = Join-Path $env:LOCALAPPDATA "HealthScale\jdk-17"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message"
}

function Test-Jdk17([string]$JavaHome) {
    $java = Join-Path $JavaHome "bin\java.exe"
    if (-not (Test-Path $java)) { return $false }
    $versionText = (cmd /c "`"$java`" -version 2>&1") -join "`n"
    if ($versionText -match 'version "(?<major>\d+)') {
        return [int]$Matches.major -ge 17
    }
    return $false
}

function Find-Jdk17 {
    $candidates = @()
    if ($env:JAVA_HOME) { $candidates += $env:JAVA_HOME }
    $candidates += $JdkRoot
    $candidates += @(
        "C:\Program Files\Eclipse Adoptium\jdk-17*",
        "C:\Program Files\Java\jdk-17*",
        "C:\Program Files\Microsoft\jdk-17*",
        "C:\Program Files\Android\Android Studio\jbr"
    )
    foreach ($pattern in $candidates) {
        $matches = @(Get-Item $pattern -ErrorAction SilentlyContinue)
        foreach ($item in $matches) {
            if (Test-Jdk17 $item.FullName) { return $item.FullName }
        }
    }
    return $null
}

function Ensure-Jdk17 {
    $existing = Find-Jdk17
    if ($existing) { return $existing }

    Write-Step "Downloading JDK 17 (one time)"
    $zip = Join-Path $env:TEMP "temurin-jdk-17.zip"
    $extract = Join-Path $env:TEMP "temurin-jdk-17"
    if (Test-Path $extract) { Remove-Item $extract -Recurse -Force }
    Invoke-WebRequest `
        -Uri "https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jdk/hotspot/normal/eclipse?project=jdk" `
        -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $extract -Force
    $inner = Get-ChildItem $extract -Directory | Select-Object -First 1
    if (-not $inner) { throw "JDK archive did not contain a folder." }
    if (Test-Path $JdkRoot) { Remove-Item $JdkRoot -Recurse -Force }
    New-Item -ItemType Directory -Force -Path (Split-Path $JdkRoot) | Out-Null
    Move-Item $inner.FullName $JdkRoot
    if (-not (Test-Jdk17 $JdkRoot)) { throw "Downloaded JDK is not usable at $JdkRoot" }
    return $JdkRoot
}

function Ensure-AndroidSdk {
    $platform = Join-Path $SdkRoot "platforms\android-35"
    $buildTools = Join-Path $SdkRoot "build-tools"
    if ((Test-Path $platform) -and (Test-Path $buildTools)) { return }

    $sdkmanager = Join-Path $SdkRoot "cmdline-tools\latest\bin\sdkmanager.bat"
    if (-not (Test-Path $sdkmanager)) {
        Write-Step "Downloading Android command-line tools (one time)"
        $zip = Join-Path $env:TEMP "android-cmdline-tools.zip"
        $extract = Join-Path $env:TEMP "android-cmdline-tools"
        $urls = @(
            "https://dl.google.com/android/repository/commandlinetools-win-13114758_latest.zip",
            "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"
        )
        $downloaded = $false
        foreach ($url in $urls) {
            try {
                Invoke-WebRequest -Uri $url -OutFile $zip
                $downloaded = $true
                break
            } catch {
                Write-Host "Could not download $url"
            }
        }
        if (-not $downloaded) { throw "Could not download Android command-line tools." }
        if (Test-Path $extract) { Remove-Item $extract -Recurse -Force }
        Expand-Archive -Path $zip -DestinationPath $extract -Force
        $latest = Join-Path $SdkRoot "cmdline-tools\latest"
        if (Test-Path $latest) { Remove-Item $latest -Recurse -Force }
        New-Item -ItemType Directory -Force -Path (Split-Path $latest) | Out-Null
        $unpacked = Join-Path $extract "cmdline-tools"
        if (-not (Test-Path $unpacked)) { throw "Command-line tools archive layout was unexpected." }
        Move-Item $unpacked $latest
    }

    Write-Step "Installing Android SDK 35 (one time)"
    $yes = ("y`n" * 80)
    $yes | & $sdkmanager --sdk_root=$SdkRoot --licenses | Out-Host
    & $sdkmanager --sdk_root=$SdkRoot "platforms;android-35" "build-tools;35.0.0"
    if ($LASTEXITCODE -ne 0) { throw "sdkmanager failed to install platform 35." }
    if (-not (Test-Path $platform)) { throw "Android SDK platform 35 was not installed." }
}

function Ensure-GradleWrapper {
    $jar = Join-Path $AndroidDir "gradle\wrapper\gradle-wrapper.jar"
    if (Test-Path $jar) { return }
    Write-Step "Downloading Gradle wrapper"
    New-Item -ItemType Directory -Force -Path (Split-Path $jar) | Out-Null
    Invoke-WebRequest `
        -Uri "https://github.com/gradle/gradle/raw/v8.9.0/gradle/wrapper/gradle-wrapper.jar" `
        -OutFile $jar
}

function Ensure-Keystore([string]$JavaHome) {
    $store = Join-Path $KeystoreDir "healthscale.jks"
    $props = Join-Path $KeystoreDir "keystore.properties"
    if ((Test-Path $store) -and (Test-Path $props)) { return }

    Write-Step "Creating a signing key for phone installs"
    New-Item -ItemType Directory -Force -Path $KeystoreDir | Out-Null
    $alphabet = (48..57) + (65..90) + (97..122)
    $password = -join ($alphabet | Get-Random -Count 24 | ForEach-Object { [char]$_ })
    $keytool = Join-Path $JavaHome "bin\keytool.exe"
    & $keytool -genkeypair -v `
        -keystore $store `
        -alias healthscale `
        -keyalg RSA -keysize 2048 -validity 10000 `
        -storepass $password -keypass $password `
        -dname "CN=Health Scale Hub, O=Personal, C=US"
    if ($LASTEXITCODE -ne 0) { throw "keytool failed to create the signing key." }

    @(
        "storePassword=$password"
        "keyPassword=$password"
        "keyAlias=healthscale"
    ) | Set-Content -Path $props -Encoding ascii
}

function Write-LocalProperties {
    $sdk = ($SdkRoot -replace '\\', '/')
    Set-Content -Path (Join-Path $AndroidDir "local.properties") -Value "sdk.dir=$sdk" -Encoding ascii
}

Write-Step "Preparing the Android build"
$javaHome = Ensure-Jdk17
$env:JAVA_HOME = $javaHome
$env:ANDROID_HOME = $SdkRoot
$env:ANDROID_SDK_ROOT = $SdkRoot
Write-Host "JDK: $javaHome"

Ensure-AndroidSdk
Ensure-GradleWrapper
Ensure-Keystore $javaHome
Write-LocalProperties

Write-Step "Building HealthScale.apk"
Push-Location $AndroidDir
try {
    & .\gradlew.bat assembleRelease --no-daemon
    if ($LASTEXITCODE -ne 0) { throw "Gradle build failed." }
} finally {
    Pop-Location
}

$apk = Join-Path $AndroidDir "app\build\outputs\apk\release\app-release.apk"
if (-not (Test-Path $apk)) { throw "Build finished but the APK was not found." }
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null
$dest = Join-Path $DistDir "HealthScale.apk"
Copy-Item $apk $dest -Force

Write-Host ""
Write-Host "APK ready: $dest"
Write-Host ""
Write-Host "USB install:"
Write-Host "  1. Plug in the phone and choose File transfer in the USB notification."
Write-Host "  2. Copy HealthScale.apk into the phone's Download folder."
Write-Host "  3. On the phone, open Files and tap the APK. Allow Install unknown apps if asked."
