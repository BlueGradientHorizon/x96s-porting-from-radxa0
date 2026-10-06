/*
 * x96s_wifi — wifi driver loader for the X96S stick (LineageOS).
 *
 * Runs once from init as the oneshot service `x96s_wifi`
 * (seclabel u:r:vendor_modprobe:s0 — the vendor policy's designed
 * module-loader domain: sys_module caps, kmsg write, vendor_file
 * read; entrypoint type is vendor_toolbox_exec).
 *
 * Selection is try-order over the map file: finit_module each
 * candidate until one sticks. No sysfs access here on purpose
 * (vendor_modprobe has none): VID:PID matching will move into each
 * driver's module_init (fail with -ENODEV when its hardware is
 * absent) once a second driver exists; until then the single entry
 * trivially selects itself. Unknown hardware or total failure exits
 * nonzero with a kmsg line (check dmesg) instead of guessing.
 *
 * No libc on purpose (Android is bionic, we build with -nostdlib):
 * raw AArch64 syscalls only, static buffers, own _start.
 *
 * Map file format (/vendor/etc/wifi/x96s_wifi.map), one per line:
 *     024c b723 /vendor_dlkm/lib/modules/x96s_8723bs.ko
 * (hex VID PID kept for the future driver-side matcher, '#' comments,
 * blank lines ok). Every path is tried in order, first success wins.
 *
 * Exit codes: 0 loaded, 2 all failed, 3 no/unreadable map.
 *
 * Build (x86_64 host with aarch64 cross-gcc, same toolchain as uboot):
 *     aarch64-linux-gnu-gcc -nostdlib -static -Os -o x96s_wifi wifi_select.c
 */
typedef unsigned long u64;
typedef long s64;

#define SYS_OPENAT 56
#define SYS_CLOSE 57
#define SYS_READ 63
#define SYS_WRITE 64
#define SYS_FINIT_MODULE 273
#define SYS_EXIT 93
#define AT_FDCWD (-100L)
#define O_RDONLY 0
#define O_WRONLY 1

#define MAP_PATH "/vendor/etc/wifi/x96s_wifi.map"
#define KMSG_PATH "/dev/kmsg"

static long sc1(long n, long a)
{
	register long r0 __asm__("x0") = a;
	register long r8 __asm__("x8") = n;
	__asm__ volatile("svc #0" : "+r"(r0) : "r"(r8) : "memory", "cc");
	return r0;
}

static long sc3(long n, long a, long b, long c)
{
	register long r0 __asm__("x0") = a;
	register long r1 __asm__("x1") = b;
	register long r2 __asm__("x2") = c;
	register long r8 __asm__("x8") = n;
	__asm__ volatile("svc #0"
			 : "+r"(r0)
			 : "r"(r1), "r"(r2), "r"(r8)
			 : "memory", "cc");
	return r0;
}

/* ---- tiny string/buffer helpers (no libc) ---- */

static int kmsg_fd = -1;
static char mbuf[256];
static int mlen;

static void mreset(void)
{
	mlen = 0;
}

static void mch(char c)
{
	if (mlen < (int)sizeof(mbuf) - 1)
		mbuf[mlen++] = c;
}

static void mput(const char *s)
{
	while (*s)
		mch(*s++);
}

static void mdec(long v)
{
	char t[24];
	int n = 0;
	int neg = 0;

	if (v < 0) {
		neg = 1;
		v = -v;
	}
	if (v == 0)
		t[n++] = '0';
	while (v != 0) {
		t[n++] = (char)('0' + v % 10);
		v /= 10;
	}
	if (neg)
		mch('-');
	while (n > 0)
		mch(t[--n]);
}

static void memit(void)
{
	int off = 0;
	long r;

	mch('\n');
	while (off < mlen) {
		r = sc3(SYS_WRITE, kmsg_fd, (long)(mbuf + off), mlen - off);
		if (r <= 0)
			break;
		off += (int)r;
	}
}

static void klog(const char *a, const char *b)
{
	if (kmsg_fd < 0)
		return;
	mreset();
	mput("<6>x96s_wifi: ");
	mput(a);
	if (b != 0)
		mput(b);
	memit();
}

/* read a small config file; returns byte count or -1 */
static long read_file(const char *path, char *buf, int cap)
{
	long fd, total = 0, r;

	fd = sc3(SYS_OPENAT, AT_FDCWD, (long)path, O_RDONLY);
	if (fd < 0)
		return -1;
	while (total < cap - 1) {
		r = sc3(SYS_READ, fd, (long)(buf + total), cap - 1 - total);
		if (r <= 0)
			break;
		total += r;
	}
	sc1(SYS_CLOSE, fd);
	buf[total] = '\0';
	return total;
}

