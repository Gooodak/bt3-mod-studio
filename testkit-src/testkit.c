/*
 * Test kit (BT3_TEST=<folder>): drives the game from another program, for testing mods without a person at the
 * controller and without going through the menus.
 *
 * Battles: the menus are skipped (headless.c asks Port_TestkitSetupBattle for every battle): a training-mode battle
 * (mode 6: no time limit) with the characters, costumes and stage last asked for; side 0 is played by the input
 * queue below, side 1 by the CPU at the level asked for (-1: the CPU does nothing, a still target). Leaving the
 * battle (command "fight") makes the game load everything again, so files changed under gamedata/mods/ meanwhile
 * are what the next battle uses.
 *
 * Mailbox: the other program writes its commands into <folder>/cmd (written as cmd.tmp, then renamed), one per line;
 * at a vertical blank the game takes the file, carries the commands out in order and, when the last one is done,
 * writes the answers into <folder>/reply (through reply.tmp). Commands:
 *   fight C0 K0 C1 K1 [STAGE [CPU1 [MODE]]]
 *                                      leave the battle and start a new one: characters C0 / C1, costumes K0 / K1;
 *                                      CPU1 = side 1's CPU level (-1: does nothing; -2: played by pad 2, the second
 *                                      input queue); MODE 6 = training (default), 0 = versus; done when the new
 *                                      fight's clock runs
 *   release                            close the files the game holds open, so that mod files can be replaced
 *   log                                the events recorded since the last "log" (every health drop and action
 *                                      change, seen at each vertical blank), with damage and hit totals
 *   restart                            the same battle again from its start (the game's rematch, nothing reloaded)
 *   hold N BUTTONS [STICK] [p2]        queue N pad reads (game frames) of player 1 (or 2) holding BUTTONS
 *                                      (a+b+..., names below, "-" for none) and the left stick (up/down/left/right)
 *   sync                               done when both input queues are empty
 *   wait N                             done N vertical blanks later
 *   state                              answers with both fighters' gauges and action
 *   shot PATH                          a screenshot of the next frame shown, as a PPM file
 *   shots N EVERY PREFIX               N screenshots, one every EVERY frames drawn: PREFIX_000.ppm ...
 *   snap save K | snap load K          the whole game state in memory (K = 0..3), as online play's rollback keeps
 *                                      it; the input queues are emptied by a load (this file is not game state)
 *   speed fast|normal                  the game runs as fast as it can (BT3_UNCAPPED) or at its own pace
 *   quit                               ends the program
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "port_addr.h"

#if (defined(__x86_64__) || defined(__aarch64__)) && defined(__clang__) /* (the 64-bit builds: game pointers are 4 bytes) */
#undef __ptr32
#undef __uptr
#define GAME_PTR *__ptr32 __uptr
#else
#define GAME_PTR *
#endif

extern struct { int state; } GAME_PTR gBtlSeq;
extern unsigned char gBattleWork[];
extern int *BtlSeq_GetClock(void);
extern int BtlCharApi_GetHp(int objId);
extern int BtlCharApi_GetHpMax(int objId);
extern int BtlCharApi_GetKi(int objId);
extern int BtlCharApi_GetBlast(int objId);
extern int BtlCharApi_GetBlastMax(int objId);
extern int BtlCharApi_GetMaxPower(int objId);
extern int BtlCharApi_GetAction(int objId);
extern int BtlCharApi_GetChara(int objId);
/* (game pointers are 4 bytes: the fighter is handed on as a number) */
extern unsigned BtlChar_FindByObjId(int objId);
extern int BtlChar_TestFlag(unsigned chr, unsigned n);

extern int BtlAnim_GetId(unsigned chr);
extern int Port_TestkitSnapSave(int n); /* gs/state.c */
extern int Port_TestkitSnapLoad(int n);

static int fighter_anim(int k) {
    unsigned chr = BtlChar_FindByObjId(k);
    return chr != 0 ? BtlAnim_GetId(chr) : -1;
}

