### PUPS is primitive ups python script or something like that.
### It can monitor UPSes which use basic Megatec protocol over USB.
### Auto shutdown on battery low and some commands are supported.
### Package hidapi should be installed.
### Package pystray if available is used to show stat/control
### icon in the system tray.

# Device ID
VID = 0x05b8
PID = 0x0000

# Shutdown voltage of one battery used for calculation with UPS ratings info
# for multi-battery devices
AUTO_OFF_LIMIT = 11.0

# Manual shutdown voltage. If 0 then AUTO_OFF_LIMIT is used in auto mode
# If negative then voltage limits are not used for shutdown. Status flag 
# from UPS is used only 
#OFF_LIMIT = 25.5
#OFF_LIMIT = -1   # Do not use
OFF_LIMIT = 0   # Auto

# User shutdown command instead of predefined for Windows and Linux
SHUTDOWN_CMD = ""
#SHUTDOWN_CMD = "@echo OS Shutdown here"

# User cancel shutdown command instead of predefined for Windows and Linux
CANCEL_SHUTDOWN_CMD = ""
#CANCEL_SHUTDOWN_CMD = "@echo Cancel OS shutdown here"

# Log file
LOGFILE = "pups.log"

# Log level for file output: 0 - off, 1 - events only, 2 - all data
LOG_LEVEL = 2


import time
import threading
import os
import platform
import sys
from datetime import datetime

try:
    import hid # hidapi package
except:
    print("Please install hidapi package.")
    sys.exit(2)

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    use_tray = True
except:
    use_tray = False


def create_image():
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), color=(7, 8, 9))
    dc = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=36)
    color = (255, 255, 0)
    dc.text((4,-6), "P U", fill=color, font=font)
    dc.text((4,25), "P S", fill=color, font=font)
    return image


# Sey of menu events
def on_exit(icon, item):
    icon.stop()


def on_test(icon, item):
    global input_val
    with lock:
        input_val = "t"


def on_cancel(icon, item):
    global input_val
    with lock:
        input_val = "c"


def on_beep(icon, item):
    global input_val
    with lock:
        input_val = "q"


class Log:
    f = 0
    level = 0
    def __init__(self, logfile = "", level = 1):
        linebuf = ""
        self.level = level
        if logfile:
            try:
                self.f = open(logfile, 'w')
            except:
                print("Unable to open log file '" + logfile + "'")

    def __del__(self):
        if self.f:
            self.f.close()
            # print("File closed")

    def new_line(self, str="", st="", end="", level = 1):
        print('\n' + st + str + end, end='')
        if self.f and level <= self.level:
            if not str == "":   # Don't write single \n to file because \r is translated to \n too
                self.f.write('\n' + datetime.now().strftime("%Y-%m-%d %H:%M:%S ") + st + str)
                self.f.flush()

    def same_line(self, str="", st="", end="", level = 1):
        print('\r' + st + str + end, end='')
        if self.f and level <= self.level:
            self.f.write('\n' + datetime.now().strftime("%Y-%m-%d %H:%M:%S ")+ st + str)
            self.f.flush()

    def cont_line(self, str, st="", end="", level = 1):
        print(st + str + end, end='')
        if self.f and level <= self.level:
            self.f.write(st + str)


def shutdown_os():
    global SHUTDOWN_CMD
    global log
    rc = -1
    if SHUTDOWN_CMD != "":
        rc = os.system(SHUTDOWN_CMD)
    else:
        sysname = platform.system()
        if sysname == "Windows":
            rc = os.system('shutdown /s /t 60 /e /c "Battery low" /d p:6:12')
        elif sysname == "Linux" or sysname == "Darwin":
            rc = os.system('shutdown -h +1 "Battery low"')
        elif "BSD" in sysname:
            rc = os.system('shutdown -p +1 "Battery low"')
        else:
            log.new_line("Unable to shutdown unknown OS")
    return rc


def cancel_shutdown_os():
    global CANCEL_SHUTDOWN_CMD
    global log
    rc = -1
    if CANCEL_SHUTDOWN_CMD != "":
        rc = os.system(CANCEL_SHUTDOWN_CMD)
    else:
        sysname = platform.system()
        if sysname == "Windows":
            rc = os.system('shutdown /a')
        elif sysname == "Linux" or sysname == "Darwin":
            rc = os.system('shutdown -c')
        elif "BSD" in sysname:
            rc = os.system('killall shutdown')
        else:
            log.new_line("Unable to cancel shutdown of unknown OS")
    return rc


