/*
 * Probe log for unattended bring-up runs (built with -DSHIM_GPUPROBE).
 *
 * plog_save() writes the console text (con_text) to a scratch area at the end
 * of the userdata partition, just below the 1025-block XNU console ring
 * (patch 0047), so a later recovery boot can read it with adb
 * (tools/sweet-probe-loop.ps1). The iOS HFS+ volume only uses the start of
 * userdata; nothing outside the scratch area is ever written.
 *
 * plog_reboot_fastboot() makes the next boot stop in ABL's fastboot: the PMIC
 * PON soft-reboot reason (what ABL reads) plus the IMEM cookie, and PS_HOLD
 * as a hard reset, as ios-flame's shim does (PM6150 PON at SID 0 0x800; SPMI
 * arbiter v5 at the same addresses as on the Pixel 4: sweet DT spmi node).
 *
 * plog_wdog_arm() lets the APSS watchdog reset a probe that hangs on a bus
 * access, so a failed step still comes back to fastboot by itself.
 *
 * UFS: JEDEC UFSHCI, polled, one command at a time on LUN 0, MMU off.
 */
#ifdef SHIM_GPUPROBE
#include <stdint.h>
#include "console.h"
#include "plog.h"

static inline uint32_t rd32(uintptr_t a) { return *(volatile uint32_t *)a; }
static inline void wr32(uintptr_t a, uint32_t v) { *(volatile uint32_t *)a = v; }

static uint64_t ticks(void)
{
	uint64_t t;
	__asm__ volatile("isb; mrs %0, cntpct_el0" : "=r"(t));
	return t;
}

static void delay_ms(unsigned ms)
{
	uint64_t end = ticks() + 19200ULL * ms;
	while (ticks() < end)
		;
}

/* ---- UFS ---- */

#define UFS_BASE	0x01d84000UL
#define REG_IS		0x20
#define REG_HCS		0x30
#define REG_HCE		0x34
#define REG_UTRLBA	0x50
#define REG_UTRLBAU	0x54
#define REG_UTRLDBR	0x58
#define REG_UTRLCLR	0x5c
#define REG_UTRLRSR	0x60
#define BLOCK		4096u
#define XNU_LOG_TAIL	1025u		/* sweet_ufs.c console ring: last 1025 blocks */
#define SCRATCH_BLOCKS	(PLOG_BLOCKS)
#define MAGIC0		0x52505753u	/* "SWPR" */
#define MAGIC1		0x3145424fu	/* "OBE1" */

struct utrd {
	uint32_t dw0, dw1, dw2, dw3;
	uint32_t ucdba, ucdbau;
	uint32_t resp, prdt;
};

struct ucd {
	uint8_t cmd[512];
	uint8_t resp[512];
	struct {
		uint32_t addr_lo, addr_hi, rsvd, dbc;
	} prdt[1];
};

static struct utrd utrl[32] __attribute__((aligned(1024)));
static struct ucd ucd __attribute__((aligned(128)));
static uint8_t blk[2 * BLOCK] __attribute__((aligned(4096)));
static uint8_t hdr[BLOCK] __attribute__((aligned(4096)));

static inline uint32_t ufs_rd(uint32_t off) { return rd32(UFS_BASE + off); }
static inline void ufs_wr(uint32_t off, uint32_t v) { wr32(UFS_BASE + off, v); }

static int ready;
static uint64_t scratch_first, part_first, part_blocks;
static uint32_t save_seq;

static void zero(void *p, unsigned n)
{
	volatile uint8_t *b = p;
	for (unsigned i = 0; i < n; i++)
		b[i] = 0;
}

