/*
 * GPU probe (built with -DSHIM_GPUPROBE): Adreno 618 bring-up from the boot
 * shim, after ios-flame's shim/gpuprobe.c (Adreno 640).
 *
 * Stage 1 powers the GPU's CX side: GCC GPU branches, GPUCC CX GDSC,
 * gmu_clk_src = XO and the CX clocks, then checks that the GMU's ITCM/DTCM
 * take writes and that the Adreno SMMU is ours (phone run 1: all yes).
 *
 * Stage 2 boots the GMU the way Linux does for the "legacy" a630-family GMU
 * (a6xx_gmu.c a6xx_gmu_fw_start with gmu->legacy, a6xx_hfi.c start_v1):
 * an SMMU context bank with our page tables for the GMU stream, RSC/PDC
 * sequencer setup, the raw a618_gmu.bin copied into ITCM, CM3 start, the
 * BOOT_SLUMBER OOB with the GX/MX votes, SPTPRAC on, HFI v1 (INIT,
 * FW_VERSION, PERF_TABLE v1, BW_TABLE, TEST), then the GPU_SET OOB that
 * makes the GMU power the GX side. Last check: RBBM_STATUS and a CP scratch
 * register write.
 *
 * Results go to the framebuffer console; the bottom row always names the
 * step in progress, so a hang shows where it stopped. The APSS watchdog is
 * switched off first (phone run 1 was reset after ~10 s).
 *
 * Addresses: sweet's DT (qcom,kgsl-3d0 0x5000000, qcom,gmu 0x506a000 with PDC
 * 0xb290000/0xb490000, kgsl-smmu 0x5040000, gpucc-sdmmagpie 0x5090000,
 * cmd-db pointer 0xc3f000c, msm-watchdog 0x17c10000), gcc-sm7150.c,
 * gpucc-sc7180.c (same A618 GPUCC). GMU register numbers are dword offsets
 * from the GPU base, as in Mesa's a6xx_gmu.xml.
 */
#ifdef SHIM_GPUPROBE
#include <stdint.h>
#include "console.h"
#include "gpuprobe.h"
#include "plog.h"

#define GCC		0x00100000UL
#define GPUCC		0x05090000UL
#define GPU		0x05000000UL
#define GMU_REG(o)	(GPU + 4UL * (o))
#define SMMU		0x05040000UL
#define WDOG		0x17c10000UL
#define CMD_DB_PTR	0x0c3f000cUL

#define GCC_DDRSS_GPU_AXI	0x4452c
#define GCC_GPU_MEMNOC_GFX	0x7100c
#define GCC_GPU_SNOC_DVM_GFX	0x71018

#define GPUCC_GX_GDSCR		0x100c
#define GPUCC_CX_GDSCR		0x106c
#define GPUCC_CRC_AHB		0x107c
#define GPUCC_CX_SNOC_DVM	0x108c
#define GPUCC_CX_GMU		0x1098
#define GPUCC_CXO		0x109c
#define GPUCC_GMU_RCG		0x1120

/* a6xx_gmu.xml */
#define GMU_SPTPRAC_PWR_CTRL	0x1a881
#define GMU_ITCM		0x1b400
#define GMU_DTCM		0x1c400
#define GMU_BOOT_SLUMBER_OPT	0x1cbf8
#define GMU_GX_VOTE_IDX		0x1cbf9
#define GMU_MX_VOTE_IDX		0x1cbfa
#define GMU_DCVS_ACK_OPTION	0x1cbfc
#define GMU_DCVS_PERF_SETTING	0x1cbfd
#define GMU_DCVS_BW_SETTING	0x1cbfe
#define GMU_DCVS_RETURN		0x1cbff
#define GMU_ICACHE_CFG		0x1f400
#define GMU_DCACHE_CFG		0x1f401
#define GMU_SYS_BUS		0x1f40f
#define GMU_SYSRESET		0x1f800
#define GMU_BOOT_CFG		0x1f801
#define GMU_INIT_RESULT		0x1f81c
#define GMU_CM3_CFG		0x1f82d
#define GMU_PWRCOL_CTRL		0x1f8c0
#define GMU_SPTPRAC_STATUS	0x1f8d0
#define GMU_RPMH_CTRL		0x1f8e8
#define GMU_RPMH_STATE		0x1f8ec
#define GMU_CP_MSG		0x1f900
#define GMU_CP_RESP		0x1f901
#define GMU_HFI_STATUS		0x1f980
#define GMU_SFR_ADDR		0x1f982
#define GMU_QTBL_INFO		0x1f984
#define GMU_QTBL_ADDR		0x1f985
#define GMU_HFI_INIT		0x1f986
#define GMU_G2H_CLR		0x1f991
#define GMU_G2H_INFO		0x1f992
#define GMU_H2G_SET		0x1f994
#define GMU_GENERAL_7		0x1f9cc
#define GMU_RSCC_REQ		0x23b07
#define GMU_RSCC_ACK		0x23b08
#define GMU_FENCE0		0x23b11

#define RSCC		(0x0506a000UL + 0x23000)	/* gmu->mmio + 0x23000 before A650 */
#define RSCC_REG(o)	(RSCC + 4UL * (o))
#define PDC		0x0b290000UL
#define PDC_REG(o)	(PDC + 4UL * (o))
#define PDC_SEQ		0x0b490000UL

/* SMMU-500 global space 0 / 1 and context banks (IDR1: 4K pages, CBs at +0x8000) */
#define SMMU_GR1	(SMMU + 0x1000)
#define SMMU_CB(n)	(SMMU + 0x8000 + 0x1000UL * (n))
#define SMR(n)		(SMMU + 0x800 + 4 * (n))
#define S2CR(n)		(SMMU + 0xc00 + 4 * (n))
#define CBAR(n)		(SMMU_GR1 + 4 * (n))
#define CBA2R(n)	(SMMU_GR1 + 0x800 + 4 * (n))
#define CB_SCTLR	0x00
#define CB_TCR2		0x10
#define CB_TTBR0	0x20
#define CB_TCR		0x30
#define CB_MAIR0	0x38
#define CB_FSR		0x58
#define CB_FAR		0x60
#define CB_FSYNR0	0x68
/*
 * sweet DT: gmu_user iommus <&kgsl_smmu 4>, gmu_kernel <&kgsl_smmu 5>. Run 3b
 * (SID 5 mask 0x400, as on the A640) left the GMU log empty and reset at HFI
 * init: match both streams (mask bit 0) and report the global fault syndrome.
 */
#define GMU_SID		4
#define GMU_SID_MASK	0x401

/* GMU buffers + page tables: top of the upper DRAM bank, never used by the shim. */
#define GMEM		0x1f0000000UL
#define GMEM_L1		(GMEM + 0x0000)
#define GMEM_L2		(GMEM + 0x1000)		/* VA 0x40000000-0x7fffffff */
#define GMEM_L3		(GMEM + 0x2000)		/* VA 0x60000000-0x601fffff */
#define GMEM_DUMMY	(GMEM + 0x10000)
#define GMEM_DEBUG	(GMEM + 0x11000)
#define GMEM_LOG	(GMEM + 0x15000)
#define GMEM_HFI	(GMEM + 0x19000)
#define GMEM_SIZE	0x20000UL

#define VA_DUMMY	0x60000000u
#define VA_DEBUG	0x60001000u
#define VA_LOG		0x60005000u
#define VA_HFI		0x60009000u
#define BUF_SIZE	0x4000u

extern const uint8_t gmu_fw[], gmu_fw_end[];

static inline uint32_t rd32(uintptr_t a) { return *(volatile uint32_t *)a; }
static inline void wr32(uintptr_t a, uint32_t v) { *(volatile uint32_t *)a = v; }

static void wr64(uintptr_t pa, uint64_t v)
{
	wr32(pa, (uint32_t)v);
	wr32(pa + 4, (uint32_t)(v >> 32));
}

static uint64_t now(void)
{
	uint64_t v;
	__asm__ volatile("isb; mrs %0, cntpct_el0" : "=r"(v));
	return v;
}

static void delay_ms(unsigned ms)
{
	uint64_t f;
	__asm__ volatile("mrs %0, cntfrq_el0" : "=r"(f));
	uint64_t end = now() + f / 1000 * ms;
	while (now() < end)
		;
}

static int wait_bit(uintptr_t reg, uint32_t mask, int set, unsigned ms)
{
	for (unsigned i = 0; i <= ms; i++) {
		if (!!(rd32(reg) & mask) == set)
			return 0;
		delay_ms(1);
	}
	return -1;
}

static const char **stage_p;

/*
 * Phone run 2: the bottom-row status was not visible; print each step as a
 * line, and save the log to UFS before it so a reset still leaves it there.
 */