def encode_cmd(str):
   res = 9*[0x20]
   res[0] = 0   # The first byte contains the Report number or 0 as demanded by hid.write()
   for idx in range(len(str)):
      res[idx+1] = ord(str[idx])
   res[len(str)+1] = 13 # CR
   return res


def decode_ans(d):
    st = ""
    for item in d:
        if 32 <= item < 128:
            st = st + chr(item)
    return st


def get_data(h):
    q = []
    while True:
        d = h.read(100) # IOError can be here
        if d:
            q = q + d 
        else:
            break
    return q


def send_data(h, d):
    h.write(d)  # IOError can be here


def run_cmd(h, cmd):
    send_data(h, encode_cmd(cmd))   # IOError can be raised to caller func
    time.sleep(0.3)
    return decode_ans(get_data(h))


def open_ups(VID, PID):
    try: 
        h = hid.device()
        h.open(VID, PID)  # UPS VID/PID
        # enable non-blocking mode
        h.set_nonblocking(1)
        # h.set_nonblocking(0)
        # print("Manufacturer: %s" % h.get_manufacturer_string())
        # print("Product: %s" % h.get_product_string())
        # print("Serial No: %s" % h.get_serial_number_string())
        return h
    except:
        raise IOError


# Running in separate thread to read keyboard input
def read_keyb():
    global input_val
    global use_tray
    while(1):
        try:
            n = input()
        except EOFError as ex:    # Raised on Ctrl-c in main thread
            print(str(ex) + " in input")
            if use_tray:
                icon.stop()
            return
        # except KeyboardInterrupt:
        #     print(str(ex) + "in input")
        #     return
        with lock:
            input_val = n


