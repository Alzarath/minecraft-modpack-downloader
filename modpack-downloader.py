import sys
import os
import requests
import argparse
import json
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

def extract_modpack(archive, directory):
    """Extracts an `archive` to a `directory`"""
    with ZipFile(archive, 'r') as zip_ref:
        zip_ref.extractall(directory)

def override_files(source_dir, target_dir):
    """Copy and replace files from inside `source_dir` to `target_dir`"""
    for picked_file in Path(source_dir).glob('*'):
        dest_file = target_dir.joinpath(picked_file.name)
        if picked_file.is_dir():
            dir_util.copy_tree(str(picked_file), str(dest_file))
        else:
            file_util.copy_file(str(picked_file), str(dest_file))
    
def download_file(url, directory="", force=False):
    """
    Downloads a file from a `url` to a `directory`, optionally replacing files with `force`.

        Paramters:
            url (string):       The url to download
            directory (string): The directory to download the file to
            force (boolean):    Whether to replace files that already exist

        Returns:
            file_path (string): The path to the downloaded file
    """
    filename = url.split('/')[-1]
    file_path = Path(Path.cwd().joinpath(directory).joinpath(filename))

    if not force and file_path.exists():
        print("Already downloaded %s. \033[96mSkipping...\033[0m" % filename, flush=True)
        return file_path

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
        mod_failures = True
        return None

    with file_path.open('wb') as output:
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
    response = None
    try:
        response = requests.get("%s/%s" % (API_URL, str(project_id)), headers = { "User-Agent": USER_AGENT })
    except:
        print("\033[91mFailed.\033[0m.")
        return None
    print("\033[92mDone.\033[0m")

    return response.json()

def main():
    mod_failures = False
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
                project_id = int(split_url[-1])
            elif split_url[-2] == "files":
                project_slug = split_url[-3]
                download_id = int(split_url[-1])
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

    if args.download:
        download_id = args.download

    if project_slug:
        project_id = fetch_project_id(project_slug)

    print("Fetching project info...", end = " ", flush=True)
    project_info = fetch_info(project_id)
    if not project_info:
        print("Error: Could not fetch project info.")
        sys.exit(1)

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

    filename_list = file_url.split('/')[-1].split('.')
    filename_list.pop()
    filename = ''.join(filename_list)

    project_path = Path.cwd().joinpath(slugify(project_info["name"]))
    if not project_path.exists():
        project_path.mkdir()

    destination_path = project_path.joinpath(slugify(filename))
    if not destination_path.exists():
        destination_path.mkdir()
        print("Created directory %s/%s." % (project_path.name, destination_path.name))

    modpack_path = destination_path.joinpath("modpack")
    if not modpack_path.exists():
        modpack_path.mkdir()

    download_path = destination_path.joinpath("download")
    if not download_path.exists():
        download_path.mkdir()

    modpack_file = download_file(file_url, download_path, args.force)
    if not modpack_file or not modpack_file.exists() or modpack_file.stat().st_size == 0:
        print("Error: Failed to download modpack.")
        sys.exit(1)

    extracted_path = download_path.joinpath("extracted")
    if not extracted_path.exists():
        extracted_path.mkdir()

    extract_modpack(modpack_file, extracted_path)

    manifest_file = extracted_path.joinpath("manifest.json")
    with manifest_file.open('r') as manifest_file:
        manifest_data = manifest_file.read()

    manifest = json.loads(manifest_data)

    mod_download_path = download_path.joinpath("mods")
    if not mod_download_path.exists():
        mod_download_path.mkdir()

    mods_path = modpack_path.joinpath("mods")
    if not mods_path.exists():
        mods_path.mkdir()

    progress_file = destination_path.joinpath("progress.json")
    if progress_file.exists() and progress_file.stat().st_size > 0:
        with progress_file.open('r') as progress_file:
            progress_data = progress_file.read()
        progress = json.loads(progress_data)
    else:
        progress_file.touch()
        progress = {}

    interrupted = False
    try:
        for mod in manifest["files"]:
            progress_modified = False
            mod_project_id = str(mod["projectID"])
            mod_file_id = str(mod["fileID"])

            if mod_project_id not in progress:
                progress[mod_project_id] = {}
                progress_modified = True
            if mod_file_id not in progress[mod_project_id]:
                progress[mod_project_id][mod_file_id] = {}
                progress_modified = True

            if args.force or "downloaded" not in progress[mod_project_id][mod_file_id] or not progress[mod_project_id][mod_file_id]["downloaded"] or "name" not in progress[mod_project_id][mod_file_id]:
                file_url = None
                fetch_url = None
                if "url" in progress[mod_project_id][mod_file_id]:
                    file_url = progress[mod_project_id][mod_file_id]["url"]
                else:
                    fetch_url = "%s/%s/file/%s/download-url" % (API_URL, mod_project_id, mod_file_id)
                mod_download_file = None

                if not file_url:
                    if not fetch_url:
                        continue
                    try:
                        file_url = requests.get(fetch_url, headers = { "User-Agent": USER_AGENT }).text
                    except KeyboardInterrupt:
                        interrupted = True
                        print("Keyboard interrupted.")
                        break
                    except:
                        print("Attempted to acquire mod information for %s. \033[91mFailed.\033[0m" % mod_project_id)
                        mod_failures = True
                        continue

                if file_url:
                    if "url" not in progress[mod_project_id][mod_file_id] or progress[mod_project_id][mod_file_id]["url"] != file_url:
                        progress[mod_project_id][mod_file_id]["url"] = file_url
                        progress_modified = True

                    try:
                        mod_download_file = download_file(file_url, mod_download_path, args.force)
                    except KeyboardInterrupt:
                        interrupted = True
                        print("Keyboard interrupted.")
                        break

                    if mod_download_file:
                        if "name" not in progress[mod_project_id][mod_file_id]:
                            progress[mod_project_id][mod_file_id]["name"] = mod_download_file.name
                            progress_modified = True
                        progress_modified = True
                    progress[mod_project_id][mod_file_id]["downloaded"] = (mod_download_file != None)
            else:
                print("Already downloaded %s. \033[96mSkipping...\033[0m" % (progress[mod_project_id][mod_file_id].get("name") or mod_project_id), flush=True)
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
        if progress_modified:
            try:
                print("Saving download progress...", end=" ", flush=True)
                with progress_file.open('w') as output:
                    output.write(json.dumps(progress, indent=4))
                print("\033[92mDone.\033[0m")
            except KeyboardInterrupt:
                pass
            except:
                print("\033[91mFailed.\033[0m")
                raise
        if interrupted:
            return

    readme = {}
    readme["path"] = destination_path.joinpath("README.md")
    readme["text"] = '\n'.join((f"Welcome to the Minecraft Modpack Downloader's installation guide for {manifest['name']}!",
                                 "",
                                 "To install the modpack:",
                                 "",
                                 f"1. Download and install [Minecraft Forge for Minecraft {manifest['minecraft']['version']}](https://files.minecraftforge.net/net/minecraftforge/forge/index_{manifest['minecraft']['version']}.html). (Recommended: {manifest['minecraft']['modLoaders'][0]['id']})",
                                 "2. Run this version of Minecraft Forge from your Minecraft launcher to generate an installation folder if you haven't already.",
                                f"3. Copy the contents of `{str(modpack_path)}` to your Minecraft Forge installation folder."
                              ))

    with readme["path"].open('w') as output:
        output.write(readme["text"])
    print("Modpack Download finished.")
    if mod_failures:
        print("There were errors downloading mods. Please try again.")

main()
