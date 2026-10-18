"""Adds the test kit's hooks to a Tenkaichi3Decomp checkout (run from its top folder). Each edit is anchored on
existing text and fails loudly when the anchor is missing or already patched."""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def patch(path, anchor, new, after=True):
    p = Path(path)
    s = p.read_text()
    if new.strip() in s:
        print(f"{path}: already patched")
        return
    if s.count(anchor) != 1:
        sys.exit(f"{path}: anchor found {s.count(anchor)} times: {anchor!r}")
    s = s.replace(anchor, anchor + new if after else new + anchor)
    p.write_text(s)
    print(f"{path}: patched")


shutil.copy(HERE / "testkit.c", "port/src/testkit.c")

# 1. battles without menus, one after another (once: an older version of this hook is turned into this one by 9.)
HEADLESS_HOOK = """    {   /* BT3_TEST: the test kit sets every battle up itself (port/src/testkit.c) and the program never ends here */
        extern int Port_TestkitActive(void);
        extern int Port_TestkitMenus(void);
        extern void Port_TestkitSetupBattle(void);
        if (Port_TestkitActive() && !Port_TestkitMenus()) {
            sBattles++;
            Port_TestkitSetupBattle();
            fflush(stdout);
            return 0;
        }
    }
"""
if "Port_TestkitSetupBattle" not in Path("port/src/headless.c").read_text():
    patch("port/src/headless.c", "    path = getenv(\"BT3_REPLAY\");\n", HEADLESS_HOOK)
else:
    print("port/src/headless.c: already patched")

# 2. the pads
patch("port/src/plat_stub.c", "static int pad_read(int socket, unsigned char *data) {\n    int i;\n", """
    {   /* BT3_TEST: the test kit's input queues answer (port/src/testkit.c) */
        extern int Port_TestkitPad(int socket, unsigned char *data);
        if (Port_TestkitPad(socket, data)) {
            return 18;
        }
    }
""")

# 3. the mailbox, once per vertical blank
patch("port/src/plat_stub.c", "    Port_Trace(gPortVBlanks);\n", """    {
        extern void Port_TestkitTick(void); /* testkit.c: BT3_TEST */
        Port_TestkitTick();
    }
""")

# 4. leaving the battle on request
patch("src/battle/battle.c", "        done = BtlGame_Update();\n", """#ifdef PORT
        {
            extern s32 Port_TestkitLeave(void); /* port/src/testkit.c: the test kit asks for another battle */
            if (Port_TestkitLeave()) {
                done = 1;
            }
        }
#endif
""")

# 6. closing the file cache, so that files under mods/ can be replaced while the program runs (Windows does not
#    let a file that is open be deleted)
patch("port/src/plat_fcache.c", "/* The file's size in bytes, or -1 if there is no such file. */\n", """/* Closes every file the cache holds open (the test kit, port/src/testkit.c: before mod files are replaced, and at
   the start of every battle it sets up, so that the battle reads the files as they are now). */
void Port_FileCacheFlush(void) {
    int i;
    while (__sync_lock_test_and_set(&sLock, 1)) {
    }
    for (i = 0; i < SLOTS; i++) {
        if (sSlot[i].fp != NULL) {
            fclose(sSlot[i].fp);
            sSlot[i].fp = NULL;
        }
    }
    __sync_lock_release(&sLock);
}

""", after=False)

# 8. snapshots for the test kit ("snap save N" / "snap load N"), with the state module's own save and load
patch("port/src/gs/state.c", "int Port_RollCan(void) {\n", """/* The test kit's snapshots (port/src/testkit.c): the whole game state, as BT3_SYNCTEST saves it, at a vertical
   blank on the game thread. The snapshots are kept outside everything a snapshot restores (calloc). Save returns 0
   after saving and 1 when the state was loaded (the call returns a second time); load returns only when there is
   no such snapshot. */
#define KIT_SNAPS 4
static Snapshot *sKitSnap[KIT_SNAPS];
int Port_TestkitSnapSave(int n) {
    if (n < 0 || n >= KIT_SNAPS) {
        return -1;
    }
    if (sKitSnap[n] == NULL) {
        sKitSnap[n] = calloc(1, sizeof(Snapshot));
    }
    return state_save(sKitSnap[n]);
}
int Port_TestkitSnapLoad(int n) {
    if (n < 0 || n >= KIT_SNAPS || sKitSnap[n] == NULL || sKitSnap[n]->parts == 0) {
        return -1;
    }
    state_load(sKitSnap[n]);
    return 0;
}

""", after=False)
patch("port/src/gs/state.c", "int Port_RollCan(void) { return 0; }\n", """int Port_TestkitSnapSave(int n) { (void)n; return -1; }
int Port_TestkitSnapLoad(int n) { (void)n; return -1; }
""")

# 9. (a checkout patched before BT3_TEST_MENUS existed) the menus stay the game's own with BT3_TEST_MENUS
h = Path("port/src/headless.c").read_text()
old9 = "        extern void Port_TestkitSetupBattle(void);\n        if (Port_TestkitActive()) {\n"
if old9 in h:
    h = h.replace(old9, "        extern int Port_TestkitMenus(void);\n        extern void Port_TestkitSetupBattle(void);\n"
                        "        if (Port_TestkitActive() && !Port_TestkitMenus()) {\n")
    Path("port/src/headless.c").write_text(h)
    print("port/src/headless.c: menus mode")

