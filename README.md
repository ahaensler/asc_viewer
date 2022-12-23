# LTspice ASC Viewer

[LTspice](https://www.analog.com/en/design-center/design-tools-and-calculators/ltspice-simulator.html) is one of the best schematic entry tools out there. It lets you draw any schematic imaginable. LTspice's simple appearance belies its true power.

- You can draw graphs for computer science.

- You can define buses.

- You can nest schematics for complex hierarchies.

**Now if only we could use these schematics in a Python GUI.**

![alt text](https://github.com/ahaensler/asc_viewer/blob/main/screenshot.png "Screenshot")

## AscCanvas
The AscCanvas class lets you import a schematic and show it as a wxPython window. It supports zooming, scrolling, searching and subclassing. It uses [rtreelib](https://github.com/lukas-shawford/rtreelib) to look up symbols and nets under the mouse pointer.

To show a schematic, you will need to import these files:

- ASY files are symbols, i.e., components, and they are imported in batch by specifying a list of paths. Load them by calling `AscCanvas.load_symbols()`

- ASC files are schematics. They define the connectivity between instances of symbols. Load them by calling `AscCanvas.load_asc()`.

## asc\_viewer
[asc_viewer](https://github.com/ahaensler/asc_viewer/blob/main/bin/asc_viewer) is a demo executable that lets you open schematics and shows how to use `AscCanvas`.

## Installation
```pip install asc_viewer```
