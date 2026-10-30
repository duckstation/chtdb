# DuckStation Cheats and Patches Database

This repository contains a collection of cheats and patches for PSX games, primarily intended for use with the DuckStation
emulator, but can also be used by other emulators that support GameShark codes.

Patches show in the UI in a separate section to cheats, and are intended for modifications to the game that do not provide
any "advantage" to the player, including:
 - Improving performance.
 - Fixing game-breaking bugs.
 - Unlocking the frame rate (e.g. "60 FPS patches").
 - Widescreen rendering where the built-in widescreen rendering rendering is insufficient.

If a modification makes the game "easier" for a player, or provides a clear advantage, it should be filed under cheats, not patches.

## Repository Format

A patch file for each game is located in either the `patches` or `cheats` subdirectory, depending on the category.

Each file is named either `SERIAL.cht`, or `SERIAL-HASH.cht`, where `HASH` is the XXHash hash provided by DuckStation.
The hash variant of files should only be used where multiple revisions of the game exist, and the executable has different
offsets which result in codes for one version not working with another.

## File Format

Files follow a syntax similar to the "INI" format. Each code begins with its name in square brackets, followed by its
metadata, then the code body:

```ini
[My Patch Code]
Type = Gameshark
Activation = EndFrame
Description = Additional text about what the code does, displayed as a tooltip.
Author = Name of patch author, optional.
A7001234 12345678
```

See [cheat-format.md](cheat-format.md) for the full specification, including:
 - Code types (`Gameshark` and `Assembly`).
 - Activation modes (`Manual`, `EndFrame` and `StartFrame`).
 - User choices (`Option` and `OptionRange`).
 - Setting overrides for patches (e.g. `OverrideAspectRatio`, `OverrideCPUOverclock`).
 - Authoring guidelines, and a reference for every supported GameShark code type.
