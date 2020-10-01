#! /usr/bin/env python3

"""Dump archive contents, test extraction."""

import binascii
import getopt
import io
import sys
from datetime import datetime

import rarfile as rf

usage = """
dumprar [switches] [ARC1 ARC2 ...] [@ARCLIST]
switches:
  @file      read archive names from file
  -pPWD      set password
  -Ccharset  set fallback charset
  -v         increase verbosity
  -t         attempt to read all files
  -x         write read files out
  -c         show archive comment
  -h         show usage
  --         stop switch parsing
""".strip()

os_list = ["DOS", "OS2", "WIN", "UNIX", "MACOS", "BEOS"]

block_strs = ["MARK", "MAIN", "FILE", "OLD_COMMENT", "OLD_EXTRA",
              "OLD_SUB", "OLD_RECOVERY", "OLD_AUTH", "SUB", "ENDARC"]

r5_block_types = {
    rf.RAR5_BLOCK_MAIN: "R5_MAIN",
    rf.RAR5_BLOCK_FILE: "R5_FILE",
    rf.RAR5_BLOCK_SERVICE: "R5_SVC",
    rf.RAR5_BLOCK_ENCRYPTION: "R5_ENC",
    rf.RAR5_BLOCK_ENDARC: "R5_ENDARC",
}


def rar3_type(btype):
    """RAR3 type code as string."""
    if btype < rf.RAR_BLOCK_MARK or btype > rf.RAR_BLOCK_ENDARC:
        return "*UNKNOWN*"
    return block_strs[btype - rf.RAR_BLOCK_MARK]


def rar5_type(btype):
    """RAR5 type code as string."""
    return r5_block_types.get(btype, "*UNKNOWN*")


main_bits = (
    (rf.RAR_MAIN_VOLUME, "VOL"),
    (rf.RAR_MAIN_COMMENT, "COMMENT"),
    (rf.RAR_MAIN_LOCK, "LOCK"),
    (rf.RAR_MAIN_SOLID, "SOLID"),
    (rf.RAR_MAIN_NEWNUMBERING, "NEWNR"),
    (rf.RAR_MAIN_AUTH, "AUTH"),
    (rf.RAR_MAIN_RECOVERY, "RECOVERY"),
    (rf.RAR_MAIN_PASSWORD, "PASSWORD"),
    (rf.RAR_MAIN_FIRSTVOLUME, "FIRSTVOL"),
    (rf.RAR_SKIP_IF_UNKNOWN, "SKIP"),
    (rf.RAR_LONG_BLOCK, "LONG"),
)

endarc_bits = (
    (rf.RAR_ENDARC_NEXT_VOLUME, "NEXTVOL"),
    (rf.RAR_ENDARC_DATACRC, "DATACRC"),
    (rf.RAR_ENDARC_REVSPACE, "REVSPACE"),
    (rf.RAR_ENDARC_VOLNR, "VOLNR"),
    (rf.RAR_SKIP_IF_UNKNOWN, "SKIP"),
    (rf.RAR_LONG_BLOCK, "LONG"),
)

file_bits = (
    (rf.RAR_FILE_SPLIT_BEFORE, "SPLIT_BEFORE"),
    (rf.RAR_FILE_SPLIT_AFTER, "SPLIT_AFTER"),
    (rf.RAR_FILE_PASSWORD, "PASSWORD"),
    (rf.RAR_FILE_COMMENT, "COMMENT"),
    (rf.RAR_FILE_SOLID, "SOLID"),
    (rf.RAR_FILE_LARGE, "LARGE"),
    (rf.RAR_FILE_UNICODE, "UNICODE"),
    (rf.RAR_FILE_SALT, "SALT"),
    (rf.RAR_FILE_VERSION, "VERSION"),
    (rf.RAR_FILE_EXTTIME, "EXTTIME"),
    (rf.RAR_FILE_EXTFLAGS, "EXTFLAGS"),
    (rf.RAR_SKIP_IF_UNKNOWN, "SKIP"),
    (rf.RAR_LONG_BLOCK, "LONG"),
)