/* dir: 0 none, 1 data out (write), 2 data in (read). */
static uint32_t scsi(const uint8_t *cdb, unsigned cdb_len, const void *buf, uint32_t len, int dir)
{
	static uint8_t tag;
	zero(&utrl[0], sizeof(utrl[0]));
	zero(&ucd, sizeof(ucd));
	ucd.cmd[0] = 0x01;
	ucd.cmd[1] = dir == 1 ? 0x20 : dir == 2 ? 0x40 : 0;
	ucd.cmd[3] = ++tag;
	ucd.cmd[12] = len >> 24;
	ucd.cmd[13] = len >> 16;
	ucd.cmd[14] = len >> 8;
	ucd.cmd[15] = len;
	for (unsigned i = 0; i < cdb_len; i++)
		ucd.cmd[16 + i] = cdb[i];
	uintptr_t ucd_pa = (uintptr_t)&ucd;
	utrl[0].dw0 = (1u << 28) | ((uint32_t)dir << 25) | (1u << 24);
	utrl[0].dw2 = 0x0f;
	utrl[0].ucdba = (uint32_t)ucd_pa;
	utrl[0].ucdbau = (uint32_t)(ucd_pa >> 32);
	utrl[0].resp = (512u / 4) << 16 | (512u / 4);
	if (len) {
		uintptr_t pa = (uintptr_t)buf;
		ucd.prdt[0].addr_lo = (uint32_t)pa;
		ucd.prdt[0].addr_hi = (uint32_t)(pa >> 32);
		ucd.prdt[0].dbc = len - 1;
		utrl[0].prdt = (1024u / 4) << 16 | 1;
	}
	__asm__ volatile("dsb sy" ::: "memory");
	ufs_wr(REG_UTRLDBR, 1);
	uint64_t start = ticks();
	while (ufs_rd(REG_UTRLDBR) & 1) {
		if (ticks() - start > 19200000ULL * 5) {
			ufs_wr(REG_UTRLCLR, ~1u);
			return 1;
		}
	}
	__asm__ volatile("dsb sy" ::: "memory");
	ufs_wr(REG_IS, ufs_rd(REG_IS));
	if (utrl[0].dw2 & 0xff)
		return 0x100 | (utrl[0].dw2 & 0xff);
	if (ucd.resp[0] != 0x21)
		return 3;
	if (ucd.resp[6] || ucd.resp[7])
		return 0x200 | ucd.resp[7];
	return 0;
}

static uint32_t rw10(int write, uint64_t lba, uint32_t count, const void *buf)
{
	uint8_t cdb[10] = { write ? 0x2a : 0x28, 0, lba >> 24, lba >> 16, lba >> 8, lba, 0,
			    count >> 8, count, 0 };
	return scsi(cdb, sizeof(cdb), buf, count * BLOCK, write ? 1 : 2);
}

static uint64_t le64(const uint8_t *p)
{
	uint64_t v = 0;
	for (int i = 7; i >= 0; i--)
		v = v << 8 | p[i];
	return v;
}