static void stage(const char *s)
{
	*stage_p = s;
	con_str("AT", s);
	plog_wdog_pet();
	plog_save(s);
}

static int branch_on(uintptr_t reg)
{
	wr32(reg, rd32(reg) | 1);
	return wait_bit(reg, 1u << 31, 0, 10);
}

/*
 * gpu_cc_pll0 (Fabia), the GPU core clock's source: gx_gfx3d_clk_src parent 1
 * is crc_div = pll0_out_even. Nobody had set it up, so after DCVS the RCG
 * pointed at a PLL that was off and the A618 ran no faster at "430 MHz" than
 * at XO (runs 0090r-0094e: 60-110 ms a CoreAnimation submission). Values
 * from the downstream sdmmagpie gpucc driver (clk_fabia_pll_configure +
 * clk_fabia_pll_enable), L/alpha for 430 MHz (22.396 x 19.2 MHz).
 */
#define PLL0		(GPUCC + 0x0)
#define PLL_MODE	0x00
#define PLL_L_VAL	0x04
#define PLL_USER_CTL	0x0c
#define PLL_USER_CTL_U	0x10
#define PLL_CONFIG_CTL	0x14
#define PLL_CONFIG_CTL_U 0x18
#define PLL_TEST_CTL_U	0x20
#define PLL_OPMODE	0x2c
#define PLL_FRAC	0x38

static int pll0_on(void)
{
	uint32_t mode = rd32(PLL0 + PLL_MODE);
	if ((rd32(PLL0 + PLL_OPMODE) & 1) && (mode & 1)) {
		con_hex2("PLL0", "already on mode=", mode, "l=", rd32(PLL0 + PLL_L_VAL));
		return 0;
	}
	wr32(PLL0 + PLL_L_VAL, 0x16);
	wr32(PLL0 + PLL_FRAC, 0x6555);
	wr32(PLL0 + PLL_CONFIG_CTL, 0x20485699);
	wr32(PLL0 + PLL_CONFIG_CTL_U, 0x00002067);
	wr32(PLL0 + PLL_USER_CTL, 0x00000001);
	wr32(PLL0 + PLL_USER_CTL_U, 0x00004805);
	wr32(PLL0 + PLL_TEST_CTL_U, 0x40000000);
	wr32(PLL0 + PLL_MODE, rd32(PLL0 + PLL_MODE) | (1u << 23));	/* UPDATE_BYPASS */
	/* enable: output off, standby, out of reset, run, lock, outputs on */
	wr32(PLL0 + PLL_MODE, rd32(PLL0 + PLL_MODE) & ~1u);
	wr32(PLL0 + PLL_OPMODE, 0);
	wr32(PLL0 + PLL_MODE, rd32(PLL0 + PLL_MODE) | (1u << 2));
	wr32(PLL0 + PLL_OPMODE, 1);
	int rc = wait_bit(PLL0 + PLL_MODE, 1u << 31, 1, 10);
	wr32(PLL0 + PLL_USER_CTL, rd32(PLL0 + PLL_USER_CTL) | 7u);
	wr32(PLL0 + PLL_MODE, rd32(PLL0 + PLL_MODE) | 1u);
	con_hex2("PLL0", rc ? "NO LOCK mode=" : "locked mode=", rd32(PLL0 + PLL_MODE), "user=", rd32(PLL0 + PLL_USER_CTL));
	return rc;
}

/* ---- stage 1: CX power ---- */

static int cx_on(void)
{
	stage("gcc branches");
	int h = branch_on(GCC + GCC_DDRSS_GPU_AXI) ? 1 : 0;
	h |= branch_on(GCC + GCC_GPU_MEMNOC_GFX) ? 2 : 0;
	h |= branch_on(GCC + GCC_GPU_SNOC_DVM_GFX) ? 4 : 0;

	stage("cx gdsc");
	/* CX GDSC: clear SW_COLLAPSE (bit 0), wait for PWR_ON (bit 31). */
	uintptr_t gdsc = GPUCC + GPUCC_CX_GDSCR;
	wr32(gdsc, rd32(gdsc) & ~1u);
	int rc = wait_bit(gdsc, 1u << 31, 1, 100);
	con_hex2("CX", rc ? "GDSC TIMEOUT=" : "gdsc=", rd32(gdsc), "gcc halted=", h);
	if (rc)
		return -1;

	stage("gmu clocks");
	/* gmu_clk_src: source 0 (XO), divider 1 (HID 1), then update. */
	uintptr_t rcg = GPUCC + GPUCC_GMU_RCG;
	wr32(rcg + 4, (rd32(rcg + 4) & ~0x71fu) | 1u);
	wr32(rcg, rd32(rcg) | 1u);
	wait_bit(rcg, 1, 0, 10);
	branch_on(GPUCC + GPUCC_CXO);
	branch_on(GPUCC + GPUCC_CX_GMU);
	/*
	 * Phone run 2b hung on the first SMMU register read without these two;
	 * run 1 (which wrote them) read the SMMU fine.
	 */
	branch_on(GPUCC + GPUCC_CRC_AHB);
	branch_on(GPUCC + GPUCC_CX_SNOC_DVM);
	con_hex2("GMUCLK", "cx_gmu=", rd32(GPUCC + GPUCC_CX_GMU), "cxo=", rd32(GPUCC + GPUCC_CXO));
	pll0_on();
	return 0;
}

/* ---- stage 2: GMU boot ---- */

static void zero32(uintptr_t pa, uint64_t size)
{
	for (uint64_t o = 0; o < size; o += 4)
		wr32(pa + o, 0);
}

/* Stage-1 AArch64 4K pages: AF, inner shareable, AttrIndx 0 (NC), privileged RW. */
static void map_pages(uintptr_t l3, uint32_t va, uintptr_t pa, uint32_t size)
{
	for (uint32_t o = 0; o < size; o += 0x1000) {
		uint32_t idx = ((va + o) >> 12) & 0x1ff;
		wr64(l3 + 8 * idx, (pa + o) | (1u << 10) | (3u << 8) | 3u);
	}
}

static int smr_used;

static int smmu_setup(void)
{
	int smr = -1, cb = -1;
	uint32_t used_cb = 0, nsmr = rd32(SMMU + 0x20) & 0xff, ncb = rd32(SMMU + 0x24) & 0xff;
	con_hex2("SMMU", "nsmr=", nsmr, "ncb=", ncb);
	for (uint32_t i = 0; i < nsmr && i < 16; i++) {
		uint32_t m = rd32(SMR(i)), c = rd32(S2CR(i));
		if ((m >> 31) && ((c >> 16) & 3) == 0)
			used_cb |= 1u << (c & 0xff);
		if (smr < 0 && !(m >> 31))
			smr = (int)i;
	}
	con_hex2("SMMU", "free smr=", (uint32_t)smr, "used cbs=", used_cb);
	/* Phone run 2 hung right here: read one context bank at a time. */
	for (uint32_t i = 0; i < ncb && i < 16; i++) {
		char l[] = "CB0 read";
		l[2] = '0' + i;
		stage(l);
		uint32_t s = rd32(SMMU_CB(i) + CB_SCTLR);
		con_hex2("  cb", "sctlr=", s, "cbar=", rd32(CBAR(i)));
		if (cb < 0 && !(used_cb & (1u << i)) && !(s & 1))
			cb = (int)i;
	}
	con_hex2("SMMU", "free smr=", (uint32_t)smr, "cb=", (uint32_t)cb);
	if (smr < 0 || cb < 0)
		return -1;

	stage("page tables at 0x1f0000000");
	zero32(GMEM, GMEM_SIZE);
	wr64(GMEM_L1 + 8, GMEM_L2 | 3);				/* 1G block 1: 0x40000000 */
	wr64(GMEM_L2 + 8 * ((VA_DUMMY >> 21) & 0x1ff), GMEM_L3 | 3);
	map_pages(GMEM_L3, VA_DUMMY, GMEM_DUMMY, 0x1000);
	map_pages(GMEM_L3, VA_DEBUG, GMEM_DEBUG, BUF_SIZE);
	map_pages(GMEM_L3, VA_LOG, GMEM_LOG, BUF_SIZE);
	map_pages(GMEM_L3, VA_HFI, GMEM_HFI, BUF_SIZE);

	/*
	 * Runs 3b/3c: SMR0 read back 0 after the write (CB registers did take
	 * writes). Find out which global registers the hypervisor lets us write.
	 */
	/*
	 * Run 3d (non-valid SMR + fault-type S2CR test writes on all five)
	 * reset the phone: the hypervisor seems to police these. Try only what
	 * the DT declares: S2CR translate to our CB, then SMR exact SID 5, mask 0.
	 */
	stage("smmu exact sid 5");
	wr32(S2CR(smr), (uint32_t)cb);
	wr32(SMR(smr), (1u << 31) | 5u);
	__asm__ volatile("dsb sy" ::: "memory");
	con_hex2("SID5", "smr=", rd32(SMR(smr)), "s2cr=", rd32(S2CR(smr)));
	if (!(rd32(SMR(smr)) >> 31) && smr + 1 < (int)nsmr) {
		stage("smmu exact sid 4");
		wr32(S2CR(smr + 1), (uint32_t)cb);
		wr32(SMR(smr + 1), (1u << 31) | 4u);
		__asm__ volatile("dsb sy" ::: "memory");
		con_hex2("SID4", "smr=", rd32(SMR(smr + 1)), "s2cr=", rd32(S2CR(smr + 1)));
	}
	con_hex2("SMMU", "scr0=", rd32(SMMU), "smr5=", rd32(SMR(5)));

	stage("program context bank");
	uintptr_t c = SMMU_CB(cb);
	wr32(c + CB_SCTLR, 0);
	wr32(CBA2R(cb), 1);					/* AArch64 descriptors */
	wr32(CBAR(cb), (1u << 16) | (0xfu << 12) | (3u << 8) | (uint32_t)(cb + 1));	/* S1, VMID */
	wr32(c + CB_TCR2, 2);					/* 40-bit PA */
	wr64(c + CB_TTBR0, GMEM_L1);
	wr32(c + CB_TCR, 32 | (1u << 8) | (1u << 10) | (3u << 12) | (1u << 23));
	wr32(c + CB_MAIR0, 0x0000ff44);
	wr32(c + CB_FSR, 0xffffffff);
	wr32(c + CB_SCTLR, 1 | 2 | 4 | 0x20 | 0x40);		/* M TRE AFE CFRE CFIE */
	wr32(SMMU + 0x68, 0);					/* TLBIALLNSNH */
	wr32(SMMU + 0x70, 0);					/* TLBGSYNC */
	wait_bit(SMMU + 0x74, 1, 0, 10);
	con_hex2("SMMU", "smr=", rd32(SMR(smr)), "sctlr=", rd32(c + CB_SCTLR));
	con_hex2("SMMU", "s2cr=", rd32(S2CR(smr)), "cbar=", rd32(CBAR(cb)));
	smr_used = (rd32(SMR(smr + 1)) >> 31) ? smr + 1 : smr;
	if (!(rd32(SMR(smr)) >> 31) && !(rd32(SMR(smr + 1)) >> 31)) {
		con_str("SMMU", "SMR NOT TAKEN: stop before the GMU uses DDR");
		return -1;
	}
	return cb;
}