# 7. a faster rebuild: an object is compiled again only when its preprocessed source or its command changed
#    (the key is the preprocessed text: every header a file includes is in it)
s = Path("port/tools/undefined.py").read_text()
if "def cached_compile" not in s:
    if s.count("def compile_ee(cmd, src, o):\n") != 1 or s.count("def cc(f):\n") != 1:
        sys.exit("port/tools/undefined.py: anchors not found")
    s = s.replace("def compile_ee(cmd, src, o):\n", "def _compile_ee(cmd, src, o):\n", 1)
    s = s.replace("def cc(f):\n", '''def cached_compile(cmd, src, o, compile_fn):
    """compile_fn(cmd, src, o), skipped when the object exists and was made from the same preprocessed text with the
    same command (the test kit's faster rebuild)."""
    import hashlib
    pre = [a for a in variant(cmd) if a not in ("-c",)]
    if "-o" in pre:
        k = pre.index("-o")
        del pre[k:k + 2]
    r = subprocess.run(pre + ["-E", str(src)], cwd=ROOT, capture_output=True)
    tools = b"".join((ROOT / "port/tools" / n).read_bytes() for n in ("eeconst.py", "ptr32.py", "irfix.py", "undefined.py"))
    key = hashlib.sha1(repr(cmd).encode() + tools + r.stdout).hexdigest() if r.returncode == 0 else None
    kf = pathlib.Path(str(o) + ".key")
    if key and pathlib.Path(o).exists() and kf.exists() and kf.read_text() == key:
        return subprocess.CompletedProcess(cmd, 0, "", "")
    res = compile_fn(cmd, src, o)
    if res.returncode == 0 and not getattr(res, "pending", None) and key:
        kf.write_text(key)
    elif kf.exists():
        kf.unlink()
    return res

def compile_ee(cmd, src, o):
    return cached_compile(cmd, src, o, _compile_ee)

def _run_compile(cmd, src, o):
    return run(cmd + [str(src), "-o", str(o)], cwd=ROOT, capture_output=True, text=True)

def cc(f):
''', 1)
    gs_old = '''        r = run(["gcc", "-m32", "-std=gnu99", "-c", "-O2", "-g", "-fno-pic", "-msse2", "-mfpmath=sse", "-fno-strict-aliasing",
                            "-Wall", "-Wno-unused", "-Wno-misleading-indentation", f"-I{gen}"] + (key if f.name == "net_sign.c" else []) + [str(f), "-o", str(o)], cwd=ROOT,
                           capture_output=True, text=True)'''
    gs_new = '''        r = cached_compile(["gcc", "-m32", "-std=gnu99", "-c", "-O2", "-g", "-fno-pic", "-msse2", "-mfpmath=sse", "-fno-strict-aliasing",
                            "-Wall", "-Wno-unused", "-Wno-misleading-indentation", f"-I{gen}"] + (key if f.name == "net_sign.c" else []), f, o, _run_compile)'''
    pc_old = '''            r = run(cmd + [str(f), "-o", str(o)], cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            print("FAILED", f.name, r.stderr.splitlines()[0][:150])'''
    pc_new = '''            r = cached_compile(cmd, f, o, _run_compile)
        if r.returncode:
            print("FAILED", f.name, r.stderr.splitlines()[0][:150])'''
    if s.count(gs_old) != 1 or s.count(pc_old) != 1:
        sys.exit("port/tools/undefined.py: compile calls not found")
    s = s.replace(gs_old, gs_new, 1).replace(pc_old, pc_new, 1)
    Path("port/tools/undefined.py").write_text(s)
    print("port/tools/undefined.py: cached compiles")
else:
    print("port/tools/undefined.py: already patched")

# 5. screenshots on request (Vulkan renderer)
patch("port/src/gs/gs_gpu.c",
      "        if (every > 0 && gGsFrame % (unsigned)every == 0 && best >= 0 && gsTargets[best].cleared &&\n",
      """        extern const char *Port_TestkitShotPath(void); /* port/src/testkit.c: a screenshot asked for */
        extern void Port_TestkitShotDone(void);
        const char *kitShot = Port_TestkitShotPath();
""", after=False)
s = Path("port/src/gs/gs_gpu.c").read_text()
old_cond = "        if (every > 0 && gGsFrame % (unsigned)every == 0 && best >= 0 && gsTargets[best].cleared &&\n"
new_cond = "        if ((kitShot != NULL && best >= 0 && gsTargets[best].cleared) || (every > 0 && gGsFrame % (unsigned)every == 0 && best >= 0 && gsTargets[best].cleared &&\n"
if new_cond not in s:
    s = s.replace(old_cond, new_cond, 1)
    s = s.replace("            (getenv(\"BT3_SHOT_TO\") == NULL || (int)gGsFrame <= atoi(getenv(\"BT3_SHOT_TO\")))) {\n            SDL_GPUTransferBufferCreateInfo ti;",
                  "            (getenv(\"BT3_SHOT_TO\") == NULL || (int)gGsFrame <= atoi(getenv(\"BT3_SHOT_TO\"))))) {\n            SDL_GPUTransferBufferCreateInfo ti;", 1)
    s = s.replace("            snprintf(name, sizeof(name), \"port/build/shots/gpu_%05u.ppm\", gGsFrame);\n            fp = fopen(name, \"wb\");",
                  "            snprintf(name, sizeof(name), \"port/build/shots/gpu_%05u.ppm\", gGsFrame);\n            fp = fopen(kitShot != NULL ? kitShot : name, \"wb\");", 1)
    s = s.replace("            SDL_UnmapGPUTransferBuffer(sDev, tb);\n            SDL_ReleaseGPUTransferBuffer(sDev, tb);\n        }\n",
                  "            SDL_UnmapGPUTransferBuffer(sDev, tb);\n            SDL_ReleaseGPUTransferBuffer(sDev, tb);\n            if (kitShot != NULL) {\n                Port_TestkitShotDone();\n            }\n        }\n", 1)
    Path("port/src/gs/gs_gpu.c").write_text(s)
    print("port/src/gs/gs_gpu.c: screenshot condition patched")
