# assign-port.ps1 — deterministic port assignment for parallel SUMMIT worktrees.
#
# WHY:
#   Ariel runs Windows 10 with built-in OpenSSH + PowerShell. This is the Windows
#   sibling of scripts/assign-port.sh. Both scripts MUST produce identical output
#   for an identical cwd string — parity is verified in test/assign-port.Tests.ps1
#   (and matching bats tests for .sh).
#
# PARITY CONTRACT:
#   - Same hash algo (MD5), same byte order (big-endian first 4 bytes as UInt32)
#   - Same constants: BASE_PORT=4000, WORKTREE_BASE=4100, WORKTREE_RANGE=100
#   - Same env precedence: $env:PORT > allowlist match > md5 hash
#   - Same allowlist: main repo leaf name only
#
# USAGE:
#   .\scripts\assign-port.ps1                         # prints port for $PWD
#   $env:PORT=9999; .\scripts\assign-port.ps1         # prints 9999
#   $env:CWD='C:\worktrees\foo'; .\scripts\assign-port.ps1  # prints port for CWD

$ErrorActionPreference = 'Stop'

$BasePort      = 4000
$WorktreeBase  = 4100
$WorktreeRange = 100

# CWD override exists so .sh and .ps1 can be tested against identical inputs
# for cross-platform parity. Normal invocation uses $PWD.
$cwd = if ($env:CWD) { $env:CWD } else { (Get-Location).Path }
$leaf = Split-Path -Leaf $cwd

# Env override always wins.
if ($env:PORT) {
  Write-Output $env:PORT
  exit 0
}

# Main repo checkout returns base port. Keep in sync with .sh allowlist.
if ($leaf -eq 'cli-anything-biddeed') {
  Write-Output $BasePort
  exit 0
}

# Hash cwd → first 4 bytes of MD5 as big-endian UInt32 → mod WorktreeRange.
$md5 = [System.Security.Cryptography.MD5]::Create()
try {
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($cwd)
  $hash = $md5.ComputeHash($bytes)
  # Big-endian: byte 0 is high-order. [BitConverter]::ToUInt32 is little-endian on x86,
  # so reverse the first 4 bytes for cross-platform byte-order parity with md5sum.
  $be = [byte[]]@($hash[0], $hash[1], $hash[2], $hash[3])
  [array]::Reverse($be)
  $u32 = [BitConverter]::ToUInt32($be, 0)
  $offset = [int]($u32 % $WorktreeRange)
  Write-Output ($WorktreeBase + $offset)
} finally {
  $md5.Dispose()
}
