# DuckStation Cheat File Format

This document describes the format of the cheat and patch files in this repository, the metadata that can be attached
to each code, and every GameShark code type supported by DuckStation.

## Contents

- [File Layout](#file-layout)
- [Code Metadata](#code-metadata)
- [Code Types](#code-types)
  - [Gameshark](#gameshark)
  - [Assembly](#assembly)
- [Activation Modes](#activation-modes)
- [User Choices](#user-choices)
- [Setting Overrides (Patches Only)](#setting-overrides-patches-only)
- [Authoring Guidelines](#authoring-guidelines)
- [GameShark Code Reference](#gameshark-code-reference)
  - [Opcode Summary](#opcode-summary)
  - [Conventions](#conventions)
  - [32-Bit Code Types](#32-bit-code-types)
  - [16-Bit Code Types](#16-bit-code-types)
  - [8-Bit Code Types](#8-bit-code-types)
  - [Copy Data Code Types](#copy-data-code-types)
  - [Block Write Code Types](#block-write-code-types)
  - [Block Conditionals](#block-conditionals)
  - [Other Code Types](#other-code-types)
  - [Register Code Types](#register-code-types)
  - [Register Block Conditionals](#register-block-conditionals)

---

## File Layout

A file for each game is located in either the `patches` or `cheats` subdirectory, depending on the category. Each file
is named either `SERIAL.cht` or `SERIAL-HASH.cht`, where `HASH` is the XXHash hash provided by DuckStation. The hash
variant should only be used where multiple revisions of the game exist and the executable has different offsets, which
result in codes for one version not working with another.

Files follow a syntax similar to the INI format:

- Lines that begin with a semicolon (`;`) or hash (`#`) are comments and are ignored by the parser.
- Each code begins with its name in square brackets, followed by its metadata as `Key = Value` lines.
- After all metadata, the code body is written without any escaping or additional characters.

```ini
[My Patch Code]
Type = Gameshark
Activation = EndFrame
Description = Additional text about what the code does, displayed as a tooltip.
Author = Name of patch author, optional.
A7001234 12345678
```

A backslash (`\`) in the name groups codes under a common heading in the UI, e.g. `[Asteroids\P1 Infinite Lives]`.

## Code Metadata

| Key | Description |
| --- | --- |
| `Type` | How the body is interpreted: `Gameshark` (default) or `Assembly`. See [Code Types](#code-types). |
| `Activation` | When the code is applied: `Manual`, `EndFrame` (default) or `StartFrame`. See [Activation Modes](#activation-modes). |
| `Description` | Text describing the code, displayed as a tooltip. |
| `Author` | Name of the code's author. Optional. |
| `Option` | A named choice, as `Name:Value`. May be repeated. See [User Choices](#user-choices). |
| `OptionRange` | A numeric range of choices, as `min:max`. See [User Choices](#user-choices). |
| `Ignore` | When `true`, the code is skipped when loading. |

The following keys only apply to patches. See [Setting Overrides](#setting-overrides-patches-only) for details.

| Key | Description |
| --- | --- |
| `OverrideAspectRatio` | Sets the display aspect ratio. |
| `OverrideCPUOverclock` | Sets the CPU overclock percentage. |
| `DisableWidescreenRendering` | Disables widescreen rendering. |
| `ForcePGXPPreserveProjectionPrecision` | Enables PGXP "Preserve Projection Precision". |
| `Enable8MBRAM` | Enables 8MB RAM mode. |
| `DisallowForAchievements` | Prevents use in RetroAchievements hardcore mode. |

## Code Types

The `Type` key selects how the code body is interpreted. If it is omitted, `Gameshark` is assumed.

### Gameshark

The body is a list of GameShark-style hexadecimal codes, one per line, in the formats described in the
[GameShark Code Reference](#gameshark-code-reference). These support every [activation mode](#activation-modes).

```ini
[Infinite Health]
Type = Gameshark
Activation = EndFrame
8005DF0A 0000
```

### Assembly

The body is written as MIPS R3000A assembly, which DuckStation assembles when the code is loaded. Each instruction
becomes a 32-bit word written to memory, so large ASM patches can be written readably without hand-assembling them into
`90`/`A9` codes.

```ini
[Example Assembly Code]
Type = Assembly
Activation = EndFrame
.org 0x80010000
  lui   v0, 0x8001
  lw    v0, 0x10(v0)
  beq   v0, zero, done
  nop
  addiu v0, v0, 1
done:
  jr    ra
```

Syntax:

- **Starting address**: `.org 0x80010000`, or an address followed by a colon (`80010000:`), sets the address of the next
  instruction. Each instruction then advances the address by 4 bytes. Addresses must be word-aligned, and several
  `.org` lines can be used to patch separate locations in a single code. An instruction must have a starting address
  before it.
- **Instructions**: standard R3000A mnemonics (including `nop` and GTE instructions), using register names such as
  `v0`, `a0`, `ra` or `zero`. The `$` prefix is optional.
- **Labels**: `name:` defines a label at the current address, which can be used as a branch or jump target. Labels may be
  referenced before they are defined. Label names cannot start with a digit, `+` or `-`, and cannot contain `?` or
  whitespace.
- **Comments**: anything after `;` or `#` on a line is ignored.
- **User choices**: one contiguous group of up to 8 `?` characters may be used in an operand, and is replaced by the
  user's chosen value. The `?` digits must map to a single contiguous field of the instruction (e.g. an immediate).
  See [User Choices](#user-choices).

Behaviour:

- Assembly codes only support automatic activation (`EndFrame` or `StartFrame`); `Manual` is rejected.
- Each frame, any word that does not hold the assembled instruction is overwritten, and its previous value is remembered.
- When the code is disabled, each word that still holds the assembled instruction is restored to its previous value,
  similar to the `A7`/`AA` GameShark types.
- Each address may only be written once per code.

## Activation Modes

The `Activation` key selects when a code is applied. If it is omitted, `EndFrame` is assumed.

| Value | UI name | Behaviour |
| --- | --- | --- |
| `Manual` | Manual | Applied once, only when the user explicitly triggers it from the cheats menu. Not supported for `Assembly` codes. |
| `EndFrame` | Automatic (Frame End) | Applied automatically every frame at the end of the frame (the start of vertical blank, "vsync"). This is the usual choice. |
| `StartFrame` | Automatic (Frame Start) | Applied automatically every frame at the start of the frame (the end of vertical blank). |

`StartFrame` exists because some codes rely on the handler running at the end of vblank rather than the start, after the
game's own vblank processing, and some hardware cheat devices also behave this way. Use it only when a code does not work
correctly with `EndFrame`: while any `StartFrame` code is active, DuckStation has to schedule an additional event every
frame to run it.

## User Choices

Cheats can allow users to pick a specific value for a code, either from a developer-specified range or from a list of
pre-determined options. A range is shown as a spinbox in the UI, and a list as a dropdown box. This reduces the number of
codes required for a game, as multiple codes can be replaced by a single choice.

- **Range**: add the `OptionRange` key with the range as `min:max`, e.g. `OptionRange = 0:255`.
- **List**: add an `Option` key for each choice, with the displayed name and value separated by a colon, e.g.
  `Option = NameOfWeapon:50`.

Values are in decimal by default; `0x` or `0b` prefixes can be used for hexadecimal or binary values respectively.

To use the chosen value in your code, replace the nibbles in the value with question marks. DuckStation shifts the
chosen value into the correct bit position if the `?` does not appear in the least significant position.

```ini
[Number of Lives]
Type = Gameshark
Activation = EndFrame
Description = Overrides the number of lives.
OptionRange = 1:100
80001234 00??
```

This writes whichever value the user chose in the spinbox to address `0x80001234`.

Question marks cannot be used in the data lines of [block write codes](#block-write-code-types). For `Assembly` codes,
see [Assembly](#assembly).

## Setting Overrides (Patches Only)

Patches can change emulator settings while they are enabled, such as the CPU overclock or aspect ratio. These keys are
only honoured for codes in the `patches` directory; they have no effect on cheats. They should be specified before the
code body (e.g. `OverrideCPUOverclock = 200`).

| Key | Value | Effect |
| --- | --- | --- |
| `OverrideAspectRatio` | Aspect ratio, e.g. `16:9` | Sets the display aspect ratio, if the user's aspect ratio is set to Auto. |
| `OverrideCPUOverclock` | Percentage, e.g. `200` | Sets the CPU overclock percentage, if the user has not already enabled overclocking. |
| `DisableWidescreenRendering` | `true`/`false` | Disables widescreen scaling for the GTE, if the user has it enabled. |
| `ForcePGXPPreserveProjectionPrecision` | `true`/`false` | Enables the PGXP "Preserve Projection Precision" option. |
| `Enable8MBRAM` | `true`/`false` | Enables the 8MB dev console mode instead of the default 2MB. |
| `DisallowForAchievements` | `true`/`false` | Prevents the patch being used in [RetroAchievements](https://retroachievements.org/) hardcore mode. |

## Authoring Guidelines

1. **Comments**: start any comment lines with a semi-colon. This can be useful to split up sections of cheats to improve
   readability, as well as to add comments to aid in understanding of the cheats. These comments do not appear in
   DuckStation, so remember to keep explanations in cheats for users. Try to keep comment lines under 80 characters.
2. **Naming**: the cheat naming convention for multiplayer games is `Px Cheat Description`, where `x` is the player
   number, e.g. `P1 Infinite Lives`. If the cheat is for all players, or you have only tested it for P1, then don't
   mention P1, e.g. `Infinite Lives`.
3. **Ordering**: try to order cheats in a logical order if possible, like so:
   - Cheats for all players for all levels
   - Cheats for P1 for all levels
   - Cheats for P2 for all levels
   - Cheats for P3 for all levels
   - Cheats for P4 for all levels
   - Cheats for all players for level 1
   - Cheats for P1 for level 1
   - Cheats for P2 for level 1
   - Cheats for P3 for level 1
   - Cheats for P4 for level 1
   - Cheats for all players for level 2
   - Cheats for P1 for level 2
   - Cheats for P2 for level 2
   - Cheats for P3 for level 2
   - Cheats for P4 for level 2
   - ...repeat for other levels
   - Cheats that you don't want to appear in the above list. These should be kept for Debug Mode Cheats, 60FPS Cheats and
     the like.
4. **Grouping**: cheats should be grouped, if possible and worthwhile, using the backslash (`\`) character. This is
   especially true for cheats that poke the same address(es) with different value(s). This makes it
   easier to skip long option lists in the cheat menus when you only need to enable one option. Where possible, prefer a single code with
   [user choices](#user-choices).
5. **Header format** (`chtdb.txt` only): each game begins with a header comment and one line per serial:

   ```
   ; [ Game Name (Region) (Year) (Publisher) {GAME_ID Numbers} <mameshortname> ]
   :GAME_ID1
   :GAME_ID2
   ```

   with each cheat name prefixed by `#`, e.g. `#Infinite Health`.

---

## GameShark Code Reference

### Opcode Summary

Codes are identified by their first byte (or first two bytes for `51`/`52` register codes). Width is the size of the
memory access.

| Opcode | Width | Name | Notes |
| --- | --- | --- | --- |
| [`10`](#16-bit-code-types) | 16 | Increment Once | |
| [`11`](#16-bit-code-types) | 16 | Decrement Once | |
| [`1F`](#16-bit-code-types) | 16 | Scratchpad Constant Write | |
| [`20`](#8-bit-code-types) | 8 | Increment Once | |
| [`21`](#8-bit-code-types) | 8 | Decrement Once | |
| [`30`](#8-bit-code-types) | 8 | Constant Write | Common |
| [`31`](#8-bit-code-types) | 8 | Constant Bit Set | |
| [`32`](#8-bit-code-types) | 8 | Constant Bit Clear | |
| [`50`](#50-serial-repeaterslide) | 8/16 | Serial Repeater/Slide | 2 lines |
| [`51`](#register-code-types) | 8/16/32 | Register Operations | |
| [`52`](#register-block-conditionals) | 8/16/32 | Register Block Conditionals | Block |
| [`53`](#53-improved-serial-repeaterslide) | 8/16/32 | Improved Serial Repeater/Slide | 2 lines |
| [`60`](#32-bit-code-types) | 32 | Increment Once | |
| [`61`](#32-bit-code-types) | 32 | Decrement Once | |
| [`80`](#16-bit-code-types) | 16 | Constant Write | Common |
| [`81`](#16-bit-code-types) | 16 | Constant Bit Set | |
| [`82`](#16-bit-code-types) | 16 | Constant Bit Clear | |
| [`90`](#32-bit-code-types) | 32 | Constant Write | |
| [`91`](#32-bit-code-types) | 32 | Constant Bit Set | |
| [`92`](#32-bit-code-types) | 32 | Constant Bit Clear | |
| [`A0`](#32-bit-code-types) | 32 | If Equal To | Next code |
| [`A1`](#32-bit-code-types) | 32 | If Not Equal To | Next code |
| [`A2`](#32-bit-code-types) | 32 | If Less Than | Next code |
| [`A3`](#32-bit-code-types) | 32 | If Greater Than | Next code |
| [`A4`](#block-conditionals) | 32 | Master Code (Equal) | Block |
| [`A5`](#32-bit-code-types) | 32 | Scratchpad Constant Write | |
| [`A6`](#32-bit-code-types) | 16 | If Equal To Write | |
| [`A7`](#32-bit-code-types) | 16 | If Equal To Write with Restore | DuckStation |
| [`A8`](#8-bit-code-types) | 8 | If Equal To Write with Restore | DuckStation |
| [`A9`](#a9-32-bit-block-write) | 32 | Block Write | DuckStation, multi-line |
| [`AA`](#aa-32-bit-block-if-equal-to-write-with-restore) | 32 | Block If Equal To Write with Restore | DuckStation, multi-line |
| [`AB`](#ab-32-bit-block-if-equal-to-write) | 32 | Block If Equal To Write | DuckStation, multi-line |
| [`C0`](#block-conditionals) | 16 | Master Code (Equal) | Block |
| [`C1`](#other-code-types) | - | Activate Codes On Delay | |
| [`C2`](#c2-copy-memory) | - | Copy Memory | 2 lines |
| [`C3`](#block-conditionals) | 8 | Master Code (Less Than) | Block |
| [`C4`](#block-conditionals) | 8 | Master Code (Greater Than) | Block |
| [`C5`](#block-conditionals) | 16 | Master Code (Less Than) | Block |
| [`C6`](#block-conditionals) | 16 | Master Code (Greater Than) | Block |
| [`D0`](#16-bit-code-types) | 16 | If Equal To | Next code |
| [`D1`](#16-bit-code-types) | 16 | If Not Equal To | Next code |
| [`D2`](#16-bit-code-types) | 16 | If Less Than | Next code |
| [`D3`](#16-bit-code-types) | 16 | If Greater Than | Next code |
| [`D4`](#16-bit-code-types) | 16 | Universal Joker | Next code |
| [`D5`](#block-conditionals) | 16 | All Codes On | |
| [`D6`](#block-conditionals) | 16 | All Codes Off | |
| [`D7`](#d7-24-bit-universal-bit-joker) | 24 | Universal BIT Joker | Block |
| [`E0`](#8-bit-code-types) | 8 | If Equal To | Next code |
| [`E1`](#8-bit-code-types) | 8 | If Not Equal To | Next code |
| [`E2`](#8-bit-code-types) | 8 | If Less Than | Next code |
| [`E3`](#8-bit-code-types) | 8 | If Greater Than | Next code |
| [`F0`](#32-bit-code-types) | 8 | Force Range | |
| [`F1`](#32-bit-code-types) | 16 | Force Range to Limit | |
| [`F2`](#32-bit-code-types) | 16 | Force Range to Opposite Limit | |
| [`F3`](#f3-16-bit-force-range) | 16 | Force Range | 2 lines |
| [`F4`](#f4-8-bit-find-and-replace) | 8 | Find and Replace | 5 lines |
| [`F5`](#32-bit-code-types) | 16 | Toggle | |
| `FB`-`FE` | - | Reserved | Internal use; codes using these won't load |

"Next code" conditionals only affect the code on the following line. "Block" conditionals affect every following code
until a `00000000 FFFF` line or the end of the cheat.

### Conventions

- `(address)` = the current value stored in the address.
- **Note:** codes will only ever contain hexadecimal characters (`0`-`F`). Any other characters (like `WXYZ`) in the
  following descriptions are for documentation purposes only.
- Addresses are written as `XXXXXX` and refer to `$80XXXXXX` in RAM unless otherwise stated.

### 32-Bit Code Types

8 Char by 8 Char code types (includes 32 bit codes). Several 8- and 16-bit types are also listed here, as they need the
longer format.

| Code | Name | Description |
| --- | --- | --- |
| `90XXXXXX YYYYYYYY` | 32-Bit Constant Write | Poke `$80XXXXXX` with `0xYYYYYYYY`. |
| `91XXXXXX YYYYYYYY` | 32-Bit Constant Bit Set | OR `($80XXXXXX)` with `0xYYYYYYYY` and Poke. |
| `92XXXXXX YYYYYYYY` | 32-Bit Constant Bit Clear | AND `($80XXXXXX)` with `~0xYYYYYYYY` and Poke. |
| `A0XXXXXX YYYYYYYY` | 32-Bit If Equal To | Activate next code if `(80XXXXXX) == 0xYYYYYYYY`. |
| `A1XXXXXX YYYYYYYY` | 32-Bit If Not Equal To | Activate next code if `(80XXXXXX) != 0xYYYYYYYY`. |
| `A2XXXXXX YYYYYYYY` | 32-Bit If Less Than | Activate next code if `(80XXXXXX) < 0xYYYYYYYY`. |
| `A3XXXXXX YYYYYYYY` | 32-Bit If Greater Than | Activate next code if `(80XXXXXX) > 0xYYYYYYYY`. |
| `60XXXXXX YYYYYYYY` | 32-Bit Increment Once | Poke `$80XXXXXX` with `($80XXXXXX) + 0xYYYYYYYY`. |
| `61XXXXXX YYYYYYYY` | 32-Bit Decrement Once | Poke `$80XXXXXX` with `($80XXXXXX) - 0xYYYYYYYY`. |
| `A5000XXX YYYYYYYY` | 32-Bit Scratchpad Constant Write | Poke `$1F800XXX` with `YYYYYYYY`, where `XXX` is between `000` & `3FF`. |
| `A6XXXXXX YYYYZZZZ` | 16-Bit If Equal To Write | If `(80XXXXXX) == 0xYYYY`, Poke `$80XXXXXX` with `0xZZZZ`. A single line alternative to a `D0`/`80` code pair which uses the same address. |
| `A7XXXXXX YYYYZZZZ` | 16-Bit If Equal To Write with Restore | If `(80XXXXXX) == 0xYYYY`, Poke `$80XXXXXX` with `0xZZZZ`. On disabling the cheat, if `(80XXXXXX) == 0xZZZZ`, Poke `$80XXXXXX` with `0xYYYY`. This can be used for an ASM cheat that has poked dynamic memory with less danger of crashing the game, or for 16:9 cheats to go back to 4:3 when disabled. |
| `F0XXXXXX HHSSULLL` | 8-Bit Force Range | If `(80XXXXXX) < 0xLL`, Poke `$80XXXXXX` with `0xSS`. If `(80XXXXXX) > 0xUL`, Poke `$80XXXXXX` with `0xHH`. |
| `F1XXXXXX ULULLLLL` | 16-Bit Force Range to Limit | If `(80XXXXXX) < 0xLLLL`, Poke `$80XXXXXX` with `0xLLLL`. If `(80XXXXXX) > 0xULUL`, Poke `$80XXXXXX` with `0xULUL`. |
| `F2XXXXXX ULULLLLL` | 16-Bit Force Range to Opposite Limit | If `(80XXXXXX) < 0xLLLL`, Poke `$80XXXXXX` with `0xULUL`. If `(80XXXXXX) > 0xULUL`, Poke `$80XXXXXX` with `0xLLLL`. |
| `F5XXXXXX YYYYZZZZ` | 16-Bit Toggle | If `(80XXXXXX) == 0xYYYY`, Poke `$80XXXXXX` with `0xZZZZ`. If `(80XXXXXX) == 0xZZZZ`, Poke `$80XXXXXX` with `0xYYYY`. |

#### `F3`: 16-Bit Force Range

```
F3XXXXXX ULULLLLL
F3000000 HHHHSSSS
```

If `(80XXXXXX) < 0xLLLL`, Poke `$80XXXXXX` with `0xSSSS`. If `(80XXXXXX) > 0xULUL`, Poke `$80XXXXXX` with `0xHHHH`.

#### `F4`: 8-Bit Find and Replace

```
F4XXXXXY 00WWSIZE
aabbccdd eeffgghh
iijjkkll mmnnoopp
AABBCCDD EEFFGGHH
IIJJKKLL MMNNOOPP
```

Find and Replace for 16 bytes.

| Field | Meaning |
| --- | --- |
| `WW` | Wildcard Byte. |
| `SIZE` | Size of Area to Search / 4, so `FFFF` = 256K. |
| `XXXXXY` | Address at the centre of the Search Area (`Y` must be even: `0/2/4/6/8/A/C/E`). |

Find `aa`,`bb`,`cc`,`dd`,`ee`,`ff`,`gg`,`hh`,`ii`,`jj`,`kk`,`ll`,`mm`,`nn`,`oo`,`pp` and replace with
`AA`,`BB`,`CC`,`DD`,`EE`,`FF`,`GG`,`HH`,`II`,`JJ`,`KK`,`LL`,`MM`,`NN`,`OO`,`PP`.

Any byte matching the `WW` character in the find bytes will be ignored. Any byte matching the `WW` character in the
replace bytes will be ignored; ideally all bytes in the replace line should be `WW`, with the exception of where an
actual replacement is required.

### 16-Bit Code Types

| Code | Name | Description |
| --- | --- | --- |
| `80XXXXXX YYYY` | 16-Bit Constant Write | Poke `$80XXXXXX` with `0xYYYY`. **COMMON** |
| `81XXXXXX YYYY` | 16-Bit Constant Bit Set | OR `($80XXXXXX)` with `0xYYYY` and Poke. |
| `82XXXXXX YYYY` | 16-Bit Constant Bit Clear | AND `($80XXXXXX)` with `~0xYYYY` and Poke. |
| `D0XXXXXX YYYY` | 16-Bit If Equal To | Activate next code if `(80XXXXXX) == 0xYYYY`. |
| `D1XXXXXX YYYY` | 16-Bit If Not Equal To | Activate next code if `(80XXXXXX) != 0xYYYY`. |
| `D2XXXXXX YYYY` | 16-Bit If Less Than | Activate next code if `(80XXXXXX) < 0xYYYY`. |
| `D3XXXXXX YYYY` | 16-Bit If Greater Than | Activate next code if `(80XXXXXX) > 0xYYYY`. |
| `D4000000 YYYY` | 16-Bit Universal Joker | Activates the next code when the buttons in `YYYY` are pressed. Add up the hex values to combine into a multi-button joker. See the [button table](#button-values). |
| `10XXXXXX YYYY` | 16-Bit Increment Once | Poke `$80XXXXXX` with `($80XXXXXX) + 0xYYYY`. |
| `11XXXXXX YYYY` | 16-Bit Decrement Once | Poke `$80XXXXXX` with `($80XXXXXX) - 0xYYYY`. |
| `1F000XXX YYYY` | 16-Bit Scratchpad Constant Write | Poke `$1F800XXX` with `YYYY`, where `XXX` is between `000` & `3FF`. |

### 8-Bit Code Types

| Code | Name | Description |
| --- | --- | --- |
| `30XXXXXX 00YY` | 8-Bit Constant Write | Poke `$80XXXXXX` with `0xYY`. **COMMON** |
| `31XXXXXX 00YY` | 8-Bit Constant Bit Set | OR `($80XXXXXX)` with `0xYY` and Poke. |
| `32XXXXXX 00YY` | 8-Bit Constant Bit Clear | AND `($80XXXXXX)` with `~0xYY` and Poke. |
| `E0XXXXXX 00YY` | 8-Bit If Equal To | Activate next code if `(80XXXXXX) == 0xYY`. |
| `E1XXXXXX 00YY` | 8-Bit If Not Equal To | Activate next code if `(80XXXXXX) != 0xYY`. |
| `E2XXXXXX 00YY` | 8-Bit If Less Than | Activate next code if `(80XXXXXX) < 0xYY`. |
| `E3XXXXXX 00YY` | 8-Bit If Greater Than | Activate next code if `(80XXXXXX) > 0xYY`. |
| `20XXXXXX 00YY` | 8-Bit Increment Once | Poke `$80XXXXXX` with `($80XXXXXX) + 0xYY`. |
| `21XXXXXX 00YY` | 8-Bit Decrement Once | Poke `$80XXXXXX` with `($80XXXXXX) - 0xYY`. |
| `A8XXXXXX YYZZ` | 8-Bit If Equal To Write with Restore | If `(80XXXXXX) == 0xYY`, Poke `$80XXXXXX` with `0xZZ`. On disabling the cheat, if `(80XXXXXX) == 0xZZ`, Poke `$80XXXXXX` with `0xYY`. This can be used for an ASM cheat that has poked dynamic memory with less danger of crashing the game, or for 16:9 cheats to go back to 4:3 when disabled. This is a byte type sister to `A7`, and just like the `A7` type this is unique to DuckStation. |

### Copy Data Code Types

#### `C2`: Copy Memory

```
C2XXXXXX YYYY
80ZZZZZZ 0000
```

Copy memory between `$80XXXXXX` and `$80XXXXXX+0xYYYY` to `$80ZZZZZZ`.

#### `50`: Serial Repeater/Slide

```
5000PPQQ TTTT
X0YYYYYY ZZZZ
```

Pokes multiple serially increasing addresses with a possibly increasing value.

| Field | Meaning |
| --- | --- |
| `poke_size` = `X0` | `30` for byte or `80` for word. |
| `start_address` = `YYYYYY` | |
| `start_value` = `ZZZZ` | |
| `number_of_addresses` = `PP` | Needs to be > `02` to be worthwhile. |
| `address_step` = `QQ` | Commonly `01` for type `30`, `02` for type `80`. |
| `value_step` = `TTTT` | Most commonly `0000`. |

#### `53`: Improved Serial Repeater/Slide

```
53WVPPPP QQQQTTTT
X0YYYYYY ZZZZZZZZ
```

Pokes multiple serially changing addresses with a possibly changing value.

| Field | Meaning |
| --- | --- |
| `address_change` = `W` | `0` = increasing, `1` = decreasing. |
| `value_change` = `V` | `0` = increasing, `1` = decreasing. |
| `poke_size` = `X0` | `30` for byte, `80` for word or `90` for longword. |
| `start_address` = `YYYYYY` | |
| `start_value` = `ZZZZZZZZ` | |
| `number_of_addresses` = `PPPP` | Needs to be > `02` to be worthwhile. |
| `address_step` = `QQQQ` | Commonly `01` for type `30`, `02` for type `80`, `04` for type `90`. |
| `value_step` = `TTTT` | Most commonly `0000`. |

### Block Write Code Types

These write a block of `NNNNNNNN` 32-bit words starting at `$80XXXXXX` in a single code. Each word is written exactly as
a `90` code would write it. They are much faster than long lists of `90`/`80`/`30` codes, so use them for big ASM
patches. These are unique to DuckStation. (An [Assembly](#assembly) code may be easier to write and read.)

The whole block must be within RAM. The data lines can't use `?` options. If a
`D0`/`D1`/`D2`/`D3`/`E0`/`E1`/`E2`/`E3`/`A0`/`A1`/`A2`/`A3`/`D4` conditional before one of these codes isn't met, the
whole block is skipped.

#### `A9`: 32-Bit Block Write

```
A9XXXXXX NNNNNNNN
aaaaaaaa bbbbbbbb
cccccccc dddddddd
........ ........
```

Poke `NNNNNNNN` words starting at `$80XXXXXX` with `aaaaaaaa`,`bbbbbbbb`,`cccccccc`,`dddddddd`... in that order. There
are `NNNNNNNN/2` data lines (rounded up), and if `NNNNNNNN` is odd the last value on the last line is ignored; use
`00000000` for it.

For example:

```
A9010000 00000003
3C028001 8C420010
24420001 00000000  <- 00000000 is ignored
```

This is the same as:

```
90010000 3C028001
90010004 8C420010
90010008 24420001
```

#### `AA`: 32-Bit Block If Equal To Write with Restore

```
AAXXXXXX NNNNNNNN
aaaaaaaa AAAAAAAA
bbbbbbbb BBBBBBBB
cccccccc CCCCCCCC
........ ........
```

There are `NNNNNNNN` data lines. If **ALL** of the `NNNNNNNN` words starting at `$80XXXXXX` equal
`aaaaaaaa`,`bbbbbbbb`,`cccccccc`... then Poke them with `AAAAAAAA`,`BBBBBBBB`,`CCCCCCCC`... If any word doesn't match,
nothing is poked, so a different overlay never gets half patched. On disabling the cheat, if **ALL** of the words equal
`AAAAAAAA`,`BBBBBBBB`,`CCCCCCCC`... they are poked back with `aaaaaaaa`,`bbbbbbbb`,`cccccccc`... This is a block sister
to `A7`, and like `A7` it is good for ASM cheats in overlays, or 16:9 cheats that go back to 4:3 when disabled.

#### `AB`: 32-Bit Block If Equal To Write

```
ABXXXXXX NNNNNNNN
aaaaaaaa AAAAAAAA
bbbbbbbb BBBBBBBB
........ ........
```

The same as `AA`, but without the restore when the cheat is disabled.

For example:

```
AB0A1230 00000003
0C02A4B6 00000000  <- jal 0x800A92D8  -> nop
24020001 24020000  <- addiu v0,zero,1 -> addiu v0,zero,0
AE020010 AE000010  <- sw v0,16(s0)    -> sw zero,16(s0)
```

This only patches `$800A1230`-`$800A123B` if all 3 original instructions are there.

> Code types `FB`, `FC`, `FD` and `FE` are reserved for DuckStation's internal use, and cheats that use them won't load.

### Block Conditionals

If the condition is met, these will execute all the following codes until either a `00000000 FFFF` line is reached or
the end of that cheat is reached. You should always use a `00000000 FFFF` line though (don't be lazy!).

```
C0XXXXXX YYYY
........ ....
00000000 FFFF
```

| Code | Name | Description |
| --- | --- | --- |
| `A4XXXXXX YYYYYYYY` | 32-Bit Master Code | If `($XXXXXX)` contains `0xYYYYYYYY`, poke all following codes for the rest of the cheat or until it reaches the `00000000 FFFF` line. |
| `C0XXXXXX YYYY` | 16-Bit Master Code | If `($XXXXXX)` contains `0xYYYY`, poke all following codes for the rest of the cheat or until it reaches the `00000000 FFFF` line. |
| `C3XXXXXX 00YY` | 8-Bit Master Code | If `($XXXXXX)` is less than `0xYY`, poke all following codes for the rest of the cheat or until it reaches the `00000000 FFFF` line. |
| `C4XXXXXX 00YY` | 8-Bit Master Code | If `($XXXXXX)` is greater than `0xYY`, poke all following codes for the rest of the cheat or until it reaches the `00000000 FFFF` line. |
| `C5XXXXXX YYYY` | 16-Bit Master Code | If `($XXXXXX)` is less than `0xYYYY`, poke all following codes for the rest of the cheat or until it reaches the `00000000 FFFF` line. |
| `C6XXXXXX YYYY` | 16-Bit Master Code | If `($XXXXXX)` is greater than `0xYYYY`, poke all following codes for the rest of the cheat or until it reaches the `00000000 FFFF` line. |
| `D5000000 YYYY` | 16-Bit All Codes On | |
| `D6000000 YYYY` | 16-Bit All Codes Off | |
| `D7PQRRRR TTYYYYYY` | 24-Bit Universal BIT Joker | See [below](#d7-24-bit-universal-bit-joker). |
| `52...... ........` | Register Master Code | Tests the cheat registers, poking all following codes for the rest of the cheat or until it reaches the `00000000 FFFF` line. See [Register Block Conditionals](#register-block-conditionals). |

#### `D7`: 24-Bit Universal BIT Joker

```
D7PQRRRR TTYYYYYY
........ ........
00000000 FFFF
```

OR the hex values to combine into a multi-button joker. Because it is BIT based, it is better than `D4`, `D5`, `D6` or
using a `D0` joker, as you do not need to worry about any other buttons being pressed at the same time, and you get both
analog sticks for extra functionality. Note: if you just want to use it as an enhanced joker, use
`D7000000 00YYYYYY` when the buttons/directions are pressed, or `D7100000 00YYYYYY` when you want to ensure they are not
all pressed.

`YYYYYY` specifies the buttons to check; see the [button table](#button-values).

| `P` | Meaning |
| --- | --- |
| `0` | Check **ALL** `YYYYYY` Bits are ON |
| `1` | Check **ALL** `YYYYYY` Bits are OFF |

`QRRRR TT` provides the capability of only activating the following codes after the keys have been held for a set
number of frames. `003C` = 60 Frames = 1 Second at 100% Speed.

| `Q` | Frame Comparison |
| --- | --- |
| `0` | Don't do any comparison. |
| `1` | Check that the button combination has been held down for exactly `RRRR` frames. |
| `2` | Check that the button combination has been held down for at least `RRRR` frames. |
| `3` | Check that the button combination has been held down for less than `RRRR` frames. |
| `4` | Check that the button combination has been held down for anything but `RRRR` frames. |

| Field | Meaning |
| --- | --- |
| `TT` | Temp Register `00`-`FF`. `00` will mean it won't be used. If it's not `00`, do not use the same value for jokers using different keypress combinations for the same game. |
| `RRRR` | `0000` to `FFFF`, Frame Comparison Value. |

> **Note:** if you have multiple `D7` lines using frame counting and the same register, the temp register will be out by
> that factor, e.g. if you have 2 `D7` lines accessing register `05`, then after 60 frames register `05` will contain
> 120 (`0x78`).

It will then poke all following codes for the rest of the cheat or until it reaches the `00000000 FFFF` line.

#### Button Values

Used by [`D4`](#16-bit-code-types) (`YYYY`, add up the values) and [`D7`](#d7-24-bit-universal-bit-joker) (`YYYYYY`,
OR the values).

| `D4` (`YYYY`) | `D7` (`YYYYYY`) | Button |
| --- | --- | --- |
| `0000` | - | Nothing |
| `0001` | `000001` | L2 Button |
| `0002` | `000002` | R2 Button |
| `0004` | `000004` | L1 Button |
| `0008` | `000008` | R1 Button |
| `0010` | `000010` | Triangle Button |
| `0020` | `000020` | Circle Button |
| `0040` | `000040` | X Button |
| `0080` | `000080` | Square Button |
| `0100` | `000100` | Select Button |
| `0200` | `000200` | L3 Button |
| `0400` | `000400` | R3 Button |
| `0800` | `000800` | Start Button |
| `1000` | `001000` | Up Direction (Digital) |
| `2000` | `002000` | Right Direction (Digital) |
| `4000` | `004000` | Down Direction (Digital) |
| `8000` | `008000` | Left Direction (Digital) |
| - | `010000` | Up (Right Thumb) |
| - | `020000` | Right (Right Thumb) |
| - | `040000` | Down (Right Thumb) |
| - | `080000` | Left (Right Thumb) |
| - | `100000` | Up (Left Thumb) |
| - | `200000` | Right (Left Thumb) |
| - | `400000` | Down (Left Thumb) |
| - | `800000` | Left (Left Thumb) |

### Other Code Types

These are only needed on hardware, when you can't enable & disable codes after the game has started without the use of
delays or global jokers. They are supported by DuckStation, but ideally don't use them if you can help it.

| Code | Name |
| --- | --- |
| `C1XXXXXX YYYY` | Activate Codes On Delay |

### Register Code Types

These codes utilise the 256 internal global 32-bit cheat registers. As they are global, they will work across all cheats
for a game, so be careful not to re-use registers unintentionally. Type `51` codes can be used to copy and manipulate
register contents between registers and memory. Type `52` codes are [block conditionals](#register-block-conditionals)
that you can test the registers with and branch accordingly.

These code types will only need to be used with very advanced cheats. Only use them if you need them, as they may blow
your mind...

#### General Notes

| Notation | Meaning |
| --- | --- |
| `RegXX` or `RegYY` | The immediate value of the register. |
| `(RegXX)` or `(RegYY)` | The indirect value of the register = contents of the address held in `RegXX` or `RegYY`. |
| `TTTTTTTT` | Write to Address `TTTTTTTT`. |
| `(TTTTTTTT)` | Read from Address `TTTTTTTT`. |
| `ZZ`, `ZZZZ`, `ZZZZZZZZ` | Value. |

Note: `RegXX`, `RegYY` and `RegWW` can be the same register.

#### 8-Bit Operations

| Code | Name | Description | Operation |
| --- | --- | --- | --- |
| `510000XX TTTTTTTT` | 8-Bit Address Write from Register | Poke address `TTTTTTTT` with the 8-bit contents of Register `XX`. | `u8Poke TTTTTTTT, RegXX` |
| `510100XX TTTTTTTT` | 8-Bit Address Read to Register | Peek the 8-bit contents of address `TTTTTTTT` and store it in Register `XX`. | `u8Poke RegXX, (TTTTTTTT)` |
| `510200XX 000000ZZ` | 8-Bit Indirect Register Write | Poke `ZZ` to the 32-bit address stored in Register `XX`. | `u8Poke (RegXX), ZZ` |
| `5103YYXX 000000ZZ` | 8-Bit Register Addition | Add `ZZ` and the 8-bit contents of Register `YY` together and write the result to Register `XX`. | `u8Poke RegXX, RegYY + ZZ` |
| `5104YYXX 000000ZZ` | 8-Bit Indirect Register Write with Addition | Add `ZZ` and the 8-bit contents of Register `YY` together and write the result to the 32-bit address stored in Register `XX`. | `u8Poke (RegXX), RegYY + ZZ` |
| `510500XX 000000ZZ` | 8-Bit Direct Register Write | Poke `ZZ` to Register `XX`. | `u8Poke RegXX, ZZ` |
| `5106YYXX ZZZZZZZZ` | 8-Bit Indirect Register Read | Peek the 8-bit contents of (32-bit address in Register `YY` + `ZZZZZZZZ`) and write it to Register `XX`. | `u8Poke RegXX, (RegYY + ZZZZZZZZ)` |
| `510700XX YYYY00ZZ` | 8-Bit Indirect Register Write of an Array of Arrays element | See [below](#5107-array-of-arrays-element-write). | |

#### `5107`: Array of Arrays Element Write

```
510700XX YYYY00ZZ
```

8-Bit Indirect Register Write of an Array of Arrays element. It will require four consecutive cht registers to be set up
in a separate cheat for it to do anything.

| Field | Meaning |
| --- | --- |
| `XX` | Will be the 1st of 4 consecutive cht registers that will be used. |
| `YYYY` | Will be the index of the array to be changed. |
| `ZZ` | Will be the value to poke. |

Example:

```ini
[Technique Slot Modifier\*MASTER* Select Slot No. (1 - 1349) for following cheats]
OptionRange = 1:1349
518500F1 001CF3C3
514500F2 0000000F
514500F3 0000????
514500F4 0000D0D0

[Technique Slot Modifier\Select Technique 6]
OptionRange = 0x00:0xFF
510700F1 000D00??
```

| Line | Meaning |
| --- | --- |
| `518500F1 001CF3C3` | `F1` is the base cheat register; `1CF3C3` is the first address in Slot 1. |
| `514500F2 0000000F` | `F2` = `F1` + 1; `0F` is the difference between the 1st addresses of Slot 1 & Slot 2. |
| `514500F3 0000????` | `F3` = `F1` + 2; `????` is the selected value. |
| `514500F4 0000D0D0` | `F4` = `F1` + 3; this must always be `D0D0` as it ensures the next cheat only works if this cheat has been enabled at least once. |
| `510700F1 000D00??` | `F1` is the base cheat register as above, and `000D` is the address offset, so `1CF3C3 + 000D` for Slot 1, or indeed `1CF3C3 + (0xF * 1349) + 000D` for Slot 1349 (this is automatically calculated, so you only have to worry about `000D`). |

> **Note:** make sure you use cht registers not used by other cheats for the game. Here I've used `F1`-`F4`; I could
> equally have used `01`-`04`, `10`-`13`, `8D`-`90` or `FC`-`FF`, or pretty much any 4 cht registers.

#### 16-Bit Operations

| Code | Name | Description | Operation |
| --- | --- | --- | --- |
| `514000XX TTTTTTTT` | 16-Bit Address Write from Register | Poke address `TTTTTTTT` with the 16-bit contents of Register `XX`. | `u16Poke TTTTTTTT, RegXX` |
| `514100XX TTTTTTTT` | 16-Bit Address Read to Register | Peek the 16-bit contents of address `TTTTTTTT` and store it in Register `XX`. | `u16Poke RegXX, (TTTTTTTT)` |
| `514200XX 0000ZZZZ` | 16-Bit Indirect Register Write | Poke `ZZZZ` to the 32-bit address stored in Register `XX`. | `u16Poke (RegXX), ZZZZ` |
| `5143YYXX 0000ZZZZ` | 16-Bit Register Addition | Add `ZZZZ` and the 16-bit contents of Register `YY` together and write the result to Register `XX`. | `u16Poke RegXX, RegYY + ZZZZ` |
| `5144YYXX 0000ZZZZ` | 16-Bit Indirect Register Write with Addition | Add `ZZZZ` and the 16-bit contents of Register `YY` together and write the result to the 32-bit address stored in Register `XX`. | `u16Poke (RegXX), RegYY + ZZZZ` |
| `514500XX 0000ZZZZ` | 16-Bit Direct Register Write | Poke `ZZZZ` to Register `XX`. | `u16Poke RegXX, ZZZZ` |
| `5146YYXX ZZZZZZZZ` | 16-Bit Indirect Register Read | Peek the 16-bit contents of (32-bit address in Register `YY` + `ZZZZZZZZ`) and write it to Register `XX`. | `u16Poke RegXX, (RegYY + ZZZZZZZZ)` |
| `514700XX YYYYZZZZ` | 16-Bit Indirect Register Write of an Array of Arrays element | It will require four consecutive cht registers to be set up in a separate cheat for it to do anything. `XX` will be the 1st of 4 consecutive cht registers that will be used; `YYYY` will be the index of the array to be changed; `ZZZZ` will be the value to poke. See type [`5107`](#5107-array-of-arrays-element-write) for an example; just replace `510700F1 000000??` with `514700F1 0000????`. | |

#### 32-Bit Operations

| Code | Name | Description | Operation |
| --- | --- | --- | --- |
| `518000XX TTTTTTTT` | 32-Bit Address Write from Register | Poke address `TTTTTTTT` with the 32-bit contents of Register `XX`. | `u32Poke TTTTTTTT, RegXX` |
| `518100XX TTTTTTTT` | 32-Bit Address Read to Register | Peek the 32-bit contents of address `TTTTTTTT` and store it in Register `XX`. | `u32Poke RegXX, (TTTTTTTT)` |
| `518200XX ZZZZZZZZ` | 32-Bit Indirect Register Write | Poke `ZZZZZZZZ` to the 32-bit address stored in Register `XX`. | `u32Poke (RegXX), ZZZZZZZZ` |
| `5183YYXX ZZZZZZZZ` | 32-Bit Register Addition | Add `ZZZZZZZZ` and the 32-bit contents of Register `YY` together and write the result to Register `XX`. | `u32Poke RegXX, RegYY + ZZZZZZZZ` |
| `5184YYXX ZZZZZZZZ` | 32-Bit Indirect Register Write with Addition | Add `ZZZZZZZZ` and the 32-bit contents of Register `YY` together and write the result to the 32-bit address stored in Register `XX`. | `u32Poke (RegXX), RegYY + ZZZZZZZZ` |
| `518500XX ZZZZZZZZ` | 32-Bit Direct Register Write | Poke `ZZZZZZZZ` to Register `XX`. Note: This is useful to write the actual address to a register. | `u32Poke RegXX, ZZZZZZZZ` |
| `5186YYXX ZZZZZZZZ` | 32-Bit Indirect Register Read | Peek the 32-bit contents of (32-bit address in Register `YY` + `ZZZZZZZZ`) and write it to Register `XX`. | `u32Poke RegXX, (RegYY + ZZZZZZZZ)` |
| `5187.... ........` | Not in use | Utilise 2 * `5147` cheats. | |

#### Generic Register Operations

All of these generic register-only codes are 32-bit, but you can read any register as a u8, u16 or a u32.

| Code | Description | Operation |
| --- | --- | --- |
| `51C0YYXX 000000RR` | Add Register `YY` to Register `XX` and store the result in Register `RR`. | `u32Poke RegRR, RegYY + RegXX` |
| `51C1YYXX 000000RR` | Subtract Register `XX` from Register `YY` and store the result in Register `RR`. | `u32Poke RegRR, RegYY - RegXX` |
| `51C2YYXX 000000RR` | Multiply Register `YY` by Register `XX` and store the result in Register `RR`. | `u32Poke RegRR, RegYY * RegXX` |
| `51C3YYXX 000000RR` | Divide Register `YY` by Register `XX` and store the result in Register `RR`. Note: If Register `XX` contains 0, `RR` will be set to 0. | `u32Poke RegRR, RegYY / RegXX` |
| `51C4YYXX 000000RR` | Divide Register `YY` by Register `XX` and store the remainder in Register `RR`. Note: If Register `XX` contains 0, `RR` will be set to `RegYY`. | `u32Poke RegRR, RegYY % RegXX` |
| `51C5YYXX 000000RR` | Bitwise AND Register `YY` and Register `XX` and store the result in Register `RR`. | `u32Poke RegRR, RegYY & RegXX` |
| `51C6YYXX 000000RR` | Bitwise OR Register `YY` and Register `XX` and store the result in Register `RR`. | `u32Poke RegRR, RegYY \| RegXX` |
| `51C7YYXX 000000RR` | Bitwise XOR Register `YY` and Register `XX` and store the result in Register `RR`. | `u32Poke RegRR, RegYY ^ RegXX` |
| `51C800XX 000000RR` | Bitwise NOT Register `XX` and store the result in Register `RR`, aka One's Complement. | `u32Poke RegRR, ~RegXX` |
| `51C9TTXX 000000RR` | Bitwise LSHIFT Register `XX` by `TT` and store the result in Register `RR`. | `u32Poke RegRR, RegXX << TT` |
| `51CATTXX 000000RR` | Bitwise RSHIFT Register `XX` by `TT` and store the result in Register `RR`. | `u32Poke RegRR, RegXX >> TT` |
| `51D0YYXX ZZZZZZZZ` | Bitwise AND Register `YY` with `ZZZZZZZZ` and store the result in Register `XX`. | `u32Poke RegXX, RegYY & ZZZZZZZZ` |
| `51D1YYXX ZZZZZZZZ` | Bitwise OR Register `YY` with `ZZZZZZZZ` and store the result in Register `XX`. | `u32Poke RegXX, RegYY \| ZZZZZZZZ` |
| `51D2YYXX ZZZZZZZZ` | Bitwise XOR Register `YY` with `ZZZZZZZZ` and store the result in Register `XX`. | `u32Poke RegXX, RegYY ^ ZZZZZZZZ` |

### Register Block Conditionals

Each of these codes pokes all following codes for the rest of the cheat, or until it reaches the `00000000 FFFF` line, if
its condition is met:

```
5200YYXX 00000000
........ ........
00000000 FFFF
```

`u8`, `u16` and `u32` give the width each register or memory value is compared at.

#### 8-Bit Register Conditionals

| Code | Condition |
| --- | --- |
| `5200YYXX 00000000` | `u8RegYY == u8RegXX` |
| `5201YYXX 00000000` | `u8RegYY != u8RegXX` |
| `5202YYXX 00000000` | `u8RegYY > u8RegXX` |
| `5203YYXX 00000000` | `u8RegYY >= u8RegXX` |
| `5204YYXX 00000000` | `u8RegYY < u8RegXX` |
| `5205YYXX 00000000` | `u8RegYY <= u8RegXX` |
| `5206YYXX 00000000` | `u8RegYY & u8RegXX == u8RegXX` |
| `5207YYXX 00000000` | `u8RegYY & u8RegXX != u8RegXX` |
| `520AYYXX 00000000` | `u8RegYY & u8RegXX == u8RegYY` |
| `520BYYXX 00000000` | `u8RegYY & u8RegXX != u8RegYY` |
| `521000XX 000000ZZ` | `u8RegXX == ZZ` |
| `521100XX 000000ZZ` | `u8RegXX != ZZ` |
| `521200XX 000000ZZ` | `u8RegXX > ZZ` |
| `521300XX 000000ZZ` | `u8RegXX >= ZZ` |
| `521400XX 000000ZZ` | `u8RegXX < ZZ` |
| `521500XX 000000ZZ` | `u8RegXX <= ZZ` |
| `521600XX 000000ZZ` | `u8RegXX & ZZ == ZZ` |
| `521700XX 000000ZZ` | `u8RegXX & ZZ != ZZ` |
| `521800XX 00TT00ZZ` | `u8RegXX > ZZ && u8RegXX < TT` |
| `521900XX 00TT00ZZ` | `u8RegXX >= ZZ && u8RegXX <= TT` |
| `521A00XX 000000ZZ` | `u8RegXX & ZZ == u8RegXX` |
| `521B00XX 000000ZZ` | `u8RegXX & ZZ != u8RegXX` |
| `5220YYXX 00000000` | `u8(RegYY) == u8(RegXX)` |
| `5221YYXX 00000000` | `u8(RegYY) != u8(RegXX)` |
| `5222YYXX 00000000` | `u8(RegYY) > u8(RegXX)` |
| `5223YYXX 00000000` | `u8(RegYY) >= u8(RegXX)` |
| `5224YYXX 00000000` | `u8(RegYY) < u8(RegXX)` |
| `5225YYXX 00000000` | `u8(RegYY) <= u8(RegXX)` |
| `522600XX 000000ZZ` | `u8(RegXX) & ZZ == ZZ` |
| `522700XX 000000ZZ` | `u8(RegXX) & ZZ != ZZ` |
| `522800XX 00TT00ZZ` | `u8(RegXX) > ZZ && u8(RegXX) < TT` |
| `522900XX 00TT00ZZ` | `u8(RegXX) >= ZZ && u8(RegXX) <= TT` |
| `522A00XX 000000ZZ` | `u8(RegXX) & ZZ == u8(RegXX)` |
| `522B00XX 000000ZZ` | `u8(RegXX) & ZZ != u8(RegXX)` |
| `523000XX TTTTTTTT` | `u8RegXX == (TTTTTTTT)` |
| `523100XX TTTTTTTT` | `u8RegXX != (TTTTTTTT)` |
| `523200XX TTTTTTTT` | `u8RegXX > (TTTTTTTT)` |
| `523300XX TTTTTTTT` | `u8RegXX >= (TTTTTTTT)` |
| `523400XX TTTTTTTT` | `u8RegXX < (TTTTTTTT)` |
| `523600XX TTTTTTTT` | `u8RegXX & (TTTTTTTT) == (TTTTTTTT)` |
| `523700XX TTTTTTTT` | `u8RegXX & (TTTTTTTT) != (TTTTTTTT)` |
| `523A00XX TTTTTTTT` | `u8RegXX & (TTTTTTTT) == u8RegXX` |
| `523B00XX TTTTTTTT` | `u8RegXX & (TTTTTTTT) != u8RegXX` |

#### 16-Bit Register Conditionals

| Code | Condition |
| --- | --- |
| `5240YYXX 00000000` | `u16RegYY == u16RegXX` |
| `5241YYXX 00000000` | `u16RegYY != u16RegXX` |
| `5242YYXX 00000000` | `u16RegYY > u16RegXX` |
| `5243YYXX 00000000` | `u16RegYY >= u16RegXX` |
| `5244YYXX 00000000` | `u16RegYY < u16RegXX` |
| `5245YYXX 00000000` | `u16RegYY <= u16RegXX` |
| `5246YYXX 00000000` | `u16RegYY & u16RegXX == u16RegXX` |
| `5247YYXX 00000000` | `u16RegYY & u16RegXX != u16RegXX` |
| `524AYYXX 00000000` | `u16RegYY & u16RegXX == u16RegYY` |
| `524BYYXX 00000000` | `u16RegYY & u16RegXX != u16RegYY` |
| `525000XX 0000ZZZZ` | `u16RegXX == ZZZZ` |
| `525100XX 0000ZZZZ` | `u16RegXX != ZZZZ` |
| `525200XX 0000ZZZZ` | `u16RegXX > ZZZZ` |
| `525300XX 0000ZZZZ` | `u16RegXX >= ZZZZ` |
| `525400XX 0000ZZZZ` | `u16RegXX < ZZZZ` |
| `525500XX 0000ZZZZ` | `u16RegXX <= ZZZZ` |
| `525600XX 0000ZZZZ` | `u16RegXX & ZZZZ == ZZZZ` |
| `525700XX 0000ZZZZ` | `u16RegXX & ZZZZ != ZZZZ` |
| `525800XX TTTTZZZZ` | `u16RegXX > ZZZZ && u16RegXX < TTTT` |
| `525900XX TTTTZZZZ` | `u16RegXX >= ZZZZ && u16RegXX <= TTTT` |
| `525A00XX 0000ZZZZ` | `u16RegXX & ZZZZ == u16RegXX` |
| `525B00XX 0000ZZZZ` | `u16RegXX & ZZZZ != u16RegXX` |
| `5260YYXX 00000000` | `u16(RegYY) == u16(RegXX)` |
| `5261YYXX 00000000` | `u16(RegYY) != u16(RegXX)` |
| `5262YYXX 00000000` | `u16(RegYY) > u16(RegXX)` |
| `5263YYXX 00000000` | `u16(RegYY) >= u16(RegXX)` |
| `5264YYXX 00000000` | `u16(RegYY) < u16(RegXX)` |
| `5265YYXX 00000000` | `u16(RegYY) <= u16(RegXX)` |
| `526600XX 0000ZZZZ` | `u16(RegXX) & ZZZZ == ZZZZ` |
| `526700XX 0000ZZZZ` | `u16(RegXX) & ZZZZ != ZZZZ` |
| `526800XX TTTTZZZZ` | `u16(RegXX) > ZZZZ && u16(RegXX) < TTTT` |
| `526900XX TTTTZZZZ` | `u16(RegXX) >= ZZZZ && u16(RegXX) <= TTTT` |
| `526A00XX 0000ZZZZ` | `u16(RegXX) & ZZZZ == u16(RegXX)` |
| `526B00XX 0000ZZZZ` | `u16(RegXX) & ZZZZ != u16(RegXX)` |
| `527000XX TTTTTTTT` | `u16RegXX == (TTTTTTTT)` |
| `527100XX TTTTTTTT` | `u16RegXX != (TTTTTTTT)` |
| `527200XX TTTTTTTT` | `u16RegXX > (TTTTTTTT)` |
| `527300XX TTTTTTTT` | `u16RegXX >= (TTTTTTTT)` |
| `527400XX TTTTTTTT` | `u16RegXX < (TTTTTTTT)` |
| `527600XX TTTTTTTT` | `u16RegXX & (TTTTTTTT) == (TTTTTTTT)` |
| `527700XX TTTTTTTT` | `u16RegXX & (TTTTTTTT) != (TTTTTTTT)` |
| `527A00XX TTTTTTTT` | `u16RegXX & (TTTTTTTT) == u16RegXX` |
| `527B00XX TTTTTTTT` | `u16RegXX & (TTTTTTTT) != u16RegXX` |

#### 32-Bit Register Conditionals

| Code | Condition |
| --- | --- |
| `5280YYXX 00000000` | `u32RegYY == u32RegXX` |
| `5281YYXX 00000000` | `u32RegYY != u32RegXX` |
| `5282YYXX 00000000` | `u32RegYY > u32RegXX` |
| `5283YYXX 00000000` | `u32RegYY >= u32RegXX` |
| `5284YYXX 00000000` | `u32RegYY < u32RegXX` |
| `5285YYXX 00000000` | `u32RegYY <= u32RegXX` |
| `5286YYXX 00000000` | `u32RegYY & u32RegXX == u32RegXX` |
| `5287YYXX 00000000` | `u32RegYY & u32RegXX != u32RegXX` |
| `528AYYXX 00000000` | `u32RegYY & u32RegXX == u32RegYY` |
| `528BYYXX 00000000` | `u32RegYY & u32RegXX != u32RegYY` |
| `529000XX ZZZZZZZZ` | `u32RegXX == ZZZZZZZZ` |
| `529100XX ZZZZZZZZ` | `u32RegXX != ZZZZZZZZ` |
| `529200XX ZZZZZZZZ` | `u32RegXX > ZZZZZZZZ` |
| `529300XX ZZZZZZZZ` | `u32RegXX >= ZZZZZZZZ` |
| `529400XX ZZZZZZZZ` | `u32RegXX < ZZZZZZZZ` |
| `529500XX ZZZZZZZZ` | `u32RegXX <= ZZZZZZZZ` |
| `529600XX ZZZZZZZZ` | `u32RegXX & ZZZZZZZZ == ZZZZZZZZ` |
| `529700XX ZZZZZZZZ` | `u32RegXX & ZZZZZZZZ != ZZZZZZZZ` |
| `529A00XX ZZZZZZZZ` | `u32RegXX & ZZZZZZZZ == u32RegXX` |
| `529B00XX ZZZZZZZZ` | `u32RegXX & ZZZZZZZZ != u32RegXX` |
| `52A0YYXX 00000000` | `u32(RegYY) == u32(RegXX)` |
| `52A1YYXX 00000000` | `u32(RegYY) != u32(RegXX)` |
| `52A2YYXX 00000000` | `u32(RegYY) > u32(RegXX)` |
| `52A3YYXX 00000000` | `u32(RegYY) >= u32(RegXX)` |
| `52A4YYXX 00000000` | `u32(RegYY) < u32(RegXX)` |
| `52A5YYXX 00000000` | `u32(RegYY) <= u32(RegXX)` |
| `52A600XX ZZZZZZZZ` | `u32(RegXX) & ZZZZZZZZ == ZZZZZZZZ` |
| `52A700XX ZZZZZZZZ` | `u32(RegXX) & ZZZZZZZZ != ZZZZZZZZ` |
| `52AA00XX ZZZZZZZZ` | `u32(RegXX) & ZZZZZZZZ == u32(RegXX)` |
| `52AB00XX ZZZZZZZZ` | `u32(RegXX) & ZZZZZZZZ != u32(RegXX)` |
| `52B000XX TTTTTTTT` | `u32RegXX == (TTTTTTTT)` |
| `52B100XX TTTTTTTT` | `u32RegXX != (TTTTTTTT)` |
| `52B200XX TTTTTTTT` | `u32RegXX > (TTTTTTTT)` |
| `52B300XX TTTTTTTT` | `u32RegXX >= (TTTTTTTT)` |
| `52B400XX TTTTTTTT` | `u32RegXX < (TTTTTTTT)` |
| `52B600XX TTTTTTTT` | `u32RegXX & (TTTTTTTT) == (TTTTTTTT)` |
| `52B700XX TTTTTTTT` | `u32RegXX & (TTTTTTTT) != (TTTTTTTT)` |
| `52BA00XX TTTTTTTT` | `u32RegXX & (TTTTTTTT) == u32RegXX` |
| `52BB00XX TTTTTTTT` | `u32RegXX & (TTTTTTTT) != u32RegXX` |
