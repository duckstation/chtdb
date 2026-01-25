#!/usr/bin/env python3

import argparse
import os
import re
import sys
from collections import OrderedDict

def cull_serials(serials:list):
    # remove serials where one is a prefix of another
    serial_set = set(serials)
    new_serials = []
    for serial in serial_set:
        found_prefix = False
        for other_serial in serial_set:
            if serial != other_serial and serial.startswith(other_serial):
                found_prefix = True
                break
        if found_prefix:
            continue
        new_serials.append(serial)
    return new_serials


def remove_empty_lines(data):
    return list(filter(lambda x: len(x) > 0, map(lambda x: x.strip(), data)))


# chtdb -> entries
def parse_chtdb(chtdb_path:str):
    entries = OrderedDict()

    with open(chtdb_path, "r", encoding="utf-8", errors="ignore") as f:
        data = f.read()

        # skip the first section, it's just documentation
        pos = data.find("; [ ")
        if pos >= 0:
            pos += 5

        while pos >= 0:
            next_pos = data.find("\n; [ ", pos)
            if next_pos >= 0:
                this_data = data[pos-5:next_pos]
                pos = next_pos + 5
            else:
                this_data = data[pos-5:]
                pos = -1

            # remove all empty lines
            this_data = list(filter(lambda x: len(x) > 0, map(lambda x: x.strip(), this_data.split("\n"))))
            serials = list()
            codes = OrderedDict()
            code_name = None
            code_body = []
            for line in this_data[1:]:
                # skip old serial lines
                if line[0] == ':':
                    serial = line[1:].strip()
                    assert len(serial) > 0
                    serials.append(serial)
                    continue

                # new code?
                elif line[0] == '#':
                    if len(code_body) > 0:
                        codes[code_name] = "\n".join(code_body)
                    code_name = line[1:].strip()
                    code_body = []
                else:
                    code_body.append(line)
            if len(code_body) > 0:
                codes[code_name] = "\n".join(code_body)

            # if there's any non-none keys, then we have some cheats
            serials = cull_serials(serials)
            sorted_serials = list(sorted(serials))
            identifier = f"ENTRY-{len(entries)}" if len(serials) == 0 else sorted_serials[0]
            has_cheats = False
            for key in codes.keys():
                if key is not None:
                    has_cheats = True
                    break
                        
            # create item
            entries[identifier] = {
                "header": this_data[0],
                "serials": serials,
                "codes": codes,
                "has_cheats": has_cheats
            }

    return entries


# entries -> cht files
def generate_cht_files(entries:OrderedDict, path:str, overwrite:bool):
    for key, entry in entries.items():
        if len(entry["serials"]) == 0 or not entry["has_cheats"]:
            continue

        header = entry["header"]
        chtdata = f"; CHTDB: {header}\n\n"
        for title, lines in entry["codes"].items():
            if title is None:
                # preceding comments
                chtdata += lines + "\n"
                continue

            stitle = title.split(":")
            name = stitle[0].strip()
            desc = stitle[1].strip() if len(stitle) > 1 else None
            chtdata += f"[{name}]\n"
            if desc is not None:
                chtdata += f"Description = {desc}\n"
            chtdata += "Type = Gameshark\n"
            chtdata += "Activation = EndFrame\n"
            chtdata += lines + "\n\n"

        filename = f"{key}.cht"
        chtpath = os.path.join(path, filename)
        if os.path.exists(chtpath):
            with open(os.path.join(path, filename), "r", encoding="utf-8", errors="ignore") as f:
                echtdata = f.read()
                if echtdata == chtdata:
                    # print(f"*** No change in {filename}.")
                    continue
                elif not overwrite:
                    print(f"*** NOT OVERWRITING {filename}.")
                    continue

        print(f"Writing {filename}...")
        with open(os.path.join(path, filename), "w", encoding="utf-8", errors="ignore") as f:
            f.write(chtdata)