int plog_init(void)
{
	uint32_t hcs = ufs_rd(REG_HCS), hce = ufs_rd(REG_HCE);
	if (!(hce & 1) || (hcs & 3) != 3 || ufs_rd(REG_UTRLDBR))
		return -1;
	ufs_wr(REG_UTRLRSR, 0);
	uintptr_t list = (uintptr_t)utrl;
	ufs_wr(REG_UTRLBA, (uint32_t)list);
	ufs_wr(REG_UTRLBAU, (uint32_t)(list >> 32));
	ufs_wr(REG_UTRLRSR, 1);
	/* Never ring a doorbell unless the host really uses our list. */
	if (ufs_rd(REG_UTRLBA) != (uint32_t)list || ufs_rd(REG_UTRLBAU) != (uint32_t)(list >> 32) ||
	    !(ufs_rd(REG_UTRLRSR) & 1))
		return -2;
	static const uint8_t tur[6] = { 0 };
	for (int i = 0; i < 3 && scsi(tur, sizeof(tur), 0, 0, 0); i++)
		;
	if (rw10(0, 1, 1, blk) || blk[0] != 'E' || blk[1] != 'F' || blk[2] != 'I')
		return -3;
	uint64_t elba = le64(blk + 72);
	uint32_t nent = blk[80] | blk[81] << 8, esz = blk[84] | blk[85] << 8;
	if (esz != 128 || nent > 128)
		return -4;
	static uint8_t ents[128 * 128] __attribute__((aligned(4096)));
	if (rw10(0, elba, (nent * 128 + BLOCK - 1) / BLOCK, ents))
		return -5;
	static const char want[] = "userdata";
	for (uint32_t i = 0; i < nent; i++) {
		const uint8_t *e = ents + i * 128;
		int match = 1;
		for (int c = 0; c < 9; c++)
			if (e[56 + 2 * c] != (uint8_t)want[c] || e[57 + 2 * c])
				match = 0;
		if (!match)
			continue;
		part_first = le64(e + 32);
		part_blocks = le64(e + 40) - part_first + 1;
	}
	if (part_blocks < 0x100000)		/* < 4 GiB: not the partition we expect */
		return -6;
	scratch_first = part_first + part_blocks - XNU_LOG_TAIL - SCRATCH_BLOCKS;
	ready = 1;
	return 0;
}

/* Header block (magic, sequence, length, reason), then the text blocks. */
int plog_save(const char *why)
{
	if (!ready)
		return -1;
	zero(hdr, sizeof(hdr));
	uint32_t *h = (uint32_t *)hdr;
	h[0] = MAGIC0;
	h[1] = MAGIC1;
	h[2] = ++save_seq;
	h[3] = con_text_len;
	for (int i = 0; why[i] && i < 255; i++)
		hdr[16 + i] = why[i];
	uint32_t n = (con_text_len + BLOCK - 1) / BLOCK;
	if (n > SCRATCH_BLOCKS - 1)
		n = SCRATCH_BLOCKS - 1;
	for (uint32_t i = 0; i < n; i++)
		if (rw10(1, scratch_first + 1 + i, 1, con_text + i * BLOCK))
			return -2;
	if (rw10(1, scratch_first, 1, hdr))	/* header last: it validates the text */
		return -3;
	static const uint8_t sync[10] = { 0x35 };
	return scsi(sync, sizeof(sync), 0, 0, 0) ? -4 : 0;
}

/* ---- SPMI (PMIC arbiter v5, EE 0) ---- */

#define CORE_PA		0x0c440000UL
#define CHNLS_PA	0x0c600000UL
#define OBS_PA		0x0e600000UL
#define CNFG_PA		0x0c40a000UL
#define NO_APID		0xffffu

static uint32_t find_apid(uint32_t ppid, uint32_t *owner)
{
	uint32_t napids = rd32(CORE_PA + 4) & 0x7ff, found = NO_APID;
	if (napids > 512)
		return NO_APID;
	for (uint32_t i = 0; i < napids; i++) {
		uint32_t map = rd32(CORE_PA + 0x900 + 4 * i);
		if (!map || ((map >> 8) & 0xfff) != ppid)
			continue;
		uint32_t own = rd32(CNFG_PA + 0x700 + 4 * i) & 7;
		if (found == NO_APID || own == 0) {
			found = i;
			*owner = own;
		}
	}
	return found;
}

static int spmi_wait(uintptr_t ch)
{
	uint64_t start = ticks();
	for (;;) {
		uint32_t st = rd32(ch + 0x08);
		if (st & 1)
			return st & 0x0e ? -2 : 0;
		if (ticks() - start > 1920000)
			return -3;
	}
}

static int spmi_read(uint32_t sid, uint32_t addr, uint8_t *out)
{
	uint32_t owner = 7, apid = find_apid(sid << 8 | (addr >> 8 & 0xff), &owner);
	if (apid == NO_APID)
		return -1;
	uintptr_t ch = OBS_PA + 0x80UL * apid;
	wr32(ch, 1u << 27 | (addr & 0xff) << 4);
	int rc = spmi_wait(ch);
	if (!rc)
		*out = rd32(ch + 0x18) & 0xff;
	return rc;
}

