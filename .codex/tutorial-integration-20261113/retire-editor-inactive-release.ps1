$ErrorActionPreference='Stop'
$planPath='C:/pc/3_code/code_rust/wood_research/.codex/tutorial-integration-20261113/editor-wasm-headroom-plan.json'
$plan=Get-Content -LiteralPath $planPath -Raw | ConvertFrom-Json
$cache=[IO.Path]::GetFullPath($plan.cacheRoot).TrimEnd('\')+'\'
$archive=[IO.Path]::GetFullPath($plan.archiveRoot).TrimEnd('\')+'\'
if($cache -ne 'C:\pc\3_code\code_rust\wood_research\session\session_viewer\target\course-cargo\'){throw 'Unexpected cache'}
if($archive -ne 'C:\pc\tmp\tutorial-presentation-release-cache-20261114\'){throw 'Unexpected archive'}
if((Get-FileHash -LiteralPath $plan.protection.path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $plan.protection.sha256){throw 'Protection changed'}
$protection=Get-Content -LiteralPath $plan.protection.path -Raw | ConvertFrom-Json
$protected=@{}; foreach($p in @($protection.baselinePaths)+@($protection.currentViewerCompilerPathRequirements)){$protected[$p]=$true}
foreach($row in $plan.rows){
 $source=[IO.Path]::GetFullPath($row.source);$dest=[IO.Path]::GetFullPath($row.destination)
 if(!$source.StartsWith($cache,[StringComparison]::OrdinalIgnoreCase) -or !$dest.StartsWith($archive,[StringComparison]::OrdinalIgnoreCase)){throw 'Path escapes approved roots'}
 if($protected.ContainsKey($row.path)){throw 'Protected input'}
 if(Test-Path -LiteralPath $dest){throw 'Archive destination exists'}
 $item=Get-Item -LiteralPath $source
 if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or $item.Length -ne $row.bytes){throw 'Source redirected or changed'}
 if((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $row.sha256){throw 'Source hash changed'}
}
$parents=@{}
foreach($row in $plan.rows){foreach($file in @($row.source,$row.destination)){$dir=[IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($file));while($dir){$parents[$dir]=$true;$dir=[IO.Path]::GetDirectoryName($dir)}}}
foreach($dir in $parents.Keys){if((Test-Path -LiteralPath $dir) -and (((Get-Item -LiteralPath $dir).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)){throw 'Parent directory is redirected'}}
$resultPath='C:/pc/3_code/code_rust/wood_research/.codex/tutorial-integration-20261113/editor-wasm-headroom-result.json'
if(Test-Path -LiteralPath $resultPath){throw 'Preserve prior attempt'}
$moved=@()
try{
 foreach($row in $plan.rows){
  [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($row.destination))|Out-Null
  Move-Item -LiteralPath $row.source -Destination $row.destination
  if((Get-FileHash -LiteralPath $row.destination -Algorithm SHA256).Hash.ToLowerInvariant() -ne $row.sha256){throw 'Archive verification failed'}
  $moved+=$row.path
 }
}finally{
 @{at=[DateTime]::UtcNow.ToString('o');planSha256=(Get-FileHash -LiteralPath $planPath -Algorithm SHA256).Hash.ToLowerInvariant();moved=$moved;complete=($moved.Count -eq $plan.rows.Count)}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $resultPath
}
Write-Output ('Archived '+$moved.Count+' exact inactive release files; no source or protected files changed.')