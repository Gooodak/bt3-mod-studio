"""Brings the extended edition of the port up to z3xox's newest code, checks it, and makes its release.

    py -I tools/update_port.py            look, merge, build, test, make the zip, push the branch
    py -I tools/update_port.py --check    only say whether z3xox has something new
    py -I tools/update_port.py --publish  the same as without, then publish the zip as a release of
                                          Gooodak/bt3-port-etendu (tag v0.1.NN-etendu.K)

What it does, in order (it stops at the first thing that goes wrong and says what):
  1. fetches z3xox's repository (remote "origin" of D:\\...\\source) and ours ("gooodak");
  2. what is new: z3xox's newest release tag (v0.1.NN) and his branch of character packages (char-packages), if
     the branch `etendu` does not hold them yet;
  3. merges them into `etendu` (a conflict: the merge is undone and the files are named; a person has to look);
  4. builds the test game from it (testkit-src/rebuild_etendu.sh in WSL);
  5. runs the test suites one after the other: net_check, kit_selftest, ui_check, import_check;
  6. makes the release zip (testkit-src/release_etendu.sh) and pushes `etendu` to Gooodak/bt3-port-etendu;
  7. --publish: a GitHub release with the zip.
A log is kept in D:\\...\\releases\\update_port.log."""
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOL)
SRC = os.path.join(ROOT, "source")
RELEASES = os.path.join(ROOT, "releases")
LOG = os.path.join(RELEASES, "update_port.log")
GH = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "gh", "bin", "gh.exe")
WSL_KIT = "/mnt/d/Tenkaichi3Decomp-windows-x64/bt3-mod-studio/testkit-src"
SUITES = ["net_check.py", "kit_selftest.py", "ui_check.py", "import_check.py"]


def say(text):
    line = time.strftime("%Y-%m-%d %H:%M ") + text
    print(text, flush=True)
    os.makedirs(RELEASES, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def git(*args, check=True):
    r = subprocess.run(["git", "-C", SRC] + list(args), capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} : {r.stderr.strip()[:400]}")
    return r.stdout.strip()


def contains(ref):
    return subprocess.run(["git", "-C", SRC, "merge-base", "--is-ancestor", ref, "etendu"]).returncode == 0


def newest_tag():
    tags = [t for t in git("tag", "--list", "v0.1.*").split() if re.fullmatch(r"v0\.1\.\d+(\.\d+)?", t)]
    return max(tags, key=lambda t: [int(x) for x in t[1:].split(".")]) if tags else None


def wsl(script):
    env = dict(os.environ, MSYS_NO_PATHCONV="1")
    r = subprocess.run(["wsl.exe", "-d", "Ubuntu", "-u", "root", "--", "sh", f"{WSL_KIT}/{script}"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    return r.returncode, (r.stdout + r.stderr).strip()


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    check_only, publish = "--check" in sys.argv, "--publish" in sys.argv
    say("— mise à jour de l'édition étendue —")
    git("fetch", "-q", "--tags", "origin")
    git("fetch", "-q", "gooodak", check=False)
    if git("rev-parse", "--abbrev-ref", "HEAD") != "etendu":
        git("checkout", "-q", "etendu")
    if git("status", "--porcelain", "--untracked-files=no"):
        say("STOP : la copie du code (source) a des changements pas commités. Commite-les ou range-les d'abord.")
        return 2
    tag = newest_tag()
    wanted = [r for r in (tag, "origin/char-packages") if r and not contains(r)]
    # (a merge made by an earlier run that stopped before pushing: build, test and push it now)
    unpushed = subprocess.run(["git", "-C", SRC, "merge-base", "--is-ancestor", "etendu", "gooodak/etendu"]
                              ).returncode != 0
    if not wanted and not unpushed:
        say(f"À jour : etendu contient déjà {tag} et la branche des personnages de z3xox.")
        return 0
    if wanted:
        say("Nouveau chez z3xox : " + ", ".join(wanted))
    else:
        say("Rien de nouveau chez z3xox, mais etendu a des changements pas encore poussés : on les vérifie.")
    if check_only:
        return 1
    for ref in wanted:
        r = subprocess.run(["git", "-C", SRC, "merge", "--no-edit", "-m",
                            f"Merge z3xox's {ref.replace('origin/', '')} into etendu", ref],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            files = git("diff", "--name-only", "--diff-filter=U", check=False)
            git("merge", "--abort", check=False)
            say(f"STOP : conflit en fusionnant {ref}. Fusion annulée, rien n'a changé. Fichiers : "
                + (files.replace("\n", ", ") or r.stdout[-300:]))
            return 2
        say(f"Fusionné : {ref}")
    version = git("describe", "--tags", "--always", "etendu")
    code, out = wsl("rebuild_etendu.sh")
    if code != 0:
        say("STOP : la compilation du jeu de test a échoué :\n" + out[-1500:])
        return 2
    say("Jeu de test compilé : " + out.splitlines()[-1])
    for suite in SUITES:
        for attempt in (1, 2):  # (a second try: a busy PC can make an online session end early, seen once)
            r = subprocess.run([sys.executable, "-I", os.path.join(HERE, suite)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", cwd=TOOL)
            lines = (r.stdout + r.stderr).strip().splitlines()
            result = next((l for l in reversed(lines) if "passed" in l), lines[-1] if lines else "?")
            fails = [l for l in lines if l.startswith("FAIL")]
            say(f"  {suite:18} {result}" + (" (2e essai)" if attempt == 2 else "")
                + "".join("\n    " + f[:160] for f in fails))
            subprocess.run(["taskkill", "/F", "/IM", "bt3.exe"], capture_output=True)  # (the test game only)
            if r.returncode == 0:
                break
        if r.returncode != 0:
            say("STOP : un test a échoué deux fois. La branche fusionnée reste en local (pas poussée) pour qu'on "
                "regarde.")
            return 2
    code, out = wsl("release_etendu.sh")
    if code != 0:
        say("STOP : le zip n'a pas pu être fait :\n" + out[-1500:])
        return 2
    zips = sorted((f for f in os.listdir(RELEASES) if f.startswith("Tenkaichi3Decomp-etendu-") and f.endswith(".zip")),
                  key=lambda f: os.path.getmtime(os.path.join(RELEASES, f)))
    say(f"Zip : releases\\{zips[-1]}")
    git("push", "-q", "gooodak", "etendu")
    say("Branche poussée sur Gooodak/bt3-port-etendu.")
    if publish:
        base = re.match(r"v0\.1\.\d+", version).group(0)
        done = subprocess.run([GH, "release", "list", "-R", "Gooodak/bt3-port-etendu", "-L", "100"],
                              capture_output=True, text=True).stdout
        k = 1 + len(re.findall(re.escape(base) + r"-etendu\.\d+", done))
        tag_name = f"{base}-etendu.{k}"
        r = subprocess.run([GH, "release", "create", tag_name, os.path.join(RELEASES, zips[-1]), "-R",
                            "Gooodak/bt3-port-etendu", "--target", "etendu", "--title",
                            f"Édition étendue {tag_name[1:]}", "--notes",
                            f"La version {base[1:]} de z3xox, avec ses personnages ajoutés et le jeu en ligne entre "
                            "joueurs qui ont les mêmes mods. Décompresser par-dessus le dossier Tenkaichi3Decomp. "
                            "Aucune donnée du jeu dans ce zip."], capture_output=True, text=True)
        say(f"Publié : {tag_name}" if r.returncode == 0 else "Publication échouée : " + r.stderr[-300:])
    say(f"Terminé : {version}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as e:
        say(f"STOP : {e}")
        sys.exit(2)