# merge cht files -> chtdb
def update_chtdb(chtdb_path:str, new_chtdb_path:str, cheats_dir:str):
    with open(chtdb_path, "r", encoding="utf-8", errors="ignore") as f:
        chtdb_data = f.read()

    for filename in sorted(os.listdir(cheats_dir)):
        with open(os.path.join(cheats_dir, filename), "r", encoding="utf-8", errors="ignore") as f:
            lines = list(filter(lambda x: len(x) > 0, map(lambda x: x.strip(), f.readlines())))
            if len(lines) == 0 or not lines[0].startswith("; CHTDB: ;"):
                continue

            header = lines[0][9:]
            pos = chtdb_data.find(header)
            if pos < 0:
                print(f"*** {header} not found in chtdb.")
                continue
            end_pos = chtdb_data.find("\n; [ ", pos)
            if end_pos < 0:
                end_pos = len(chtdb_data)
            else:
                # remove trailing newline, so we don't delete it below
                end_pos -= 1

            # dump header lines into the comparison list
            old_lines = remove_empty_lines(chtdb_data[pos:end_pos].split("\n"))
            new_lines = [old_lines[0]]
            for line in old_lines[1:]:
                if line[0] != ':':
                    break
                new_lines.append(line)

            # convert names/descriptions
            name = None
            author = None
            for line in lines[1:]:
                # Skip new fields
                no_whitespace = line.replace(" ", "")
                if no_whitespace.startswith("Type=") or no_whitespace.startswith("Activation="):
                    continue
                elif no_whitespace.startswith("Author="):
                    author = line
                    continue
                elif no_whitespace.startswith("Description="):
                    assert name is not None
                    name = "{}:{}".format(name, line.split("=", 1)[1].lstrip())
                    continue
                elif line[0] == '[' and line[-1] == ']':
                    # convert name format
                    name = line[1:-1]
                    continue

                # dump out name before line
                if name is not None:
                    new_lines.append(f"#{name}")
                    name = None
                if author is not None:
                    new_lines.append(f"{author}")
                    author = None
                new_lines.append(line)

            if old_lines == new_lines:
                #print(f"*** No change in {filename}")
                continue

            print(f"*** Updating '{header}'")

            # update that slice of the original file
            chtdb_data = chtdb_data[:pos] + "\n".join(new_lines) + chtdb_data[end_pos:]

    print(f"Writing {new_chtdb_path}...")
    with open(new_chtdb_path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(chtdb_data)


def old_parse():
        for line in f.read():
            line = line.strip()
            if len(line) == 0:
                continue

            if line[0] == ":" or line.startswith(";:"):
                # finish codes
                if len(current_lines) > 0 and code_count > 0:
                    save_codes(cheats_directory, overwrite, current_lines, current_serials, code_count)
                    current_lines = []
                    current_serials = []
                    code_count = 0

                # merge in comment lines
                if len(current_extra_lines) > 0:
                    if len(current_extra_lines) > 10:
                        print(f"TOSSING {len(current_extra_lines)} EXTRA LINES")
                        print(current_extra_lines[-1:])
                        current_lines += current_extra_lines[-1:]
                    else:
                        current_lines += current_extra_lines
                current_extra_lines = []

                # extra serial for current game?
                if line[0] == ':':
                    current_serials.append(line[1:].strip())
            elif line[0] == "#":
                name = line[1:].strip()
                current_lines = current_lines + current_extra_lines
                current_extra_lines = []
                current_lines.append("")
                current_lines.append(f"[{name}]")
                current_lines.append("Type = Gameshark")
                current_lines.append("Activation = EndFrame")
                code_count += 1
            elif line[0] == ';':
                if line != ";This game currently has no cheats":
                    current_extra_lines.append(line)
            else:
                # merge extra lines
                current_lines = current_extra_lines + current_lines
                current_extra_lines = []
                current_lines.append(line)
        current_lines += current_extra_lines
        save_codes(cheats_directory, overwrite, current_lines, current_serials, code_count)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true", help="Overwrites any existing .cht files")
    parser.add_argument("action", help="Action, update or export")
    parser.add_argument("chtdb_path", help="Path to chtdb.txt")
    parser.add_argument("cheats_directory", help="Directory to read/write .cht files from/to")
    args = parser.parse_args()

    if args.action == "update":
        print(f"Merging cheats from {args.cheats_directory} into {args.chtdb_path}...")
        update_chtdb(args.chtdb_path, args.chtdb_path, args.cheats_directory)
    elif args.action == "export":
        print(f"Parsing {args.chtdb_path}...")
        chtdb = parse_chtdb(args.chtdb_path)

        print(f"Writing files to {args.cheats_directory}")
        generate_cht_files(chtdb, args.cheats_directory, args.overwrite)
    else:
        print(f"Unknown action: {args.action}")
        sys.exit(1)

