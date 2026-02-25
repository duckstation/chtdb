#!/usr/bin/env python3
"""
Validator for DuckStation .cht cheat/patch files.

Part 1: Validates the CHT file structure (sections, metadata keys, values).
Part 2: Validates Gameshark instruction codes (opcodes, multi-instruction
        sequences, option masks).

Usage:
  python validate_cht.py <file1.cht> [file2.cht ...] [--warnings-as-errors]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

VALID_TYPES = frozenset({"Gameshark"})
VALID_ACTIVATIONS = frozenset({"Manual", "EndFrame"})

VALID_METADATA_KEYS = frozenset({
    "Author", "Description", "Type", "Activation",
    "Option", "OptionRange",
    "OverrideAspectRatio", "OverrideCPUOverclock",
    "DisableWidescreenRendering", "Enable8MBRAM",
    "DisallowForAchievements", "Ignore",
})

BOOLEAN_KEYS = frozenset({
    "DisableWidescreenRendering", "Enable8MBRAM",
    "DisallowForAchievements", "Ignore",
})

# Keys that may appear more than once in a single code section.
REPEATABLE_KEYS = frozenset({"Option"})

# Gameshark opcodes: byte -> (name, total instructions consumed including self)
GAMESHARK_OPCODES: dict[int, tuple[str, int]] = {
    0x00: ("Nop", 1),
    0x10: ("Increment16", 1),
    0x11: ("Decrement16", 1),
    0x1F: ("ScratchpadWrite16", 1),
    0x20: ("Increment8", 1),
    0x21: ("Decrement8", 1),
    0x30: ("ConstantWrite8", 1),
    0x31: ("ExtConstantBitSet8", 1),
    0x32: ("ExtConstantBitClear8", 1),
    0x50: ("Slide", 2),
    0x51: ("ExtCheatRegisters", 1),
    0x52: ("ExtCheatRegistersCompare", 1),
    0x53: ("ExtImprovedSlide", 2),
    0x60: ("ExtIncrement32", 1),
    0x61: ("ExtDecrement32", 1),
    0x80: ("ConstantWrite16", 1),
    0x81: ("ExtConstantBitSet16", 1),
    0x82: ("ExtConstantBitClear16", 1),
    0x90: ("ExtConstantWrite32", 1),
    0x91: ("ExtConstantBitSet32", 1),
    0x92: ("ExtConstantBitClear32", 1),
    0xA0: ("ExtCompareEqual32", 1),
    0xA1: ("ExtCompareNotEqual32", 1),
    0xA2: ("ExtCompareLess32", 1),
    0xA3: ("ExtCompareGreater32", 1),
    0xA4: ("ExtSkipIfNotEqual32", 1),
    0xA5: ("ExtScratchpadWrite32", 1),
    0xA6: ("ExtConstantWriteIfMatch16", 1),
    0xA7: ("ExtConstantWriteIfMatchWithRestore16", 1),
    0xA8: ("ExtConstantWriteIfMatchWithRestore8", 1),
    0xC0: ("SkipIfNotEqual16", 1),
    0xC1: ("DelayActivation", 1),
    0xC2: ("MemoryCopy", 2),
    0xC3: ("ExtSkipIfNotLess8", 1),
    0xC4: ("ExtSkipIfNotGreater8", 1),
    0xC5: ("ExtSkipIfNotLess16", 1),
    0xC6: ("ExtSkipIfNotGreater16", 1),
    0xD0: ("CompareEqual16", 1),
    0xD1: ("CompareNotEqual16", 1),
    0xD2: ("CompareLess16", 1),
    0xD3: ("CompareGreater16", 1),
    0xD4: ("CompareButtons", 1),
    0xD5: ("SkipIfButtonsNotEqual", 1),
    0xD6: ("SkipIfButtonsEqual", 1),
    0xD7: ("ExtBitCompareButtons", 1),
    0xE0: ("CompareEqual8", 1),
    0xE1: ("CompareNotEqual8", 1),
    0xE2: ("CompareLess8", 1),
    0xE3: ("CompareGreater8", 1),
    0xE4: ("ExtCompareBitsSet8", 1),
    0xE5: ("ExtCompareBitsClear8", 1),
    0xF0: ("ExtConstantForceRange8", 1),
    0xF1: ("ExtConstantForceRangeLimits16", 1),
    0xF2: ("ExtConstantForceRangeRollRound16", 1),
    0xF3: ("ExtConstantForceRange16", 2),
    0xF4: ("ExtFindAndReplace", 5),
    0xF5: ("ExtConstantSwap16", 1),
    0xF6: ("ExtMultiConditionals", 1),
}

# Valid second-instruction opcodes for Slide (0x50)
SLIDE_VALID_WRITE_OPCODES = frozenset({0x30, 0x80, 0x90})

# Valid second-instruction opcodes for ExtImprovedSlide (0x53)
IMPROVED_SLIDE_VALID_WRITE_OPCODES = frozenset({
    0x30, 0x80, 0x90,  # ConstantWrite 8/16/32
    0x31, 0x32,         # ExtConstantBitSet/Clear 8
    0x81, 0x82,         # ExtConstantBitSet/Clear 16
    0x91, 0x92,         # ExtConstantBitSet/Clear 32
})

# Valid conditional opcodes inside ExtMultiConditionals (0xF6) blocks.
# Derived from the switch inside the AND/OR loops in Apply().
F6_VALID_CONDITIONAL_OPCODES = frozenset({
    0xD0, 0xD1, 0xD2, 0xD3,  # Compare 16-bit
    0xE0, 0xE1, 0xE2, 0xE3,  # Compare 8-bit
    0xA0, 0xA1, 0xA2, 0xA3,  # Compare 32-bit
    0xE4, 0xE5,               # CompareBitsSet/Clear8 (F6 internal)
    0xD7,                     # ExtBitCompareButtons
})

# Valid sub-types for ExtCheatRegistersCompare (0x52).
# Byte at bits 16-23 of the first value.  Extracted from switch(sub_type).
VALID_0x52_SUBTYPES = frozenset({
    # u8 reg-vs-reg
    *range(0x00, 0x08), 0x0A, 0x0B,
    # u8 reg-vs-imm / range / mask
    *range(0x10, 0x1C),
    # u8 mem-vs-mem / mem-vs-imm
    *range(0x20, 0x2C),
    # u8 reg-vs-mem
    *range(0x30, 0x35), 0x36, 0x37, 0x3A, 0x3B,
    # u16 reg-vs-reg
    *range(0x40, 0x48), 0x4A, 0x4B,
    # u16 reg-vs-imm / range / mask
    *range(0x50, 0x5C),
    # u16 mem-vs-mem / mem-vs-imm
    *range(0x60, 0x6C),
    # u16 reg-vs-mem
    *range(0x70, 0x75), 0x76, 0x77, 0x7A, 0x7B,
    # u32 reg-vs-reg
    *range(0x80, 0x88), 0x8A, 0x8B,
    # u32 reg-vs-imm
    *range(0x90, 0x98), 0x9A, 0x9B,
    # u32 mem-vs-mem
    *range(0xA0, 0xA8), 0xAA, 0xAB,
    # u32 reg-vs-mem
    *range(0xB0, 0xB5), 0xB6, 0xB7, 0xBA, 0xBB,
})

_HEX_SET = frozenset("0123456789abcdefABCDEF")


# ═══════════════════════════════════════════════════════════════════════════════
# Validation Result
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Message:
    line: int
    level: str  # "error" | "warning"
    text: str

    def __str__(self) -> str:
        return f"  Line {self.line}: [{self.level}] {self.text}"


@dataclass
class Result:
    messages: list[Message] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(1 for m in self.messages if m.level == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for m in self.messages if m.level == "warning")

    @property
    def ok(self) -> bool:
        return self.errors == 0

    def error(self, line: int, text: str) -> None:
        self.messages.append(Message(line, "error", text))

    def warning(self, line: int, text: str) -> None:
        self.messages.append(Message(line, "warning", text))

    def merge(self, other: Result) -> None:
        self.messages.extend(other.messages)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _is_hex(ch: str) -> bool:
    return ch in _HEX_SET


def _parse_hex_u32(s: str) -> int | None:
    """Parse a hex string as u32. Returns None if invalid or out of range."""
    if not s:
        return None
    try:
        v = int(s, 16)
        return v if v <= 0xFFFFFFFF else None
    except ValueError:
        return None


def _parse_uint(s: str) -> int | None:
    """Parse an integer with optional 0x prefix (matches FromCharsWithOptionalBase)."""
    s = s.strip()
    if not s:
        return None
    try:
        if s.startswith(("0x", "0X")):
            return int(s, 16)
        return int(s)
    except ValueError:
        return None


def _strip_line_comment(line: str) -> str:
    """Strip trailing comment at last '#' or ';' (matches C++ find_last_of)."""
    for i in range(len(line) - 1, -1, -1):
        if line[i] in ('#', ';'):
            return line[:i].strip()
    return line


# ═══════════════════════════════════════════════════════════════════════════════
# Part 1 – CHT File Structure Validation
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ParsedCode:
    """A code section extracted from the CHT file."""
    name: str
    code_type: str
    activation: str
    body_lines: list[tuple[int, str]]  # (1-based line number, stripped text)
    start_line: int
    has_options: bool = False


def validate_cht_structure(content: str) -> tuple[Result, list[ParsedCode]]:
    """
    Validate CHT file structure and extract code sections.

    Checks performed:
      - Section headers are well-formed ([Name])
      - Metadata keys are recognized and values are valid
      - Type must be a known CodeType (currently: Gameshark)
      - Activation must be Manual or EndFrame
      - Option format: Name:Value (value is uint with optional 0x)
      - OptionRange format: Start:End (u16, end > start)
      - Boolean keys have boolean values
      - OverrideCPUOverclock is a non-zero uint
      - OverrideAspectRatio must be M:N (integer ratio)
      - Code bodies are non-empty
      - No code data appears outside a section
      - Duplicate code names are flagged
      - Duplicate metadata keys within a code are flagged
    """
    res = Result()
    codes: list[ParsedCode] = []
    seen_names: set[str] = set()
    seen_keys: set[str] = set()

    lines = content.splitlines()
    cur: ParsedCode | None = None

    def _finish() -> None:
        nonlocal cur
        if cur is None:
            return
        if not cur.body_lines:
            res.error(cur.start_line, f"Empty body for cheat '{cur.name}'")
        if cur.name in seen_names:
            res.warning(cur.start_line,
                        f"Duplicate code name '{cur.name}' (overwrites previous)")
        seen_names.add(cur.name)
        codes.append(cur)
        cur = None

    for idx, raw in enumerate(lines):
        ln = idx + 1
        lv = raw.strip()
        if not lv:
            continue

        # ── Comments ──────────────────────────────────────────────────
        if lv[0] in ('#', ';'):
            continue

        # ── Section header [Name] ─────────────────────────────────────
        if lv[0] == '[':
            if len(lv) < 3 or lv[-1] != ']':
                res.error(ln, f"Malformed section header: {lv}")
                continue
            name = lv[1:-1].strip()
            if not name:
                res.error(ln, "Empty code name in section header")
                continue
            _finish()
            seen_keys = set()
            cur = ParsedCode(
                name=name,
                code_type="Gameshark",
                activation="EndFrame",
                body_lines=[],
                start_line=ln,
            )
            continue

        # ── Strip trailing comment ────────────────────────────────────
        lv = _strip_line_comment(lv)
        if not lv:
            continue

        # ── Key = Value metadata ──────────────────────────────────────
        eq = lv.find('=')
        if eq >= 0:
            key = lv[:eq].strip()
            val = lv[eq + 1:].strip()
            if not key:
                res.error(ln, f"Malformed key=value pair: {lv}")
                continue
            if cur is None:
                res.warning(ln, f"Metadata '{key}' outside any code section")
                continue
            if key not in VALID_METADATA_KEYS:
                res.warning(ln, f"Unknown metadata key: '{key}'")
                continue
            if key not in REPEATABLE_KEYS and key in seen_keys:
                res.warning(ln,
                            f"Duplicate key '{key}' in code '{cur.name}'")
            seen_keys.add(key)

            if key == "Type":
                if val not in VALID_TYPES:
                    res.error(ln, f"Unknown code type: '{val}'")
                else:
                    cur.code_type = val

            elif key == "Activation":
                if val not in VALID_ACTIVATIONS:
                    res.error(ln, f"Unknown activation: '{val}'")
                else:
                    cur.activation = val

            elif key == "Option":
                sep = val.rfind(':')
                if sep < 0:
                    res.error(ln,
                              f"Invalid Option (expected Name:Value): '{val}'")
                else:
                    oname = val[:sep].strip()
                    oval = val[sep + 1:].strip()
                    if not oname:
                        res.error(ln, "Empty option name")
                    pv = _parse_uint(oval)
                    if pv is None:
                        res.error(ln, f"Invalid option value: '{oval}'")
                    elif pv > 0xFFFFFFFF:
                        res.error(ln, f"Option value exceeds u32: {pv}")
                cur.has_options = True

            elif key == "OptionRange":
                sep = val.rfind(':')
                if sep < 0:
                    res.error(ln,
                              f"Invalid OptionRange (expected Start:End): "
                              f"'{val}'")
                else:
                    sv = _parse_uint(val[:sep].strip())
                    ev = _parse_uint(val[sep + 1:].strip())
                    if sv is None:
                        res.error(ln, "Invalid OptionRange start value")
                    elif ev is None:
                        res.error(ln, "Invalid OptionRange end value")
                    elif sv > 0xFFFF:
                        res.error(ln,
                                  f"OptionRange start exceeds u16: {sv}")
                    elif ev > 0xFFFF:
                        res.error(ln,
                                  f"OptionRange end exceeds u16: {ev}")
                    elif ev <= sv:
                        res.error(ln,
                                  f"OptionRange end ({ev}) must be > "
                                  f"start ({sv})")
                cur.has_options = True

            elif key == "OverrideCPUOverclock":
                pv = _parse_uint(val)
                if pv is None or pv == 0:
                    res.error(ln,
                              f"Invalid CPU overclock (must be non-zero "
                              f"uint): '{val}'")
                elif pv > 0xFFFFFFFF:
                    res.error(ln,
                              f"CPU overclock exceeds u32: {pv}")

            elif key == "OverrideAspectRatio":
                parts = val.split(':')
                if len(parts) != 2:
                    res.error(ln,
                              f"Invalid aspect ratio (expected M:N): '{val}'")
                else:
                    try:
                        m, n = int(parts[0].strip()), int(parts[1].strip())
                        if m <= 0 or n <= 0:
                            res.error(ln,
                                      f"Aspect ratio components must be "
                                      f"positive integers: '{val}'")
                    except ValueError:
                        res.error(ln,
                                  f"Aspect ratio components must be "
                                  f"integers: '{val}'")

            elif key in BOOLEAN_KEYS:
                if val.lower() not in ("true", "false", "1", "0"):
                    res.warning(ln,
                                f"Expected boolean for '{key}', got: '{val}'")

            # Author, Description: any string accepted
            continue

        # ── Code body line ────────────────────────────────────────────
        if cur is None:
            res.error(ln, f"Code data outside any section: {lv}")
            continue
        cur.body_lines.append((ln, lv))

    _finish()
    return res, codes


# ═══════════════════════════════════════════════════════════════════════════════
# Part 2 – Gameshark Code Validation
# ═══════════════════════════════════════════════════════════════════════════════

def _validate_option_mask(token: str) -> tuple[int | None, str | None]:
    """
    Validate a hex token containing '?' option placeholders.
    Matches ParseHexOptionMask: max 8 chars, only hex digits and '?',
    and all '?' must be consecutive.
    Returns (parsed_value, error_message).
    """
    if len(token) > 8:
        return None, f"Option mask too long ({len(token)} chars, max 8)"
    digits: list[str] = []
    q_positions: list[int] = []
    for i, ch in enumerate(token):
        if ch == '?':
            q_positions.append(i)
            digits.append('0')
        elif _is_hex(ch):
            digits.append(ch)
        else:
            return None, f"Invalid character '{ch}' in option mask"
    if len(q_positions) > 1:
        for j in range(1, len(q_positions)):
            if q_positions[j] != q_positions[j - 1] + 1:
                return None, "'?' characters must be consecutive"
    v = _parse_hex_u32(''.join(digits))
    return (v, None) if v is not None else (None, "Failed to parse option mask")


def _parse_gs_line(text: str) -> tuple[tuple[int, int] | None, str | None]:
    """
    Parse a single Gameshark instruction line.
    Matches GamesharkCheatCode::Parse: skip lines not starting with hex,
    parse two hex u32 values separated by whitespace, second value may
    contain '?' option mask placeholders.
    Returns ((first, second), None) on success,
            (None, error_string) on parse failure,
            (None, None) if the line should be silently skipped.
    """
    s = text.strip()
    if not s or not _is_hex(s[0]):
        return None, None  # not an instruction line

    # Extract first hex token
    i = 0
    while i < len(s) and _is_hex(s[i]):
        i += 1
    first = _parse_hex_u32(s[:i])
    if first is None:
        return None, f"Invalid first hex value: '{s[:i]}'"

    # Skip separator chars (anything that's not hex and not '?')
    while i < len(s) and s[i] != '?' and not _is_hex(s[i]):
        i += 1
    if i >= len(s):
        return None, "Missing second value in instruction"

    # Extract second token (hex digits and '?')
    j = i
    while j < len(s) and (_is_hex(s[j]) or s[j] == '?'):
        j += 1
    token2 = s[i:j]

    if '?' in token2:
        second, err = _validate_option_mask(token2)
        if err:
            return None, f"Option mask error: {err}"
    else:
        second = _parse_hex_u32(token2)

    if second is None:
        return None, f"Invalid second hex value: '{token2}'"

    return (first, second), None


def validate_gameshark(code: ParsedCode) -> Result:
    """
    Validate Gameshark instructions in a parsed code's body.

    Checks performed:
      - Each instruction line has two valid u32 hex values
      - The opcode byte (top byte of first value) is a known InstructionCode
      - Multi-instruction opcodes have enough following instructions:
          Slide (0x50): 2 total
          ExtImprovedSlide (0x53): 2 total
          MemoryCopy (0xC2): 2 total
          ExtConstantForceRange16 (0xF3): 2 total
          ExtFindAndReplace (0xF4): 5 total
      - Slide second instruction is ConstantWrite8/16/32
      - ExtImprovedSlide second instruction is a valid write type
      - ExtMultiConditionals (0xF6) header, conditionType, totalConds,
        and following conditional opcodes are validated
      - ExtCheatRegistersCompare (0x52) sub-type is validated
      - Option masks have consecutive '?' and are ≤8 chars
      - At least one valid instruction exists
    """
    res = Result()
    tag = code.name

    # Collect parsed instructions
    insts: list[tuple[int, int, int]] = []  # (line, first, second)
    for ln, text in code.body_lines:
        parsed, err = _parse_gs_line(text)
        if err:
            res.error(ln, f"[{tag}] {err}")
            continue
        if parsed is None:
            continue  # silently skip non-instruction lines
        insts.append((ln, parsed[0], parsed[1]))

    if not insts:
        res.error(code.start_line,
                  f"[{tag}] No valid Gameshark instructions found")
        return res

    # Walk instructions validating opcodes and multi-instruction sequences
    i = 0
    n = len(insts)
    while i < n:
        ln, first, second = insts[i]
        opcode = (first >> 24) & 0xFF

        if opcode not in GAMESHARK_OPCODES:
            res.error(ln, f"[{tag}] Unknown opcode 0x{opcode:02X}")
            i += 1
            continue

        name, size = GAMESHARK_OPCODES[opcode]
        remaining = n - i
        if remaining < size:
            res.error(ln,
                      f"[{tag}] {name} (0x{opcode:02X}) requires {size} "
                      f"instruction(s), only {remaining} remaining")
            break

        # Validate Slide second instruction
        if opcode == 0x50:
            _, f2, _ = insts[i + 1]
            op2 = (f2 >> 24) & 0xFF
            if op2 not in SLIDE_VALID_WRITE_OPCODES:
                n2 = GAMESHARK_OPCODES.get(op2, (f"0x{op2:02X}",))[0]
                res.error(
                    insts[i + 1][0],
                    f"[{tag}] Slide second instruction must be "
                    f"ConstantWrite8/16/32, got {n2}")

        # Validate ExtImprovedSlide second instruction
        elif opcode == 0x53:
            _, f2, _ = insts[i + 1]
            op2 = (f2 >> 24) & 0xFF
            if op2 not in IMPROVED_SLIDE_VALID_WRITE_OPCODES:
                n2 = GAMESHARK_OPCODES.get(op2, (f"0x{op2:02X}",))[0]
                res.error(
                    insts[i + 1][0],
                    f"[{tag}] ExtImprovedSlide second instruction must "
                    f"be a write type, got {n2}")

        # Validate ExtMultiConditionals (0xF6) structure
        elif opcode == 0xF6:
            condition_type = first & 0xFF
            second_header = second & 0xFFFFFF00
            total_conds = second & 0xFF

            if second_header != 0x1F000000:
                # Not an "if" header – could be else/elseif within a
                # block, but standalone it is suspicious.
                res.warning(ln,
                            f"[{tag}] F6 instruction does not have "
                            f"'if' header (second & 0xFFFFFF00 != "
                            f"0x1F000000)")
            else:
                if condition_type not in (0x00, 0x01):
                    res.error(ln,
                              f"[{tag}] F6 conditionType must be 0x00 "
                              f"(AND) or 0x01 (OR), got "
                              f"0x{condition_type:02X}")
                if total_conds == 0:
                    res.error(ln,
                              f"[{tag}] F6 totalConds must be > 0")
                elif i + total_conds >= n:
                    res.error(ln,
                              f"[{tag}] F6 expects {total_conds} "
                              f"conditional instruction(s) to follow, "
                              f"only {n - i - 1} remaining")
                else:
                    for ci in range(1, total_conds + 1):
                        cln, cfirst, _ = insts[i + ci]
                        cop = (cfirst >> 24) & 0xFF
                        if cop not in F6_VALID_CONDITIONAL_OPCODES:
                            cop_name = GAMESHARK_OPCODES.get(
                                cop, (f"0x{cop:02X}",))[0]
                            res.error(
                                cln,
                                f"[{tag}] F6 conditional #{ci} has "
                                f"invalid opcode {cop_name} (expected "
                                f"a compare instruction)")

        # Validate ExtCheatRegistersCompare (0x52) sub-type
        elif opcode == 0x52:
            sub_type = (first >> 16) & 0xFF
            if sub_type not in VALID_0x52_SUBTYPES:
                res.warning(ln,
                            f"[{tag}] ExtCheatRegistersCompare unknown "
                            f"sub-type 0x{sub_type:02X}")

        i += size

    return res


# ═══════════════════════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def validate_file(filepath: str) -> Result:
    """Full end-to-end validation of a .cht file."""
    p = Path(filepath)
    if not p.exists():
        r = Result()
        r.error(0, f"File not found: {filepath}")
        return r

    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        r = Result()
        r.error(0, f"Cannot read file: {exc}")
        return r

    # Part 1: validate file structure
    result, codes = validate_cht_structure(content)

    # Part 2: validate Gameshark instruction bodies
    for code in codes:
        if code.code_type == "Gameshark" and code.body_lines:
            result.merge(validate_gameshark(code))

    return result


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Validate DuckStation .cht cheat/patch files.")
    ap.add_argument("files", nargs="+", help=".cht file(s) to validate")
    ap.add_argument("-W", "--warnings-as-errors", action="store_true",
                    help="Treat warnings as errors for the exit code")
    args = ap.parse_args()

    rc = 0
    for fpath in args.files:
        r = validate_file(fpath)
        fail = r.errors > 0 or (args.warnings_as_errors and r.warnings > 0)

        if r.errors > 0 or r.warnings > 0:
            print(f"\n{fpath}:")
            for m in r.messages:
                print(m)
            print(f"  Summary: {r.errors} error(s), {r.warnings} warning(s)")
        else:
            print(f"{fpath}: OK")

        if fail:
            rc = 1

    return rc


if __name__ == "__main__":
    sys.exit(main())