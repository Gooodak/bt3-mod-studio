"""Updates: of BT3 Mod Studio itself and of the game (the extended edition of the port), from their GitHub releases.

- The tool: its release's zip holds the folder bt3-mod-studio/ (exe, runtime, guides). A running program cannot
  replace itself on Windows: the files are put aside, and a small script (written to a temporary folder) waits for
  the tool to close, copies them over, and starts it again.
- The game: a release zip of the port holds the folder Tenkaichi3Decomp/ (no game data); it is unpacked over the
  player's game folder, as an update of the port is done by hand. The game must be closed. The first time the
  official program is replaced, it is kept as Tenkaichi3Decomp-officielle.exe (and its .dat), to go back.
  What was installed is written in bt3ms_installed.json in the game folder.
GitHub answers about a private repository only with a token: BT3MS_GITHUB_TOKEN or GH_TOKEN (never needed once the
repositories are public)."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile

TOOL_VERSION = "1.1.3"
TOOL_REPO = "Gooodak/bt3-mod-studio"
PORT_REPO = "Gooodak/bt3-port-etendu"     # the extended edition
OFFICIAL_REPO = "z3xox/Tenkaichi3Decomp"   # the official one (its zip, to go back)
MARK = "bt3ms_installed.json"
GAME_EXE = "Tenkaichi3Decomp.exe"


class UpdateError(Exception):
    pass


def _token():
    return os.environ.get("BT3MS_GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""


def _get(url, accept="application/vnd.github+json", timeout=10):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "BT3-Mod-Studio"})
    if _token():
        req.add_header("Authorization", "Bearer " + _token())
    return urllib.request.urlopen(req, timeout=timeout)


def latest(repo):
    """The newest release of a repository: {"tag", "title", "notes", "assets": [{"name", "url", "size"}]}."""
    try:
        with _get(f"https://api.github.com/repos/{repo}/releases/latest") as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise UpdateError("pas de version publiée, ou dépôt privé (inaccessible sans autorisation)")
        raise UpdateError(f"GitHub a répondu {e.code}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise UpdateError(f"pas de connexion ({getattr(e, 'reason', e)})")
    return {"tag": data.get("tag_name", ""), "title": data.get("name") or data.get("tag_name", ""),
            "notes": data.get("body") or "",
            "assets": [{"name": a["name"], "url": a["url"], "size": a.get("size", 0)} for a in data.get("assets", [])]}


def releases(repo, count=30):
    """The repository's releases, newest first: [{"tag", "date" (UTC, "2026-10-17T22:01:31Z")}]."""
    try:
        with _get(f"https://api.github.com/repos/{repo}/releases?per_page={count}") as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise UpdateError(f"GitHub a répondu {e.code}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise UpdateError(f"pas de connexion ({getattr(e, 'reason', e)})")
    return [{"tag": d.get("tag_name", ""), "date": d.get("published_at") or ""} for d in data if not d.get("draft")]


def official_installed(game, known=None):
    """(tag, exact) of the official program installed: what the tool installed (exact), else a guess from the
    program file's date: the newest official release published before it (the zip is unpacked after it is out).
    (None, False) when there is no official program."""
    if game.edition() != "officielle":
        return None, False
    have = installed(game)
    if have.get("edition") == "officielle" and have.get("tag"):
        return have["tag"], True
    import datetime
    try:
        stamp = os.path.getmtime(os.path.join(game_dir(game), GAME_EXE))
    except OSError:
        return None, False
    when = datetime.datetime.fromtimestamp(stamp, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rels = known if known is not None else releases(OFFICIAL_REPO)
    before = [r for r in rels if r["date"] and r["date"] <= when]
    return (before[0]["tag"] if before else None), False


def official_status(game):
    """What z3xox has published, against what is installed: {"latest": release, "have", "exact", "update": bool,
    "extended_behind": bool (the extended edition's newest release is built on an older official one)}."""
    rel = latest(OFFICIAL_REPO)
    rels = releases(OFFICIAL_REPO)
    rel["date"] = next((r["date"] for r in rels if r["tag"] == rel["tag"]), "")
    have, exact = official_installed(game, rels)
    out = {"latest": rel, "have": have, "exact": exact,
           "update": game.edition() == "officielle" and newer(rel["tag"], have or "v0"), "extended_behind": False}
    try:
        ext = latest(PORT_REPO)["tag"]  # v0.1.NN-etendu.K: built on the official v0.1.NN
        base = re.match(r"v0\.1\.\d+(\.\d+)?", ext)
        out["extended_behind"] = bool(base) and newer(rel["tag"], base.group(0))
    except UpdateError:
        pass
    return out


def version_key(tag):
    """(numbers...) of a tag such as v1.0.2 or v0.1.38-etendu.2, to compare."""
    nums = [int(x) for x in re.findall(r"\d+", tag)]
    return tuple(nums)


def newer(tag, than):
    return bool(tag) and version_key(tag) > version_key(than)


def download(asset, dest, progress=None):
    """Downloads a release asset to `dest`; progress(done, total) now and then."""
    try:
        with _get(asset["url"], accept="application/octet-stream", timeout=30) as r, open(dest, "wb") as f:
            total, done = asset.get("size") or 0, 0
            while True:
                block = r.read(1 << 16)
                if not block:
                    break
                f.write(block)
                done += len(block)
                if progress:
                    progress(done, total)
    except (urllib.error.URLError, OSError) as e:
        raise UpdateError(f"téléchargement impossible ({getattr(e, 'reason', e)})")
    return dest


def pick(assets, pattern):
    return next((a for a in assets if re.search(pattern, a["name"], re.I)), None)


# ---- the game ----------------------------------------------------------------------------------------------------
def game_dir(game):
    return os.path.dirname(os.path.abspath(game.root))


def installed(game):
    """What the tool installed in the game folder last ({"edition", "tag"}), or {}."""
    try:
        with open(os.path.join(game_dir(game), MARK), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def game_running():
    r = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {GAME_EXE}", "/NH"], capture_output=True, text=True)
    return GAME_EXE.lower() in r.stdout.lower()


def game_update(game):
    """(the release to install or None, why): the extended edition's newest release, when the game is not it yet or
    has an older one."""
    rel = latest(PORT_REPO)
    if not pick(rel["assets"], r"windows.*\.zip$"):
        raise UpdateError("la dernière version de l'édition étendue n'a pas de zip Windows")
    have = installed(game)
    if game.edition() != "etendu":
        return rel, "le jeu installé est l'édition officielle"
    if have.get("edition") == "etendu" and not newer(rel["tag"], have.get("tag", "")):
        return None, f"à jour ({have.get('tag')})"
    return rel, "nouvelle version" if have.get("tag") else "version installée inconnue"


def install_game(game, zip_path, edition, tag):
    """Unpacks a port release zip (its folder Tenkaichi3Decomp/) over the game folder; keeps the official program
    aside the first time. Returns the number of files written."""
    if game_running():
        raise UpdateError("le jeu est ouvert : ferme-le d'abord")
    dest = game_dir(game)
    if game.edition() == "officielle" and edition == "etendu":
        for name in (GAME_EXE, "Tenkaichi3Decomp.dat"):
            src = os.path.join(dest, name)
            keep = os.path.join(dest, name.replace("Tenkaichi3Decomp", "Tenkaichi3Decomp-officielle", 1))
            if os.path.exists(src) and not os.path.exists(keep):
                shutil.copy2(src, keep)
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            parts = info.filename.replace("\\", "/").split("/")
            if parts[0].lower() == "tenkaichi3decomp":
                parts = parts[1:]
            rel = "/".join(p for p in parts if p)
            if not rel or info.is_dir():
                continue
            if rel.startswith("/") or ".." in rel.split("/") or rel.lower().startswith("gamedata/"):
                continue  # (never outside the game folder, never its data)
            target = os.path.join(dest, *rel.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            n += 1
    with open(os.path.join(dest, MARK), "w", encoding="utf-8") as f:
        json.dump({"edition": edition, "tag": tag}, f)
    game._cache.pop("edition", None)
    return n


def back_to_official(game):
    """Puts the official program kept aside back (the files of the extended edition's zip stay: the official one
    ignores them). True when it was there."""
    if game_running():
        raise UpdateError("le jeu est ouvert : ferme-le d'abord")
    dest = game_dir(game)
    done = False
    for name in (GAME_EXE, "Tenkaichi3Decomp.dat"):
        keep = os.path.join(dest, name.replace("Tenkaichi3Decomp", "Tenkaichi3Decomp-officielle", 1))
        if os.path.exists(keep):
            shutil.copy2(keep, os.path.join(dest, name))
            done = True
    if done:
        with open(os.path.join(dest, MARK), "w", encoding="utf-8") as f:
            json.dump({"edition": "officielle", "tag": ""}, f)
        game._cache.pop("edition", None)
    return done


# ---- the tool ----------------------------------------------------------------------------------------------------
def tool_update():
    """The tool's newest release when it is newer than this one, else None."""
    rel = latest(TOOL_REPO)
    return rel if newer(rel["tag"], TOOL_VERSION) and pick(rel["assets"], r"\.zip$") else None


EXE_NAME = "BT3 Mod Studio.exe"
STAGE_PREFIX = "bt3ms_update_"


def stage_tool(zip_path, exe_name=EXE_NAME):
    """Unpacks the tool's zip into a staging folder; returns the NEW program there (run_staged starts it)."""
    stage = tempfile.mkdtemp(prefix=STAGE_PREFIX)
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/"):
                raise UpdateError("le zip de l'outil contient un chemin dangereux")
        z.extractall(stage)
    inner = os.path.join(stage, "bt3-mod-studio")
    src = inner if os.path.isdir(inner) else stage
    if not os.path.exists(os.path.join(src, exe_name)):
        raise UpdateError("le zip ne contient pas l'outil")
    return os.path.join(src, exe_name)


def run_staged(new_exe, tool_dir, pid, restart=True):
    """Starts the new version from its staging folder with --finish-update: once process `pid` (this tool) has ended,
    it copies itself over `tool_dir` and starts the tool from there (finish_update). Up to 1.1.0 a .cmd script did
    the copy; started without a console, Windows ended it at its first command and nothing was copied."""
    args = [new_exe, "--finish-update", str(pid), tool_dir] + ([] if restart else ["--no-restart"])
    try:  # (out of the tool's job, if it is in one that ends its processes with it)
        subprocess.Popen(args, cwd=os.path.dirname(new_exe), close_fds=True,
                         creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 0x01000000)  # CREATE_BREAKAWAY_FROM_JOB
    except OSError:
        subprocess.Popen(args, cwd=os.path.dirname(new_exe), close_fds=True,
                         creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)


def wait_process(pid, seconds=120):
    """Waits for process `pid` to end; True when it has (or never was)."""
    import ctypes
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x00100000, False, int(pid))  # SYNCHRONIZE
    if not h:
        return True
    try:
        return k.WaitForSingleObject(h, int(seconds * 1000)) == 0
    finally:
        k.CloseHandle(h)


def finish_update(src, tool_dir, pid, restart=True, exe_name=EXE_NAME, log=None):
    """Run by the NEW version from its staging folder `src`: waits for the old tool (`pid`) to end, copies `src`
    over `tool_dir` (each file retried while still locked), then starts the tool there. Writes what it did in `log`
    (default: update.log next to the staging folder). Raises UpdateError when the copy could not be done."""
    import time
    stage = os.path.dirname(src) if os.path.basename(src) == "bt3-mod-studio" else src
    log = log or os.path.join(stage, "update.log")
    lines = []

    def note(text):
        lines.append(text)
        with open(log, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    note(f"de {src}\nvers {tool_dir}\nattente de la fermeture de l'outil (processus {pid})")
    if not os.path.exists(os.path.join(tool_dir, exe_name)):
        note("ERREUR : ce dossier ne contient pas l'outil")
        raise UpdateError(f"le dossier « {tool_dir} » ne contient pas l'outil")
    if not wait_process(pid):
        note("ERREUR : l'outil ne s'est pas fermé")
        raise UpdateError("l'ancienne version de l'outil ne s'est pas fermée")
    # the staging folders of earlier tries (not this one: its program is running)
    for d in os.listdir(tempfile.gettempdir()):
        p = os.path.join(tempfile.gettempdir(), d)
        if d.startswith(STAGE_PREFIX) and os.path.normcase(os.path.abspath(p)) != os.path.normcase(os.path.abspath(stage)):
            shutil.rmtree(p, ignore_errors=True)
    failed = []
    count = 0
    for folder, _dirs, files in os.walk(src):
        rel = os.path.relpath(folder, src)
        dest = os.path.normpath(os.path.join(tool_dir, rel))
        os.makedirs(dest, exist_ok=True)
        for name in files:
            if rel == "." and name == "update.log":
                continue
            for attempt in range(60):  # (an antivirus or the old process's last moments: up to 30 s per file)
                try:
                    shutil.copy2(os.path.join(folder, name), os.path.join(dest, name))
                    count += 1
                    break
                except OSError as e:
                    if attempt == 59:
                        failed.append(f"{os.path.join(rel, name)} ({e})")
                    time.sleep(0.5)
    if failed:
        note(f"{count} fichiers copiés, {len(failed)} en échec :\n" + "\n".join(failed))
        raise UpdateError(f"{len(failed)} fichier(s) n'ont pas pu être remplacés, dont {failed[0]}")
    note(f"{count} fichiers copiés : mise à jour faite")
    if restart:
        subprocess.Popen([os.path.join(tool_dir, exe_name)], cwd=tool_dir, close_fds=True)
    return count