static int fighter_flag(int k, unsigned n) {
    unsigned chr = BtlChar_FindByObjId(k);
    return chr != 0 ? BtlChar_TestFlag(chr, n) != 0 : -1;
}
extern void Battle_ClearWork(void);
extern void BattleSetup_SetRule(int screenMode, int mode, int bgm, int timeLimit, int announcer, int stage, int unk10);
extern void BattleSetup_SetSide(int side, int control, int pad, int memberCount, int unk1FC, int unk200, int lead,
                                void *charaBits);
extern void BattleSetup_SetMember(int side, int idx, int chara, int costume, int variant, int cpuLevel, float health,
                                  void *items);
extern void BattleSetup_Finish(void);
extern unsigned gPortVBlanks;

#define BATTLE_FLAGS (*(unsigned long long *)(gBattleWork + 0x19F0))
#define BATTLE_RUNNING (*(int *)(gBattleWork + 0x19F8)) /* set by Battle_Main for the whole battle scene */
#define BATTLE_FLAG_RESTART 0x8000ull

static int sActive = -1;
static char sDir[400];

/* the battle to set up next */
static int sChara[2] = {0, 11}, sCostume[2] = {0, 0}, sStage = 0, sCpu1 = -1, sMode = 6;
static int sBattle;     /* battles set up so far */
static int sLeave;      /* leave the battle at the end of this frame */

/* input queues: runs of identical pad reads */
typedef struct { int count; unsigned char data[6]; } Run;
#define RUNS 4096
static Run sQueue[2][RUNS];
static int sHead[2], sTail[2];

/* commands of the current mailbox file */
#define LINES 256
static char sLines[LINES][160];
static int sLineCount, sLineNext;
static char sReply[16384];
static int sReplyLen;
/* the command being waited for */
static enum { W_NONE, W_FIGHT, W_RESTART, W_SYNC, W_WAIT, W_SHOT, W_BURST } sWaitKind;
static int sLeftFight; /* restart: the fight state has been left (the rematch began) */
static unsigned sWaitUntil;
static int sWaitBattle;

/* event recorder (record(), "log"): health drops and action changes, as the game sees them at every vertical blank */
#define LOG_MAX 2000
static char sLog[LOG_MAX][64];
static int sLogCount, sDamage[2], sHits[2];
static int sLastHp[2] = {-1, -1}, sLastAction[2] = {-1, -1}, sLastAnim[2] = {-1, -1}, sLastBattle = -1;
static int sSnapLoading = -1; /* the snapshot being loaded: its save returns a second time */

/* screenshot request, read by the renderer (gs/gs_gpu.c) */
static char sShotPath[400];
static volatile int sShotWanted, sShotDone;
/* burst: a screenshot every sBurstEvery frames drawn, sBurstLeft more to take, named <prefix>_NNN.ppm */
static char sBurstPrefix[400];
static volatile int sBurstLeft, sBurstEvery, sBurstFrame, sBurstIndex, sBurstPending;

/* BT3_TEST_MENUS=1 (with BT3_TEST): the game's own menus run (no battle is set up here); the mailbox and the input
   queues work as in battles, so the menus can be walked screen by screen. */
int Port_TestkitMenus(void) {
    static int m = -1;
    if (m < 0) {
        const char *e = getenv("BT3_TEST_MENUS");
        m = e != NULL && *e != '\0' && *e != '0';
    }
    return m;
}

/* gProgress (include/menu/menu_a.h): the menus' state; +0x1C mode = which screen runs */
extern struct { int unk0[2]; int loadPack, loadRes, loadSprites; int flags; int mode; } GAME_PTR gProgress;

int Port_TestkitActive(void) {
    if (sActive < 0) {
        const char *d = getenv("BT3_TEST");
        sActive = d != NULL && *d != '\0';
        if (sActive) {
            snprintf(sDir, sizeof(sDir), "%s", d);
            fprintf(stderr, "bt3: test kit: commands in %s/cmd\n", sDir);
        }
    }
    return sActive;
}

