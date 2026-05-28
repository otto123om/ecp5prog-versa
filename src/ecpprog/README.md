# ecpprog-versa

A fork of [ecpprog](https://github.com/gregdavill/ecpprog) patched to support the **Lattice ECP5-5G Versa Development Board** (FPGA-EB-02048).

## What Changed

The Versa board has **two devices in the JTAG chain**:

| Position | Device | IDCODE | IR Length |
|----------|--------|--------|-----------|
| 0 (first) | ispClock5406D (U13) | `0x00191043` | 8 bits |
| 1 (second) | ECP5UM5G-45F (U1) | `0x81112043` | 8 bits |

The original ecpprog reads only the first device in the chain, which on this board is the ispClock5406D clock chip — not the FPGA. This fork patches the IDCODE detection to handle the two-device chain correctly and target the ECP5 directly.

**JTAG chain confirmed via OpenOCD:**
```
JTAG tap: auto0.tap tap/device found: 0x00191043 (ispClock5406D)
JTAG tap: auto0.tap tap/device found: 0x81112043 (ECP5UM5G-45F)
```

## Board Setup

### SW4 Configuration (JTAG mode)
| Switch | Position |
|--------|----------|
| CFG2 (SW4.1) | DOWN |
| CFG1 (SW4.2) | DOWN |
| CFG0 (SW4.3) | DOWN |
| SW4.4 | UP (unused) |

### J50 JTAG Chain Selector
Set J50 to **ECP5 only** for simplest operation:
- Pin 1 → Pin 2 (jumper)
- Pin 3 → Pin 5 (jumper)

Or leave J50 in **full chain** mode (both devices) — this fork handles both cases.

### USB Connection
Connect via **J2 (onboard USB)** using a standard USB cable. The onboard FT2232H handles JTAG automatically.

## Features
- SRAM and SPI Flash programming for ECP5-5G Versa board
- Two-device JTAG chain support (ispClock5406D + ECP5UM5G-45F)
- IDCODE detection and validation
- ECP5 status register decode
- Includes blink example for quick verification

## Prerequisites

```bash
sudo apt install libftdi1-dev libusb-1.0-0-dev
```

## Building

```bash
git clone https://github.com/yourusername/ecpprog-versa
cd ecpprog-versa/src/ecpprog
make
sudo make install
```

## Usage

### Verify JTAG connection
```
$ ecpprog -t
init..
IDCODE: 0x81112043 (LFE5UM5G-45)
ECP5 Status Register: 0x00000204
flash ID: 0xEF 0x40 0x18 0x00
Bye.
```

### Program SRAM (volatile, lost on power-off)
```
$ ecpprog -S bitstream.bit
init..
IDCODE: 0x81112043 (LFE5UM5G-45)
ECP5 Status Register: 0x00000204
reset..
programming..
ECP5 Status Register: 0x00400200
Bye.
```

### Flash a bitstream (persistent)
```
$ ecpprog bitstream.bit
init..
IDCODE: 0x81112043 (LFE5UM5G-45)
ECP5 Status Register: 0x00000204
reset..
flash ID: 0xEF 0x40 0x18 0x00
file size: 99302
erase 64kB sector at 0x000000..
programming..  99302/99302
verify..       99302/99302  VERIFY OK
Bye.
```

### Flash User/SoC code
```
$ ecpprog -o 1M firmware.bin
init..
IDCODE: 0x81112043 (LFE5UM5G-45)
ECP5 Status Register: 0x00000204
reset..
flash ID: 0xEF 0x40 0x18 0x00
file size: 294312
erase 64kB sector at 0x100000..
programming..  294312/294312
verify..       294312/294312  VERIFY OK
Bye.
```

## Examples

### Blink
A minimal LED blink to verify the full toolchain works end-to-end.

```bash
cd FPGA/blink

# Build bitstream
make

# Program to SRAM
make prog

# Program to Flash
make flash
```

Requires:
- `yosys`
- `nextpnr-ecp5`
- `prjtrellis` (ecppack)

## Open Source Toolchain

Full open-source flow used in this repo:

```
Verilog (.v)
    └── yosys          → synthesis     → .json
         └── nextpnr-ecp5 → place & route → .config
              └── ecppack    → bitstream    → .bit
                   └── ecpprog    → program FPGA
```

## Tested On

| OS | Board | Interface |
|----|-------|-----------|
| Ubuntu 24.04 | ECP5-5G Versa (FPGA-EB-02048) | J2 onboard USB (FT2232H) |

## Credits

- Original ecpprog by (https://github.com/gregdavill/ecpprog)
- JTAG chain analysis via OpenOCD
- ECP5 open-source toolchain by [YosysHQ](https://github.com/YosysHQ)
- Project Trellis (https://github.com/daveshah1/prjtrellis)