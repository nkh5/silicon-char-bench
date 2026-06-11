/* Bench payload firmware v0 (session 2).
 *
 * Line-oriented ASCII command protocol over USB CDC serial (see bench/dut.py
 * for the host-side table): PING, ID, STATUS, MARCH, CRC. Emits an HB line
 * every second while idle and a BOOT line once the host connects.
 *
 * The watchdog is armed at all times; a hung workload reboots the chip into
 * a safe configuration and the host sees "BOOT WATCHDOG" instead of a dead
 * port. True MOSFET power cycling replaces this as the recovery path in
 * session 4.
 */
#include <inttypes.h>
#include <stdio.h>
#include <strings.h>

#include "hardware/watchdog.h"
#include "pico/stdio_usb.h"
#include "pico/stdlib.h"
#include "pico/unique_id.h"

#include "workloads.h"

#define FW_VERSION "0.2.0"
#define WATCHDOG_TIMEOUT_MS 5000u /* RP2040 watchdog max is ~8.3 s */
#define HEARTBEAT_PERIOD_MS 1000u
#define CMD_BUF_LEN 64u

#ifndef PICO_BOARD
#define PICO_BOARD "unknown"
#endif

static uint32_t workload_buf[WORKLOAD_BUF_WORDS];
static uint32_t hb_seq;

static void cmd_ping(void)
{
    printf("PONG %" PRIu32 "\n", to_ms_since_boot(get_absolute_time()));
}

static void cmd_id(void)
{
    char board_id[2 * PICO_UNIQUE_BOARD_ID_SIZE_BYTES + 1];
    pico_get_unique_board_id_string(board_id, sizeof board_id);
    printf("ID %s %s %s\n", board_id, PICO_BOARD, FW_VERSION);
}

static void cmd_status(void)
{
    printf("STATUS uptime_ms=%" PRIu32 " hb_seq=%" PRIu32 "\n",
           to_ms_since_boot(get_absolute_time()), hb_seq);
}

static void cmd_march(void)
{
    static const uint32_t pairs[][2] = {
        {0x00000000u, 0xFFFFFFFFu},
        {0x55555555u, 0xAAAAAAAAu},
    };
    absolute_time_t t0 = get_absolute_time();
    march_fault_t fault = {0};

    for (size_t p = 0; p < sizeof pairs / sizeof pairs[0]; p++) {
        watchdog_update();
        if (!march_c_minus(workload_buf, WORKLOAD_BUF_WORDS,
                           pairs[p][0], pairs[p][1], &fault)) {
            printf("RESULT MARCH FAIL elem=%d idx=%u exp=0x%08" PRIX32
                   " got=0x%08" PRIX32 "\n",
                   fault.element, (unsigned)fault.index, fault.expected, fault.got);
            return;
        }
    }
    uint32_t elapsed_ms = (uint32_t)(absolute_time_diff_us(t0, get_absolute_time()) / 1000);
    printf("RESULT MARCH PASS %" PRIu32 "\n", elapsed_ms);
}

static void cmd_crc(void)
{
    absolute_time_t t0 = get_absolute_time();

    watchdog_update();
    fill_xorshift32(workload_buf, WORKLOAD_BUF_WORDS, CRC_SEED);
    uint32_t crc = crc32_ieee((const uint8_t *)workload_buf,
                              WORKLOAD_BUF_WORDS * sizeof(uint32_t));
    uint32_t elapsed_ms = (uint32_t)(absolute_time_diff_us(t0, get_absolute_time()) / 1000);
    printf("RESULT CRC %s 0x%08" PRIX32 " %" PRIu32 "\n",
           crc == CRC_EXPECTED ? "PASS" : "FAIL", crc, elapsed_ms);
}

static void handle_command(const char *cmd)
{
    if (strcasecmp(cmd, "PING") == 0) {
        cmd_ping();
    } else if (strcasecmp(cmd, "ID") == 0) {
        cmd_id();
    } else if (strcasecmp(cmd, "STATUS") == 0) {
        cmd_status();
    } else if (strcasecmp(cmd, "MARCH") == 0) {
        cmd_march();
    } else if (strcasecmp(cmd, "CRC") == 0) {
        cmd_crc();
    } else {
        printf("ERR unknown command: %s\n", cmd);
    }
}

int main(void)
{
    stdio_init_all();
    watchdog_enable(WATCHDOG_TIMEOUT_MS, true);

    bool banner_sent = false;
    absolute_time_t next_hb = make_timeout_time_ms(HEARTBEAT_PERIOD_MS);
    char cmd[CMD_BUF_LEN];
    size_t cmd_len = 0;

    while (true) {
        watchdog_update();

        if (!banner_sent && stdio_usb_connected()) {
            printf("BOOT %s %s\n",
                   watchdog_caused_reboot() ? "WATCHDOG" : "CLEAN", FW_VERSION);
            banner_sent = true;
        }

        if (absolute_time_diff_us(next_hb, get_absolute_time()) >= 0) {
            if (stdio_usb_connected()) {
                printf("HB %" PRIu32 " %" PRIu32 "\n",
                       hb_seq++, to_ms_since_boot(get_absolute_time()));
            }
            next_hb = make_timeout_time_ms(HEARTBEAT_PERIOD_MS);
        }

        int c = getchar_timeout_us(10 * 1000);
        if (c == PICO_ERROR_TIMEOUT) {
            continue;
        }
        if (c == '\r' || c == '\n') {
            if (cmd_len > 0) {
                cmd[cmd_len] = '\0';
                handle_command(cmd);
                cmd_len = 0;
            }
        } else if (cmd_len < CMD_BUF_LEN - 1) {
            cmd[cmd_len++] = (char)c;
        } else {
            cmd_len = 0;
            printf("ERR command too long\n");
        }
    }
}