generic_bits = (
    (rf.RAR_SKIP_IF_UNKNOWN, "SKIP"),
    (rf.RAR_LONG_BLOCK, "LONG"),
)

file_parms = ("D64", "D128", "D256", "D512",
              "D1024", "D2048", "D4096", "DIR")

r5_block_flags = (
    (rf.RAR5_BLOCK_FLAG_EXTRA_DATA, "EXTRA"),
    (rf.RAR5_BLOCK_FLAG_DATA_AREA, "DATA"),
    (rf.RAR5_BLOCK_FLAG_SKIP_IF_UNKNOWN, "SKIP"),
    (rf.RAR5_BLOCK_FLAG_SPLIT_BEFORE, "SPLIT_BEFORE"),
    (rf.RAR5_BLOCK_FLAG_SPLIT_AFTER, "SPLIT_AFTER"),
    (rf.RAR5_BLOCK_FLAG_DEPENDS_PREV, "DEPENDS"),
    (rf.RAR5_BLOCK_FLAG_KEEP_WITH_PARENT, "KEEP"),
)

r5_main_flags = (
    (rf.RAR5_MAIN_FLAG_ISVOL, "ISVOL"),
    (rf.RAR5_MAIN_FLAG_HAS_VOLNR, "VOLNR"),
    (rf.RAR5_MAIN_FLAG_SOLID, "SOLID"),
    (rf.RAR5_MAIN_FLAG_RECOVERY, "RECOVERY"),
    (rf.RAR5_MAIN_FLAG_LOCKED, "LOCKED"),
)

r5_file_flags = (
    (rf.RAR5_FILE_FLAG_ISDIR, "DIR"),
    (rf.RAR5_FILE_FLAG_HAS_MTIME, "MTIME"),
    (rf.RAR5_FILE_FLAG_HAS_CRC32, "CRC32"),
    (rf.RAR5_FILE_FLAG_UNKNOWN_SIZE, "NOSIZE"),
)

r5_enc_flags = (
    (rf.RAR5_ENC_FLAG_HAS_CHECKVAL, "CHECKVAL"),
)

r5_endarc_flags = (
    (rf.RAR5_ENDARC_FLAG_NEXT_VOL, "NEXTVOL"),
)

r5_file_enc_flags = (
    (rf.RAR5_XENC_CHECKVAL, "CHECKVAL"),
    (rf.RAR5_XENC_TWEAKED, "TWEAKED"),
)

r5_file_redir_types = {
    rf.RAR5_XREDIR_UNIX_SYMLINK: "UNIX_SYMLINK",
    rf.RAR5_XREDIR_WINDOWS_SYMLINK: "WINDOWS_SYMLINK",
    rf.RAR5_XREDIR_WINDOWS_JUNCTION: "WINDOWS_JUNCTION",
    rf.RAR5_XREDIR_HARD_LINK: "HARD_LINK",
    rf.RAR5_XREDIR_FILE_COPY: "FILE_COPY",
}

r5_file_redir_flags = (
    (rf.RAR5_XREDIR_ISDIR, "DIR"),
)


dos_mode_bits = (
    (0x01, "READONLY"),
    (0x02, "HIDDEN"),
    (0x04, "SYSTEM"),
    (0x08, "VOLUME_ID"),
    (0x10, "DIRECTORY"),
    (0x20, "ARCHIVE"),
    (0x40, "DEVICE"),
    (0x80, "NORMAL"),
    (0x0100, "TEMPORARY"),
    (0x0200, "SPARSE_FILE"),
    (0x0400, "REPARSE_POINT"),
    (0x0800, "COMPRESSED"),
    (0x1000, "OFFLINE"),
    (0x2000, "NOT_CONTENT_INDEXED"),
    (0x4000, "ENCRYPTED"),
    (0x8000, "INTEGRITY_STREAM"),
    (0x00010000, "VIRTUAL"),
    (0x00020000, "NO_SCRUB_DATA"),
    (0x00040000, "RECALL_ON_OPEN"),
    (0x00080000, "PINNED"),
    (0x00100000, "UNPINNED"),
    (0x00400000, "RECALL_ON_DATA_ACCESS"),
    (0x20000000, "STRICTLY_SEQUENTIAL"),
)


