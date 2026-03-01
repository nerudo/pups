# pups
PUPS is primitive ups python script or something like that. It can monitor UPSes which use basic Megatec protocol over USB. Auto shutdown on battery low and some commands are supported.

## Requirements
Package **hidapi** should be installed.
Package **pystray** if available is used to show stat/control icon in the system tray.

## Compatibility
USB connection is supported only. Checked with SVEN POWER Smart 1000 (VID/PID 05b8/0000). It should support a lot of other models and vendors (such as Sven, Powerman, Ippon, Mustek) after setting appropriate VID/PID. Tested with Windows but should support Linux/BSD. It should be run under root to shutdown Linux/BSD.

## Interface
Three user actions are available in interactive mode via console or system tray icon:
* Test battery for 10 seconds;
* Beep on/off;
* Cancel shutdown.

## Settings
Settings are available in the script file as variables:
* VID, PID - Device ID;
* AUTO_OFF_LIMIT - Shutdown voltage of one battery used for calculation with UPS ratings info for multi-battery devices;
* OFF_LIMIT - Manual shutdown voltage. If 0 then AUTO_OFF_LIMIT is used in auto mode. If negative then voltage limits are not used for shutdown. Status flag from UPS is used only;
* SHUTDOWN_CMD - User shutdown command instead of predefined for Windows and Linux;
* CANCEL_SHUTDOWN_CMD - User cancel shutdown command instead of predefined for Windows and Linux;
* LOGFILE - log file name;
* LOG_LEVEL - Log level for file output: 0 - off, 1 - events only, 2 - all data.

