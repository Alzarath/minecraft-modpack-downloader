import sys
import os
import requests
import argparse
import json
from pathlib import Path
from zipfile import ZipFile
from slugify import slugify

API_URL="https://addons-ecs.forgesvc.net/api/v2/addon"
USER_AGENT="Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0"

parser = argparse.ArgumentParser(description="Downloads full Minecraft modpacks from Curseforge.")
parser.add_argument('value', metavar='VALUE', type=str, help="URL or ID for the modpack")
parser.add_argument('-f', '--force', action='store_true', help="Forces re-downloading of all files.")

args = parser.parse_args()

def extract_modpack(archive, directory):
    """Extracts an `archive` to a `directory`"""
    with ZipFile(archive, 'r') as zip_ref:
        zip_ref.extractall(directory)

def override_directories(source_dir, target_dir):
    """Replaces the files at `target_dir` with files from `source_dir"""
    for picked_directory in Path(source_dir).glob('*'):
        if picked_directory.is_dir():
            picked_directory.rename(target_dir.joinpath(picked_directory.name))
    
def download_file(url, directory="", force=False):
    """
    Downloads a file from a `url` to a `directory`, optionally replacing files with `force`.

        Paramters
            url (string):       The url to download
            directory (string): The directory to download the file to
            force (boolean):    Whether to replace files that already exist

        Returns:
            file_path (string): The path to the downloaded file
    """
    filename = url.split('/')[-1]
    file_path = Path(Path.cwd().joinpath(directory).joinpath(filename))

    if not force and file_path.exists():
        print("Already downloaded %s. \033[96mSkipping...\033[0m" % filename)
        return file_path

    print("Downloading %s..." % filename, end=" ", flush=True)
    contents = requests.get(url, headers = { 'User-Agent': USER_AGENT })

    if not contents:
        print("\033[91mFailed.\0330m")
        return None

    with open(file_path, 'wb') as output:
        output.write(contents.content)
    print("\033[92mDone.\033[0m")

    return file_path

def fetch_project_id(project_slug, max_search=20):
    """Returns the project ID from a search of a `project_slug` with a maximum items to search through of `max_search`."""
    response = requests.get("%s/search?gameId=432&searchFilter=%s&pageSize=%s&sectionId=4471" % (API_URL, project_slug, str(max_search)), headers = { "User-Agent": USER_AGENT })
    json = response.json()
    for result in json:
        if result["slug"] == project_slug:
            return result["id"]
    print("Error: No results found for '%s'" % project_slug)
    sys.exit(1)

def fetch_info(project_id):
    """Returns the JSON value of a CurseForge project using a `project_id`."""
    response = requests.get("%s/%s" % (API_URL, str(project_id)), headers = { "User-Agent": USER_AGENT })

    return response.json()

def main():
    project_url = None
    project_id = None
    download_id = None
    project_slug = None

    if args.value.isdigit():
        project_id = args.value
    else:
        split_url = args.value.split('/')

        if len(split_url) >= 2:
            if not split_url[-1]:
                # Remove the leading element if it's empty to make things easier with trailing slashes
                split_url.pop()
            if split_url[-2] == "modpacks":
                project_slug = split_url[-1]
            elif split_url[-2] == "projects":
                project_id = split_url[-1]
            elif split_url[-2] == "files":
                project_slug = split_url[-3]
                download_id = split_url[-1]
            else:
                print("Error: Something went wrong parsing the URL.\n\nValid URLs:\nhttps://www.curseforge.com/projects/<ID>\nhttps://www.curseforge.com/minecraft/modpacks/<MODPACK>\nhttps://www.curseforge.com/minecraft/modpacks/<MODPACK>/download/<DOWNLOAD-ID>\n")
                parser.print_help()
                sys.exit(1)
        elif len(split_url) > 0 and split_url[0] == "http:":
            print("Error: Something went wrong parsing the URL.\n\nValid URLs:\nhttps://www.curseforge.com/projects/<ID>\nhttps://www.curseforge.com/minecraft/modpacks/<MODPACK>\nhttps://www.curseforge.com/minecraft/modpacks/<MODPACK>/download/<DOWNLOAD-ID>\n")
            parser.print_help()
            sys.exit(1)
        else:
            import re
            if re.search('[\W-]', args.value):
                print("Error: Invalid argument.\n")
                parser.print_help()
                sys.exit(1)
            else:
                project_slug = args.value

    if project_slug:
        project_id = fetch_project_id(project_slug)

    print("Fetching project info...", end = " ", flush=True)
    project_info = fetch_info(project_id)
    if project_info:
        print("\033[92mDone.\033[0m")
    else:
        print("")
        print("\033[91mFailed.\0330m. Could not fetch project info.")
        sys.exit(1)

    file_url = None
    # If the download ID is known, get the file URL
    if download_id:
        for file_index in project_info["latestFiles"]:
            if file_index["id"] == int(download_id):
                file_url = file_index["downloadUrl"]
                break

    # If the download ID is not known or fetching the file url from the download ID failed, get the first file URL
    if not file_url:
        file_url = file_url or project_info["latestFiles"][0]["downloadUrl"]

    write_path = Path.cwd().joinpath(slugify(project_info["name"]))
    #write_path = os.path.abspath(slugify(project_info["name"]))
    if not write_path.exists():
        write_path.mkdir()
        print("Directory Created.")

    modpack_path = download_file(file_url, write_path)
    if not modpack_path:
        print("Error: Failed to download modpack.")
        sys.exit(1)
    extract_modpack(modpack_path, write_path)

    transfer_path = write_path.joinpath("minecraft")
    if not transfer_path.exists():
        transfer_path.mkdir()

    with open("%s/manifest.json" % str(write_path), 'r') as input_file:
        input_file_data = input_file.read()

    manifest = json.loads(input_file_data)

    mod_path = transfer_path.joinpath("mods")
    if not mod_path.exists():
        mod_path.mkdir()
    for mod in manifest["files"]:
        fetch_url = "%s/%s/file/%s/download-url" % (API_URL, mod["projectID"], mod["fileID"])
        file_url = requests.get(fetch_url, headers = { "User-Agent": USER_AGENT }).text
        if file_url:
            download_file(file_url, mod_path, args.force)
    
    override_directories(transfer_path.joinpath("overrides"), transfer_path)

    print("Modpack Download finished.")

main()
