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

Files follow a syntax similar to the "INI" format, with the code body following any options.

Lines that begin with a semicolon (`;`) or hash (`#`) are comments, and ignored by the parser.

Each code should be preceded with its metadata, including the name of the code in square brackets. After all options are
listed, then the code body should be written without any escaping or additional characters. For example:

```ini
[My Patch Code]
Type = Gameshark
Activation = EndFrame
Description = Additional text about what the code does, displayed as a tooltip.
Author = Name of patch author, optional.
A7001234 12345678
```

Activation can be `Manual` or `EndFrame`, with manual codes requiring explicit one-shot triggering by the user, and end-frame
codes applying automatically at the end of the frame ("vsync").

### User Choices

Cheats can now allow users to pick a specific value for a given code, either between a developer-specified range, or from a list
of pre-determined options. The former will display as a spinbox on the UI, and the latter a dropdown box. The idea of the choice
option is to reduce the number of codes required for a game, as multiple codes can be replaced by a single dropdown/choice.

To create a range option, add the `OptionRange` key to the metadata, with the range specified as `min:max`.
For example: `OptionRange = 0:255`.

To create a choice option, add a `Option` key to the metadata, with the displayed name and value separated by a colon.
For exmaple: `Option = NameOfWeapon:50`. The option values are in decimal by default, `0x` or `0b` prefixes can be used for
hexadecimal or binary values respectively.

To utilize the user's choice in your code, simply replace the nibbles in the value with question marks. DuckStation will shift
the chosen option into the correct bit position if the `?` does not appear in the least significant bit position. For example:

```ini
[My Patch Code]
Type = Gameshark
Activation = EndFrame
Description = Overrides the number of lives.
OptionRange = 1:100
80001234 00??
```

This would write whichever value the user chose in the spinbox to the memory location 0x1234.

### Overriding Settings

Patches can apply settings to the game, including CPU overclock parameters and aspect ratios. These options should
be specified before the code body (e.g. `OverrideCPUOverclock = 200`).

 - `OverrideAspectRatio`: Sets the display aspect ratio to the corresponding value.
 - `OverrideCPUOverclock`: Sets the CPU overclock percentage to the corresponding value.
 - `DisableWidescreenRendering`: Disables the widescreen scaling for the GTE, if the user has it enabled.
 - `Enable8MBRAM`: Enables the 8MB dev console mode instead of the default 2MB.
 - `DisallowForAchievements`: Prevents the patch being used in [RetroAchievements](https://retroachievements.org/) hardcore mode.