/*
 * a6xx_gmu_rpmh_init for the A618 (TCS3 data+4 = 2). Linux hardcodes the PDC
 * TCS resource addresses for sc7180 (0x30010, 0x30000, pdc_address_offset
 * 0x30090); run 3a's GPU RSC wake was never acked, so these come from sweet's
 * own cmd-db now (mx.lvl, cx.lvl, gfx.lvl), shown on the log.
 */
static uint32_t cmddb_addr(const char *id);

static void rpmh_init(void)
{
	uint32_t a_mx = cmddb_addr("mx.lvl"), a_cx = cmddb_addr("cx.lvl"), a_gfx = cmddb_addr("gfx.lvl");
	con_hex2("ARC", "mx=", a_mx, "cx=", a_cx);
	con_hex2("ARC", "gfx=", a_gfx, "linux=", 0x30090);
	if (!a_mx)
		a_mx = 0x30010;
	if (!a_cx)
		a_cx = 0x30000;
	if (!a_gfx)
		a_gfx = 0x30090;
	wr32(RSCC_REG(0x0004), 1u << 24);
	wr32(RSCC_REG(0x000b), 1);
	wr32(RSCC_REG(0x000e), 0);
	wr32(RSCC_REG(0x000d), 0);
	wr32(RSCC_REG(0x000e + 2), 0);
	wr32(RSCC_REG(0x000d + 2), 0);
	wr32(RSCC_REG(0x000e + 4), 0x80000000);
	wr32(RSCC_REG(0x000d + 4), 0);
	wr32(RSCC_REG(0x0100), 0);
	wr32(RSCC_REG(0x0008), 0x4520);
	wr32(RSCC_REG(0x0009), 0x4510);
	wr32(RSCC_REG(0x000a), 0x4514);
	wr32(RSCC_REG(0x0180), 0xa7a506a0);
	wr32(RSCC_REG(0x0181), 0xa1e6a6e7);
	wr32(RSCC_REG(0x0182), 0xa2e081e1);
	wr32(RSCC_REG(0x0183), 0xe9a982e2);
	wr32(RSCC_REG(0x0184), 0x0020e8a8);

	wr32(PDC_SEQ + 0, 0xfebea1e1);
	wr32(PDC_SEQ + 4, 0xa5a4a3a2);
	wr32(PDC_SEQ + 8, 0x8382a6e0);
	wr32(PDC_SEQ + 12, 0xbce3e284);
	wr32(PDC_SEQ + 16, 0x002081fc);

	wr32(PDC_REG(0x1573), 7);
	wr32(PDC_REG(0x1574), 0);
	wr32(PDC_REG(0x1572), 0);
	wr32(PDC_REG(0x1575), 0x10108);
	wr32(PDC_REG(0x1576), a_mx);
	wr32(PDC_REG(0x1577), 1);
	wr32(PDC_REG(0x1575 + 4), 0x10108);
	wr32(PDC_REG(0x1576 + 4), a_cx);
	wr32(PDC_REG(0x1577 + 4), 0);
	wr32(PDC_REG(0x1575 + 8), 0x10108);
	wr32(PDC_REG(0x1576 + 8), a_gfx);
	wr32(PDC_REG(0x1577 + 8), 0);

	wr32(PDC_REG(0x15d7), 7);
	wr32(PDC_REG(0x15d8), 0);
	wr32(PDC_REG(0x15d6), 0);
	wr32(PDC_REG(0x15d9), 0x10108);
	wr32(PDC_REG(0x15da), a_mx);
	wr32(PDC_REG(0x15db), 2);
	wr32(PDC_REG(0x15d9 + 4), 0x10108);
	wr32(PDC_REG(0x15da + 4), a_cx);
	wr32(PDC_REG(0x15db + 4), 2);
	wr32(PDC_REG(0x15d9 + 8), 0x10108);
	wr32(PDC_REG(0x15da + 8), a_gfx);
	wr32(PDC_REG(0x15db + 8), 3);

	wr32(PDC_REG(0x1148), 0);
	wr32(PDC_REG(0x1140), 0x80000001);
	__asm__ volatile("dsb sy" ::: "memory");
}

/* a6xx_hfi_init: table header, 3 queue headers; legacy queue ids 0, 4, 5. */
#define QHDR(q)		(GMEM_HFI + 24 + 48 * (q))
#define QDATA(q)	(GMEM_HFI + 0x1000 * ((q) + 1))
#define QSIZE		1024		/* dwords */

static void hfi_table(void)
{
	static const uint32_t ids[3] = { 0, 4, 5 };
	uintptr_t t = GMEM_HFI;
	wr32(t + 0, 0);
	wr32(t + 4, 24 + 3 * 48);
	wr32(t + 8, 6);
	wr32(t + 12, 12);
	wr32(t + 16, 3);
	wr32(t + 20, 3);
	for (int q = 0; q < 3; q++) {
		uintptr_t h = QHDR(q);
		wr32(h + 0, 1);					/* status */
		wr32(h + 4, VA_HFI + 0x1000 * (q + 1));		/* iova */
		wr32(h + 8, (10u << 8) | ids[q]);		/* type */
		wr32(h + 12, QSIZE);
		wr32(h + 24, 1);				/* rx watermark */
		wr32(h + 28, 1);				/* tx watermark */
		wr32(h + 32, 1);				/* rx request */
	}
}

static uint32_t hfi_seq;

