# Docker Migration Guide - Moving to F: Drive

**Status**: Optional / Low Priority  
**Created**: 2025-01-31  
**Last Updated**: 2025-01-31

---

## Current Status

**C: Drive Space**: 47.4 GB free / 475.6 GB total (9.9% free)  
**F: Drive Space**: 1604 GB free / 3726 GB total (43.1% free)

**Docker Location**: `C:\Users\{User}\AppData\Local\Docker` (WSL2 backend)  
**Docker Size**: ~36.34 GB (images + volumes + build cache)

---

## When to Migrate

### ✅ Migrate Docker to F: Drive When:
- C: drive free space drops below **30 GB**
- Frequent "low disk space" warnings
- Planning to add more Docker images/services
- Running out of space for Windows updates

### ❌ No Need to Migrate If:
- C: drive has > 40 GB free space (current: 47.4 GB)
- Docker usage is stable
- Regular cleanup maintains sufficient space

**Current Recommendation**: **NO MIGRATION NEEDED** after 64GB cleanup completed on 2025-01-31.

---

## Migration Steps (When Needed)

### Prerequisites
- Administrator privileges
- Docker Desktop installed
- Sufficient space on F: drive (at least 50 GB free)
- **Backup important data** before proceeding

### Step 1: Stop Docker Desktop
1. Right-click Docker Desktop tray icon
2. Click "Quit Docker Desktop"
3. Wait for Docker to fully shut down
4. Verify in Task Manager: No `Docker Desktop.exe` or `com.docker.service` processes running

### Step 2: Export WSL2 Docker Data
```powershell
# Open PowerShell as Administrator

# Create target directory
New-Item -ItemType Directory -Path "F:\wsl\docker-data" -Force

# Export docker-desktop-data distribution
wsl --export docker-desktop-data "F:\wsl\docker-data\docker-desktop-data.tar"

# Export docker-desktop distribution (optional, smaller)
wsl --export docker-desktop "F:\wsl\docker-data\docker-desktop.tar"
```

**Note**: Export may take 10-30 minutes depending on Docker data size.

### Step 3: Unregister Old WSL2 Distributions
```powershell
# List current distributions to verify
wsl --list -v

# Unregister docker-desktop-data (THIS DELETES THE C: DRIVE COPY)
wsl --unregister docker-desktop-data

# Unregister docker-desktop (optional)
wsl --unregister docker-desktop
```

⚠️ **WARNING**: This permanently deletes the WSL2 distributions from C: drive. Ensure export succeeded before proceeding!

### Step 4: Import to F: Drive
```powershell
# Import docker-desktop-data to F: drive
wsl --import docker-desktop-data "F:\wsl\docker-desktop-data" "F:\wsl\docker-data\docker-desktop-data.tar" --version 2

# Import docker-desktop to F: drive (if exported)
wsl --import docker-desktop "F:\wsl\docker-desktop" "F:\wsl\docker-data\docker-desktop.tar" --version 2
```

### Step 5: Verify and Start Docker
```powershell
# List distributions - should show new location
wsl --list -v

# Expected output:
# NAME                   STATE           VERSION
# docker-desktop-data    Stopped         2
# docker-desktop         Stopped         2
```

1. Start Docker Desktop
2. Wait for Docker to initialize (2-5 minutes)
3. Verify services are running:
   ```bash
   docker ps
   docker images
   ```

### Step 6: Cleanup (After Successful Migration)
```powershell
# Remove export tar files (optional, saves ~36GB on F:)
Remove-Item "F:\wsl\docker-data\*.tar" -Force
```

---

## Verification Checklist

After migration, verify:

- [ ] Docker Desktop starts successfully
- [ ] All images are present: `docker images`
- [ ] All volumes are intact: `docker volume ls`
- [ ] Services start correctly: `docker compose -f ops/docker/docker-compose.yml up -d`
- [ ] Backend API responds: `curl http://localhost:18000/api/version`
- [ ] Frontend loads: `http://localhost:5173`
- [ ] Ollama responds: `curl http://localhost:11434/api/tags`

---

## Rollback Procedure

If migration fails:

1. **Stop Docker Desktop**
2. **Unregister new distributions**:
   ```powershell
   wsl --unregister docker-desktop-data
   wsl --unregister docker-desktop
   ```
3. **Import from backup**:
   ```powershell
   wsl --import docker-desktop-data "C:\Users\{User}\AppData\Local\Docker\wsl\data" "F:\wsl\docker-data\docker-desktop-data.tar" --version 2
   ```
4. **Restart Docker Desktop**

---

## Expected Space Savings

**Before Migration**:
- C: Drive: 47.4 GB free
- F: Drive: 1604 GB free

**After Migration**:
- C: Drive: ~83 GB free (+36 GB from Docker removal)
- F: Drive: ~1568 GB free (-36 GB from Docker addition)

---

## Alternative: Selective Cleanup Instead of Migration

If C: drive space is still acceptable (>40GB free), consider these alternatives:

### Weekly Maintenance
```bash
# Clean build cache (safe)
docker builder prune -f

# Remove unused images (safe)
docker image prune -f

# Remove unused volumes (CAUTION: verify not in use)
docker volume prune -f
```

### Monthly Deep Clean
```bash
# Remove all unused data (CAUTION: stops containers)
docker system prune -a --volumes
```

### Monitor Space Usage
```bash
# Check Docker disk usage
docker system df -v

# Check C: drive space (PowerShell)
Get-PSDrive C | Select-Object Used,Free
```

---

## Troubleshooting

### Issue: "wsl --export" fails with "Element not found"
**Solution**: Ensure Docker Desktop is fully stopped. Check Task Manager for lingering processes.

### Issue: "wsl --import" fails with "Access denied"
**Solution**: Run PowerShell as Administrator.

### Issue: Docker Desktop won't start after import
**Solution**:
1. Check WSL2 kernel is updated: `wsl --update`
2. Restart computer
3. Check Docker Desktop logs: `%LOCALAPPDATA%\Docker\log.txt`

### Issue: Images/volumes missing after migration
**Solution**: Verify export completed successfully. Check tar file size matches expected data size.

---

## References

- [Docker Desktop WSL2 Backend](https://docs.docker.com/desktop/wsl/)
- [WSL2 Command Reference](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)
- [Moving WSL2 Distributions](https://learn.microsoft.com/en-us/windows/wsl/disk-space)

---

## Maintenance History

| Date | Action | Space Saved | C: Free | F: Free |
|------|--------|-------------|---------|---------|
| 2025-01-31 | Build cache cleanup | 53.58 GB | 47.4 GB | 1604 GB |
| 2025-01-31 | Volume cleanup | 7.23 GB | - | - |
| 2025-01-31 | Dangling image cleanup | 3.40 GB | - | - |
| - | **Migration (if needed)** | 36 GB | 83 GB | 1568 GB |

**Total cleanup without migration: ~64 GB saved**

**Recommendation**: Continue monitoring. Migrate only if C: drops below 30GB.