def xprint(m, *args):
    """Print string to stdout.
    """
    if args:
        m = m % args
    print(m)


def tohex(data):
    """Return hex string."""
    return binascii.hexlify(data).decode("ascii")


def render_flags(flags, bit_list):
    """Show bit names.
    """
    res = []
    known = 0
    for bit in bit_list:
        known = known | bit[0]
        if flags & bit[0]:
            res.append(bit[1])
    unknown = flags & ~known
    n = 0
    while unknown:
        if unknown & 1:
            res.append("UNK_%04x" % (1 << n))
        unknown = unknown >> 1
        n += 1

    if not res:
        return "-"

    return ",".join(res)


def get_file_flags(flags):
    """Show flag names and handle dict size.
    """
    res = render_flags(flags & ~rf.RAR_FILE_DICTMASK, file_bits)

    xf = (flags & rf.RAR_FILE_DICTMASK) >> 5
    res += "," + file_parms[xf]
    return res


def fmt_time(t):
    """Format time.
    """
    if t is None:
        return "(-)"
    if isinstance(t, datetime):
        return t.isoformat("T")
    return "%04d-%02d-%02d %02d:%02d:%02d" % t


def show_item(h):
    """Show any RAR3/5 record.
    """
    if isinstance(h, rf.Rar3Info):
        show_item_v3(h)
    elif isinstance(h, rf.Rar5Info):
        show_item_v5(h)
    else:
        xprint("Unknown info record")


def show_rftype(h):
    return "".join([
        h.is_file() and "F" or "-",
        h.is_dir() and "D" or "-",
        h.is_symlink() and "L" or "-",
    ])


def modex3(v):
    return [v & 4 and "r" or "-", v & 2 and "w" or "-", v & 1 and "x" or "-"]


def unix_mode(mode):
    perms = modex3(mode >> 6) + modex3(mode >> 3) + modex3(mode)
    if mode & 0x0800:
        perms[2] = perms[2] == "x" and "s" or "S"
    if mode & 0x0400:
        perms[5] = perms[5] == "x" and "s" or "S"
    if mode & 0x0200:
        perms[8] = perms[8] == "x" and "t" or "-"
    rest = mode & 0xF000
    if rest == 0x4000:
        perms.insert(0, "d")
    elif rest == 0xA000:
        perms.insert(0, "l")
    elif rest == 0x8000:
        # common
        perms.insert(0, "-")
    elif rest == 0:
        perms.insert(0, "-")
    else:
        perms.insert(0, "?")
        perms.append("(0x%04x)" % rest)
    return "".join(perms)


def show_mode(h):
    if h.host_os in (rf.RAR_OS_UNIX, rf.RAR_OS_BEOS):
        s_mode = unix_mode(h.mode)
    elif h.host_os in (rf.RAR_OS_MSDOS, rf.RAR_OS_WIN32, rf.RAR_OS_OS2):
        s_mode = render_flags(h.mode, dos_mode_bits)
    else:
        s_mode = "0x%x" % h.mode
    return s_mode


