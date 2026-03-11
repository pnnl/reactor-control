# Personal DAQ/56 Troubleshooting Guide

## Table of Contents
1. [Overview](#overview)
2. [Architecture Problem](#architecture-problem)
3. [32-bit Python Setup](#32-bit-python-setup)
4. [Configuration](#configuration)
5. [Common Issues](#common-issues)
6. [Troubleshooting Steps](#troubleshooting-steps)
7. [Test Procedures](#test-procedures)
8. [Known Limitations](#known-limitations)

---

## Overview

The Personal DAQ/56 is a USB data acquisition module manufactured by IOtech (acquired by Measurement Computing, now part of Digilent).

### Device Specifications
- **Model:** Personal DAQ/56 (OMB-DAQ-56)
- **Connection:** USB 1.1 & 2.0 compatible
- **ADC Resolution:** 22-bit
- **Sample Rate:** 1 to 80 Hz
- **Thermocouple Support:** Type K (and others) with built-in cold-junction compensation
- **Digital Isolation:** 500V optical isolation from PC
- **USB Vendor ID:** VID_0622&PID_0001

### Driver Information
- **DLL Required:** `pdaqx.dll`
- **Driver Version:** 3.0.0.0 (Released: 2011-11-01)
- **Architecture:** **32-bit only**
- **Status:** Legacy/End of Life (no 64-bit drivers available)

---

## Architecture Problem

### The Core Issue

**Personal DAQ/56 drivers are 32-bit only and incompatible with 64-bit Python.**

When attempting to load the 32-bit `pdaqx.dll` with 64-bit Python, you get:

```
OSError: [WinError 193] %1 is not a valid Win32 application
```

### Why This Happens

| Python Architecture | DLL Architecture | Result |
|-------------------|-------------------|---------|
| 64-bit | 32-bit | ❌ **FAILS** - Cannot load DLL |
| 32-bit | 32-bit | ✅ **WORKS** - Compatible |

### No 64-bit Driver Exists

After extensive research:
- Measurement Computing/Digilent does NOT provide 64-bit drivers for Personal DAQ/56
- The last driver update was in 2011 (14+ years ago)
- Personal DAQ/50 series is listed as "Legacy" and "End of Life"
- NI Community vendor response (2010): *"pDAQ-50 series will work on 32-bit Operating systems only as USB driver is not compatible with 64-bit OS yet."*

### Long-term Recommendation

Consider migrating to a modern DAQ device with 64-bit support:
- MCC USB-2600 Series (high-speed, high-channel USB DAQ)
- Or any Digilent/MCC device with current 64-bit driver support

---

## 32-bit Python Setup

### Step 1: Install 32-bit Python

Download and install Python 3.14.2 (32-bit embeddable):

```bash
# Download 32-bit embeddable Python
curl -o python-3.14.2-embed-win32.zip https://www.python.org/ftp/python/3.14.2/python-3.14.2-embed-win32.zip

# Extract to C:\Python314-32bit\
python -m zipfile -e python-3.14.2-embed-win32.zip C:\Python314-32bit

# Enable site-packages
echo python314.zip > C:\Python314-32bit\python314._pth
echo . >> C:\Python314-32bit\python314._pth
echo import site >> C:\Python314-32bit\python314._pth
```

### Step 2: Install Dependencies

```bash
# Install pip
cd C:\Python314-32bit
curl -o get-pip.py https://bootstrap.pypa.io/get-pip.py
python get-pip.py

# Install required packages
python -m pip install pyserial pymodbus
```

### Step 3: Verify 32-bit Installation

```bash
C:\Python314-32bit\python.exe --version
# Should show: Python 3.14.2

C:\Python314-32bit\python.exe -c "import struct; print(8 * struct.calcsize('P'))"
# Should show: 32
```

### Step 4: Test DLL Loading

```bash
C:\Python314-32bit\python.exe -c "import ctypes; dll = ctypes.windll.LoadLibrary(r'C:\Windows\SysWOW64\pdaqx.dll'); print('Success:', dll)"
# Should show: Success: <WinDLL ...>
```

---

## Configuration

### DLL Location

The correct 32-bit DLL location is:

```
C:\Windows\SysWOW64\pdaqx.dll
```

**Note:** The `USB_x64` folder naming is misleading - it refers to USB device support, not the DLL architecture. All pdaqx.dll files (System32, USB_x64, DriverStore) are 32-bit.

### Device Configuration

Update `src/core/config.py`:

```python
# Personal DAQ/56 settings
# 32-bit drivers in SysWOW64 (required for 32-bit Python on 64-bit OS)
personal_daq_dll_path: str = r"C:\Windows\SysWOW64\pdaqx.dll"
personal_daq_device_name: str = "Personal Daq"  # Device name to open
personal_daq_channel: int = 1  # PD1_A01 → channel 1
personal_daq_gain: float = 1.0  # Default gain (adjust if needed)
```

### Device Name Verification

The correct device name is `"Personal Daq"` (confirmed in Windows registry):

```
HKLM\SYSTEM\CurrentControlSet\Enum\USB\VID_0622&PID_0001
DeviceDesc: Personal Daq
```

Verified via Device Manager and Windows Registry.

---

## Common Issues

### Issue 1: "Invalid alias name for Vxd lookup" (Error Code 113)

**Error Dialog:**
```
Daq error: handle=-1, errCode=113-->(0x71).
Invalid alias name for Vxd lookup
```

**Root Causes:**

1. **Wrong device name** - Using incorrect device name
2. **Personal DaqView running** - Device is locked by another application
3. **Device not found** - USB device not connected or not detected

**Solutions:**

#### Check Personal DaqView Status

```bash
tasklist | findstr /i "daq"
# If PDAQVIEW.exe is running, it has the device locked
```

**Close Personal DaqView:**
```bash
taskkill /IM PDAQVIEW.exe /F
```

#### Verify Device Connection

```powershell
# Check Device Manager
Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Personal*'} | Select-Object FriendlyName, Status

# Expected output:
# FriendlyName        Status
# -------------      ------
# Personal Daq        OK
```

#### Check Registry for Device Name

```bash
reg query "HKLM\SYSTEM\CurrentControlSet\Enum\USB\VID_0622&PID_0001" /s /f "Personal" 2>nul | findstr /i "DeviceDesc"
# Expected: DeviceDesc    REG_SZ    Personal Daq
```

### Issue 2: `daqOpen()` Hangs Indefinitely

**Symptoms:**
- Script stops at `daqOpen()` call
- No error message
- Script appears frozen

**Root Causes:**

1. **Personal DaqView was previously running** - USB device in bad state
2. **Device firmware locked up** - Needs physical reset
3. **USB driver issue** - Windows driver stack confused
4. **USB device not properly recognized** - Power or connection issue

**Solutions:**

#### Solution 1: Physical Device Reset (Try First)

```
1. Unplug Personal DAQ/56 from USB
2. Wait 5 seconds
3. Replug into same or different USB port
4. Wait 10 seconds for Windows to detect device
5. Test connection again
```

#### Solution 2: Restart Computer

```
1. Save any work
2. Restart Windows completely
3. After reboot, replug Personal Daq
4. Test connection
```

#### Solution 3: Reinstall USB Driver

```
1. Open Device Manager
2. Right-click "Personal Daq" → Uninstall device
3. Check "Delete the driver software for this device" if present
4. Unplug device
5. Replug device
6. Windows should reinstall driver automatically
```

### Issue 3: Cannot Load DLL with 64-bit Python

**Symptoms:**
```
OSError: [WinError 193] %1 is not a valid Win32 application
```

**Solution:**
Use 32-bit Python (see [32-bit Python Setup](#32-bit-python-setup))

---

## Troubleshooting Steps

### Complete Diagnostic Workflow

#### Step 1: Verify Python Architecture

```bash
# Check current Python
python --version
python -c "import struct; print('Python is', 8 * struct.calcsize('P'), '-bit')"

# Check 32-bit Python
C:\Python314-32bit\python.exe --version
C:\Python314-32bit\python.exe -c "import struct; print('32-bit Python is', 8 * struct.calcsize('P'), '-bit')"

# Expected: Both show 32-bit
```

#### Step 2: Verify DLL Loading

```bash
# With 64-bit Python (should fail)
python -c "import ctypes; dll = ctypes.windll.LoadLibrary(r'C:\Windows\SysWOW64\pdaqx.dll'); print('Loaded:', dll)"
# Expected: OSError [WinError 193]

# With 32-bit Python (should succeed)
C:\Python314-32bit\python.exe -c "import ctypes; dll = ctypes.windll.LoadLibrary(r'C:\Windows\SysWOW64\pdaqx.dll'); print('Loaded:', dll)"
# Expected: Loaded: <WinDLL 'C:\Windows\SysWOW64\pdaqx.dll', handle 10000000 at ...>
```

#### Step 3: Check Device Detection

```powershell
Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Personal*'} | Select-Object FriendlyName, Status, InstanceId

# Expected:
# FriendlyName        Status    InstanceId
# -------------      ------     ----------
# Personal Daq        OK         USB\VID_0622&PID_0001\...
```

#### Step 4: Check Personal DaqView

```bash
tasklist | findstr /i "PDAQVIEW"

# If running, close it:
taskkill /IM PDAQVIEW.exe /F

# Then replug device and retry
```

#### Step 5: Test Basic Connection

Create minimal test script (`test_simple_open.py`):

```python
import ctypes

dll = ctypes.windll.LoadLibrary(r'C:\Windows\SysWOW64\pdaqx.dll')

print('Testing daqOpen...')
h = dll.daqOpen(b'Personal Daq')
print('Handle:', h)

if h:
    print('SUCCESS: Device opened')
    dll.daqClose(h)
    print('Device closed')
else:
    print('FAILED: daqOpen returned NULL')
```

Run with 32-bit Python:
```bash
C:\Python314-32bit\python.exe test_simple_open.py
```

**Expected Outcomes:**

| Result | Interpretation | Action |
|--------|---------------|--------|
| `Handle: <ctypes.LP_c_void_p object at ...>` | ✅ **SUCCESS** | Proceed with full test |
| `Handle: None` or `Handle: 0` | ❌ **Device not found** | Check USB connection, verify device name |
| Script hangs indefinitely | ❌ **Device in bad state** | Unplug/replug or restart computer |

#### Step 6: Full Connection Test

Use the PersonalDAQ class:

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from devices.personal_daq import PersonalDAQ

daq = PersonalDAQ(
    port="COM7",  # Not used for USB
    device_name="Personal Daq",
    channel=1,
    gain=1.0,
    dll_path=r"C:\Windows\SysWOW64\pdaqx.dll",
)

if daq.connect():
    print("Connected successfully!")
    temp = daq.read_temperature()
    if temp:
        print(f"Temperature: {temp:.2f} °C")
    daq.disconnect()
else:
    print("Connection failed")
```

Run with 32-bit Python:
```bash
C:\Python314-32bit\python.exe test_personal_daq.py
```

---

## Test Procedures

### Test 1: Environment Setup

**Purpose:** Verify 32-bit Python and DLL compatibility

```bash
# Verify Python is 32-bit
C:\Python314-32bit\python.exe -c "import struct; assert 8 * struct.calcsize('P') == 32; print('✓ 32-bit Python confirmed')"

# Verify DLL loads
C:\Python314-32bit\python.exe -c "import ctypes; dll = ctypes.windll.LoadLibrary(r'C:\Windows\SysWOW64\pdaqx.dll'); print('✓ 32-bit DLL loaded:', dll)"

# Verify dependencies
C:\Python314-32bit\python.exe -c "import serial; import pymodbus; print('✓ Dependencies installed')"
```

### Test 2: Device Detection

**Purpose:** Confirm Personal DAQ is visible to Windows

```powershell
# Check Device Manager
Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Personal*'}

# Check USB details
Get-PnpDevice | Where-Object {$_.InstanceId -like '*0622*PID_0001*'} | Select-Object FriendlyName, Status, InstanceId
```

**Expected Output:**
```
FriendlyName   : Personal Daq
Status        : OK
InstanceId    : USB\VID_0622&PID_0001\...
```

### Test 3: Basic DLL Function Test

**Purpose:** Test daqOpen() without PersonalDAQ class

```python
# test_daq_dll_minimal.py
import ctypes

dll = ctypes.windll.LoadLibrary(r'C:\Windows\SysWOW64\pdaqx.dll')

# Test function availability
functions = ['daqOpen', 'daqClose', 'daqAdcSetDataFormat', 'daqAdcRd']
for f in functions:
    if hasattr(dll, f):
        print(f"✓ {f}")
    else:
        print(f"✗ {f} missing")

# Test daqOpen
print("\nTesting daqOpen...")
try:
    h = dll.daqOpen(b'Personal Daq')
    print(f"✓ Handle: {h}")
    if h:
        dll.daqClose(h)
        print("✓ Closed successfully")
    else:
        print("✗ daqOpen returned NULL")
except Exception as e:
    print(f"✗ Error: {e}")
```

**Run:**
```bash
C:\Python314-32bit\python.exe test_daq_dll_minimal.py
```

### Test 4: PersonalDAQ Class Test

**Purpose:** Test full PersonalDAQ class functionality

```python
# test_personal_daq_simple.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from devices.personal_daq import PersonalDAQ

daq = PersonalDAQ(
    port="COM7",
    device_name="Personal Daq",
    channel=1,
    gain=1.0,
    dll_path=r"C:\Windows\SysWOW64\pdaqx.dll",
)

print(f"Device: {daq.device_name}")
print(f"Channel: {daq.channel}")

if daq.connect():
    print("✓ Connected to Personal DAQ")

    # Read temperature
    temp = daq.read_temperature()
    if temp is not None:
        print(f"✓ Temperature: {temp:.2f} °C")
    else:
        print("✗ Could not read temperature")

    daq.disconnect()
    print("✓ Disconnected")
else:
    print("✗ Connection failed")
    print("  Check:")
    print("  - Personal DaqView is closed")
    print("  - Device is connected to USB")
    print("  - Device is recognized in Device Manager")
    print("  - Try unplugging/replugging or restarting computer")
```

**Run:**
```bash
C:\Python314-32bit\python.exe test_personal_daq_simple.py
```

---

## Known Limitations

### 1. 32-bit Only Driver
- No 64-bit driver available
- Must use 32-bit Python for Personal DAQ/56
- Requires maintaining two Python environments

### 2. Legacy Device
- Drivers from 2011 (no updates in 14+ years)
- Marked as "Legacy" and "End of Life" by vendor
- No official support for modern Windows versions

### 3. Device Exclusivity
- Only one application can access Personal DAQ at a time
- Personal DaqView must be closed before using custom Python code
- Error 113 if device is locked by another process

### 4. USB Device State Sensitivity
- Device can enter bad state if application crashes or disconnects improperly
- May require physical unplugging/replugging
- May require computer restart to recover

### 5. Limited Feature Set
- Current implementation: Single temperature read (P0 scope)
- Not implemented: Multiple channel reads, high-speed acquisition, digital I/O, frequency measurement
- Based on minimal feature set for immediate usability

---

## Quick Reference

### File Locations

| File/Directory | Path | Purpose |
|----------------|------|---------|
| 32-bit Python | `C:\Python314-32bit\` | 32-bit Python installation |
| 32-bit DLL | `C:\Windows\SysWOW64\pdaqx.dll` | 32-bit Personal DAQ DLL |
| Config | `src/core/config.py` | Device configuration |
| Device Class | `src/devices/personal_daq.py` | PersonalDAQ implementation |

### Device Information

| Property | Value |
|----------|-------|
| Model | Personal DAQ/56 (OMB-DAQ-56) |
| USB VID | 0622 |
| USB PID | 0001 |
| Device Name | Personal Daq |
| Channel for PD1_A01 | 1 |
| Thermocouple Type | K (default) |
| Gain | 1.0 (default) |

### Error Codes

| Error Code | Meaning | Solution |
|------------|-----------|----------|
| 113 (0x71) | Invalid alias name for Vxd lookup | Check device name, close Personal DaqView |
| 193 | Not a valid Win32 application | Use 32-bit Python, not 64-bit |
| NULL handle | Device not found | Check USB connection, verify device name |

### Running Scripts

| Script | Purpose | Command |
|--------|-----------|----------|
| test_simple_open.py | Basic daqOpen test | `C:\Python314-32bit\python.exe test_simple_open.py` |
| test_daq_dll_minimal.py | DLL function test | `C:\Python314-32bit\python.exe test_daq_dll_minimal.py` |
| test_personal_daq_simple.py | Full PersonalDAQ test | `C:\Python314-32bit\python.exe test_personal_daq_simple.py` |

---

## Conclusion

The Personal DAQ/56 is a legacy device that requires 32-bit Python to function. While it can work correctly with the proper setup, users should be aware of:

1. **Architecture limitation:** Must use 32-bit Python (dual environment required)
2. **Legacy status:** No 64-bit drivers available, last update in 2011
3. **Device exclusivity:** Cannot share device with Personal DaqView
4. **State sensitivity:** May require physical reset after errors

For long-term projects, consider migrating to a modern DAQ device with full 64-bit support and active maintenance.

---

## Last Updated

- Date: 2026-02-02
- Python Version Tested: 3.14.2 (32-bit)
- DLL Version: 3.0.0.0 (2011-11-01)
- Status: 32-bit Python environment configured, ready for hardware testing
