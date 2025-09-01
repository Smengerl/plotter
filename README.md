# gcode pen plotter

Plotter for drawing vector graphics in gcode format with a pen:

- Use any pin up to 11mm diameter
- rigid frame
- low cost components

<img src="./print/zsb/full_nocolor.png" alt="full assembly"/>

# Index
- [Mechanics](#Mechanics)
- [Electronics](#Electronics)
- [Software](#Software)
- [Acknowledgements](#Acknowledgements)


## Mechanics

### 3D printed parts

| Part | Material | Quantity |
| ---- | -------- | -------- |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/carriage_penholder_base.stl) | PLA / PETG | 1 |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/carriage_penholder_connector_fitting.stl) | TPU | 1 |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/carriage_penholder_connector_head.stl) | PLA / PETG | 1 |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/carriage_penholder_connector_screw.stl) | PLA / PETG | 1 |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/carriage.stl) | PLA / PETG | 1 |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/flat_steel_flange.stl) | PLA / PETG | 4 |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/flat_steel_lever.stl) | PLA / PETG | 1 |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/frame_back.stl) | PLA / PETG | 1 |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/frame_front.stl) | PLA / PETG | 1 |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/housing_back.stl) | PLA / PETG | 1 |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/housing_front.stl) | PLA / PETG | 1 |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/housing_feet.stl) | PLA / PETG | 4 |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/paper_guide_1.stl) | PLA / PETG | 1 |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/paper_guide_2.stl) | PLA / PETG | 1 |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/paper_guide_lever.stl) | PLA / PETG | 1 |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/paper_guide_pusher.stl) | PLA / PETG | 1 |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/paper_guide_lever.stl) | PLA / PETG | 1 |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/paper_intake_support.stl) | PLA / PETG | 1 |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/shaft_connector_flange.stl) | PLA / PETG | optional, if no standard couplers are used |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/shaft_end_flange.stl) | PLA / PETG | 1 |
| [STL-Vorschau](https://viewstl.com/?embedded&url=https://raw.githubusercontent.com/Smengerl/plotter/main/print/stl/solenoid_slider.stl) | PLA / PETG | 1 |

### Standard parts

| Quantity | Part | McMaster Part No | Note |
| -------- | ---- | ---------------- | ---- |
| 1 | 5mm/12mm shaft diameter couplings | 8819n55 | |
| 3 | Stainless Steel Ball Bearing, Flanged, Shielded | 57155K563 | |
| 2 | Stepper Motor with Square Body, NEMA 17 | 6627T64 | |
| 1 | Corrosion-Resistant Extension Spring with Loop Ends | 8464n179 | |
| 1 | Corrosion-Resistant HTD Timing Belt Pulley, 5mm width | 3684N12 | |
| 1 | Corrosion-Resistant HTD Timing Belt, 5mm width | - | |
| 1 | High-Strength HTD Timing Belt Idler Pulley, 5mm width | 3693N11 | | 
| 1 | hexagon socket screw, DIN EN ISO 4762 - M2 x 12 | - | For solenoid pin |
| 1 | hexagon nut, DIN 439-2 - M2 x 0.4 | - | For solenoid pin |
| 20 | hexagon socket screw, DIN EN ISO 4762 - M3 x 6 | - | Standard screw used unless otherwise specified |
| 4 | hexagon socket screw, DIN EN ISO 4762 - M3 x 30 | - | For shaft stepper |
| 10 | hexagon nut, DIN 439-2 - M3 x 0.6 | - | Insert in front and back frame |
| 1 | threaded pin, DIN EN ISO 4027 - M4 x 16 | - | For timing belt idler |
| 2 | hexagon socket screw, DIN EN ISO 4762 - M3 x 10 Stahl | - | For Carriage |
| 2 | hexagon nut, DIN 439-2 - M5 x 0.8 | - | For Rollers |
| 2 | hexagon socket screw, DIN EN ISO 4762 - M5 x 20 | - | For Rollers |
| 2 | V nut POM wheel roller | - | Rollers |


## Electronics

Coming soon



## Software

Coming soon