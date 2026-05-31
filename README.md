# ecp5prog-versa

> Open-source programming toolchain for the **Lattice ECP5-5G Versa Development Board**, patched to handle its two-device JTAG chain.

---

## Background

The ECP5-5G Versa board exposes two devices on its JTAG chain:

```
TDI → [ispClock5406D] → [ECP5UM5G-45F] → TDO
```

Upstream `ecpprog` assumes a single-device chain and locks up trying to detect the FPGA when the clock chip is sitting in front of it. This fork patches `ecpprog` to skip past the `ispClock5406D` using correct BYPASS chain handling, so you can program the ECP5 with fully open-source tooling.

---

## Repository layout

```
ecp5prog-versa/
├── src/
│   └── ecpprog/        # Patched ecpprog source (C)
└── fpga/               # Example Verilog + build scripts
```

---

## Prerequisites

### Ubuntu / Debian

```bash
sudo apt install libftdi1-dev build-essential yosys nextpnr-ecp5
```

After connecting the board, you may need a udev rule so ecpprog can access the FT2232H without root:

```bash
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0403", ATTR{idProduct}=="6010", MODE="0666"' \
  | sudo tee /etc/udev/rules.d/99-ftdi.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

### macOS

Install dependencies via [Homebrew](https://brew.sh):

```bash
brew install libftdi yosys
```

`nextpnr-ecp5` and `ecppack` (prjtrellis) are not in the default Homebrew tap — install them from the YosysHQ tap:

```bash
brew tap YosysHQ/oss-cad-suite
brew install oss-cad-suite
```

This installs a self-contained suite with `yosys`, `nextpnr-ecp5`, and `ecppack` all in one go.


---

## Building ecpprog

```bash
cd src/ecpprog
make
sudo make install        # installs to /usr/local/bin/ecpprog
```

---

## Verifying the JTAG chain

Before programming, confirm both devices are visible on the chain:

```bash
python3 verify_chain.py
```

Expected output:

```
Device 0: IDCODE=0x00012555  → ispClock5406D  (BYPASS)
Device 1: IDCODE=0x81113043  → ECP5UM5G-45F   ✓
```

---

## Programming the FPGA

```bash
ecpprog -d i:0x0403:0x6010 bitstream.bit
```

The `-d i:0x0403:0x6010` selects the on-board FT2232H by USB VID:PID. If you have multiple FTDI devices connected, also pass `-I A` to target interface A.

---

## Building the example design

```bash
cd fpga
make                     # synthesise → P&R → pack → program
```

The Makefile calls `yosys`, `nextpnr-ecp5`, `ecppack`, and `ecpprog` in sequence.

---

## How the patch works

Upstream `ecpprog` sends the standard IDCODE scan and expects to find the ECP5 at position 0. On the Versa board, the `ispClock5406D` answers first with its own IDCODE, causing detection to fail.

The patch:

1. Reads the full raw IDCODE scan to discover chain length.
2. Identifies the ECP5 IDCODE (`0x81113043`) at its correct position (index 1).
3. Drives the clock chip into BYPASS by shifting a 1-bit `1` into its IR, then proceeds normally with the ECP5.

This replaces the earlier forced-detection hack with proper multi-device BYPASS chain handling per IEEE 1149.1.

---

## Toolchain versions tested

| Tool | Version |
|------|---------|
| yosys | 0.38+ |
| nextpnr-ecp5 | 0.7+ |
| ecppack | (prjtrellis) |
| libftdi | 1.5 |

---

## References

- [Project Trellis](https://github.com/YosysHQ/prjtrellis) — ECP5 open-source bitstream documentation
- [ecpprog upstream](https://github.com/gregdavill/ecpprog) — original programmer by Greg Davill
- [Lattice ECP5-5G Versa board schematic](https://www.latticesemi.com/products/developmentboardsandkits/ecp55gversadevkit) — JTAG chain topology
- [IEEE 1149.1](https://en.wikipedia.org/wiki/JTAG) — JTAG / boundary scan standard

---

## License

`src/ecpprog` retains the original ISC license from upstream ecpprog.  
Everything else in this repository is released under the **MIT License** — see [`LICENSE`](LICENSE).