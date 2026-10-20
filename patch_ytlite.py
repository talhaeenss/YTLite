#!/usr/bin/env python3
import sys
import os
import zipfile

# Patch definitions for YTLite.dylib (v5.2.x)
# Removes Patreon/Account login wall, removes "Log in" button from Settings,
# silences donation reminder toasts, and removes anti-debugging.
PATCHES = [
    # 1. In -[YTPSettingsBuilder rootTable], branch over patreonSection creation and addition:
    # 0x13a114: b #0x13a158
    {
        'offset': 0x13a114,
        'orig': b'\x08\x8a\x08\x90', # adrp x8, #0x114d000
        'patch': b'\x11\x00\x00\x14', # b #0x13a158
        'desc': 'rootTable: branch over patreonSection'
    },
    # 2. In -[YTPSettingsBuilder patreonSection:], return nil immediately:
    # 0x177f70: mov x0, #0; ret
    {
        'offset': 0x177f70,
        'orig': b'\xf8\x5f\xbc\xa9', # stp x24, x23, [sp, #-0x40]!
        'patch': b'\x00\x00\x80\xd2\xc0\x03\x5f\xd6', # mov x0, #0; ret
        'desc': 'patreonSection: return nil'
    },
    # 3. In -[YTPSettingsBuilder patreonButtonCellWithType:model:], return nil immediately:
    # 0x178a68: mov x0, #0; ret
    {
        'offset': 0x178a68,
        'orig': b'\xfc\x6f\xba\xa9', # stp x28, x27, [sp, #-0x60]!
        'patch': b'\x00\x00\x80\xd2\xc0\x03\x5f\xd6', # mov x0, #0; ret
        'desc': 'patreonButtonCellWithType:model: return nil'
    },
    # 4. In -[ToastView showDonationReminder:], return immediately:
    # 0x1c1af8: ret
    {
        'offset': 0x1c1af8,
        'orig': b'\xff\x83\x01\xd1', # sub sp, sp, #0x60
        'patch': b'\xc0\x03\x5f\xd6', # ret
        'desc': 'showDonationReminder: return immediately'
    },
    # 5. Disable ptrace(PT_DENY_ATTACH) anti-debugging:
    # 0x1acf0: nop
    {
        'offset': 0x1acf0,
        'orig': b'\x61\x91\x07\xd4', # svc #0x3c8b
        'patch': b'\x1f\x20\x03\xd5', # nop
        'desc': 'ptrace PT_DENY_ATTACH: nop'
    }
]

def patch_dylib_bytes(data: bytearray) -> bytearray:
    applied = 0
    for p in PATCHES:
        off = p['offset']
        patch_len = len(p['patch'])
        current = bytes(data[off:off+patch_len])
        if current == p['patch']:
            print(f"  [+] Already patched: {p['desc']}")
            applied += 1
        elif current == p['orig']:
            data[off:off+patch_len] = p['patch']
            print(f"  [+] Applied patch: {p['desc']} at {hex(off)}")
            applied += 1
        else:
            print(f"  [!] Note: offset {hex(off)} differs, searching pattern...")
            pos = data.find(p['orig'])
            if pos != -1:
                data[pos:pos+patch_len] = p['patch']
                print(f"  [+] Found pattern and applied: {p['desc']} at {hex(pos)}")
                applied += 1
            else:
                print(f"  [-] Could not match pattern for: {p['desc']}")

    print(f"Total patches applied: {applied}/{len(PATCHES)}")
    return data

def patch_file(target_path: str, output_path: str = None):
    if not os.path.exists(target_path):
        print(f"Error: Target path '{target_path}' does not exist.")
        return False

    if target_path.endswith('.dylib'):
        print(f"Patching dylib in-place: {target_path}")
        with open(target_path, 'rb') as f:
            data = bytearray(f.read())
        patched = patch_dylib_bytes(data)
        out = output_path or target_path
        with open(out, 'wb') as f:
            f.write(patched)
        print(f"Saved to: {out}")
        return True

    elif target_path.endswith('.ipa'):
        out = output_path or target_path.replace('.ipa', '_Patched.ipa')
        print(f"Patching IPA: {target_path} -> {out}")
        with zipfile.ZipFile(target_path, 'r') as zin:
            with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    data = zin.read(item.filename)
                    if item.filename.endswith('YTLite.dylib'):
                        print(f"Found dylib inside IPA: {item.filename}")
                        data = bytes(patch_dylib_bytes(bytearray(data)))
                    zout.writestr(item, data)
        print(f"Saved patched IPA to: {out}")
        return True

    else:
        print(f"Unknown target file format: {target_path}")
        return False

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'ipa_extracted/Payload/YouTube.app/Frameworks/YTLite.dylib'
    output = sys.argv[2] if len(sys.argv) > 2 else None
    patch_file(target, output)
