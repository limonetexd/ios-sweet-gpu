/*
 * GPU probe (built with -DSHIM_GPUPROBE): first step of the Adreno 618
 * bring-up, after ios-flame's shim/gpuprobe.c (Adreno 640). Stage 1 powers
 * only the GPU's CX side (no GMU firmware, no GX rail):
 *
 *   GCC   ddrss_gpu_axi, gpu_memnoc_gfx, gpu_snoc_dvm_gfx
 *   GPUCC CX GDSC on, gmu_clk_src = XO (19.2 MHz), cxo, cx_gmu, crc_ahb,
 *         cx_snoc_dvm
 *
 * then reads GMU registers, checks that the GMU's ITCM/DTCM take writes and
 * reads the Adreno SMMU's ID registers (does the hypervisor let us at it?).
 * Results go to the framebuffer console; a hung bus access leaves the last
 * "STAGE" line on screen.
 *
 * Addresses: sweet's DT (qcom,kgsl-3d0 0x5000000, qcom,gmu 0x506a000,
 * kgsl-smmu 0x5040000, gpucc-sdmmagpie 0x5090000), gcc-sm7150.c, and
 * gpucc-sc7180.c (same A618 GPUCC layout; the values read before any write
 * are shown so a mismatch is visible). GMU register numbers are dword
 * offsets from the GPU base, as in a6xx_gmu.xml.
 */
#ifdef SHIM_GPUPROBE
#include <stdint.h>
#include "console.h"
#include "gpuprobe.h"

#define GCC		0x00100000UL
#define GPUCC		0x05090000UL
#define GPU		0x05000000UL
#define GMU_REG(o)	(GPU + 4UL * (o))
#define SMMU		0x05040000UL

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

#define GMU_ITCM	0x1b400
#define GMU_DTCM	0x1c400
#define GMU_FW_VERSION	0x1d3f8	/* legacy: written by the firmware */
#define GMU_INIT_RESULT	0x1f81c
#define GMU_RPMH_STATE	0x1f8ec
#define GMU_SPTPRAC_PWR	0x1a881	/* GMU_SPTPRAC_PWR_CLK_STATUS */
#define GMU_CX_BUSY	0x23b0c

static inline uint32_t rd32(uintptr_t a) { return *(volatile uint32_t *)a; }
static inline void wr32(uintptr_t a, uint32_t v) { *(volatile uint32_t *)a = v; }

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

static void stage(const char *s)
{
	*stage_p = s;
	con_str("STAGE", s);
}

static void branch_on(const char *name, uintptr_t reg)
{
	uint32_t before = rd32(reg);
	wr32(reg, before | 1);
	int rc = wait_bit(reg, 1u << 31, 0, 10);
	con_hex2(name, "was=", before, rc ? "HALTED=" : "now=", rd32(reg));
}

void gpuprobe_run(const char **stage_var)
{
	stage_p = stage_var;
	con_str("GPUPROBE", "adreno 618 stage 1 (cx only)");
	con_hex2("CX GDSC", "was=", rd32(GPUCC + GPUCC_CX_GDSCR), "gx=", rd32(GPUCC + GPUCC_GX_GDSCR));
	con_hex2("GMU RCG", "cmd=", rd32(GPUCC + GPUCC_GMU_RCG), "cfg=", rd32(GPUCC + GPUCC_GMU_RCG + 4));
	con_hex2("GPUCC", "cxo=", rd32(GPUCC + GPUCC_CXO), "cx_gmu=", rd32(GPUCC + GPUCC_CX_GMU));

	stage("gcc branches");
	branch_on("AXI", GCC + GCC_DDRSS_GPU_AXI);
	branch_on("MEMNOC", GCC + GCC_GPU_MEMNOC_GFX);
	branch_on("SNOCDVM", GCC + GCC_GPU_SNOC_DVM_GFX);

	stage("cx gdsc");
	/* CX GDSC: clear SW_COLLAPSE (bit 0), wait for PWR_ON (bit 31). */
	uintptr_t gdsc = GPUCC + GPUCC_CX_GDSCR;
	wr32(gdsc, rd32(gdsc) & ~1u);
	int rc = wait_bit(gdsc, 1u << 31, 1, 100);
	con_hex2("CX GDSC", rc ? "TIMEOUT=" : "on=", rd32(gdsc), 0, 0);
	if (rc)
		return;

	stage("gmu rcg");
	/* gmu_clk_src: source 0 (XO), divider 1 (HID 1), then update. */
	uintptr_t rcg = GPUCC + GPUCC_GMU_RCG;
	wr32(rcg + 4, (rd32(rcg + 4) & ~0x71fu) | 1u);
	wr32(rcg, rd32(rcg) | 1u);
	rc = wait_bit(rcg, 1, 0, 10);
	con_hex2("GMU RCG", rc ? "TIMEOUT=" : "cmd=", rd32(rcg), "cfg=", rd32(rcg + 4));

	stage("gpucc branches");
	branch_on("CXO", GPUCC + GPUCC_CXO);
	branch_on("CX_GMU", GPUCC + GPUCC_CX_GMU);
	branch_on("CRC_AHB", GPUCC + GPUCC_CRC_AHB);
	branch_on("CX_DVM", GPUCC + GPUCC_CX_SNOC_DVM);

	stage("gmu reads");
	con_hex2("GMU", "fwver=", rd32(GMU_REG(GMU_FW_VERSION)), "init=", rd32(GMU_REG(GMU_INIT_RESULT)));
	con_hex2("GMU", "rpmh=", rd32(GMU_REG(GMU_RPMH_STATE)), "cxbusy=", rd32(GMU_REG(GMU_CX_BUSY)));
	con_hex2("GMU", "sptprac=", rd32(GMU_REG(GMU_SPTPRAC_PWR)), 0, 0);

	stage("tcm test");
	/* ITCM/DTCM write test: proves the GMU's memories are reachable. */
	uintptr_t itcm = GMU_REG(GMU_ITCM), dtcm = GMU_REG(GMU_DTCM);
	uint32_t i0 = rd32(itcm), d0 = rd32(dtcm);
	wr32(itcm, 0x464c414d);
	wr32(dtcm, 0x45475055);
	con_hex2("ITCM", "was=", i0, "now=", rd32(itcm));
	con_hex2("DTCM", "was=", d0, "now=", rd32(dtcm));
	con_str("  want", "itcm 464c414d dtcm 45475055");

	stage("smmu ids");
	con_hex2("SMMU", "cr0=", rd32(SMMU + 0x0), "idr0=", rd32(SMMU + 0x20));
	con_hex2("SMMU", "idr1=", rd32(SMMU + 0x24), "idr2=", rd32(SMMU + 0x28));
	con_hex2("SMMU", "idr7=", rd32(SMMU + 0x3c), "gfsr=", rd32(SMMU + 0x48));
	for (int i = 0; i < 8; i++) {
		char l[] = "SMR0";
		l[3] = '0' + i;
		con_hex2(l, "smr=", rd32(SMMU + 0x800 + 4 * i), "s2cr=", rd32(SMMU + 0xc00 + 4 * i));
	}
	stage("stage 1 done");
}
#endif /* SHIM_GPUPROBE */
