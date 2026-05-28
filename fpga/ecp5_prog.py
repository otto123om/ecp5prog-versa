#!/usr/bin/env python3
"""
ECP5 JTAG Programmer using pyftdi
Replaces openFPGALoader with modular Python implementation
"""

from pyftdi.ftdi import Ftdi
import time
import sys
import argparse
import struct

class ECP5Programmer:
    """ECP5 JTAG Programmer"""
    
    # JTAG TAP states
    TEST_LOGIC_RESET = 0
    RUN_TEST_IDLE = 1
    SELECT_DR_SCAN = 2
    CAPTURE_DR = 3
    SHIFT_DR = 4
    EXIT1_DR = 5
    PAUSE_DR = 6
    EXIT2_DR = 7
    UPDATE_DR = 8
    SELECT_IR_SCAN = 9
    CAPTURE_IR = 10
    SHIFT_IR = 11
    EXIT1_IR = 12
    PAUSE_IR = 13
    EXIT2_IR = 14
    UPDATE_IR = 15
    
    # ECP5 JTAG Instructions
    IDCODE = 0x01
    USERCODE = 0x08
    ISC_ERASE = 0x0C
    ISC_PROGRAM = 0x0E
    ISC_READ = 0x0F
    ISC_ENABLE = 0x10
    ISC_DISABLE = 0x11
    
    def __init__(self, ftdi_vid=0x0403, ftdi_pid=0x6010):
        self.ftdi = Ftdi()
        try:
            self.ftdi.open(ftdi_vid, ftdi_pid)
        except Exception as e:
            print(f"[-] Failed to open FTDI device: {e}")
            sys.exit(1)
        
        # Set MPSSE mode
        self.ftdi.set_bitmode(0x0B, self.ftdi.BitMode.MPSSE)
        self.ftdi.set_frequency(1e6)  # 1 MHz for safety
        
        print("[+] FTDI device opened in MPSSE mode")
        self.tap_state = self.TEST_LOGIC_RESET
    
    def mpsse_shift(self, tdi_bits, num_bits, read_back=True, cmd_mode='default'):
        """
        Shift bits via MPSSE
        tdi_bits: integer or bytes to shift in
        num_bits: number of bits to shift
        read_back: whether to read TDO
        cmd_mode: 'default', 'lsb', 'read_only'
        """
        num_bytes = (num_bits + 7) // 8
        
        # Different MPSSE commands to try
        if cmd_mode == 'lsb':
            shift_cmd = 0x31  # LSB first, read on negative edge
        elif cmd_mode == 'msb_pos':
            shift_cmd = 0x39  # MSB, read on positive edge (inverted)
        else:  # default
            shift_cmd = 0x39  # MSB first, read on negative edge
        
        cmd = bytearray()
        cmd.append(shift_cmd)
        cmd.append((num_bits - 1) & 0xFF)
        cmd.append(((num_bits - 1) >> 8) & 0xFF)
        
        # Add TDI data
        if isinstance(tdi_bits, int):
            tdi_bytes = tdi_bits.to_bytes(num_bytes, 'little')
        else:
            tdi_bytes = tdi_bits
        
        cmd.extend(tdi_bytes)
        
        self.ftdi.write_data(cmd)
        time.sleep(0.001)
        
        if read_back:
            response = self.ftdi.read_data(num_bytes)
            if isinstance(response, bytes):
                return int.from_bytes(response, 'little')
            return response
        return None
    
    def mpsse_set_tms(self, tms_sequence, num_bits):
        """Set TMS line to change TAP state"""
        cmd = bytearray()
        cmd.append(0x4B)  # TMS shift
        cmd.append((num_bits - 1) & 0xFF)
        cmd.append(((num_bits - 1) >> 8) & 0xFF)
        cmd.append(tms_sequence & 0xFF)
        
        self.ftdi.write_data(cmd)
        time.sleep(0.001)
    
    def reset_tap(self):
        """Reset TAP controller to TEST_LOGIC_RESET"""
        print("[*] Resetting TAP controller...")
        self.mpsse_set_tms(0x3F, 6)  # TMS: 111111
        self.tap_state = self.TEST_LOGIC_RESET
        time.sleep(0.05)
    
    def goto_shift_dr(self):
        """Navigate TAP from TEST_LOGIC_RESET to SHIFT_DR"""
        print("[*] Entering Shift-DR state...")
        self.mpsse_set_tms(0x01, 2)  # TMS: 01
        self.tap_state = self.SHIFT_DR
    
    def goto_shift_ir(self):
        """Navigate TAP to SHIFT_IR"""
        print("[*] Entering Shift-IR state...")
        self.mpsse_set_tms(0x03, 2)  # TMS: 11
        time.sleep(0.001)
        self.mpsse_set_tms(0x01, 2)  # TMS: 01
        self.tap_state = self.SHIFT_IR
    
    def read_idcode(self, mode='default'):
        """Read and display IDCODE"""
        print(f"[*] Reading IDCODE (mode: {mode})...")
        
        self.reset_tap()
        
        # Load IDCODE instruction (0x01) into IR
        print("[*] Loading IDCODE instruction into IR...")
        self.goto_shift_ir()
        
        # Shift in IDCODE instruction (6 bits for ECP5)
        self.mpsse_shift(0x01, 6, cmd_mode=mode)
        
        # Move to RUN-TEST-IDLE then back to Shift-DR
        self.mpsse_set_tms(0x01, 1)  # Exit1-IR
        self.mpsse_set_tms(0x01, 1)  # Update-IR
        self.mpsse_set_tms(0x01, 1)  # Select-DR
        self.mpsse_set_tms(0x00, 1)  # Capture-DR
        self.mpsse_set_tms(0x00, 1)  # Shift-DR
        
        # Shift 32 bits to read IDCODE
        idcode = self.mpsse_shift(0xFFFFFFFF, 32, cmd_mode=mode)
        
        print(f"\n[+] IDCODE: 0x{idcode:08x}")
        
        # Parse IDCODE
        bit0 = idcode & 1
        manufacturer = (idcode >> 1) & 0x7FF
        part = (idcode >> 12) & 0xFFFF
        version = (idcode >> 28) & 0xF
        
        print(f"    Bit 0 (always 1): {bit0}")
        print(f"    Manufacturer ID: 0x{manufacturer:03x}")
        print(f"    Part Number: 0x{part:04x}")
        print(f"    Version: 0x{version:x}")
        
        # Decode manufacturer
        if manufacturer == 0x021:
            print("    → Lattice Semiconductor")
            
            # Decode ECP5 variants
            part_names = {
                0x0041: "ECP5-25k (LFE5U-25F)",
                0x0044: "ECP5-45k (LFE5U-45F)",
                0x0045: "ECP5-85k (LFE5U-85F)",
                0x0101: "ECP5-25k 5G (LFE5UM-25F)",
                0x0104: "ECP5-45k 5G (LFE5UM-45F)",
                0x0105: "ECP5-85k 5G (LFE5UM-85F)",
            }
            
            if part in part_names:
                print(f"    → {part_names[part]}")
            else:
                print(f"    → Unknown part 0x{part:04x}")
        else:
            print(f"    → Unknown manufacturer")
        
        return idcode
    
    def detect(self):
        """Detect FPGA on JTAG chain"""
        try:
            self.read_idcode()
            print("\n[+] Detection successful!")
            return True
        except Exception as e:
            print(f"\n[-] Detection failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def program_sram(self, bitfile):
        """Program FPGA SRAM (not implemented yet)"""
        print("[-] SRAM programming not yet implemented")
        print(f"    Would program: {bitfile}")
    
    def program_flash(self, bitfile):
        """Program FPGA Flash (not implemented yet)"""
        print("[-] Flash programming not yet implemented")
        print(f"    Would program: {bitfile}")
    
    def dump_flash(self, output_file, size):
        """Read flash memory (not implemented yet)"""
        print("[-] Flash dump not yet implemented")
        print(f"    Would dump {size} bytes to: {output_file}")
    
    def close(self):
        """Close FTDI device"""
        self.ftdi.close()
        print("[*] FTDI device closed")

def main():
    parser = argparse.ArgumentParser(
        description="ECP5 JTAG Programmer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --detect              # Detect FPGA
  %(prog)s -m bitstream.bit      # Program SRAM
  %(prog)s -f bitstream.bit      # Program Flash
  %(prog)s --dump-flash -o dump.bin --file-size 1000000
        """
    )
    
    parser.add_argument("-m", "--write-sram", metavar="FILE",
                        help="Write bitstream to FPGA SRAM")
    parser.add_argument("-f", "--write-flash", metavar="FILE",
                        help="Write bitstream to Flash")
    parser.add_argument("--detect", action="store_true",
                        help="Detect FPGA on JTAG chain")
    parser.add_argument("--dump-flash", action="store_true",
                        help="Read and dump Flash contents")
    parser.add_argument("-o", "--output", metavar="FILE",
                        help="Output file for dump")
    parser.add_argument("--file-size", type=int, default=1000000,
                        help="Size to read from Flash (default: 1000000)")
    parser.add_argument("--test-modes", action="store_true",
                        help="Test different MPSSE modes to find correct IDCODE")
    parser.add_argument("--skip-detect", action="store_true",
                        help="Skip IDCODE detection and go straight to programming")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")
    
    args = parser.parse_args()
    
    if not any([args.detect, args.write_sram, args.write_flash, args.dump_flash, args.test_modes, args.skip_detect]):
        parser.print_help()
        return 1
    
    try:
        prog = ECP5Programmer()
        
        if args.test_modes:
            print("[*] Testing different MPSSE modes...\n")
            for mode in ['default', 'lsb', 'msb_pos']:
                try:
                    prog.reset_tap()
                    prog.goto_shift_dr()
                    idcode = prog.mpsse_shift(0xFFFFFFFF, 32, cmd_mode=mode)
                    print(f"Mode '{mode:12}': 0x{idcode:08x}")
                except Exception as e:
                    print(f"Mode '{mode:12}': ERROR - {e}")
            prog.close()
            return 0
        
        if args.skip_detect:
            print("[*] Skipping IDCODE detection")
            print("[-] SRAM/Flash programming not yet implemented")
            prog.close()
            return 0
        
            prog.detect()
        
        if args.write_sram:
            prog.program_sram(args.write_sram)
        
        if args.write_flash:
            prog.program_flash(args.write_flash)
        
        if args.dump_flash:
            if not args.output:
                print("[-] --dump-flash requires -o/--output")
                return 1
            prog.dump_flash(args.output, args.file_size)
        
        prog.close()
        return 0
        
    except KeyboardInterrupt:
        print("\n[-] Interrupted by user")
        return 130
    except Exception as e:
        print(f"[-] Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
