# AMPTemplates-UrbanTerror — Urban Terror 4.3 dedicated server for AMP

**AMP Generic Module** template for the official **Urban Terror 4.3** dedicated server
(`Quake3-UrT-Ded.x86_64`), the free tactical FPS by FrozenSand on the ioquake3 engine
(<https://www.urbanterror.info/>). Written for TeamKit, a free French game host, on 10 Oct 2026.
CubeCoders ships no Urban Terror template (their *Quake III Arena* template, same engine, was used
as a reference), and no community AMP template was found.

> Résumé en français à la fin du fichier.

## Version and download

| | |
|---|---|
| Game version | **4.3.4** (21 Jun 2018), still the latest: the official updater API lists it as `4.3.4 (latest)` on 10 Oct 2026 |
| Server binary | `Quake3-UrT-Ded.x86_64`, prints `ioQ3 1.35 urt 4.3.4 linux-x86_64 Jun  7 2018`; needs only libc, libm, libdl |
| Size | ~1.41 GB (`q3ut4/zUrT43_001…021.pk3`, `zUrT43_qvm.pk3`, `ut4_jumpents.pk3`), 35 maps |
| Installer | FrozenSand's own **UrTUpdater** for dedicated servers, `ded/UrTUpdater_Ded.sh` of <https://github.com/FrozenSand/UrTUpdater> (LGPL-2.1) |

The website's download page does not allow direct downloads, but the updater talks to the official
API (`http://www.urbanterror.info/api/updaterv4/`), gets the file list with MD5 sums and downloads
from FrozenSand's CDN (`cdn.urbanterror.info`). It only downloads missing or changed files and
deletes outdated `zUrT*.pk3`, so it is also the update path. The `master` branch copy of the
script is used: the release asset (v4.0.3-RC1, 2016) calls `tempfile`, which Debian 13 no longer has.

The updater asks questions on its first run (licence, version, mirror, engine). The start script
writes its answer file `updater-cfg` beforehand (`CURRENTVERSION=1` = latest, `DOWNLOADSERVER=2` =
the only mirror, `GAMEENGINE=1` = official engine, `ASKBEFOREUPDATING=0`) and runs it with `-q`.
The updater needs `xmllint`, absent from `cubecoders/ampbase:debian`: `Meta.ExtraContainerPackages`
installs `libxml2-utils`, so **the template requires container mode**.

**Licence.** Urban Terror is free but covered by the *Quake III Arena SDK* licence (non-commercial
use; text in `q3ut4/QIIIA_Game_Source_License.doc`, downloaded with the game). Running the updater
non-interactively means the instance owner accepts it; the Update prints a notice.
`Meta.NoCommercialUsage=True`.

## Files

| File | Role |
|---|---|
| `urbanterror.kvp`, `urbanterror*.json`, `manifest.json` | the AMP template |
| `scripts/AMP_reglages.txt` | settings model; AMP renders it to `reglages-amp.txt` (`ConfigType: template`) |
| `scripts/lancer-urt.sh` | install (`installer`) and start (`lancer <port>`) script |
| `verifier.py` | pre-push checks, must print `Tout est bon.` |

Both `scripts/` files are fetched from this repository (raw.githubusercontent.com, branch `main`)
at each Update, so **the repository must be public**.

Update stages: download `UrTUpdater_Ded.sh` (FrozenSand), `AMP_reglages.txt`, `lancer-urt.sh`, then
`/bin/bash lancer-urt.sh installer` (writes `updater-cfg`, runs the updater with a progress line
every 10 s, `chmod +x`, creates `q3ut4/mapcycle.txt` from the example if missing, prints the version).
Measured on the TeamKit host: **19 s** for a fresh install, 2 s for an up-to-date check.

## How the server is started

`/bin/bash lancer-urt.sh lancer <port>`:

1. reads `reglages-amp.txt` (written by AMP), checks every value and **makes texts displayable**:
   the engine turns every byte above 127 and every `%` into a dot on the client (`MSG_ReadString`,
   `MSG_ReadBigString` in `code/qcommon/msg.c`), and `"`, `;`, `\` are forbidden in server info
   strings. Accents are transliterated (`é` → `e`, `œ` → `oe`, `—` → `-`, `« x »` → `'x'`),
   `"` → `'`, `;` → `,`, `\` → `/`, `%` → ` pour cent`, with a console notice when something changed.
   Passwords are not altered: one with a space, accent, `"`, `;`, `\` or `%` stops the start with a
   French error (a client could not type it). Invalid numbers or choices stop it too;
2. lists the maps in `q3ut4/*.pk3` (`maps/*.bsp`, added maps included) into `cartes-disponibles.txt`,
   writes the rotation to `q3ut4/mapcycle.txt` (unknown maps removed, with a notice), checks the
   start map (falls back to the first rotation map);
3. writes `q3ut4/amp-teamkit.cfg`: the AMP settings, a few fixed values from the official
   `server_example.cfg` (`sv_master2 "master2.urbanterror.info"` — `sv_master1` already defaults to
   `master.urbanterror.info` —, `sv_dlURL`, `auth_enable 1`, `g_mapcycle`, `g_log games.log`,
   `g_logsync 1`, `filterban 1`), then `exec perso.cfg`, then `map <start map>`;
4. creates `q3ut4/perso.cfg` once (never overwritten) for any other cvar, read after AMP's values;
5. rotates `q3ut4/games.log` above 50 MB (one old copy kept);
6. `exec stdbuf -oL -eL ./Quake3-UrT-Ded.x86_64 +set fs_game q3ut4 +set fs_basepath <instance>
   +set fs_homepath <instance> +set dedicated <1|2> +set net_port <port> +set ttycon 0
   +exec amp-teamkit.cfg`, its output going through a small Python filter (below).

Because of `exec`, the server **is** the process AMP runs: AMP's console goes straight to its stdin
(the dedicated engine reads commands from stdin when it is not a TTY — `status`, `kick`, `map`,
`cyclemap`, `say`… tested) and AMP stops it by typing `quit` (`App.ExitMethod=String`): `Server
Shutdown (Server quit)`, exit code 0, tested. SIGTERM is also handled cleanly (`Signal caught`).

`dedicated 2` (default) announces the server to the master servers (the Internet list in the game);
`dedicated 1` keeps it unlisted (players type `/connect IP:port`).

## Console and player list

The engine writes its console to **stderr** (`Sys_Print`, `code/unix/unix_main.c`). Real lines
(UrT 4.3.4, two real clients, 10 Oct 2026):

```
------- Game Initialization -------                       <- AppReadyRegex
ClientUserinfoChanged: 0 n\Kevin\t\3\r\2\tl\0...
broadcast: print "Kevin^7 connected\n"
ClientBegin: 0
say: 0 Kevin: Bonjour : premier message                     <- UserChatRegex
broadcast: print "Kevin^7 renamed to KevBis\n"
broadcast: print "KevBis^7 was kicked\n"
ClientDisconnect: 0
broadcast: print "^1Ke^4vin^7 disconnected\n"
```

The join line carries the **cleaned** name (`Kevin`) but the leave line the **raw** one with colour
codes (`^1Ke^4vin`), and a kick or rename prints something else again: no regex can pair them. The
filter follows the slots (`ClientUserinfoChanged` → name, `ClientBegin` → in, `ClientDisconnect` →
out, rename → out + in, map change → nothing) and adds its own lines, which AMP's regexes read:

```
TeamKit : Kevin a rejoint la partie (emplacement 0).        <- UserJoinRegex
TeamKit : Kevin a quitte la partie (emplacement 0).         <- UserLeaveRegex
```

Every game line still goes through unchanged. `Console.FilterMatchRegex=\^[0-9]` strips colour
codes in AMP's console; `Hitch warning` lines (load spikes, mostly at map load) are thrown away.

## Settings exposed in AMP (French UI)

| AMP setting | cvar | Default |
|---|---|---|
| Port du jeu (Network tab) | `net_port` | 27960/UDP (game, master list and RCON) |
| Nom du serveur | `sv_hostname` | `^4[^7FR^1] ^5TeamKit ^7- ^3Urban Terror ^7\| ^2teamkit.fr` |
| Message de bienvenue | `sv_joinmessage` | French TeamKit message with the Discord link |
| Message de chargement | `g_motd` (loading screen) | French TeamKit message with the Discord link |
| Joueurs maximum | `sv_maxclients` (`$MaxUsers`) | 16 (FrozenSand: no more than 16 advised, bugs above 24) |
| Liste publique des serveurs | `dedicated` 2 / 1 | 2, listed |
| Mot de passe pour entrer | `g_password` (masked) | empty |
| Mot de passe RCON | `rconpassword` (masked) | empty = RCON off |
| Mode de jeu | `g_gametype` | 7, CTF (0 FFA, 1 LMS, 3 TDM, 4 TS, 5 FTL, 6 CAH, 7 CTF, 8 Bomb, 9 Jump, 10 Freeze Tag, 11 Gun Game) |
| Carte de départ | `map` | `ut4_turnpike` |
| Rotation des cartes | `mapcycle.txt` | the official `mapcycle_example.txt` (32 maps); empty = file left alone |
| Durée d'une carte | `timelimit` | 20 min |
| Score / Captures pour finir la carte | `fraglimit` / `capturelimit` | 0 / 0 |
| Durée d'une manche | `g_roundtime` | 2 min (game default) |
| Tir allié | `g_friendlyfire` 0/1/2 | 1 |
| Votes des joueurs | `g_allowvote` | 603981055 (official example) or 0 |
| Téléchargement des cartes ajoutées | `sv_allowDownload` | on, mirror `urbanterror.info` |

Colour codes in names and messages: `^0` black, `^1` red, `^2` green, `^3` yellow, `^4` blue,
`^5` cyan, `^6` magenta, `^7` white. Default values are written without accents, so what AMP shows
is what players see.

**Per-map game modes.** With *Rotation des cartes* empty, `q3ut4/mapcycle.txt` is no longer touched
and can use the 4.3 block syntax (one map per line, optional `{ g_gametype 4 }` block after a map).
**Added maps:** drop the `.pk3` into `q3ut4/`; it shows up in `cartes-disponibles.txt` at the next
start. Players download it from `sv_dlURL` (the `urbanterror.info` mirror has most community maps).

## How a player connects

Listed servers appear in the game's server browser (Internet tab). Otherwise, in the game console:
`/connect IP:port` (`/connect IP` when the port is 27960). With a password: `/password xxx` first.

## Resources (measured)

| | |
|---|---|
| RAM | ~96 MB idle, ~100 MB with two players and after two map changes |
| Disk | ~1.41 GB |
| Start | ~1 s to `Game Initialization` (19 s fresh install) |
| CPU | low; a short spike at each map load (~0.6–1.8 s `Hitch warning` with 1 CPU) |

## Not tested

The AMP side itself (Update stages run by AMP, rendering of `reglages-amp.txt`, player list and chat
in the panel), the **public listing** (`dedicated 2`: not tried to avoid announcing a test server;
both master hostnames resolve), the auth system with a real account, `/rcon` from a client, a
Windows client. Everything else above was run in a throwaway `cubecoders/ampbase:debian` container.

## Before pushing

```
python verifier.py
```

Must print `Tout est bon.`: JSON, includes, port, complete `Console.*` / `Limits.*` block, every AMP
setting → model → start script and back, same choices/bounds/defaults in AMP and the script, Update
URLs, LF/ASCII, `bash -n`, a render → start script → Quake 3 command parser round trip on default and
tricky values (accents, quotes, `;`, `%`, `\`, empty, bad passwords and numbers, unknown maps), the
console filter on real lines, and the console regexes with and without `FilterMatchRegex`.

## Install in AMP

ADS → Configuration → Instance Deployment → **Configuration Repositories**: add
`hydrocut/AMPTemplates-UrbanTerror:main`, save, **Fetch latest**. Create Instance →
**Urban Terror 4.3 (TeamKit)** → **Update** (must end with `TeamKit : Urban Terror a jour (urt 4.3.4)`)
→ **Start**.

## Credits

Urban Terror © FrozenSand Games Limited, free game under the Quake III Arena SDK licence; engine
ioquake3 (GPL-2.0). This repository only contains the template; game files come from FrozenSand's
updater, on the server.

---

## Résumé en français

Template AMP pour le **serveur dédié officiel d'Urban Terror 4.3.4** (FPS tactique gratuit de
FrozenSand, moteur ioquake3). Installé et mis à jour par **l'updater officiel de FrozenSand**
(1,4 Go, 35 cartes, 19 s sur le dédié), conteneur obligatoire (paquet `libxml2-utils`).
Un seul port, **27960 en UDP**.

- **Réglages en français dans AMP** : nom en couleurs (`^1` à `^7`), message de bienvenue et de
  chargement TeamKit + Discord, joueurs max (16), liste publique oui/non, mot de passe pour entrer,
  mot de passe RCON (masqués), mode de jeu (CTF par défaut, TS, Bomb, Freeze Tag, Gun Game…),
  carte de départ, rotation des cartes, durées et limites, tir allié, votes, téléchargement des cartes.
- **Accents** : le jeu les affiche comme des points ; le script les remplace (é → e) et le dit.
  Un mot de passe avec espace, accent, guillemet, `;`, `\` ou `%` empêche le démarrage, avec un
  message clair.
- **Console d'AMP branchée sur le serveur** (status, kick, map, say…), arrêt propre par `quit`,
  **joueurs visibles dans AMP** grâce à un petit filtre qui suit les emplacements (le jeu écrit le
  nom différemment à l'arrivée et au départ).
- **Testé en vrai** le 10 oct. 2026 dans un conteneur jetable, avec deux vrais clients Urban Terror :
  ~96 Mo de RAM, prêt en 1 s. Pas testé : AMP lui-même et l'annonce sur la liste publique.
- Avant de pousser : `python verifier.py` doit répondre « Tout est bon. ».