/* ---- battles (headless.c) ---------------------------------------------------------------------------------- */

void Port_TestkitSetupBattle(void) {
    extern void Port_FileCacheFlush(void); /* plat_fcache.c: read the files as they are now */
    extern void Common_Reload(void);       /* src/sys/common.c */
    Port_FileCacheFlush();
    {   /* The second archive (pzs3us2: voice lines, and an added character's voice banks) is registered on the
           menus' way, which the kit skips: registered here (src/sys/file.c). */
        extern int File_IsPartitionLoaded(int pt);
        extern int File_LoadPartitionNw(int pt);
        extern int File_WaitPartition(int pt);
        if (!File_IsPartitionLoaded(2)) {
            File_LoadPartitionNw(2);
            File_WaitPartition(2);
        }
    }
    /* The common files (2..4: among them the character table with health, starting ki and blast stocks) are read
       once at start-up by Game_Main; read them again so that a mod of them counts from this battle on. */
    Common_Reload();
    Battle_ClearWork();
    /* mode 6 (training) or 0 (versus); no time limit */
    BattleSetup_SetRule(0, sMode, 0, 0, 7, sStage, 0);
    BattleSetup_SetSide(0, 0, 0, 1, 1, 1, 0, NULL);
    /* side 1: the CPU at level sCpu1, or (sCpu1 == -2) pad 2, which plays the second input queue */
    BattleSetup_SetSide(1, sCpu1 == -2 ? 0 : 2, 1, 1, 1, 1, 0, NULL);
    BattleSetup_SetMember(0, 0, sChara[0], sCostume[0], 0, 0, 100.0f, NULL);
    BattleSetup_SetMember(1, 0, sChara[1], sCostume[1], 0, sCpu1 == -2 ? 0 : sCpu1, 100.0f, NULL);
    BattleSetup_Finish();
    sBattle++;
    sLeave = 0; /* (a request made while no battle ran is this battle) */
    sHead[0] = sTail[0] = sHead[1] = sTail[1] = 0;
    fprintf(stderr, "bt3: test kit: battle %d (mode %d): character %d costume %d against %d costume %d, stage %d, side 1 %d\n",
            sBattle, sMode, sChara[0], sCostume[0], sChara[1], sCostume[1], sStage, sCpu1);
}

/* Battle_Loop (src/battle/battle.c) asks after every frame. */
int Port_TestkitLeave(void) {
    int r = sLeave;
    sLeave = 0;
    return r;
}

/* ---- input (plat_stub.c) ----------------------------------------------------------------------------------- */

int Port_TestkitPad(int socket, unsigned char *data) {
    int p = socket == 0 ? 0 : 1;
    if (!Port_TestkitActive() || socket < 0 || socket > 1) {
        return 0;
    }
    memset(data, 0, 18);
    data[0] = data[1] = 0xFF;
    data[2] = data[3] = data[4] = data[5] = 0x80;
    if (sHead[p] != sTail[p]) {
        Run *r = &sQueue[p][sHead[p]];
        memcpy(data, r->data, 6);
        if (--r->count <= 0) {
            sHead[p] = (sHead[p] + 1) % RUNS;
        }
    }
    return 1;
}

static unsigned button_bits(const char *s) {
    static const struct { const char *name; unsigned bit; } names[] = {
        {"select", 0x0001}, {"l3", 0x0002}, {"r3", 0x0004}, {"start", 0x0008}, {"up", 0x0010}, {"right", 0x0020},
        {"down", 0x0040}, {"left", 0x0080}, {"l2", 0x0100}, {"r2", 0x0200}, {"l1", 0x0400}, {"r1", 0x0800},
        {"triangle", 0x1000}, {"circle", 0x2000}, {"cross", 0x4000}, {"square", 0x8000},
    };
    unsigned bits = 0;
    char buf[128], *tok, *save = NULL;
    size_t k;
    snprintf(buf, sizeof(buf), "%s", s);
    for (tok = strtok_r(buf, "+", &save); tok != NULL; tok = strtok_r(NULL, "+", &save)) {
        for (k = 0; k < sizeof(names) / sizeof(names[0]); k++) {
            if (strcmp(tok, names[k].name) == 0) {
                bits |= names[k].bit;
            }
        }
    }
    return bits;
}