# Worker thread
def worker():
    GOOD_STAT = 0x9
    MASK_STAT = 0x8
    MS_PERIOD = 2000
    MS_INC    = 10

    global input_val
    global stop_dev
    global use_tray
    global AUTO_OFF_LIMIT
    global OFF_LIMIT
    # global log

    STAT_CODES = [ [0x80, 'On_battery'], 
                    [0x40, 'Battery_low'],
                    [0x20, 'AVR_on'],
                    [0x10, 'UPS_fail'],
                    [0x04, 'Test'],
                    [0x02, 'UPS_off']]

    log.new_line("")
    log.new_line("Running " + ("with" if use_tray else "without") + " tray support.")
    log.new_line("Use <t> for test, <c> for cancel shutdown, <q> for beeper change followed by <Enter>")
    first_open = True

    while True:
        try:
            dev = open_ups(VID, PID)
        except IOError:
            if first_open:
                log.new_line("Unable to open device " + hex(VID) + "/" + hex(PID))
                os._exit(1) # No way...
                # if use_tray:
                #     time.sleep(.5)  # Without delay icon don't stop
                #     icon.stop()
                # return

            else:
                if stop_dev:    # Flag from main loop
                    try:
                        dev.close()
                    finally:
                        None
                    return
                time.sleep(5)
                continue
        first_open = False

        try:    # IOError exception in run_cmd() raises device reopening
            ups_info = ' '.join(run_cmd(dev, "I").lstrip("#").split())  # Remove unnecessary spaces and other
            log.new_line(ups_info)
            ups_cap_s = run_cmd(dev, "F").lstrip("#")
            user_off_limit = 0
            try:
                ups_cap = [float(item) for item in ups_cap_s.split()]
                log.new_line("Reported ratings: " + str(ups_cap))
                if len(ups_cap) != 4:
                    raise
                if OFF_LIMIT == 0 :
                    user_off_limit = AUTO_OFF_LIMIT/12*ups_cap[2]
                    log.new_line("Set auto off limit to " + str(user_off_limit) + "V")
            except ValueError:
                log.new_line("Invalid rating info")
            log.new_line()

            last_flags = GOOD_STAT
            ok = True
            shutdown_in_progress = False
            pre_shutdown_wait = 0

            mscnt = MS_PERIOD + 1
            while True:
                if stop_dev:    # Flag from main loop
                    dev.close()
                    return

                time.sleep(.01)
                mscnt = mscnt + MS_INC

                if mscnt > MS_PERIOD:
                    mscnt = 0
                    stat_s = run_cmd(dev, "Q1").lstrip('(')
                    stat = stat_s.split()
                    # if random.randint(0, 20)>19:
                        # stat = stat + ["debug"]
                    if len(stat) != 8:
                        if(ok): # Print error only once per fail
                            log.same_line(stat_s)
                            log.cont_line("Invalid status format", st=' ')
                            log.new_line() # Line feed after changed status to save history of events
                        ok = False
                        time.sleep(3)
                        continue

                    ok = True
                    try:
                        flags = int(stat[7], 2) 
                        # flags = (1<<random.randint(0, 7)) * int(random.randint(0, 10)>9) # Debug
                    except:
                        flags = 0

                    flags_changed = (flags != last_flags)
                    log_lev = 1 if flags_changed else 2
                    log.same_line(stat_s, level=log_lev)

                    try:
                        load = int(stat[3])
                    except:
                        load = -1
                    traystr = "Shutdown in progress\n" if shutdown_in_progress else ""
                    traystr += "Input: " + stat[0] + "V, Battery: " + stat[5] + \
                            "V, " + (("Load: " + str(load) + "%, ") if load >=0 else "") + "Tempr: " + stat[6] + " \n"

                    flag_count = 0
                    for item in STAT_CODES:
                        if flags & item[0]:
                            log.cont_line(item[1], st=' ', level=log_lev)
                            traystr += (" " if flag_count else "") + item[1]
                            flag_count += 1
                            
                    beep_str = "Beep_" + ("On" if flags & 0x01 else "Off")
                    log.cont_line(beep_str, st=' ', end='           ', level=log_lev) # clean old output
                    traystr += (" " if flag_count else "") + beep_str
                    if use_tray:
                        # icon.title = stat_s
                        icon.title = traystr

                    if flags_changed:
                        log.new_line(level=log_lev) # Line feed after changed status to save history of events
                        last_flags = flags

                    if pre_shutdown_wait:   # Count down wait before repeat shutdown 
                        pre_shutdown_wait = pre_shutdown_wait - 1   # on every cycle

                    if not shutdown_in_progress:
                        try:
                            batt_level = -1.0
                            batt_level = float(stat[5])
                        except ValueError:
                            log.cont_line("Bad_Batt_Lev", st=' ')
                        if batt_level > 0:
                            if batt_level < user_off_limit or flags & 0x40:
                                if not pre_shutdown_wait:   # Do not run shutdown immidiately 
                                    log.new_line()                 # when it was manually canceled
                                    log.new_line("Shutting down on battery low. Press <C>, <Enter> to cancel")
                                    shutdown_os()
                                    run_cmd(h, "S03")   # Shutdown UPS after 3 minutes
                                    shutdown_in_progress = True

                with lock:
                    event = ''
                    if len(input_val) > 0:
                        event = input_val[0]
                        input_val = ""
                if event.lower() == 't':
                    log.new_line(" Run UPS test")
                    log.new_line()
                    run_cmd(dev, "T")
                elif event.lower() == 'q':
                    log.new_line(" Switch beep")
                    log.new_line()
                    run_cmd(dev, "Q")
                elif event.lower() == 'c':
                    log.new_line(" Canceling shutdown")
                    log.new_line()
                    cancel_shutdown_os()
                    run_cmd(dev, "C")  # Cancel UPS shutdown
                    shutdown_in_progress = False
                    pre_shutdown_wait = 20

        except IOError:  # Raise here from run_cmd() if problem with dev
            log.new_line()
            log.new_line("I/O error. Reopening device...")
            try:
                dev.close()
            finally:
                pass
            time.sleep(1)


# Init and threads run
log = Log(LOGFILE, level=LOG_LEVEL)
stop_dev = False
input_val = ""

# mutex lock for keyboard input variable
lock = threading.Lock()

keyb_thread = threading.Thread(target=read_keyb)
keyb_thread.daemon = True   # Stop it when main thread exited
work_thread = threading.Thread(target=worker)
keyb_thread.start()
work_thread.start()

if use_tray:
    # Create systray menu
    menu = pystray.Menu(
        pystray.MenuItem("Run test", on_test),
        pystray.MenuItem("Cancel shutdown", on_cancel),
        pystray.MenuItem("Change beep", on_beep),
        pystray.MenuItem("Exit", on_exit)
    )
    # Init icon
    icon = pystray.Icon("PUPS", create_image(), "PUPS starting...", menu)

try:
    if use_tray:
        icon.run()
    else:
        keyb_thread.join()  # Wait here for exception on Ctrl-C
    # print("Exited from icon")

except KeyboardInterrupt as ex:
    print("Ctrl-C is pressed")
finally:
    stop_dev = True
