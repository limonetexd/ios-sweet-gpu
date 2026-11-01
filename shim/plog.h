#pragma once

/* Probe log in a userdata scratch area + automatic return to fastboot (plog.c). */
#define PLOG_BLOCKS	32u	/* header + 31 text blocks, below the XNU console ring */

int plog_init(void);
int plog_save(const char *why);
int plog_set_fastboot_reason(void);
void plog_wdog_arm(unsigned seconds);
void plog_wdog_pet(void);
void __attribute__((noreturn)) plog_reboot(void);
