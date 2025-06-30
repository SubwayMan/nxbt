## NXBT-fork: Turn your laptop into a bluetooth emulator for Nintendo Switch

This fork of the NXBT library allows the usage of a generic USB controller on the Nintendo Switch. The script provided turns the target (for me, a laptop running Fedora Linux)
into a Bluetooth emulator that can connect to the Nintendo Switch.

#### Usage
Tested on my laptop (fedora 41).

Create a virtual environment:
```bash
python -m venv venv/
source venv/bin/activate
pip install -R requirements.txt
```

I currently run the controller wrapper script from the directory just outside the source for this repository, in this manner:
```bash
sudo -E env PATH="$PATH" python -m nxbt.controller_mapper 
```
Ensure that you have a usb controller plugged in and ready before running this command, and that your switch is set to the Change Grip/Order menu. You should see a paring notification/connection within around 30s.

For any BlueZ issues, try following the steps used by this project: github.com/Poohl/joycontrol

#### Todo
- Multi-controller emulation
- Gyroscope data sending support
- Conversion to C++ frontend with Python/system daemons

