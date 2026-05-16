# G-code Pen Plotter

[![3D Printing](https://img.shields.io/badge/3D_printing-STL-green)](#)
[![C/C++](https://img.shields.io/badge/C/C++-firmware-green)](#)
[![License](https://img.shields.io/badge/license-CC%20BY--SA%204.0-blue)](http://creativecommons.org/licenses/by-sa/4.0/)

This plotter draws vector graphics in G-code format using a pen. It is compatible with pens up to 11 mm in diameter, relies on inexpensive and widely available components, and uses a mostly 3D-printed frame with a few off-the-shelf mechanical parts. A set of test cases guides the user to verify the functionality of each hardware component before running GRBL.

The plotter's firmware is based on GRBL v1.1, which is a widely used open-source CNC controller firmware.
It comes with a GUI toolset to transform images provided by the user to drawings in different styles via AI (technical drawing, pencil drawing, oil painting etc.) to send them to the plotter for drawing.

![Assembly overview](./print/zsb/full.png)

# Table of contents

- [Overview](#overview)
- [Features](#features)
- [Bill of Materials](#bill-of-materials)
- [Assembly](#assembly)
- [Electronics](#electronics) — see [electronics.md](electronics.md) for full details
- [Firmware](#firmware) — see [firmware/README.md](firmware/README.md) for full details
- [Testing](#testing) — see [testing.md](testing.md) for full details
- [Software for host computer](#software-for-host-computer) — see [pipeline/README.md](pipeline/README.md) for full details
- [License and Acknowledgements](#license-and-acknowledgements)

## Overview

This pen plotter is meant for hobbyists and makers who want a low-cost machine to draw vector artwork on paper. It uses two stepper-driven axes, a simple pen carriage with a lift mechanism via solenoid for automated pen up/down control. Most structural parts are 3D-printed and a number of standard mechanical parts (rods, bearings, springs, belt and pulleys) complete the build.

## Features

- Compatible with pens up to 11 mm diameter
- Mostly 3D-printed components for easy reproduction
- Designed for A4-sized paper by default (adjustable)
- Open-source firmware based on GRBL v1.1
- Test suite to verify hardware functionality before running GRBL
- GUI toolset for image-to-G-code conversion with AI-based drawing styles (technical, pencil, oil painting etc.)

## Bill of Materials

Below are the main 3D-printed parts and standard hardware used in the project. See the [full BOM](BOM.md) and the `print/` directory for the source STL/PNG files and visual references.

### 3D-printed parts (selected)

Refer to the `print/stl/` and `print/png/` folders for all printable parts and preview images.

- `frame_front.stl`, `frame_back.stl` — frame halves
- `housing_front.stl`, `housing_back.stl`, `housing_feet.stl` — optional housing
- `carriage_penholder_base.stl`, `carriage_penholder_connector_screw.stl` — carriage and pen holder
- `flat_steel_flange.stl`, `flat_steel_lever.stl` — parts that interface with the steel pen-raising strip
- `paper_bail_*.stl` — paper bail and rollers
- `paper_guide_front.stl`, `paper_guide_back.stl` — paper gudie
- `shaft_end_flange.stl`, `shaft_connector_flange.stl` — shaft support parts
- `solenoid_slider.stl` — slider to make the pull solenoid a push solenoid (optional)
- `cable_management.stl` — optional cable management clips

### Standard hardware (selected)

- 12 mm square rods
- 6 mm round rods
- 12 mm steel shaft
- 2x 6mm linear ball bearings
- 2x NEMA 17 stepper motors
- 2GT 5mm timing belt, timing pulley and idler pulley
- Assorted M2/M3/M4 screws and nuts (details in original BOM)
- Bearings: F624ZZ bearings used in the rollers
- Springs: compression and extension springs as needed for pen lift and paper drive
- Pull solenoid 12 V (example: TAU-0530)

For a complete part list including quantities and McMaster/AliExpress references, see the original [BOM](BOM.md) in the repository.

## Assembly

The repository contains step-by-step photos and GIFs in `print/zsb/` that show how parts fit together. The high-level assembly steps are:

1. Prepare the back frame: press in M3 nuts, install bearings, fit the timing-belt pulley and mount the optical endstop and solenoid.

2. Prepare the front frame: press in M3 nuts, install bearings, attach stepper motor and shaft coupler, and mount the drive pulley and endstop.

3. Join both frame halves: insert the paper guide rods, shaft, and the movable flat-steel strip used for pen lifting.

Fully assembled lever mechanism:
<img src="./print/zsb/lever_assembly.png">

Fully assembled drive shaft:
<img src="./print/zsb/drive_assembly.png">

1. Slide the carriage onto the guide rods and secure the timing belt to the carriage. Fit the belt around the drive and idler pulleys and tension appropriately.

Fully assembled carriage and timing belt mechanism:
<img src="./print/zsb/carriage_assembly.png">

1. Assemble and install the paper bail rollers and springs that hold and move the paper.

Detail for each paper bail roller:
<img src="./print/zsb/paper_bail_roller_assembly.png">

Fully assembled paper bail:
<img src="./print/zsb/paper_bail_assembly.png">

1. Optionally assemble and attach the housing halves for a finished enclosure.

Important: some assembly steps (press-fitting nuts and bearings, re-threading printed holes) may require light machining or careful rework for reliable operation.

## Electronics

The electronics are intentionally simple: an Arduino Uno with a CNC Shield v3 and two A4988 stepper drivers.
A solenoid controlled via a MOSFET handles pen lift.

For full details on wiring, pin mapping, microstepping, endstops and the solenoid circuit see **[electronics.md](electronics.md)**.

Assembly steps:

1. Route the stepper motor and endstop cables through the frame openings into the enclosure.
2. Secure cables with cable ties and cable management clips to avoid interference with moving parts.
3. Prepare the PCB holder by pressing in the M3 nuts. Screw the Arduino to it. Add the CNC Shield and the stepper drivers. Finally slide the PCB holder over the rods.
4. Assemble all wires according to [electronics.md](electronics.md).
5. Attach the housing and fix it to the PCB holder and rods with M3 screws. Make sure the USB port and power jack are accessible.

## Firmware

The plotter runs [GRBL](https://github.com/gnea/grbl) v1.1 on the Arduino Uno.
All firmware sources live in `firmware/`; GRBL is included as a Git submodule under `firmware/grbl/`.

For build instructions, flashing, GRBL parameter setup and G-code tooling see **[firmware/README.md](firmware/README.md)**.

Quick start:

```bash
git clone --recurse-submodules https://github.com/Smengerl/plotter.git
cd plotter/firmware
pio run -t upload   # build and flash
pio device monitor  # open serial console at 115200 baud
```

## Testing

A dedicated test suite verifies each hardware component before running GRBL.  
See **[testing.md](testing.md)** for the full procedure.

## Software for host computer

A set of CLI tools to send G-code files to the plotter is included in pipeline.
The tool allows to configure individual processing pipelines by pure configuration without changing the code for images including adaptation of styles via prompt to a provided image, the necessary vectorization and sending the G-code.

A GUI frontend is provided for convenient usage of these mechanism including management of the raw images, applying various pipelines to them, previewing the adapted images and eventually sending the images to the plotter.

See **[pipeline/README.md](/pipeline/README.md)** for the full procedure.

## Acknowledgements

Thanks to the open-source community and suppliers of affordable components. If you found or adapted any parts from other projects, please credit them in the repository history or in a CONTRIBUTORS file.

## Development

Contributions are welcome.  
See `CONTRIBUTING.md` for details and follow the `CODE_OF_CONDUCT.md` when contributing.

All .stl, .png and assembly pictures are automatically exported via my Fusion add-in, see [here](https://github.com/smengerl/fusion-exporter)

## License

This project is licensed under the Creative Commons Attribution-ShareAlike 4.0 International License (CC BY-SA 4.0) — see `LICENSE.txt` for details or visit <http://creativecommons.org/licenses/by-sa/4.0/>

## Authors

- Simon Gerlach <https://github.com/Smenger>

---

If something in this README is missing or unclear, please open an issue in the repository so the instructions can be improved.