/* a6xx_hfi_send_msg for the legacy GMU: no 4-dword padding either way. */
static int hfi_send(uint32_t id, uint32_t *msg, uint32_t dwords, uint32_t *resp)
{
	uint32_t seq = ++hfi_seq;
	msg[0] = (seq << 20) | (dwords << 8) | id;
	uintptr_t h = QHDR(0);
	uint32_t w = rd32(h + 44);
	for (uint32_t i = 0; i < dwords; i++) {
		wr32(QDATA(0) + 4 * w, msg[i]);
		w = (w + 1) % QSIZE;
	}
	__asm__ volatile("dsb sy" ::: "memory");
	wr32(h + 44, w);
	wr32(GMU_REG(GMU_H2G_SET), 1);

	for (int t = 0; t < 1000; t++) {
		if (rd32(GMU_REG(GMU_G2H_INFO)) & 1) {
			wr32(GMU_REG(GMU_G2H_CLR), 1);
			uintptr_t rh = QHDR(1);
			while (rd32(rh + 40) != rd32(rh + 44)) {
				uint32_t r = rd32(rh + 40), hdr = rd32(QDATA(1) + 4 * r);
				uint32_t n = (hdr >> 8) & 0xff, buf[24] = { 0 };
				for (uint32_t i = 0; i < n; i++) {
					if (i < 24)
						buf[i] = rd32(QDATA(1) + 4 * r);
					r = (r + 1) % QSIZE;
				}
				wr32(rh + 40, r);
				if ((hdr & 0xff) == 100) {	/* F2H error */
					con_hex2("HFI ERR", "code=", buf[1], "p=", buf[2]);
					continue;
				}
				if (((buf[1] >> 20) & 0xfff) == seq) {
					if (resp)
						*resp = buf[3];
					return (int)buf[2];	/* error, 0 = ok */
				}
			}
		}
		delay_ms(1);
	}
	return -1000;
}

/* cmd-db aux data (an array of u16 levels) for an id such as "gfx.lvl". */
static int cmddb_aux(const char *id, uintptr_t *aux, uint32_t *len)
{
	uintptr_t db = rd32(CMD_DB_PTR);
	if (rd32(db + 4) != 0x0c0330db)
		return -1;
	uintptr_t data = db + 4 + 4 + 8 * 16 + 4 + 4;
	for (int r = 0; r < 8; r++) {
		uintptr_t rh = db + 8 + 16 * r;
		uint32_t w0 = rd32(rh), w1 = rd32(rh + 4);
		uint32_t hoff = w0 >> 16, doff = w1 & 0xffff, cnt = w1 >> 16;
		for (uint32_t e = 0; e < cnt; e++) {
			uintptr_t ent = data + hoff + 24 * e;
			int match = 1;
			for (int i = 0; i < 8; i++) {
				char c = (char)(rd32(ent + (i & ~3)) >> (8 * (i & 3)));
				if (c != id[i]) {
					match = 0;
					break;
				}
				if (!id[i])
					break;
			}
			if (!match)
				continue;
			uint32_t w5 = rd32(ent + 20);
			*len = (w5 & 0xffff) / 2;
			*aux = data + doff + (w5 >> 16);
			return 0;
		}
	}
	return -1;
}

/* cmd-db resource address (e.g. a BCM such as "MC0"), 0 if absent. */
static uint32_t cmddb_addr(const char *id)
{
	uintptr_t db = rd32(CMD_DB_PTR);
	if (rd32(db + 4) != 0x0c0330db)
		return 0;
	uintptr_t data = db + 4 + 4 + 8 * 16 + 4 + 4;
	for (int r = 0; r < 8; r++) {
		uintptr_t rh = db + 8 + 16 * r;
		uint32_t w0 = rd32(rh), w1 = rd32(rh + 4);
		uint32_t hoff = w0 >> 16, cnt = w1 >> 16;
		for (uint32_t e = 0; e < cnt; e++) {
			uintptr_t ent = data + hoff + 24 * e;
			int match = 1;
			for (int i = 0; i < 8; i++) {
				char c = (char)(rd32(ent + (i & ~3)) >> (8 * (i & 3)));
				if (c != id[i]) {
					match = 0;
					break;
				}
				if (!id[i])
					break;
			}
			if (match)
				return rd32(ent + 16);
		}
	}
	return 0;
}

/*
 * One ACTIVE (AMC) request on the apps RSC, DRV2, after the kernel's
 * sweet_rpmh.c (patch 0062): TCS bank at 0x18220d00, stride 0x2a0, command
 * stride 0x14. Returns 0 when every command reports issued + completed.
 */
#define RH_TCS		0x18220d00UL
#define RH_STRIDE	0x2a0u
#define RH_CSTRIDE	0x14u

static int rpmh_send(const uint32_t *addr, const uint32_t *data, unsigned n)
{
	int t = -1;
	for (unsigned i = 0; i < 2 && t < 0; i++) {
		uintptr_t b = RH_TCS + i * RH_STRIDE;
		if (rd32(b + 0x18) && rd32(b + 0x14) == 0 && rd32(b + 0x1c) == 0)
			t = (int)i;
	}
	if (t < 0)
		return -1;
	uintptr_t b = RH_TCS + (unsigned)t * RH_STRIDE;
	uint32_t en = rd32(RH_TCS + 0x00);
	wr32(RH_TCS + 0x00, en & ~(1u << t));
	for (unsigned c = 0; c < n; c++) {
		uintptr_t cmd = b + c * RH_CSTRIDE;
		wr32(cmd + 0x30, 8 | (1u << 8) | (1u << 16));	/* write, response, len 8 */
		wr32(cmd + 0x34, addr[c]);
		wr32(cmd + 0x38, data[c]);
	}
	uint32_t mask = (1u << n) - 1;
	wr32(b + 0x10, mask);			/* wait for completion */
	wr32(b + 0x1c, mask);			/* enable commands */
	wr32(b + 0x14, 0);
	wr32(b + 0x14, 1u << 16);		/* AMC */
	__asm__ volatile("dsb sy" ::: "memory");
	wr32(b + 0x14, (1u << 16) | (1u << 24));	/* trigger */
	int done = 0;
	for (int i = 0; i < 100 && !done; i++) {
		done = rd32(b + 0x18) != 0;
		for (unsigned c = 0; c < n && done; c++)
			done = (rd32(b + 0x3c + c * RH_CSTRIDE) & 0x10100) == 0x10100;
		if (!done)
			delay_ms(1);
	}
	wr32(b + 0x14, 1u << 16);
	wr32(b + 0x14, 0);
	wr32(b + 0x1c, 0);
	wr32(b + 0x10, 0);
	wr32(RH_TCS + 0x08, 1u << t);
	wr32(RH_TCS + 0x00, en);
	return done ? t : -2;
}

/*
 * GPU -> DDR bandwidth (what Linux's dev_pm_opp_set_opp does before the GMU
 * boots). Run 2e: the system reset as soon as the GMU first read DDR (HFI
 * init) and gcc gpu_memnoc_gfx stays halted. Run 2e used the Adreno 619's
 * lowest non-zero level (a619_build_bw_table: MC0 0x30c, SH0 0xdb, ACV 0x8);
 * with it a CoreAnimation submission took 60-80 ms at 430 MHz (run 0094d,
 * RBBM busy, ring consumed): the GPU starved for DDR bandwidth. Linux votes
 * per OPP through the interconnect; here one high vote (the BCM takes the
 * highest level it has for anything above it), ACV unchanged.
 */
static int ddr_vote(void)
{
	/* VOTE_Y is bits 13:0 (Linux tcs.h): 0x4000 was peak 0, average 1 */
	static const uint32_t y[3] = { 0x3fff, 0x2000, 0x8 };
	uint32_t addr[3], data[3];
	addr[0] = cmddb_addr("MC0");	/* no pointer table: no absolute relocations */
	addr[1] = cmddb_addr("SH0");
	addr[2] = cmddb_addr("ACV");
	for (int i = 0; i < 3; i++)
		data[i] = (1u << 30) | (1u << 29) | y[i];	/* commit, valid, vote_y */
	con_hex2("BCM", "mc0=", addr[0], "sh0=", addr[1]);
	if (!addr[0] || !addr[1] || !addr[2])
		return -1;
	int rc = rpmh_send(addr, data, 3);
	con_hex2("BCM", "acv=", addr[2], "vote tcs=", (uint32_t)rc);
	con_hex2("BCM", "memnoc=", rd32(GCC + GCC_GPU_MEMNOC_GFX), "dvm=", rd32(GCC + GCC_GPU_SNOC_DVM_GFX));
	return rc < 0 ? -1 : 0;
}

static uint32_t aux16(uintptr_t aux, uint32_t i)
{
	return (rd32(aux + 2 * (i & ~1u)) >> (16 * (i & 1))) & 0xffff;
}

/* a6xx_gmu_rpmh_arc_votes_init */
static int arc_votes(uint32_t *votes, const uint32_t *lvl, int n, const char *pri_id, const char *sec_id)
{
	uintptr_t pri, sec;
	uint32_t plen, slen;
	if (cmddb_aux(pri_id, &pri, &plen) || cmddb_aux(sec_id, &sec, &slen))
		return -1;
	for (int i = 0; i < n; i++) {
		uint32_t pindex = 0, sindex = 0, j;
		for (j = 0; j < plen; j++)
			if (aux16(pri, j) >= lvl[i]) {
				pindex = j;
				break;
			}
		if (j == plen)
			return -2;
		for (j = 0; j < slen; j++) {
			if (aux16(sec, j) >= lvl[i]) {
				sindex = j;
				break;
			} else if (aux16(sec, j)) {
				sindex = j;
			}
		}
		votes[i] = (aux16(pri, pindex) << 16) | (sindex << 8) | pindex;
	}
	return 0;
}

