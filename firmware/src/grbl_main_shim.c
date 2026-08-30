/*
  grbl_main_shim.c  —  Re-exports GRBL's main() as grbl_main()
  -------------------------------------------------------------
  The Arduino framework already provides int main(), so we cannot link
  GRBL's original main.c unchanged.  Instead we exclude grbl/grbl/main.c
  from the build (see platformio.ini build_src_filter) and provide this
  shim, which contains exactly the same code but under the name grbl_main().

  Our main.cpp (C++) then calls grbl_main() from setup().

  This file is copied from grbl/grbl/main.c and is therefore a derivative
  work of GRBL:

    Copyright (c) 2011-2016 Sungeun K. Jeon for Gnea Research LLC
    Copyright (c) 2009-2011 Simen Svale Skogsrud

  SPDX-License-Identifier: GPL-3.0-or-later
*/

#include "../grbl/grbl/grbl.h"

/* System global variables — identical to grbl/grbl/main.c */
system_t sys;
int32_t sys_position[N_AXIS];
int32_t sys_probe_position[N_AXIS];
volatile uint8_t sys_probe_state;
volatile uint8_t sys_rt_exec_state;
volatile uint8_t sys_rt_exec_alarm;
volatile uint8_t sys_rt_exec_motion_override;
volatile uint8_t sys_rt_exec_accessory_override;
#ifdef DEBUG
volatile uint8_t sys_rt_exec_debug;
#endif

int grbl_main(void)
{
    // Initialize system upon power-up.
    serial_init();
    settings_init();
    stepper_init();
    system_init();

    memset(sys_position, 0, sizeof(sys_position));
    sei();

#ifdef FORCE_INITIALIZATION_ALARM
    sys.state = STATE_ALARM;
#else
    sys.state = STATE_IDLE;
#endif

#ifdef HOMING_INIT_LOCK
    if (bit_istrue(settings.flags, BITFLAG_HOMING_ENABLE))
    {
        sys.state = STATE_ALARM;
    }
#endif

    for (;;)
    {
        uint8_t prior_state = sys.state;
        memset(&sys, 0, sizeof(system_t));
        sys.state = prior_state;
        sys.f_override = DEFAULT_FEED_OVERRIDE;
        sys.r_override = DEFAULT_RAPID_OVERRIDE;
        sys.spindle_speed_ovr = DEFAULT_SPINDLE_SPEED_OVERRIDE;
        memset(sys_probe_position, 0, sizeof(sys_probe_position));
        sys_probe_state = 0;
        sys_rt_exec_state = 0;
        sys_rt_exec_alarm = 0;
        sys_rt_exec_motion_override = 0;
        sys_rt_exec_accessory_override = 0;

        serial_reset_read_buffer();
        gc_init();
        spindle_init();
        coolant_init();
        limits_init();
        probe_init();
        plan_reset();
        st_reset();

        plan_sync_position();
        gc_sync_position();

        report_init_message();
        protocol_main_loop();
    }

    return 0; /* never reached */
}
