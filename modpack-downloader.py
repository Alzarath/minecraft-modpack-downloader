#!/usr/bin/env python3
import sys
import os
import requests
import argparse
import json
import hashlib
from distutils import dir_util
from distutils import file_util
from pathlib import Path
from zipfile import ZipFile
from slugify import slugify

API_URL="https://addons-ecs.forgesvc.net/api/v2/addon"
USER_AGENT="Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0"

parser = argparse.ArgumentParser(description="Downloads full Minecraft modpacks from Curseforge.")
parser.add_argument('value', metavar='PACK', type=str, help="URL or ID for the modpack")
parser.add_argument('download', metavar='DOWN', type=int, nargs='?', help="ID for the modpack download")
parser.add_argument('-f', '--force', action='store_true', help="Forces re-downloading of all files.")

args = parser.parse_args()

error_msg = "Catastrophic Error."

def extract_modpack(archive, directory):
    """Extracts an `archive` to a `directory`"""
    try:
        with ZipFile(archive, 'r') as zip_ref:
            zip_ref.extractall(directory)
    except KeyboardInterrupt:
        raise
    except:
        return False
    return True


def override_files(source_dir: Path, target_dir: Path):
    """Copy and replace files from inside `source_dir` to `target_dir`"""
    try:
        for picked_file in Path(source_dir).glob('*'):
            dest_file = target_dir.joinpath(picked_file.name)
            if picked_file.is_dir():
                dir_util.copy_tree(str(picked_file), str(dest_file))
            else:
                file_util.copy_file(str(picked_file), str(dest_file))
    except KeyboardInterrupt:
        raise
    except:
        return False
    return True

def download_file(url: str, directory: Path, force: bool=False, md5: str=None):
    """
    Downloads a file from a `url` to a `directory`, optionally replacing files with `force`.

        Paramters:
            url (string):       The url to download
            directory (string): The directory to download the file to
            force (boolean):    Whether to replace files that already exist

        Returns:
            contents (json):    The download response
            file_path (string): The path to the downloaded file
    """
    filename = url.split('/')[-1]
    file_path = directory.joinpath(filename).resolve()

    if not force and file_path.exists() and (md5 is None or validate_file(file_path, md5)):
        print("Already downloaded %s. \033[96mSkipping...\033[0m" % filename, flush=True)
        return (None, file_path)

    contents = None
    print("Downloading %s..." % filename, end=" ", flush=True)
    try:
        contents = requests.get(url, headers = { 'User-Agent': USER_AGENT })
    except KeyboardInterrupt:
        raise
    except:
        pass

    if not contents:
        print("\033[91mFailed.\033[0m")
        return (None, None)

    # If no md5 was supplied, supply it
    if not md5:
        md5 = contents.headers["ETag"].strip("\"")

    with file_path.open('wb') as output:
        output.write(contents.content)

    # Validate the downloaded file to determine if the download was successful
    if validate_file(file_path, md5):
        print("\033[92mDone.\033[0m")
    else:
        print("\033[91mFailed.\033[0m")

    return (contents, file_path)

def validate_file(checked_file_path: Path, md5: str):
    if not Path(checked_file_path).exists() or not md5:
        return False

    with open(checked_file_path, 'rb') as opened_file:
        file_data = opened_file.read()
    file_hash = hashlib.md5(file_data).hexdigest()

    return (file_hash == md5)


def fetch_project_id(project_slug: str, max_search: int=20):
    """Returns the project ID from a search of a `project_slug`, searching through up to `max_search` items."""
    response = requests.get("%s/search?gameId=432&searchFilter=%s&pageSize=%s&sectionId=4471" % (API_URL, project_slug, str(max_search)), headers = { "User-Agent": USER_AGENT })
    json = response.json()
    for result in json:
        if result["slug"] == project_slug:
            return result["id"]
    error_msg = "Error: No results found for '%s'" % project_slug
    sys.exit(error_msg)

def fetch_info(project_id: int):
    """Returns the JSON value of a CurseForge project from a `project_id`."""
    response = None
    try:
        response = requests.get("%s/%s" % (API_URL, str(project_id)), headers = { "User-Agent": USER_AGENT })
    except:
        print("\033[91mFailed.\033[0m.")
        return None
    print("\033[92mDone.\033[0m")

    return response.json()

def create_missing_dir(created_dir: Path):
    if not created_dir.exists():
        return created_dir.mkdir()
    return created_dir