static int is_space(char c)
{
	return c == ' ' || c == '\t' || c == '\r' || c == '\n';
}

static int hexval(char c)
{
	if (c >= '0' && c <= '9')
		return c - '0';
	if (c >= 'a' && c <= 'f')
		return c - 'a' + 10;
	if (c >= 'A' && c <= 'F')
		return c - 'A' + 10;
	return -1;
}

/* parse one hex number (optional 0x), advance *pp past it */
static unsigned long parse_hex(const char **pp)
{
	const char *p = *pp;
	unsigned long v = 0;
	int d;

	while (is_space(*p))
		p++;
	if (p[0] == '0' && (p[1] == 'x' || p[1] == 'X'))
		p += 2;
	while ((d = hexval(*p)) >= 0) {
		v = (v << 4) | (unsigned long)d;
		p++;
	}
	*pp = p;
	return v;
}

/* ---- map-driven try-order load ----
 *
 * NOTE: blank/comment lines are skipped INSIDE the loop below; the
 * entry parser never signals EOF by itself (returning 0 for both
 * "skip" and "end" once hid the whole map behind its leading '#'
 * lines — every map starts with comments, so zero drivers were ever
 * tried).
 */

static char mapbuf[4096];
static char kopath[256];

/* skip blanks and full-line comments; returns 0 at end of input */
static const char *skip_noise(const char *p)
{
	for (;;) {
		while (*p == '\n')
			p++;
		if (*p != '#')
			return p;
		while (*p != '\0' && *p != '\n')
			p++;
	}
}

/* parse one "VID PID /path" entry at p (leading noise already
 * skipped, *p != 0). Returns path, or (char *)-1 when malformed.
 * *pp advances past the line. */
static const char *parse_entry(const char **pp)
{
	const char *p = *pp;
	const char *q;
	int n;
	unsigned long mv, mp;

	mv = parse_hex(&p);
	mp = parse_hex(&p);
	(void)mv;
	(void)mp;
	while (is_space(*p) && *p != '\n')
		p++;
	q = p;
	while (*p != '\0' && *p != '\n' && !is_space(*p))
		p++;
	n = (int)(p - q);
	while (*p != '\0' && *p != '\n')
		p++;
	*pp = p;
	if (n <= 0 || n >= (int)sizeof(kopath))
		return (const char *)-1;
	{
		int i;

		for (i = 0; i < n; i++)
			kopath[i] = q[i];
		kopath[n] = '\0';
	}
	return kopath;
}

static int xmain(void)
{
	const char *p;
	const char *ko;
	int tried = 0;
	long r;
	static const char empty = '\0';

	kmsg_fd = (int)sc3(SYS_OPENAT, AT_FDCWD, (long)KMSG_PATH,
			   O_WRONLY);
	klog("start", 0);
	if (read_file(MAP_PATH, mapbuf, sizeof(mapbuf)) < 0) {
		klog("no map " MAP_PATH, 0);
		return 3;
	}
	p = mapbuf;
	for (;;) {
		p = skip_noise(p);
		if (*p == '\0')
			break;
		ko = parse_entry(&p);
		if (ko == (const char *)-1) {
			klog("bad map line, stop", 0);
			return 3;
		}
		tried++;
		klog("trying ", ko);
		r = sc3(SYS_OPENAT, AT_FDCWD, (long)ko, O_RDONLY);
		if (r < 0) {
			mreset();
			mput("<6>x96s_wifi: open err ");
			mdec(r);
			mput(" ");
			mput(ko);
			memit();
			continue;
		}
		{
			long kfd = r;

			r = sc3(SYS_FINIT_MODULE, kfd, (long)&empty, 0);
			sc1(SYS_CLOSE, kfd);
		}
		if (r == 0) {
			klog("up ", ko);
			return 0;
		}
		mreset();
		mput("<6>x96s_wifi: finit err ");
		mdec(r);
		mput(" ");
		mput(ko);
		memit();
	}
	if (!tried)
		klog("map empty, nothing to load", 0);
	else
		klog("no driver stuck, wifi left unloaded", 0);
	return 2;
}

void _start(void)
{
	long rc = xmain();

	sc1(SYS_EXIT, rc);
}