/* RPMh regulator levels (dt-bindings qcom-rpmpd.h). */
#define LVL_MIN_SVS	48
#define LVL_LOW_SVS	64
#define LVL_SVS		128

#define LVL_SVS_L1	192
#define LVL_NOM		256
#define LVL_NOM_L1	320
#define LVL_TURBO	384

/*
 * sweet's GPU OPPs up to 650 MHz (bin 0 goes to 825), "off" first, like Linux.
 * Corners one step on the safe side. CoreAnimation's passes over 1125x2436
 * targets are bandwidth- and clock-bound (7-12 ms a submission at 430 MHz).
 */
#define NGPU	7
static const uint32_t gpu_khz[NGPU] = { 0, 180000, 267000, 355000, 430000, 565000, 650000 };
static const uint32_t gpu_lvl[NGPU] = { 0, LVL_LOW_SVS, LVL_SVS, LVL_SVS_L1, LVL_NOM, LVL_NOM_L1, LVL_TURBO };
static const uint32_t gmu_khz[2] = { 0, 200000 };
static const uint32_t gmu_lvl[2] = { 0, LVL_MIN_SVS };

static int oob(int set_bit, int ack_bit)
{
	wr32(GMU_REG(GMU_H2G_SET), 1u << set_bit);
	int rc = wait_bit(GMU_REG(GMU_G2H_INFO), 1u << ack_bit, 1, 100);
	wr32(GMU_REG(GMU_G2H_CLR), 1u << ack_bit);
	return rc;
}

/* ---- stage 3: zap shader through TrustZone PAS (qcom_scm + mdt_loader) ---- */

#define PAS_GPU		13
#define ZAP_REGION	0x97715000UL	/* sweet DT: gpu_region (pil_gpu_mem), 8K */
#define ZAP_SIZE	0x2000UL
#define ZAP_META	(GMEM + 0xa0000)	/* metadata buffer TZ reads */
#define SCM_PIL(cmd)	(0x42000000UL | (2u << 8) | (cmd))	/* SMC64 std call, SIP, svc PIL */

extern const uint8_t zap_mdt[], zap_mdt_end[], zap_b02[], zap_b02_end[];
extern const uint8_t sqe_fw[], sqe_fw_end[];

static int64_t scm(uint32_t cmd, uint64_t arginfo, uint64_t a, uint64_t b, uint64_t c, uint64_t *r1)
{
	register uint64_t x0 __asm__("x0") = SCM_PIL(cmd);
	register uint64_t x1 __asm__("x1") = arginfo;
	register uint64_t x2 __asm__("x2") = a;
	register uint64_t x3 __asm__("x3") = b;
	register uint64_t x4 __asm__("x4") = c;
	register uint64_t x5 __asm__("x5") = 0;
	register uint64_t x6 __asm__("x6") = 0;
	__asm__ volatile("smc #0"
			 : "+r"(x0), "+r"(x1), "+r"(x2), "+r"(x3), "+r"(x4), "+r"(x5), "+r"(x6)
			 :
			 : "x7", "x8", "x9", "x10", "x11", "x12", "x13", "x14", "x15", "x16", "x17",
			   "memory");
	if (r1)
		*r1 = x1;
	return (int64_t)x0;
}

static void copy_in(uintptr_t dst, const uint8_t *src, uint32_t len)
{
	for (uint32_t o = 0; o < len; o += 4) {
		uint32_t w = 0;
		for (uint32_t i = 0; i < 4 && o + i < len; i++)
			w |= (uint32_t)src[o + i] << (8 * i);
		wr32(dst + o, w);
	}
}

static int zap_load(void)
{
	uint64_t r1 = 0;
	int64_t rc = scm(7, 1, PAS_GPU, 0, 0, &r1);		/* PAS_IS_SUPPORTED */
	con_hex2("ZAP", "supported rc=", (uint32_t)rc, "r1=", (uint32_t)r1);

	uint32_t mlen = (uint32_t)(zap_mdt_end - zap_mdt);
	copy_in(ZAP_META, zap_mdt, mlen);
	__asm__ volatile("dsb sy" ::: "memory");
	stage("zap init image");
	rc = scm(1, 2 | (2u << 6), PAS_GPU, ZAP_META, 0, &r1);	/* INIT_IMAGE */
	con_hex2("ZAP", "init rc=", (uint32_t)rc, "r1=", (uint32_t)r1);
	if (rc || r1)
		return -1;

	stage("zap mem setup");
	rc = scm(2, 3, PAS_GPU, ZAP_REGION, ZAP_SIZE, &r1);	/* MEM_SETUP */
	con_hex2("ZAP", "mem rc=", (uint32_t)rc, "r1=", (uint32_t)r1);
	if (rc || r1)
		return -2;

	/* Relocatable: the one LOAD segment (paddr 0x5000, the lowest) at the region base. */
	for (uint32_t o = 0; o < ZAP_SIZE; o += 4)
		wr32(ZAP_REGION + o, 0);
	copy_in(ZAP_REGION, zap_b02, (uint32_t)(zap_b02_end - zap_b02));
	__asm__ volatile("dsb sy" ::: "memory");

	stage("zap auth and reset");
	rc = scm(5, 1, PAS_GPU, 0, 0, &r1);			/* AUTH_AND_RESET */
	con_hex2("ZAP", "auth rc=", (uint32_t)rc, "r1=", (uint32_t)r1);
	return rc || r1 ? -3 : 0;
}

/* ---- stage 3: SQE, ringbuffer, first commands (a6xx hw_init subset, A618) ---- */

#define GREG(o)		(GPU + 4UL * (o))
#define GPU_SID		0	/* sweet DT: kgsl user context iommus <&kgsl_smmu 0>, exact */
#define GT_L1		(GMEM + 0x200000)
#define GT_L2		(GMEM + 0x201000)
#define GT_L3		(GMEM + 0x202000)	/* VA 0x10000000-0x101fffff */
#define G_SQE		(GMEM + 0x300000)
#define G_RING		(GMEM + 0x310000)
#define G_TARGET	(GMEM + 0x320000)
#define GVA_SQE		0x10000000u
#define GVA_RING	0x10010000u
#define GVA_TARGET	0x10020000u
#define RING_DW		(0x8000 / 4)

static uint32_t wptr;

static uint32_t pm4_parity(uint32_t v)
{
	return (0x9669 >> (0xf & (v ^ (v >> 4) ^ (v >> 8) ^ (v >> 12) ^ (v >> 16) ^
				   (v >> 20) ^ (v >> 24) ^ (v >> 28)))) & 1;
}

static void ring(uint32_t v)
{
	wr32(G_RING + 4 * wptr, v);
	wptr = (wptr + 1) % RING_DW;
}

static void pkt7(uint32_t op, uint32_t cnt)
{
	ring(0x70000000 | cnt | (pm4_parity(cnt) << 15) | ((op & 0x7f) << 16) | (pm4_parity(op) << 23));
}

static int flush_wait(const char *what)
{
	__asm__ volatile("dsb sy" ::: "memory");
	wr32(GREG(0x807), wptr);			/* CP_RB_WPTR */
	int i;
	for (i = 0; i < 1000; i++) {
		if (rd32(GREG(0x806)) == wptr && !(rd32(GREG(0x210)) & (1u << 23)))
			break;
		delay_ms(1);
	}
	con_hex2(what, i < 1000 ? "idle rptr=" : "TIMEOUT rptr=", rd32(GREG(0x806)), "status=", rd32(GREG(0x210)));
	if (i >= 1000)
		con_hex2("  cp", "int=", rd32(GREG(0x201)), "hwfault=", rd32(GREG(0x821)));
	return i < 1000 ? 0 : -1;
}

/* AArch64 4K pages, AP=01 (unprivileged), NC: as Linux maps GPU buffers. */
static void map_user(uintptr_t l3, uint32_t va, uintptr_t pa, uint32_t size)
{
	for (uint32_t o = 0; o < size; o += 0x1000) {
		uint32_t idx = ((va + o) >> 12) & 0x1ff;
		wr64(l3 + 8 * idx, (pa + o) | (1u << 10) | (3u << 8) | (1u << 6) | 3u);
	}
}

#define GVA_FB		0x20000000u
#define FB_STRIDE_B	(FB_W * 4)
#define BAND_Y		1500
#define BAND_H		500

/*
 * Visible proof: map the panel framebuffer into the GPU and let the GPU paint
 * a band (one gradient row by CP_MEM_WRITE, then CP_MEMCPY down the rows).
 * The CPU never touches those framebuffer pixels.
 */
