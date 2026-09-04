@echo off
REM Shim to make `typescript-language-server` discoverable for tools that spawn it.
REM Uses npx to run the installed package (prefers local, then global).
npx --no-install typescript-language-server %*
