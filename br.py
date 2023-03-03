#!/usr/bin/env python
# mostly copied from ranger's bulkrename command (https://github.com/ranger/ranger/blob/master/ranger/config/commands.py#L1114)
# and from ranger's shell_escape util (https://github.com/ranger/ranger/blob/master/ranger/ext/shell_escape.py)
# TODO fix / in filename
import os
import sys
import tempfile
import subprocess
import re

META_CHARS = (
    " ",
    "'",
    '"',
    "`",
    "&",
    "|",
    ";",
    "#",
    "$",
    "!",
    "(",
    ")",
    "[",
    "]",
    "<",
    ">",
    "\t",
)
UNESCAPABLE = set(
    map(chr, list(range(9)) + list(range(10, 32)) + list(range(127, 256)))
)
META_DICT = dict([(mc, "\\" + mc) for mc in META_CHARS])


def shell_quote(string):
    """Escapes by quoting"""
    return "'" + str(string).replace("'", "'\\''") + "'"


def shell_escape(arg):
    """Escapes by adding backslashes"""
    arg = str(arg)
    if UNESCAPABLE & set(arg):
        return shell_quote(arg)
    arg = arg.replace("\\", "\\\\")  # make sure this comes at the start
    for key, value in META_DICT.items():
        arg = arg.replace(key, value)
    return arg


def get_tmpfile(dirname):
    """Generate a unique filename in the given directory"""
    while True:
        tmp_name = next(tempfile._get_candidate_names())
        tmp_file = os.path.join(dirname, tmp_name)
        if not os.path.exists(tmp_file):
            return tmp_file


# throw help message if no paths were passed
if len(sys.argv) == 1:
    print(f"Usage: {os.path.basename(sys.argv[0])} [directory|file]")
    sys.exit(1)

# get files and editor
filenames = sys.argv[1:]
editor = os.environ.get("EDITOR", "vim")

# write list of files into tmp file
tmp_filelist = tempfile.NamedTemporaryFile(delete=False)
tmp_filelist.write("\n".join(filenames).encode("utf-8"))
tmp_filename = tmp_filelist.name
tmp_filelist.close()

# open tmp file in editor
subprocess.call([editor, tmp_filename])

# get new file names and delete tmp file
tmp_filelist = open(tmp_filename, "r")
new_filenames = tmp_filelist.read().split("\n")
tmp_filelist.close()
os.unlink(tmp_filename)

# check if all new names are the same as old names
if all(a == b for a, b in zip(filenames, new_filenames)):
    print("No renaming to be done.")
    sys.exit(1)

# make sure the number of new files equals the number of old files
if len(filenames) != (len(new_filenames)):
    print("Number of new files does not match the number of old files.")
    sys.exit(1)

# create tmp file for renaming review
review_file = tempfile.NamedTemporaryFile(delete=False)
review_lines = []

# add all the renamings to the review file
for old, new in zip(filenames, new_filenames):
    if old == new:
        continue
    review_lines.append(f"{shell_escape(old)} -> {shell_escape(new)}")

# write reviews to file
review_content = "\n".join(review_lines)
review_file.write(review_content.encode("utf-8"))
review_file_name = review_file.name
review_file.close()

# open review file in editor
subprocess.call([editor, review_file.name])

# get files to rename from review file
review_file = open(review_file_name, "r")
rename_pairs = review_file.read().split("\n")
review_file.close()
rename_pairs = [re.split(r" -> ", f) for f in rename_pairs]

cmd_lines_buf = []
cmd_lines_final = []
new_dirs = []

cmd_file = tempfile.NamedTemporaryFile(delete=False)

# add commands to rename files and create new folders if necessary
for rename_pair in rename_pairs:
    if len(rename_pair) != 2:
        print("Error in parsing review file")
        sys.exit(1)

    old, new = rename_pair
    if old == new:
        continue

    basepath, _ = os.path.split(os.path.abspath(new))
    if (
        (basepath is not None)
        and (basepath not in new_dirs)
        and (not os.path.isdir(basepath))
    ):
        cmd_lines_buf.append(f"mkdir -vp -- {shell_escape(basepath)}")
        new_dirs.append(basepath)

    buf_file = get_tmpfile(os.path.dirname(old))
    cmd_lines_buf.append(f"mv -i -- {old} {buf_file}")
    cmd_lines_final.append(f"mv -i -- {buf_file} {new}")
    print(f"{old} -> {buf_file} -> {new}")

# write to command file
cmd_content = "\n".join(cmd_lines_buf) + "\n" + "\n".join(cmd_lines_final)
cmd_file.write(cmd_content.encode("utf-8"))
cmd_file_name = cmd_file.name
cmd_file.close()


# rename files
subprocess.call(["/bin/sh", cmd_file_name])
