# Electronics Guide

This document provides recommended controller options, wiring notes and example pinouts for the G-code Pen Plotter. It is intended as a starting point — choose controllers and drivers that match your experience and available parts.

## Recommended controller options

- Arduino Uno to run GRBL and CNC shield to drive steppers

## Stepper drivers

Choose a driver compatible with your stepper motors and desired microstepping/noise characteristics.
Heat-sink stepper drivers and set current limits before running the motors under load.


## Power

12 V for common NEMA 17 motors and solenoid
Use a supply capable of providing peak current for both motors and solenoid

## Solenoid control

Use an N-channel MOSFET (logic-level) to switch the solenoid ground. Add a flyback diode across the solenoid coil and a gate resistor/pull-down on the MOSFET for reliability.
Test the solenoid switching with a bench power supply and a current-limited setup before connecting to the full system.

## Endstops

- The design uses two optical endstops (front and back). Connect them to digital input pins on the controller and enable internal pull-ups or use pull-up resistors if required.

## Firmware suggestions

GRBL (or a fork) — runs on many Arduino-style controllers and accepts standard G-code.


## Wiring diagram

TBD


## GRBL config 

TBD
