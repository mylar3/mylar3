import os

def link(src, dst):
    if os.name == 'nt':
        import ctypes
        if ctypes.windll.kernel32.CreateHardLinkW(str(dst), str(src), 0) == 0: raise ctypes.WinError()
    else:
        os.link(src, dst)

def symlink(src, dst):
    if os.name == 'nt':
        import ctypes
        if ctypes.windll.kernel32.CreateSymbolicLinkW(str(dst), str(src), 1 if os.path.isdir(src) else 0) in [0, 1280]: raise ctypes.WinError()
    else:
        os.symlink(src, dst)

def is_rarfile(f):
    import binascii

    with open(f, "rb") as f:
        byte = f.read(12)

    spanned = binascii.hexlify(byte[10])
    main = binascii.hexlify(byte[11])

    if spanned == "01" and main == "01":  # main rar archive in a set of archives
        return True
    elif spanned == "00" and main == "00":  # single rar
        return True

    return False