def main():
    project_url = None
    project_id = None
    download_id = None
    project_slug = None

    if args.value.isdigit():
        # If the given value is numbers, it can be assumed to be a project ID
        project_id = args.value
    else:
        split_url = args.value.split('/')

        # Assume the given value is a modpack URL
        if len(split_url) >= 2:
            if not split_url[-1]:
                split_url.pop() # Remove empty trailing element
            if split_url[-2] == "modpacks":
                project_slug = split_url[-1]
            elif split_url[-2] == "projects":
                project_id = int(split_url[-1])
            elif split_url[-2] == "files":
                project_slug = split_url[-3]
                download_id = int(split_url[-1])
            # The modpack URL is probably invalid
            else:
                error_msg = "Error: Unable to parse the URL.\n\nValid URLs:\nhttps://www.curseforge.com/projects/<ID>\nhttps://www.curseforge.com/minecraft/modpacks/<MODPACK>\nhttps://www.curseforge.com/minecraft/modpacks/<MODPACK>/download/<DOWNLOAD-ID>"
                parser.print_help()
                sys.exit(error_msg)
        # The URL is probably invalid
        elif len(split_url) > 0 and split_url[0] == "http:":
            error_msg = "Error: Unable to parse the URL.\n\nValid URLs:\nhttps://www.curseforge.com/projects/<ID>\nhttps://www.curseforge.com/minecraft/modpacks/<MODPACK>\nhttps://www.curseforge.com/minecraft/modpacks/<MODPACK>/download/<DOWNLOAD-ID>"
            parser.print_help()
            sys.exit(error_msg)
        else:
            project_slug = slugify(args.value)
            # The value does not look like anything usable
            if project_slug != args.value:
                error_msg = "Error: Invalid argument."
                parser.print_help()
                sys.exit(error_msg)

    if args.download:
        download_id = args.download

    if project_slug:
        project_id = fetch_project_id(project_slug)

    # Fetches the modpack's info that contains the download URL and IDs
    print("Fetching project info...", end = " ", flush=True)
    project_info = fetch_info(project_id)
    if not project_info:
        error_msg = "Error: Could not fetch project info."
        sys.exit(error_msg)

    file_url = None
    # If the download ID is known, get the file URL
    if download_id:
        fetch_url = "%s/%s/file/%s/download-url" % (API_URL, project_id, download_id)
        file_url = requests.get(fetch_url, headers = { "User-Agent": USER_AGENT }).text
    else:
        download_id = project_info["latestFiles"][-1]["id"]

    # If the download ID is not known or fetching the file url from the download ID failed, get the latest file URL
    if not file_url:
        file_url = project_info["latestFiles"][-1]["downloadUrl"]

    # Grab the filename from the modpack url that excludes the file extension
    filename_list = file_url.split('/')[-1].split('.')
    filename_list.pop()
    filename = ''.join(filename_list)

    # Directory that holds sub-directories for different versions of the modpack
    project_path = create_missing_dir(Path.cwd().joinpath(slugify(project_info["name"])))

    # Directory that holds the specific version of the modpack
    destination_path = project_path.joinpath(slugify(filename))
    if not destination_path.exists():
        destination_path.mkdir()
        print("Created directory %s/%s." % (project_path.name, destination_path.name))

    # Directory where the "complete" modpack will be stored
    modpack_path = create_missing_dir(destination_path.joinpath("modpack"))

    # Download folder for the modpack and mods
    download_path = create_missing_dir(destination_path.joinpath("download"))

    # Modpack archive
    _, modpack_file = download_file(file_url, download_path, args.force)
    if not modpack_file or not modpack_file.exists() or modpack_file.stat().st_size == 0:
        error_msg = "Error: Failed to download modpack."
        sys.exit(error_msg)

    # Directory where the modpack files will be extracted for reading
    extracted_path = create_missing_dir(download_path.joinpath("extracted"))

    extract_modpack(modpack_file, extracted_path)

    # Manifest file, used to acquire modpack information
    manifest_file = extracted_path.joinpath("manifest.json")
    with manifest_file.open('r') as manifest_file:
        manifest_data = manifest_file.read()

    manifest = json.loads(manifest_data)

    # Directory that downloaded mods will be stored
    mod_download_path = create_missing_dir(download_path.joinpath("mods"))

    # Directory that downloaded mods will write to
    mods_path = create_missing_dir(modpack_path.joinpath("mods"))

    # File where mod information and download progress will be stored
    progress_file = destination_path.joinpath("progress.json")
    if progress_file.exists() and progress_file.stat().st_size > 0:
        with progress_file.open('r') as open_progress_file:
            progress_data = open_progress_file.read()
        progress = json.loads(progress_data)
    else:
        progress_file.touch()
        progress = {}

    # Loop through all the mods and attempt to download them
    interrupted = False
    progress_modified = False
    mod_failures = []
    retry = True
    while retry:
        retry = False
        try:
            for mod in manifest["files"]:
                mod_project_id = str(mod["projectID"])
                mod_file_id = str(mod["fileID"])

                # Initialize mod progress category
                if mod_project_id not in progress:
                    progress[mod_project_id] = {}
                    progress_modified = True
                if mod_file_id not in progress[mod_project_id]:
                    progress[mod_project_id][mod_file_id] = {}
                    progress_modified = True

                mod_info = progress[mod_project_id][mod_file_id]

                # Initialize mod progress variables
                force_download = args.force

                mod_info_defaults = {
                    "name" : None,
                    "url" : None,
                    "md5" : "",
                    "downloaded" : False
                }

                for key, val in mod_info_defaults.items():
                    if key not in mod_info:
                        mod_info[key] = val
                        force_download = progress_modified = True

                # Validate mod file if it exists
                if not force_download and mod_info["downloaded"] and mod_info["name"] and mod_info["md5"] != "":
                    mod_download_file = mod_download_path.joinpath(mod_info["name"])
                    if validate_file(mod_download_file, mod_info["md5"]):
                        print("Already downloaded %s (md5sum). \033[96mSkipping...\033[0m" % (mod_info.get("name") or mod_project_id), flush=True)
                        continue
                    else:
                        force_download = True

                # Download mod file if it's been designated to
                if force_download or not mod_info["name"] or not mod_info["downloaded"] or not mod_info["url"] or mod_info["md5"] == "":
                    file_url = mod_info["url"]
                    fetch_url = None
                    mod_download_file = None

                    # Get the mod download URL if one is not already defined
                    if not file_url:
                        fetch_url = "%s/%s/file/%s/download-url" % (API_URL, mod_project_id, mod_file_id)
                        try:
                            file_url = requests.get(fetch_url, headers = { "User-Agent": USER_AGENT }).text
                        except KeyboardInterrupt:
                            interrupted = True
                            break
                        except:
                            print("Attempted to acquire mod information for %s. \033[91mFailed.\033[0m" % mod_project_id)
                            mod_failures.append(mod)
                            continue

                    # Download the mod file
                    if file_url:
                        if not mod_info["url"] or mod_info["url"] != file_url:
                            mod_info["url"] = file_url
                            progress_modified = True

                        try:
                            download_response, mod_download_file = download_file(file_url, mod_download_path, args.force, mod_info["md5"])
                            if download_response != None:
                                new_hash = download_response.headers["ETag"].strip("\"")
                                if mod_info["md5"] != new_hash:
                                    progress_modified = True
                                    mod_info["md5"] = new_hash
                        except KeyboardInterrupt:
                            interrupted = True
                            break

                        if mod_download_file:
                            progress_modified = True
                            mod_info["name"] = mod_download_file.name
                        else:
                            mod_failures = True
                        mod_info["downloaded"] = (mod_download_file != None)
                else:
                    print("Already downloaded %s. \033[96mSkipping...\033[0m" % (mod_info.get("name") or mod_project_id), flush=True)

            # Override mods and write other files from modpack-supplied files
            if not interrupted:
                try:
                    print("Overriding files...", end=" ", flush=True)
                    override_files(mod_download_path, mods_path)
                    override_files(extracted_path.joinpath("overrides"), modpack_path)
                    print("\033[92mDone.\033[0m")
                except:
                    print("\033[91mFailed.\033[0m")
                    raise
        except:
            raise
        finally:
            # If any mods failed to download, inform the user and allow them to decide what to do.
            input_response = None

            if interrupted:
                error_msg = "Keyboard interrupted."
            elif mod_failures:
                error_msg = "Error: Failed to download all mods."
                print(f"{error_msg} Would you like to try again? (Y/N)")
                input_response = input()[:1].lower()
                while input_response not in ["n", "y"]:
                    input_response = input()[:1].lower()
                if input_response == "y":
                    mod_failures = None
                    retry = True

            # If the progress was modified, write the progress to `progress.json` whether or not the download succeeded
            if progress_modified:
                try:
                    print("Saving download progress...", end=" ", flush=True)
                    with progress_file.open('w') as output:
                        output.write(json.dumps(progress, indent=4))
                    print("\033[92mDone.\033[0m")
                except:
                    print("\033[91mFailed.\033[0m")
                    raise

            # If the program has been interrupted by the user, stop it entirely
            if interrupted:
                sys.exit(error_msg)
            elif input_response == "n":
                sys.exit(error_msg)

    # Create a README for installing the modpack. TODO: Other mod APIs (e.g. Fabric)
    readme = {
        "path" : destination_path.joinpath("README.md"),
        "text" : '\n'.join((f"Welcome to the Minecraft Modpack Downloader's installation guide for {manifest['name']}!",
                             "",
                             "To install the modpack:",
                             "",
                            f"1. Download and install [Minecraft Forge for Minecraft {manifest['minecraft']['version']}](https://files.minecraftforge.net/net/minecraftforge/forge/index_{manifest['minecraft']['version']}.html). (Recommended: {manifest['minecraft']['modLoaders'][0]['id']})",
                             "2. Run this version of Minecraft Forge from your Minecraft launcher to generate an installation folder if you haven't already.",
                            f"3. Copy the contents of `{str(modpack_path)}` to your Minecraft Forge installation folder."
                          ))
    }

    # Write the README to the designated README.md file
    with readme["path"].open('w') as output:
        output.write(readme["text"])
    print("Modpack Download finished.")

if __name__ == "__main__":
    main()