/* ---- the mailbox ---------------------------------------------------------------------------------------------- */

static void reply(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
#include <stdarg.h>
static void reply(const char *fmt, ...) {
    va_list ap;
    int n;
    if (sReplyLen >= (int)sizeof(sReply) - 2) {
        return;
    }
    va_start(ap, fmt);
    n = vsnprintf(sReply + sReplyLen, sizeof(sReply) - sReplyLen, fmt, ap);
    va_end(ap);
    if (n > 0) {
        sReplyLen += n;
        if (sReplyLen > (int)sizeof(sReply) - 1) {
            sReplyLen = sizeof(sReply) - 1;
        }
    }
}

static int seq_state(void) {
    return gBtlSeq != NULL ? gBtlSeq->state : -1;
}

static void fighter_state(int k) {
    /* flag 5: locked on; flag 6: the powered-up ("max power") mode (docs/systems/combat.md) */
    reply(" p%d hp=%d/%d ki=%d blast=%d/%d maxpower=%d action=0x%X lock=%d power=%d", k, BtlCharApi_GetHp(k),
          BtlCharApi_GetHpMax(k), BtlCharApi_GetKi(k), BtlCharApi_GetBlast(k), BtlCharApi_GetBlastMax(k),
          BtlCharApi_GetMaxPower(k), BtlCharApi_GetAction(k), fighter_flag(k, 5), fighter_flag(k, 6));
    reply(" anim=0x%X chara=%d", fighter_anim(k), BtlCharApi_GetChara(k));
}

/* Starts the next command; returns 1 when it is already done. */
static int start_command(char *line) {
    char *w[8] = {0};
    int n = 0;
    char *save = NULL, *tok;
    for (tok = strtok_r(line, " \t\r\n", &save); tok != NULL && n < 8; tok = strtok_r(NULL, " \t\r\n", &save)) {
        w[n++] = tok;
    }
    if (n == 0) {
        return 1;
    }
    if (strcmp(w[0], "fight") == 0 && n >= 5) {
        sChara[0] = atoi(w[1]);
        sCostume[0] = atoi(w[2]);
        sChara[1] = atoi(w[3]);
        sCostume[1] = atoi(w[4]);
        sStage = n > 5 ? atoi(w[5]) : 0;
        sCpu1 = n > 6 ? atoi(w[6]) : -1;
        sMode = n > 7 ? atoi(w[7]) : 6;
        sWaitBattle = sBattle + 1;
        if (BATTLE_RUNNING) {
            sLeave = 1; /* else no battle runs yet: the next one set up takes these */
        }
        sWaitKind = W_FIGHT;
        return 0;
    }
    if (strcmp(w[0], "restart") == 0) {
        BATTLE_FLAGS |= BATTLE_FLAG_RESTART;
        sHead[0] = sTail[0] = sHead[1] = sTail[1] = 0;
        sLeftFight = 0;
        sWaitKind = W_RESTART;
        return 0;
    }
    if (strcmp(w[0], "hold") == 0 && n >= 3) {
        int p = (n >= 4 && strcmp(w[n - 1], "p2") == 0) ? 1 : 0;
        int count = atoi(w[1]);
        unsigned bits = strcmp(w[2], "-") == 0 ? 0 : button_bits(w[2]);
        const char *stick = (n >= 4 && strcmp(w[3], "p2") != 0) ? w[3] : "none";
        int next = (sTail[p] + 1) % RUNS;
        Run *r = &sQueue[p][sTail[p]];
        if (next == sHead[p] || count <= 0) {
            reply("error: input queue full or empty hold\n");
            return 1;
        }
        r->count = count;
        r->data[0] = (unsigned char)(~bits & 0xFF);
        r->data[1] = (unsigned char)(~(bits >> 8) & 0xFF);
        r->data[2] = r->data[3] = 0x80;
        r->data[4] = strcmp(stick, "left") == 0 ? 0x00 : strcmp(stick, "right") == 0 ? 0xFF : 0x80;
        r->data[5] = strcmp(stick, "up") == 0 ? 0x00 : strcmp(stick, "down") == 0 ? 0xFF : 0x80;
        sTail[p] = next;
        return 1;
    }
    if (strcmp(w[0], "sync") == 0) {
        sWaitKind = W_SYNC;
        return 0;
    }
    if (strcmp(w[0], "wait") == 0 && n >= 2) {
        sWaitKind = W_WAIT;
        sWaitUntil = gPortVBlanks + (unsigned)atoi(w[1]);
        return 0;
    }
    if (strcmp(w[0], "state") == 0) {
        int *clock = seq_state() >= 0 ? BtlSeq_GetClock() : NULL;
        reply("state vblank=%u battle=%d seq=%d clock=%d menu=%d", gPortVBlanks, sBattle, seq_state(),
              clock != NULL ? clock[0] : -1, gProgress != NULL ? gProgress->mode : -1);
        if (seq_state() >= 2) {
            fighter_state(0);
            fighter_state(1);
        }
        reply("\n");
        return 1;
    }
    if (strcmp(w[0], "unlock") == 0) { /* everything unlocked in the save in memory (the port's Cheats tab) */
        extern volatile int gPortUnlockAll; /* headless.c: carried out at the next vertical blank */
        gPortUnlockAll = 1;
        reply("unlock\n");
        return 1;
    }
    if (strcmp(w[0], "release") == 0) { /* close the cached files: mod files can be replaced now */
        extern void Port_FileCacheFlush(void);
        Port_FileCacheFlush();
        reply("release\n");
        return 1;
    }
    if (strcmp(w[0], "log") == 0) { /* log: the events recorded since the last "log", then forget them */
        int i;
        for (i = 0; i < sLogCount; i++) {
            reply("%s\n", sLog[i]);
        }
        reply("log events=%d damage0=%d damage1=%d hits0=%d hits1=%d\n", sLogCount, sDamage[0], sDamage[1], sHits[0],
              sHits[1]);
        sLogCount = 0;
        sDamage[0] = sDamage[1] = sHits[0] = sHits[1] = 0;
        return 1;
    }
    if (strcmp(w[0], "flag") == 0 && n >= 2) { /* flag N [P]: fighter flag N (hex or decimal) of player P (0 or 1) */
        unsigned f = (unsigned)strtoul(w[1], NULL, 0);
        int k = n >= 3 ? atoi(w[2]) : 0;
        reply("flag 0x%X p%d=%d\n", f, k, seq_state() >= 2 ? fighter_flag(k, f) : -1);
        return 1;
    }
    if (strcmp(w[0], "snap") == 0 && n >= 3) { /* snap save N / snap load N: the whole game state, in memory */
        int k = atoi(w[2]);
        if (strcmp(w[1], "save") == 0) {
            int r = Port_TestkitSnapSave(k);
            if (r == 0) {
                reply("snap saved %d vblank=%u\n", k, gPortVBlanks);
            } else if (r == 1) { /* (the load below continues here: the state is the one saved) */
                sLastHp[0] = sLastHp[1] = sLastAction[0] = sLastAction[1] = sLastAnim[0] = sLastAnim[1] = -1;
                sHead[0] = sTail[0] = sHead[1] = sTail[1] = 0;
                reply("snap loaded %d vblank=%u\n", sSnapLoading, gPortVBlanks);
                sSnapLoading = -1;
            } else {
                reply("error: snapshot number 0..3\n");
            }
            return 1;
        }
        if (strcmp(w[1], "load") == 0) {
            sSnapLoading = k;
            if (Port_TestkitSnapLoad(k) != 0) { /* (returns only when there is no such snapshot) */
                sSnapLoading = -1;
                reply("error: no snapshot %d\n", k);
            }
            return 1;
        }
    }
    if (strcmp(w[0], "shots") == 0 && n >= 4) { /* shots N EVERY PREFIX: N screenshots, one every EVERY frames drawn */
        snprintf(sBurstPrefix, sizeof(sBurstPrefix), "%s", w[3]);
        sBurstEvery = atoi(w[2]) > 0 ? atoi(w[2]) : 1;
        sBurstFrame = sBurstIndex = sBurstPending = 0;
        sBurstLeft = atoi(w[1]);
        sWaitKind = W_BURST;
        sWaitUntil = gPortVBlanks + (unsigned)(sBurstLeft * sBurstEvery * 2 + 240);
        return 0;
    }
    if (strcmp(w[0], "shot") == 0 && n >= 2) {
        snprintf(sShotPath, sizeof(sShotPath), "%s", w[1]);
        sShotDone = 0;
        sShotWanted = 1;
        sWaitKind = W_SHOT;
        sWaitUntil = gPortVBlanks + 120; /* (gives up after two seconds: nothing is being drawn) */
        return 0;
    }
    if (strcmp(w[0], "speed") == 0 && n >= 2) {
#ifdef _WIN32
        _putenv(strcmp(w[1], "fast") == 0 ? "BT3_UNCAPPED=1" : "BT3_UNCAPPED=");
#else
        if (strcmp(w[1], "fast") == 0) { setenv("BT3_UNCAPPED", "1", 1); } else { unsetenv("BT3_UNCAPPED"); }
#endif
        return 1;
    }
    if (strcmp(w[0], "quit") == 0) {
        fprintf(stderr, "bt3: test kit: quit\n");
        exit(0);
    }
    reply("error: unknown command %s\n", w[0]);
    return 1;
}

/* 1 when the command being waited for is done. */
static int wait_done(void) {
    switch (sWaitKind) {
    case W_FIGHT: {
        int *clock;
        if (sBattle < sWaitBattle || gPortVBlanks < sWaitUntil || seq_state() < 3) {
            return 0;
        }
        clock = BtlSeq_GetClock();
        if (clock == NULL || clock[0] <= 0) {
            return 0;
        }
        reply("fight battle=%d\n", sBattle);
        return 1;
    }
    case W_RESTART: { /* the rematch goes through the ready state (inputs ignored) before fighting again */
        int *clock;
        if (seq_state() != 3) {
            sLeftFight = 1;
            return 0;
        }
        clock = BtlSeq_GetClock();
        if (!sLeftFight || clock == NULL || clock[0] <= 0) {
            return 0;
        }
        sHead[0] = sTail[0] = sHead[1] = sTail[1] = 0;
        reply("restart battle=%d\n", sBattle);
        return 1;
    }
    case W_SYNC:
        if (sHead[0] != sTail[0] || sHead[1] != sTail[1]) {
            return 0;
        }
        reply("sync vblank=%u\n", gPortVBlanks);
        return 1;
    case W_WAIT:
        return gPortVBlanks >= sWaitUntil;
    case W_BURST:
        if (sBurstLeft <= 0) {
            reply("shots %d %s_000.ppm ..\n", sBurstIndex, sBurstPrefix);
            return 1;
        }
        if (gPortVBlanks >= sWaitUntil) {
            sBurstLeft = 0;
            reply("error: only %d screenshots taken\n", sBurstIndex);
            return 1;
        }
        return 0;
    case W_SHOT:
        if (sShotDone) {
            reply("shot %s\n", sShotPath);
            return 1;
        }
        if (gPortVBlanks >= sWaitUntil) {
            sShotWanted = 0;
            reply("error: no frame drawn for the screenshot\n");
            return 1;
        }
        return 0;
    default:
        return 1;
    }
}

static void write_reply(void) {
    char tmp[480], dst[480];
    FILE *fp;
    snprintf(tmp, sizeof(tmp), "%s/reply.tmp", sDir);
    snprintf(dst, sizeof(dst), "%s/reply", sDir);
    fp = fopen(tmp, "wb");
    if (fp != NULL) {
        fwrite(sReply, 1, sReplyLen, fp);
        fclose(fp);
        remove(dst);
        rename(tmp, dst);
    }
    sReplyLen = 0;
    sReply[0] = '\0';
}

static void record(void) {
    int k;
    if (seq_state() < 2) {
        return;
    }
    if (sLastBattle != sBattle) { /* a new battle: nothing to compare with yet */
        sLastBattle = sBattle;
        sLastHp[0] = sLastHp[1] = sLastAction[0] = sLastAction[1] = -1;
    }
    for (k = 0; k < 2; k++) {
        int hp = BtlCharApi_GetHp(k), act = BtlCharApi_GetAction(k), anim = fighter_anim(k);
        if (anim != sLastAnim[k] && sLastAnim[k] >= 0 && sLogCount < LOG_MAX) {
            snprintf(sLog[sLogCount++], sizeof(sLog[0]), "anim vblank=%u p%d 0x%X", gPortVBlanks, k, anim);
        }
        sLastAnim[k] = anim;
        if (sLastHp[k] >= 0 && hp < sLastHp[k]) { /* (rises are the training mode's refill: not recorded) */
            sDamage[k] += sLastHp[k] - hp;
            sHits[k]++;
            if (sLogCount < LOG_MAX) {
                snprintf(sLog[sLogCount++], sizeof(sLog[0]), "hit vblank=%u p%d damage=%d hp=%d", gPortVBlanks, k,
                         sLastHp[k] - hp, hp);
            }
        }
        if (act != sLastAction[k] && sLastAction[k] >= 0 && sLogCount < LOG_MAX) {
            snprintf(sLog[sLogCount++], sizeof(sLog[0]), "action vblank=%u p%d 0x%X", gPortVBlanks, k, act);
        }
        sLastHp[k] = hp;
        sLastAction[k] = act;
    }
}

/* Every vertical blank (plat_stub.c). */
void Port_TestkitTick(void) {
    if (!Port_TestkitActive()) {
        return;
    }
    record();
    if (sLineNext >= sLineCount && sWaitKind == W_NONE) { /* idle: is there a new mailbox file? */
        char path[480];
        FILE *fp;
        snprintf(path, sizeof(path), "%s/cmd", sDir);
        fp = fopen(path, "rb");
        if (fp == NULL) {
            return;
        }
        sLineCount = sLineNext = 0;
        while (sLineCount < LINES && fgets(sLines[sLineCount], sizeof(sLines[0]), fp) != NULL) {
            sLineCount++;
        }
        fclose(fp);
        remove(path);
        if (sLineCount == 0) {
            write_reply();
            return;
        }
    }
    for (;;) {
        if (sWaitKind != W_NONE) {
            if (!wait_done()) {
                return;
            }
            sWaitKind = W_NONE;
        }
        if (sLineNext >= sLineCount) {
            write_reply();
            sLineCount = sLineNext = 0;
            return;
        }
        if (!start_command(sLines[sLineNext++])) {
            continue; /* (a wait starts: checked at once, it may be over already) */
        }
    }
}

/* ---- screenshots (gs/gs_gpu.c) --------------------------------------------------------------------------------- */

/* Asked once per frame drawn. */
const char *Port_TestkitShotPath(void) {
    if (sShotWanted) {
        return sShotPath;
    }
    if (sBurstLeft > 0 && !sBurstPending && sBurstFrame++ % sBurstEvery == 0) {
        snprintf(sShotPath, sizeof(sShotPath), "%s_%03d.ppm", sBurstPrefix, sBurstIndex);
        sBurstPending = 1;
        return sShotPath;
    }
    return NULL;
}

void Port_TestkitShotDone(void) {
    if (sBurstPending) {
        sBurstPending = 0;
        sBurstIndex++;
        sBurstLeft--;
        return;
    }
    sShotWanted = 0;
    sShotDone = 1;
}