static int spmi_write(uint32_t sid, uint32_t addr, uint8_t val)
{
	uint32_t owner = 7, apid = find_apid(sid << 8 | (addr >> 8 & 0xff), &owner);
	if (apid == NO_APID || owner != 0)
		return -1;
	uintptr_t ch = CHNLS_PA + 0x10000UL * apid;
	wr32(ch + 0x10, val);
	wr32(ch, (addr & 0xff) << 4);
	return spmi_wait(ch);
}

#define PON_SOFT_RB_SPARE	0x88f	/* PM6150 (SID 0) PON, reason in [7:1] */
#define PON_REASON_BOOTLOADER	0x02
#define PON_PS_HOLD_RESET_CTL	0x85a
#define PON_PS_HOLD_RESET_CTL2	0x85b
#define PON_RESET_EN		0x80
#define PON_HARD_RESET		0x7
#define IMEM_RESTART_REASON	0x146aa65cUL
#define RESTART_BOOTLOADER	0x77665500U

int plog_set_fastboot_reason(void)
{
	uint8_t v = 0xff, ctl = 0xff, ctl2 = 0xff;
	int rc = spmi_read(0, PON_SOFT_RB_SPARE, &v);
	if (!rc)
		rc = spmi_write(0, PON_SOFT_RB_SPARE, (v & 1) | PON_REASON_BOOTLOADER << 1);
	/* PS_HOLD (PSCI reset, watchdog bite) as a PMIC hard reset, as Linux sets it. */
	int rc2 = spmi_read(0, PON_PS_HOLD_RESET_CTL, &ctl);
	rc2 |= spmi_read(0, PON_PS_HOLD_RESET_CTL2, &ctl2);
	if (!rc2) {
		rc2 |= spmi_write(0, PON_PS_HOLD_RESET_CTL2, ctl2 & ~PON_RESET_EN);
		delay_ms(1);
		rc2 |= spmi_write(0, PON_PS_HOLD_RESET_CTL, (ctl & ~0xf) | PON_HARD_RESET);
		rc2 |= spmi_write(0, PON_PS_HOLD_RESET_CTL2, ctl2 | PON_RESET_EN);
	}
	wr32(IMEM_RESTART_REASON, RESTART_BOOTLOADER);
	uint8_t after = 0;
	spmi_read(0, PON_SOFT_RB_SPARE, &after);
	con_hex2("REBOOT", "pon spare=", after, "rc=", (uint32_t)(rc | rc2 << 8));
	return rc | rc2;
}

/* ---- watchdog ---- */

#define WDOG		0x17c10000UL

void plog_wdog_arm(unsigned seconds)
{
	uint32_t t = seconds * 32768u;	/* sleep clock */
	wr32(WDOG + 0x08, 0);		/* EN */
	wr32(WDOG + 0x10, t);		/* BARK_TIME */
	wr32(WDOG + 0x14, t + 32768u);	/* BITE_TIME */
	wr32(WDOG + 0x04, 1);		/* RST (pet) */
	wr32(WDOG + 0x08, 1);
}

void plog_wdog_pet(void)
{
	wr32(WDOG + 0x04, 1);
}

void __attribute__((noreturn)) plog_reboot(void)
{
	__asm__ volatile("dsb sy" ::: "memory");
	register uint64_t x0 __asm__("x0") = 0x84000009UL;	/* PSCI SYSTEM_RESET */
	__asm__ volatile("smc #0" : "+r"(x0) : : "x1", "x2", "x3", "memory");
	wr32(0x0c264000UL, 0);					/* PS_HOLD low */
	for (;;)
		__asm__ volatile("wfe");
}
#endif /* SHIM_GPUPROBE */