static void gpu_paint(uintptr_t c)
{
	for (int i = 0; i < 6; i++)	/* 12 MB as 2 MB blocks, AP=01, NC */
		wr64(GT_L2 + 8 * (((GVA_FB >> 21) & 0x1ff) + i),
		     (FB_BASE + 0x200000UL * i) | (1u << 10) | (3u << 8) | (1u << 6) | 1u);
	wr32(c + 0x618, 0);		/* CB TLBIALL */
	wr32(c + 0x7f0, 0);		/* CB TLBSYNC */
	wait_bit(c + 0x7f4, 1, 0, 10);

	uint32_t row = GVA_FB + BAND_Y * FB_STRIDE_B;
	pkt7(0x3d, 2 + FB_W);		/* CP_MEM_WRITE one row */
	ring(row);
	ring(0);
	for (uint32_t x = 0; x < FB_W; x++) {
		uint32_t r = x * 255 / (FB_W - 1), b = 255 - r, g = (x / 60) % 2 ? 200 : 40;
		ring(0xff000000 | (r << 16) | (g << 8) | b);
	}
	pkt7(0x26, 0);
	flush_wait("PAINT1");
	for (uint32_t y = 1; y < BAND_H; y++) {
		pkt7(0x75, 5);		/* CP_MEMCPY dwords, src, dst */
		ring(FB_W);
		ring(row);
		ring(0);
		ring(row + y * FB_STRIDE_B);
		ring(0);
		if ((y % 100) == 0)
			flush_wait("PAINT");
	}
	pkt7(0x26, 0);
	flush_wait("PAINTED");
	con_hex2("FB", "band word=", rd32(FB_BASE + (BAND_Y + BAND_H / 2) * FB_STRIDE_B + 540 * 4), 0, 0);
}

static void gpu_run(int smr, int gmu_cb)
{
	int cb = gmu_cb + 1;
	stage("gpu smmu (sid 0)");
	zero32(GT_L1, 0x3000);
	zero32(G_SQE, 0x21000);
	wr64(GT_L1 + 0, GT_L2 | 3);
	wr64(GT_L2 + 8 * ((GVA_SQE >> 21) & 0x1ff), GT_L3 | 3);
	map_user(GT_L3, GVA_SQE, G_SQE, 0x10000);
	map_user(GT_L3, GVA_RING, G_RING, 0x8000);
	map_user(GT_L3, GVA_TARGET, G_TARGET, 0x1000);
	wr32(G_TARGET, 0x11111111);

	uintptr_t c = SMMU_CB(cb);
	wr32(c + CB_SCTLR, 0);
	wr32(CBA2R(cb), 1);
	wr32(CBAR(cb), (1u << 16) | (0xfu << 12) | (3u << 8) | (uint32_t)(cb + 1));
	wr32(c + CB_TCR2, 2);
	wr64(c + CB_TTBR0, GT_L1);
	wr32(c + CB_TCR, 32 | (1u << 8) | (1u << 10) | (3u << 12) | (1u << 23));
	wr32(c + CB_MAIR0, 0x0000ff44);
	wr32(c + CB_FSR, 0xffffffff);
	wr32(c + CB_SCTLR, 1 | 2 | 4 | 0x20 | 0x40);
	wr32(SMMU + 0x68, 0);
	wr32(SMMU + 0x70, 0);
	wait_bit(SMMU + 0x74, 1, 0, 10);
	wr32(S2CR(smr), (uint32_t)cb);
	wr32(SMR(smr), (1u << 31) | GPU_SID);
	con_hex2("GPU SMMU", "smr=", rd32(SMR(smr)), "cb=", (uint32_t)cb);
	if (!(rd32(SMR(smr)) >> 31))
		return;

	stage("gpu hw init");
	wr32(GREG(0x3c45), 0);			/* GBIF_HALT */
	(void)rd32(GREG(0x3c45));
	wr32(GREG(0x16), 0);			/* RBBM_GBIF_HALT */
	(void)rd32(GREG(0x16));
	wr32(GREG(0xf803), 0);			/* RBBM_SECVID_TSB_CNTL */
	wr32(GREG(0xf800), 0);
	wr32(GREG(0xf801), 0);
	wr32(GREG(0xf802), 0);
	static const uint16_t addr_mode[] = { 0x0842, 0x0c01, 0x8601, 0x8e05, 0x9e01, 0xbe05,
					      0xa601, 0x9601, 0x0e00, 0xae01, 0xb601, 0xf810 };
	for (unsigned i = 0; i < sizeof(addr_mode) / sizeof(addr_mode[0]); i++)
		wr32(GREG(addr_mode[i]), 1);
	wr32(GREG(0x10), 3);			/* RBBM_VBIF_CLIENT_QOS_CNTL (A618: not a640 family) */
	wr32(GREG(0x50b), 0xffffffff);		/* RBBM_PERFCTR_GPU_BUSY_MASKED */
	uint64_t trap = 0x1fffffffff000ull;
	wr32(GREG(0xe05), (uint32_t)(trap + 0xfc0));
	wr32(GREG(0xe06), (uint32_t)((trap + 0xfc0) >> 32));
	wr32(GREG(0xe09), (uint32_t)trap);
	wr32(GREG(0xe0a), (uint32_t)(trap >> 32));
	wr32(GREG(0xe07), (uint32_t)trap);
	wr32(GREG(0xe08), (uint32_t)(trap >> 32));
	wr32(GREG(0xe0b), 0x100000);		/* GMEM range 1M .. 1M + 512K - 1 */
	wr32(GREG(0xe0c), 0);
	wr32(GREG(0xe0d), 0x17ffff);
	wr32(GREG(0xe0e), 0);
	wr32(GREG(0xe18), 0x804);		/* UCHE_FILTER_CNTL */
	wr32(GREG(0xe17), 0x4);			/* UCHE_CACHE_WAYS */
	wr32(GREG(0x8c2), 0x010000c0);		/* CP_ROQ_THRESHOLDS_2 */
	wr32(GREG(0x8c1), 0x8040362c);		/* CP_ROQ_THRESHOLDS_1 */
	wr32(GREG(0x8c3), 128);			/* CP_MEM_POOL_SIZE */
	wr32(GREG(0x98d), 1);			/* CP_AHB_CNTL */
	wr32(GREG(0x500), 1);			/* RBBM_PERFCTR_CNTL */
	wr32(GREG(0x1f), (1u << 30) | 0x1fffff);	/* RBBM_INTERFACE_HANG_INT_CNTL */
	wr32(GREG(0xe19), (1u << 7) | 1);	/* UCHE_CLIENT_PF */

	/* SQE microcode: the file minus its first dword. */
	uint32_t sqe_len = (uint32_t)(sqe_fw_end - sqe_fw) - 4;
	copy_in(G_SQE, sqe_fw + 4, sqe_len);
	wr32(GREG(0x830), GVA_SQE);		/* CP_SQE_INSTR_BASE */
	wr32(GREG(0x831), 0);
	wr32(GREG(0x800), GVA_RING);		/* CP_RB_BASE */
	wr32(GREG(0x801), 0);
	wr32(GREG(0x802), 0x0800020c);		/* 32K ring, 32-byte blocks, no rptr update */
	wptr = 0;
	stage("cp start");
	wr32(GREG(0x808), 1);			/* CP_SQE_CNTL */
	con_hex2("CP", "started status=", rd32(GREG(0x210)), "sqe bytes=", sqe_len);

	pkt7(0x48, 8);				/* CP_ME_INIT */
	ring(0x2f);
	ring(3);
	ring(0x20000000);
	for (int i = 0; i < 5; i++)
		ring(0);
	if (flush_wait("ME_INIT"))
		goto out;

	stage("zap shader");
	int zr = zap_load();
	con_hex2("ZAP", "result=", (uint32_t)zr, 0, 0);

	stage("secure mode off");
	pkt7(0x66, 1);				/* CP_SET_SECURE_MODE 0 */
	ring(0);
	if (flush_wait("SECURE0"))
		goto out;

	stage("cp mem write");
	pkt7(0x3d, 3);				/* CP_MEM_WRITE */
	ring(GVA_TARGET);
	ring(0);
	ring(0xcafef00d);
	pkt7(0x26, 0);				/* CP_WAIT_FOR_IDLE */
	flush_wait("MEMWRITE");
	for (int i = 0; i < 100 && rd32(G_TARGET) != 0xcafef00d; i++)
		delay_ms(1);
	con_hex2("TARGET", "mem=", rd32(G_TARGET), 0, 0);
	if (rd32(G_TARGET) == 0xcafef00d) {
		con_str("GPU", "*** GPU EXECUTED OUR COMMANDS ***");
#ifndef SHIM_GPUBOOT	/* booting XNU next: leave the ring clean for sweet_gpu.c */
		stage("gpu paint");
		gpu_paint(c);
#endif
	}
out:
	con_hex2("GPU CB", "fsr=", rd32(c + CB_FSR), "far=", rd32(c + CB_FAR));
}