def show_item_v3(h):
    """Show any RAR3 record.
    """
    st = rar3_type(h.type)
    xprint("%s: hdrlen=%d datlen=%d is=%s",
           st, h.header_size, h.add_size, show_rftype(h))
    if h.type in (rf.RAR_BLOCK_FILE, rf.RAR_BLOCK_SUB):
        s_mode = show_mode(h)
        xprint("  flags=0x%04x:%s", h.flags, get_file_flags(h.flags))
        if h.host_os >= 0 and h.host_os < len(os_list):
            s_os = os_list[h.host_os]
        else:
            s_os = "?"
        if h.flags & rf.RAR_FILE_UNICODE:
            s_namecmp = " namecmp=%d/%d" % (len(h.orig_filename), h._name_size)
        else:
            s_namecmp = ""
        xprint("  os=%d:%s ver=%d mode=%s meth=%c cmp=%d dec=%d vol=%d%s",
               h.host_os, s_os,
               h.extract_version, s_mode, h.compress_type,
               h.compress_size, h.file_size, h.volume, s_namecmp)
        ucrc = (h.CRC + (1 << 32)) & ((1 << 32) - 1)
        xprint("  crc=0x%08x (%d) date_time=%s", ucrc, h.CRC, fmt_time(h.date_time))
        xprint("  name=%s", h.filename)
        if h.mtime:
            xprint("  mtime=%s", fmt_time(h.mtime))
        if h.ctime:
            xprint("  ctime=%s", fmt_time(h.ctime))
        if h.atime:
            xprint("  atime=%s", fmt_time(h.atime))
        if h.arctime:
            xprint("  arctime=%s", fmt_time(h.arctime))
    elif h.type == rf.RAR_BLOCK_MAIN:
        xprint("  flags=0x%04x:%s", h.flags, render_flags(h.flags, main_bits))
    elif h.type == rf.RAR_BLOCK_ENDARC:
        xprint("  flags=0x%04x:%s", h.flags, render_flags(h.flags, endarc_bits))
        if h.flags & rf.RAR_ENDARC_DATACRC:
            xprint("  datacrc=0x%08x", h.endarc_datacrc)
        if h.flags & rf.RAR_ENDARC_DATACRC:
            xprint("  volnr=%d", h.endarc_volnr)
    elif h.type == rf.RAR_BLOCK_MARK:
        xprint("  flags=0x%04x:", h.flags)
    else:
        xprint("  flags=0x%04x:%s", h.flags, render_flags(h.flags, generic_bits))

    if h.comment is not None:
        cm = repr(h.comment)
        if cm[0] == "u":
            cm = cm[1:]
        xprint("  comment=%s", cm)


