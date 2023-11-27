#!/usr/bin/env python3

import argparse
import os
import json
import re

import subprocess

TEMPORARY_FILE_SUFFIX = "_tmp.scad"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="The scad file to be compiled")
    parser.add_argument("-o", "--output", help="Path to the output directory (created if it doesn't exist)")
    parser.add_argument("-fn", help="Set number of fragments", type=int, default=0)

    args = parser.parse_args()

    if args.output:
        output_dir = args.output
    else:
        output_dir = args.file[:-5] + "_stl"

    if args.fn > 0:
        number_of_fragments = args.fn
    else:
        number_of_fragments = None

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Read the scad file, looking for MULTIPART_COMPILE directives
    print("Reading {}...".format(args.file))
    header_start = None
    header_end = None
    compilation_descriptions = {}
    with open(args.file) as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if "MULTIPART_COMPILE" in line:
            if "begin" in line:
                header_start = i
            elif "end" in line:
                header_end = i
                break
            elif header_start is not None:
                # Try to parse the json header and extract the variable name and default value
                first_open_bracket = line.find("{")
                last_close_bracket = line.rfind("}")
                first_equal_sign = line.find("=")
                first_semicolon = line.find(";")
                if (first_open_bracket != -1 and first_open_bracket < last_close_bracket
                        and first_equal_sign != -1 and first_semicolon != -1):
                    header = json.loads(line[first_open_bracket:last_close_bracket+1])
                    var_name = line[:first_equal_sign].strip()
                    default_value = line[first_equal_sign+1:first_semicolon].strip()
                    header["default"] = default_value
                    compilation_descriptions[var_name] = header

    print("Found {} compilation descriptions".format(len(compilation_descriptions)))

    # Write a temporary file without the MULTIPART_COMPILE directives
    temp_file = args.file[:-5] + TEMPORARY_FILE_SUFFIX
    with open(temp_file, "w") as f:
        f.writelines(lines[:header_start])
        f.writelines(lines[header_end + 1:])

    # Compile the temporary file according to the compilation descriptions
    tasks = {}
    for var_name, header in compilation_descriptions.items():
        assert "values" in header
        values = header["values"]
        assert "name" in header
        name = header["name"]

        # make sure we set all the other variables to their default values
        base_openscad_cmd = "".join(["{} = {}; ".format(key, header["default"])
                                for key, header in compilation_descriptions.items()
                                if key != var_name])

        if number_of_fragments is not None:
            base_openscad_cmd += "$fn = {}; ".format(number_of_fragments)

        for value in values:
            if isinstance(value, bool):
                value = str(value).lower()

            openscad_cmd = base_openscad_cmd + "{} = {}; ".format(var_name, value)

            if "{}" in name:
                out_file = name.format(value)
            else:
                out_file = name

            out_file = os.path.join(output_dir, out_file + ".stl")

            print("starting to compile {} to {}".format(args.file, out_file))
            t = subprocess.Popen(["openscad", "-o", out_file, "-D", openscad_cmd, temp_file])
            tasks[out_file] = t

    # Wait for all the tasks to finish
    for out_file, t in tasks.items():
        t.wait()
        print("finished compiling {}".format(out_file))

    os.remove(temp_file)
    print("Done!")


if __name__ == "__main__":
    main()