static void gmu_boot(void)
{
	static uint32_t msg[256];
	uint32_t gx[NGPU], cx[2];

	/*
	 * Runs 2b/2c hung on the first SMMU read after the cmd-db walk; run 1
	 * read the SMMU right after the GMU/TCM accesses. Same order as run 1
	 * now, with each bus touched in turn so a hang names its block.
	 */
	stage("gdsc + gmu read");
	con_hex2("CHECK", "cx gdsc=", rd32(GPUCC + GPUCC_CX_GDSCR), "gmu rpmh=", rd32(GMU_REG(GMU_RPMH_STATE)));
	stage("smmu idr read");
	con_hex2("CHECK", "smmu idr0=", rd32(SMMU + 0x20), "idr1=", rd32(SMMU + 0x24));

	stage("smmu setup");
	int cb = smmu_setup();
	if (cb < 0)
		return;
	uintptr_t c = SMMU_CB(cb);

	stage("arc votes (cmd-db)");
	int rv = arc_votes(gx, gpu_lvl, NGPU, "gfx.lvl", "mx.lvl");
	if (!rv)
		rv = arc_votes(cx, gmu_lvl, 2, "cx.lvl", "mx.lvl");
	con_hex2("VOTES", "gx2=", rv ? (uint32_t)rv : gx[2], "cx1=", rv ? 0 : cx[1]);
	con_hex2("CHECK", "cx gdsc=", rd32(GPUCC + GPUCC_CX_GDSCR), "smmu cr0=", rd32(SMMU));
	if (rv)
		return;

	stage("ddr bandwidth vote (rpmh bcm)");
	if (ddr_vote())
		return;

	stage("rsc/pdc init");
	rpmh_init();
	hfi_table();

	stage("rsc wake");
	wr32(GMU_REG(GMU_GENERAL_7), 1);
	wr32(GMU_REG(GMU_RSCC_REQ), 1u << 1);
	int rc = wait_bit(GMU_REG(GMU_RSCC_ACK), 1u << 1, 1, 200);
	int rc2 = wait_bit(RSCC_REG(0x0101), 0xffffffff, 0, 10);
	wr32(GMU_REG(GMU_RSCC_REQ), 0);
	con_hex2("RSC", rc ? "ACK TIMEOUT=" : "ack=", rd32(GMU_REG(GMU_RSCC_ACK)),
		 rc2 ? "SEQ BUSY=" : "pdc=", rc2 ? rd32(RSCC_REG(0x0101)) : rd32(PDC_REG(0x1140)));
	con_hex2("RSC", "status0=", rd32(RSCC_REG(0x0004)), "seq busy=", rd32(RSCC_REG(0x0101)));
	con_hex2("RSC TCS", "0=", rd32(RSCC_REG(0x0346)), "1=", rd32(RSCC_REG(0x03ee)));
	con_hex2("RSC TCS", "2=", rd32(RSCC_REG(0x0496)), "3=", rd32(RSCC_REG(0x053e)));

	stage("fw load (itcm)");
	uint32_t fwlen = (uint32_t)(gmu_fw_end - gmu_fw);
	if (fwlen > 0x8000)
		return;
	for (uint32_t o = 0; o < fwlen; o += 4) {
		uint32_t w;
		__builtin_memcpy(&w, gmu_fw + o, 4);
		wr32(GMU_REG(GMU_ITCM) + o, w);
	}
	uint32_t w0;
	__builtin_memcpy(&w0, gmu_fw, 4);
	con_hex2("GMU FW", "bytes=", fwlen, "itcm0 ok=", rd32(GMU_REG(GMU_ITCM)) == w0);

	wr32(GMU_REG(GMU_INIT_RESULT), 0);
	wr32(GMU_REG(GMU_BOOT_CFG), 2);
	wr32(GMU_REG(GMU_QTBL_ADDR), VA_HFI);
	wr32(GMU_REG(GMU_QTBL_INFO), 1);
	wr32(GMU_REG(GMU_FENCE0), (1u << 31) | (0xau << 18) | 0xa0);
	wr32(GMU_REG(GMU_CM3_CFG), 0x4052);
	wr32(GMU_REG(GMU_SFR_ADDR), 0x06018000);	/* GMU-style chip id of 618 (0x06010800) */
	wr32(GMU_REG(GMU_CP_MSG), VA_LOG | (BUF_SIZE / 0x1000 - 1));
	/* a6xx_gmu_power_config: idle level ACTIVE, RPMh interface + votes on */
	wr32(GMU_REG(GMU_SYS_BUS), 1);
	wr32(GMU_REG(GMU_ICACHE_CFG), 1);
	wr32(GMU_REG(GMU_DCACHE_CFG), 1);
	wr32(GMU_REG(GMU_PWRCOL_CTRL), 0x9c40400);
	wr32(GMU_REG(GMU_RPMH_CTRL), rd32(GMU_REG(GMU_RPMH_CTRL)) |
	     1 | (1u << 4) | (1u << 8) | (1u << 9) | (1u << 10) | (1u << 11));

	stage("cm3 start");
	uint32_t v = rd32(GMU_REG(GMU_DTCM) + 0xff8 * 4);
	uint32_t mask = v <= 0x20010004 ? 0xffffffff : 0x1ff;
	uint32_t want = v <= 0x20010004 ? 0xbabeface : 0x100;
	wr32(GMU_REG(GMU_SYSRESET), 1);
	wr32(GMU_REG(GMU_CP_RESP), 0);
	wr32(GMU_REG(GMU_SYSRESET), 0);
	uint32_t r = 0;
	int ok = 0;
	for (int i = 0; i < 1000; i++) {
		r = rd32(GMU_REG(GMU_INIT_RESULT));
		if ((r & mask) == want) {
			ok = 1;
			break;
		}
		delay_ms(1);
	}
	con_hex2(ok ? "GMU UP" : "GMU DEAD", "init=", r, "fsr=", rd32(c + CB_FSR));
	if (!ok) {
		con_hex2("  far", "hi=", rd32(c + CB_FAR + 4), "lo=", rd32(c + CB_FAR));
		con_hex2("  log", "w0=", rd32(GMEM_LOG), "w1=", rd32(GMEM_LOG + 4));
		return;
	}
	/* Run 2d filled the screen here: start a new page for the rest. */
	delay_ms(1000);
	con_clear(RED);
	con_hex2("GMU UP", "init=", r, "cb fsr=", rd32(c + CB_FSR));
	con_hex2("  (rsc)", "ack=", rd32(GMU_REG(GMU_RSCC_ACK)), "seq busy=", rd32(RSCC_REG(0x0101)));

	stage("gfx rail on (oob slumber)");
	wr32(GMU_REG(GMU_BOOT_SLUMBER_OPT), 0);
	wr32(GMU_REG(GMU_GX_VOTE_IDX), gx[NGPU - 1] & 0xff);
	wr32(GMU_REG(GMU_MX_VOTE_IDX), (gx[NGPU - 1] >> 8) & 0xff);
	rc = oob(22, 30);
	con_hex2("RAIL", rc ? "OOB TIMEOUT info=" : "ack info=", rd32(GMU_REG(GMU_G2H_INFO)),
		 "rpmh=", rd32(GMU_REG(GMU_RPMH_STATE)));

	stage("sptprac on");
	wr32(GMU_REG(GMU_SPTPRAC_PWR_CTRL), 0x778000);
	for (int i = 0; i < 100 && (rd32(GMU_REG(GMU_SPTPRAC_STATUS)) & 0x38) != 0x28; i++)
		delay_ms(1);
	con_hex2("SPTPRAC", "status=", rd32(GMU_REG(GMU_SPTPRAC_STATUS)), "gx gdsc=",
		 rd32(GPUCC + GPUCC_GX_GDSCR));

	con_hex2("GMU LOG", "w0=", rd32(GMEM_LOG), "w1=", rd32(GMEM_LOG + 4));
	con_hex2("CB", "fsr=", rd32(c + CB_FSR), "far=", rd32(c + CB_FAR));
	con_hex2("SMMU G", "gfsr=", rd32(SMMU + 0x48), "gfsynr0=", rd32(SMMU + 0x50));
	con_hex2("SMMU G", "gfsynr1=", rd32(SMMU + 0x54), "gfsynr2=", rd32(SMMU + 0x58));
	con_hex2("HFI", "ctrl status=", rd32(GMU_REG(GMU_HFI_STATUS)), "g2h=", rd32(GMU_REG(GMU_G2H_INFO)));
	stage("hfi start");
	wr32(GMU_REG(GMU_HFI_INIT), 1);
	rc = wait_bit(GMU_REG(GMU_HFI_STATUS), 1, 1, 10);
	con_hex2("HFI", rc ? "INIT TIMEOUT=" : "status=", rd32(GMU_REG(GMU_HFI_STATUS)), 0, 0);
	if (rc)
		return;

	stage("hfi v1 messages");
	for (int i = 0; i < 256; i++)
		msg[i] = 0;
	msg[1] = 0;			/* seg_id */
	msg[2] = VA_DEBUG;
	msg[3] = BUF_SIZE;
	msg[4] = 0;			/* boot_state: cold */
	int e_init = hfi_send(0, msg, 5, 0);
	uint32_t ver = 0;
	msg[1] = (1u << 28) | (1u << 19) | (1u << 17);
	int e_ver = hfi_send(1, msg, 2, &ver);
	con_hex2("HFI", "init=", (uint32_t)e_init, "fwver err=", (uint32_t)e_ver);

	/* perf table v1: header, num gpu, num gmu, gx[16] {vote, freq}, cx[4] {vote, freq} */
	for (int i = 0; i < 256; i++)
		msg[i] = 0;
	msg[1] = NGPU;
	msg[2] = 2;
	/*
	 * Frequencies in kHz (Linux: gpu_freqs[i] / 1000, freqs in Hz). They were
	 * sent in MHz: the GMU then programmed gpu_cc_pll0 for "430 kHz" (L 0,
	 * PLL unlocked, probe 5) and the GPU crawled at every DCVS level.
	 */
	for (int i = 0; i < NGPU; i++) {
		msg[3 + 2 * i] = gx[i];
		msg[4 + 2 * i] = gpu_khz[i];
	}
	for (int i = 0; i < 2; i++) {
		msg[3 + 32 + 2 * i] = cx[i];
		msg[4 + 32 + 2 * i] = gmu_khz[i];
	}
	int e_perf = hfi_send(4, msg, 3 + 32 + 8, 0);

	/* bw table, a618_build_bw_table */
	for (int i = 0; i < 256; i++)
		msg[i] = 0;
	msg[1] = 1;			/* bw levels */
	msg[2] = 1;			/* cnoc cmds */
	msg[3] = 3;			/* ddr cmds */
	msg[4] = 1;			/* cnoc wait */
	msg[5] = 1;			/* ddr wait */
	msg[6] = 0x5007c;		/* cnoc addrs [6] at 6..11 */
	msg[12] = 0x40000000;		/* cnoc data [2][6] at 12..23 */
	msg[18] = 0x60000001;
	msg[24] = 0x50000;		/* ddr addrs [8] at 24..31 */
	msg[25] = 0x5003c;
	msg[26] = 0x5000c;
	msg[32] = 0x40000000;		/* ddr data [16][8] at 32.. */
	msg[33] = 0x40000000;
	msg[34] = 0x40000000;
	int e_bw = hfi_send(3, msg, 32 + 128, 0);
	con_hex2("HFI", "perf=", (uint32_t)e_perf, "bw=", (uint32_t)e_bw);
	int e_test = hfi_send(5, msg, 1, 0);
	con_hex2("HFI", "test=", (uint32_t)e_test, "fw ver=", ver);

	stage("oob gpu_set (gx on)");
	rc = oob(16, 24);
	con_hex2("GX", rc ? "OOB TIMEOUT gdsc=" : "acked gdsc=", rd32(GPUCC + GPUCC_GX_GDSCR),
		 "info=", rd32(GMU_REG(GMU_G2H_INFO)));
	con_hex2("GMU", "rpmh=", rd32(GMU_REG(GMU_RPMH_STATE)), "fsr=", rd32(c + CB_FSR));
	if (!(rd32(GPUCC + GPUCC_GX_GDSCR) & (1u << 31))) {
		con_str("GX", "not powered; not touching GPU regs");
		return;
	}

	/*
	 * GPU clock: the GMU owns gx_gfx3d and leaves it at XO until asked (Linux
	 * a6xx_gmu_set_freq, legacy GMU): perf index, then OOB DCVS_SET 23/31.
	 * At 19.2 MHz a full-screen CoreAnimation frame took ~250 ms.
	 */
	stage("dcvs (gpu clock)");
	uint32_t rcg0 = rd32(GPUCC + 0x1020);
	int lvl = NGPU - 1;
	for (; lvl >= 2; lvl--) {
		wr32(GMU_REG(GMU_DCVS_ACK_OPTION), 0);
		wr32(GMU_REG(GMU_DCVS_PERF_SETTING), (3u << 28) | (uint32_t)lvl);
		wr32(GMU_REG(GMU_DCVS_BW_SETTING), 0xff);
		rc = oob(23, 31);
		wr32(GMU_REG(GMU_H2G_SET), 1u << 31);	/* clear DCVS_SET */
		if (!rc && rd32(GMU_REG(GMU_DCVS_RETURN)) == 0)
			break;
		con_hex2("DCVS", "failed lvl=", (uint32_t)lvl, "ret=", rd32(GMU_REG(GMU_DCVS_RETURN)));
	}
	con_hex2("DCVS", "lvl=", (uint32_t)lvl, "khz=", lvl >= 2 ? gpu_khz[lvl] : 0);
	con_hex2("DCVS", "gfx3d cfg was=", rcg0, "now=", rd32(GPUCC + 0x1020));
	con_hex2("DCVS", "gfx3d cmd=", rd32(GPUCC + 0x101c), "pll0 mode=", rd32(PLL0 + PLL_MODE));
	con_hex2("DCVS", "pll0 l=", rd32(PLL0 + PLL_L_VAL), "frac=", rd32(PLL0 + PLL_FRAC));

	stage("gpu register test");
	/* RBBM_STATUS (0x210) and CP_SCRATCH_REG0 (0x883) write/read test. */
	uint32_t st = rd32(GPU + 4 * 0x210);
	wr32(GPU + 4 * 0x883, 0x41445245);
	con_hex2("GPU", "rbbm=", st, "scratch=", rd32(GPU + 4 * 0x883));
	con_str("GPU", rd32(GPU + 4 * 0x883) == 0x41445245 ? "*** GX REGISTERS ALIVE ***" : "scratch mismatch");
	if (rd32(GPU + 4 * 0x883) == 0x41445245)
		gpu_run(smr_used + 1, cb);
}

