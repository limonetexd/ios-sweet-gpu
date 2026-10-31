/*
 * GPU firmware for the probe image. The files are Qualcomm's (sweet's vendor
 * partition) and stay out of git: research/gpu-sweet/fw/ (see FACTS.md).
 */
#ifdef SHIM_GPUPROBE
	.section .rodata
	.balign 16
	.global gmu_fw, gmu_fw_end
gmu_fw:
	.incbin "../research/gpu-sweet/fw/a618_gmu.bin"
gmu_fw_end:
	.balign 16
	.global sqe_fw, sqe_fw_end
sqe_fw:
	.incbin "../research/gpu-sweet/fw/a630_sqe.fw"
sqe_fw_end:
#endif