def show_item_v5(h):
    """Show any RAR5 record.
    """
    st = rar5_type(h.block_type)
    xprint("%s: hdrlen=%d datlen=%d hdr_extra=%d is=%s", st, h.header_size,
           h.compress_size, h.block_extra_size, show_rftype(h))
    xprint("  block_flags=0x%04x:%s", h.block_flags, render_flags(h.block_flags, r5_block_flags))
    if h.block_type in (rf.RAR5_BLOCK_FILE, rf.RAR5_BLOCK_SERVICE):
        xprint("  name=%s", h.filename)
        s_mode = show_mode(h)
        if h.file_host_os == rf.RAR5_OS_UNIX:
            s_os = "UNIX"
        else:
            s_os = "WINDOWS"
        xprint("  file_flags=0x%04x:%s", h.file_flags, render_flags(h.file_flags, r5_file_flags))

        cmp_flags = h.file_compress_flags
        xprint("  cmp_algo=%d cmp_meth=%d dict=%d solid=%r",
               cmp_flags & 0x3f,
               (cmp_flags >> 7) & 0x07,
               cmp_flags >> 10,
               cmp_flags & rf.RAR5_COMPR_SOLID > 0)
        xprint("  os=%d:%s mode=%s cmp=%r dec=%r vol=%r",
               h.file_host_os, s_os, s_mode,
               h.compress_size, h.file_size, h.volume)
        if h.CRC is not None:
            xprint("  crc=0x%08x (%d)", h.CRC, h.CRC)
        if h.blake2sp_hash is not None:
            xprint("  blake2sp=%s", tohex(h.blake2sp_hash))
        if h.date_time is not None:
            xprint("  date_time=%s", fmt_time(h.date_time))
        if h.mtime:
            xprint("  mtime=%s", fmt_time(h.mtime))
        if h.ctime:
            xprint("  ctime=%s", fmt_time(h.ctime))
        if h.atime:
            xprint("  atime=%s", fmt_time(h.atime))
        if h.arctime:
            xprint("  arctime=%s", fmt_time(h.arctime))
        if h.flags & rf.RAR_FILE_PASSWORD:
            enc_algo, enc_flags, kdf_count, salt, iv, checkval = h.file_encryption
            algo_name = "AES256" if enc_algo == rf.RAR5_XENC_CIPHER_AES256 else "UnknownAlgo"
            xprint("  algo=%d:%s enc_flags=%04x:%s kdf_lg=%d kdf_count=%d salt=%s iv=%s checkval=%s",
                   enc_algo, algo_name, enc_flags, render_flags(enc_flags, r5_file_enc_flags),
                   kdf_count, 1 << kdf_count, tohex(salt), tohex(iv),
                   checkval and tohex(checkval) or "-")
        if h.file_redir:
            redir_type, redir_flags, redir_name = h.file_redir
            xprint("  redir: type=%s flags=%d:%s destination=%s",
                   r5_file_redir_types.get(redir_type, "Unknown"),
                   redir_flags, render_flags(redir_flags, r5_file_redir_flags),
                   redir_name)
        if h.file_owner:
            uname, gname, uid, gid = h.file_owner
            xprint("  owner: name=%r group=%r uid=%r gid=%r",
                   uname, gname, uid, gid)
        if h.file_version:
            flags, version = h.file_version
            xprint("  version: flags=%r version=%r", flags, version)
    elif h.block_type == rf.RAR5_BLOCK_MAIN:
        xprint("  flags=0x%04x:%s", h.flags, render_flags(h.main_flags, r5_main_flags))
    elif h.block_type == rf.RAR5_BLOCK_ENDARC:
        xprint("  flags=0x%04x:%s", h.flags, render_flags(h.endarc_flags, r5_endarc_flags))
    elif h.block_type == rf.RAR5_BLOCK_ENCRYPTION:
        algo_name = "AES256" if h.encryption_algo == rf.RAR5_XENC_CIPHER_AES256 else "UnknownAlgo"
        xprint("  algo=%d:%s flags=0x%04x:%s", h.encryption_algo, algo_name, h.flags,
               render_flags(h.encryption_flags, r5_enc_flags))
        xprint("  kdf_lg=%d kdf_count=%d", h.encryption_kdf_count, 1 << h.encryption_kdf_count)
        xprint("  salt=%s", tohex(h.encryption_salt))
    else:
        xprint("  - missing info -")

    if h.comment is not None:
        cm = repr(h.comment)
        if cm[0] == "u":
            cm = cm[1:]
        xprint("  comment=%s", cm)


cf_show_comment = 0
cf_verbose = 0
cf_charset = None
cf_extract = 0
cf_test_read = 0
cf_test_unrar = 0
cf_test_memory = 0


def check_crc(f, inf, desc):
    """Compare result crc to expected value.
    """
    exp = inf._md_expect
    if exp is None:
        return
    ucrc = f._md_context.digest()
    if ucrc != exp:
        print("crc error - %s - exp=%r got=%r" % (desc, exp, ucrc))


