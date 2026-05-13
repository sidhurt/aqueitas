$HookDir = Resolve-Path ".\sensor"
git config --global core.hooksPath $HookDir.Path
Write-Host "Global Git hooks path successfully set to: $($HookDir.Path)"
Write-Host "Aqueitas Sensor is now watching all Git commits globally."
