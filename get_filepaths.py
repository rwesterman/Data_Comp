import os
from collections import defaultdict


def get_csv_paths(top_path):
    """
    Walks through current directory and subdirectories, then returns paths to all .csv and .tsv files
    :return: Dictionary with dirpath as key, filename as value
    """
    # exclude is a set holding all dirnames to be excluded
    exclude = {"fails", "archive", "exclude", "fail", "backup"}
    # files is a dict that defaults to lists, so values can be appended to keys
    files = defaultdict(list)
    for dirpath, dirnames, filenames in os.walk(top_path, topdown=True):
        dirnames[:] = [d for d in dirnames if d.lower() not in exclude]

        for filename in filenames:

            # gather .csv and .tsv files
            if ".csv" in str(filename).lower() or ".tsv" in str(filename).lower():
                # Add filename to the key of dirpath
                files[dirpath].append(filename)
    return files


def filter_data(files_dict):
    """

    :param files_dict: A dictionary where each key is the dirpath, and values are a list of filenames in that dirpath
    :return:
    """
    # sort_files will hold a list of dictionaries, where each dictionary has smart, thermal, and power as keys
    sort_files = []

    for dirpath, filenames in files_dict.items():

        # holder will store the full paths for smart, thermal, and power data
        holder = {}
        # go through each filename in the filenames list, sort the files based on their
        for filename in filenames:

            if "smart" in str(filename).lower():
                # Don't need to catch suffix because files are in named and nested directories
                holder["smart"] = os.path.join(str(dirpath), filename)

            if "therm" in str(filename).lower():
                holder["thermal"] = os.path.join(str(dirpath), filename)

            if "3p3" in str(filename).lower():
                holder["3p3v"] = os.path.join(str(dirpath), filename)

            if "12v" in str(filename).lower():
                holder["12v"] = os.path.join(str(dirpath), filename)

        # Add the holder dictionary to the list sort_files
        sort_files.append(holder)

    return sort_files