/*
 * CPU clocks (qcom-cpufreq-hw v1 / OSM, sm7150 DT: freq-domain0 0x18323000 =
 * silver, freq-domain1 0x18325800 = gold). XNU has no cpufreq: the cores
 * stay at whatever perf state ABL left. LUT rows 32 bytes from +0x110:
 * src (bits 31:30), core count (18:16), L value (7:0); +0x920 perf state.
 */
#define CPUFREQ0	0x18323000UL
#define CPUFREQ1	0x18325800UL

static void cpufreq_dump(void)
{
	static const uintptr_t dom[2] = { CPUFREQ0, CPUFREQ1 };
	for (int d = 0; d < 2; d++) {
		uintptr_t b = dom[d];
		uint32_t last = 0;
		con_hex2("CPUFREQ", "enable=", rd32(b + 0x0), "perf state=", rd32(b + 0x920));
		for (int i = 0; i < 40; i++) {
			uint32_t v = rd32(b + 0x110 + 32 * i);
			uint32_t khz = ((v >> 30) & 3) ? (v & 0xff) * 19200 : 300000;
			if (i > 0 && khz == last)
				break;
			con_hex2("  lut", "idx=", (uint32_t)i, "khz=", khz);
			last = khz;
		}
	}
}

/*
 * Probe 6: ABL leaves the silver cores at perf state 6 (1497.6 MHz, max 9 =
 * 1804.8) and the gold cores (the two A76s backboardd's frames mostly end on)
 * at perf state 0: 300 MHz of 2304. Ask the OSM for gold 1939.2 MHz (state
 * 10) and silver 1708.8 MHz (state 8); the OSM sets the voltage, and the
 * SoC's own limits-management hardware still throttles when hot.
 */
static void cpu_boost(void)
{
	wr32(CPUFREQ0 + 0x920, 8);
	wr32(CPUFREQ1 + 0x920, 10);
	delay_ms(2);
	con_hex2("CPUFREQ", "silver state=", rd32(CPUFREQ0 + 0x920), "gold state=", rd32(CPUFREQ1 + 0x920));
}

void gpuprobe_run(const char **stage_var)
{
	stage_p = stage_var;
	cpufreq_dump();
	cpu_boost();
	con_str("GPUPROBE", "adreno 618 stage 2 (gmu boot)");
	if (cx_on())
		return;
	gmu_boot();
	stage("done");
}
#endif /* SHIM_GPUPROBE */