def test_read_long(r, inf):
    """Test read and readinto.
    """
    md_class = inf._md_class or rf.NoHashContext
    bctx = md_class()
    f = r.open(inf.filename)
    total = 0
    while 1:
        data = f.read(8192)
        if not data:
            break
        bctx.update(data)
        total += len(data)
    if total != inf.file_size:
        xprint("\n *** %s has corrupt file: %s ***", r.rarfile, inf.filename)
        xprint(" *** short read: got=%d, need=%d ***\n", total, inf.file_size)
    check_crc(f, inf, "read")
    bhash = bctx.hexdigest()
    if cf_verbose > 1:
        if f._md_context.digest() == inf._md_expect:
            #xprint("  checkhash: %r", bhash)
            pass
        else:
            xprint("  checkhash: %r  got=%r exp=%r cls=%r\n",
                   bhash, f._md_context.digest(), inf._md_expect, inf._md_class)

    # test .seek() & .readinto()
    if cf_test_read > 1:
        f.seek(0, 0)

        total = 0
        buf = bytearray(1024)
        while 1:
            res = f.readinto(buf)
            if not res:
                break
            total += res
        if inf.file_size != total:
            xprint(" *** readinto failed: got=%d, need=%d ***\n", total, inf.file_size)
        #check_crc(f, inf, "readinto")
    f.close()


def test_read(r, inf):
    """Test file read."""
    test_read_long(r, inf)


def test_real(fn, pwd):
    """Actual archive processing.
    """
    xprint("Archive: %s", fn)

    cb = None
    if cf_verbose > 1:
        cb = show_item

    rfarg = fn
    if cf_test_memory:
        rfarg = io.BytesIO(open(fn, "rb").read())

    # check if rar
    if not rf.is_rarfile(rfarg):
        xprint(" --- %s is not a RAR file ---", fn)
        return

    # open
    r = rf.RarFile(rfarg, charset=cf_charset, info_callback=cb)
    # set password
    if r.needs_password():
        if pwd:
            r.setpassword(pwd)
        else:
            xprint(" --- %s requires password ---", fn)
            return

    # show comment
    if cf_show_comment and r.comment:
        for ln in r.comment.split("\n"):
            xprint("    %s", ln)
    elif cf_verbose > 0 and r.comment:
        cm = repr(r.comment)
        if cm[0] == "u":
            cm = cm[1:]
        xprint("  comment=%s", cm)

    # process
    for n in r.namelist():
        inf = r.getinfo(n)
        if cf_verbose == 1:
            show_item(inf)
        if cf_test_read and inf.is_file():
            test_read(r, inf)

    if cf_extract:
        r.extractall()
        for inf in r.infolist():
            r.extract(inf)

    if cf_test_unrar:
        r.testrar()


def test(fn, pwd):
    """Process one archive with error handling.
    """
    try:
        test_real(fn, pwd)
    except rf.NeedFirstVolume as ex:
        xprint(" --- %s is middle part of multi-vol archive (%s)---", fn, str(ex))
    except rf.Error:
        exc, msg, tb = sys.exc_info()
        xprint("\n *** %s: %s ***\n", exc.__name__, msg)
        del tb
    except IOError:
        exc, msg, tb = sys.exc_info()
        xprint("\n *** %s: %s ***\n", exc.__name__, msg)
        del tb


def main():
    """Program entry point.
    """
    global cf_verbose, cf_show_comment, cf_charset
    global cf_extract, cf_test_read, cf_test_unrar
    global cf_test_memory

    pwd = None

    # parse args
    try:
        opts, args = getopt.getopt(sys.argv[1:], "p:C:hvcxtRM")
    except getopt.error as ex:
        print(str(ex), file=sys.stderr)
        sys.exit(1)

    for o, v in opts:
        if o == "-p":
            pwd = v
        elif o == "-h":
            xprint(usage)
            return
        elif o == "-v":
            cf_verbose += 1
        elif o == "-c":
            cf_show_comment = 1
        elif o == "-x":
            cf_extract = 1
        elif o == "-t":
            cf_test_read += 1
        elif o == "-T":
            cf_test_unrar = 1
        elif o == "-M":
            cf_test_memory = 1
        elif o == "-C":
            cf_charset = v
        else:
            raise Exception("unhandled switch: " + o)

    args2 = []
    for a in args:
        if a[0] == "@":
            for ln in open(a[1:], "r"):
                fn = ln[:-1]
                args2.append(fn)
        else:
            args2.append(a)
    args = args2

    if not args:
        xprint(usage)

    for fn in args:
        test(fn, pwd)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

