#!/bin/bash
# lancer-urt.sh - pose par le template AMP TeamKit (recree a chaque Update).
#
#   lancer-urt.sh installer        etape d'Update : installe ou met a jour Urban Terror
#                                  avec le script officiel de FrozenSand (UrTUpdater_Ded.sh)
#   lancer-urt.sh lancer <port>    demarrage : prepare la config puis lance le serveur
#
# AMP ecrit les reglages de l'onglet Configuration dans reglages-amp.txt (une ligne
# cle=valeur, valeurs brutes). Ce script les controle, les rend lisibles par le jeu
# (le moteur Quake 3 remplace chaque caractere non ASCII par un point chez les
# joueurs), puis ecrit q3ut4/amp-teamkit.cfg et q3ut4/mapcycle.txt.
# Ensuite le serveur REMPLACE ce script (exec) : la console d'AMP arrive directement
# sur son entree (status, kick, map...) et AMP l'arrete en tapant quit.
cd "$(dirname "$0")" || exit 1
export LANG=C.UTF-8 LC_ALL=C.UTF-8
BIN=./Quake3-UrT-Ded.x86_64
MOD=q3ut4

if [ "$1" = "installer" ]; then
  for outil in xmllint curl md5sum python3; do
    if ! command -v "$outil" >/dev/null 2>&1; then
      echo "ERREUR : $outil absent. Cette instance doit tourner en conteneur : le paquet libxml2-utils est installe par ExtraContainerPackages."
      exit 1
    fi
  done
  if [ ! -f UrTUpdater_Ded.sh ]; then
    echo "ERREUR : UrTUpdater_Ded.sh absent (etape de telechargement precedente en echec ?)."
    exit 1
  fi
  # Reponses aux questions du premier lancement de l'updater : version 1 = la derniere
  # (4.3.4), miroir 2 = serveur de telechargement de FrozenSand, moteur 1 = moteur officiel,
  # pas de question avant de mettre a jour. Avec ce fichier, l'updater tourne sans question (-q).
  printf '%s\n' "# Ecrit par lancer-urt.sh (template AMP TeamKit) a chaque Update." \
    "CURRENTVERSION=1" "DOWNLOADSERVER=2" "GAMEENGINE=1" "ASKBEFOREUPDATING=0" > updater-cfg
  echo "TeamKit : Urban Terror est distribue gratuitement par FrozenSand sous la licence du SDK de Quake III Arena (usage non commercial, voir q3ut4/QIIIA_Game_Source_License.doc et www.urbanterror.info)."
  echo "TeamKit : verification et telechargement des fichiers du jeu (environ 1,4 Go la premiere fois)..."
  mkdir -p "$MOD"
  (
    while sleep 10; do
      echo "TeamKit : telechargement en cours, $(du -sm "$MOD" 2>/dev/null | cut -f1) Mo sur environ 1 410."
    done
  ) &
  SUIVI=$!
  bash ./UrTUpdater_Ded.sh -q
  CODE=$?
  kill "$SUIVI" 2>/dev/null
  wait "$SUIVI" 2>/dev/null
  if [ "$CODE" != 0 ]; then
    echo "ERREUR : l'updater de FrozenSand a echoue (code $CODE). 3 = site injoignable, 4 = updater perime (voir le README), 7 = fichier corrompu : relance Update."
    exit "$CODE"
  fi
  if [ ! -f "$BIN" ]; then
    echo "ERREUR : $BIN absent apres l'updater."
    exit 1
  fi
  chmod +x "$BIN"
  [ -f "$MOD/mapcycle.txt" ] || cp "$MOD/mapcycle_example.txt" "$MOD/mapcycle.txt" 2>/dev/null
  VERSION=$(grep -a -o -m 1 'urt 4\.[0-9.]*' "$BIN" | head -n 1)
  echo "TeamKit : Urban Terror a jour ($VERSION), $(du -sm "$MOD" | cut -f1) Mo de fichiers du jeu."
  exit 0
fi

if [ "$1" != "lancer" ]; then
  echo "Usage : lancer-urt.sh installer | lancer <port>"
  exit 1
fi
PORT="$2"
if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1024 ] || [ "$PORT" -gt 65535 ]; then
  echo "ERREUR : port invalide : '$PORT'."
  exit 1
fi
if [ ! -x "$BIN" ]; then
  echo "ERREUR : Urban Terror n'est pas installe ($BIN absent) : lance Update."
  exit 1
fi
if [ ! -f reglages-amp.txt ]; then
  echo "ERREUR : reglages-amp.txt absent. AMP l'ecrit au demarrage a partir de AMP_reglages.txt : lance Update."
  exit 1
fi

ARGS_FICHIER="${XDG_RUNTIME_DIR:-/tmp}/urt-teamkit-$PORT.args"
rm -f "$ARGS_FICHIER"
python3 -I - "$PWD" "$ARGS_FICHIER" <<'PY'
import glob, io, os, re, sys, unicodedata, zipfile

ICI, SORTIE = sys.argv[1], sys.argv[2]
MOD = os.path.join(ICI, 'q3ut4')
erreurs = []


def dire(texte):
    print('TeamKit : ' + texte, flush=True)


# 1. reglages ecrits par AMP (cle=valeur, valeur brute jusqu'a la fin de la ligne)
R = {}
with io.open(os.path.join(ICI, 'reglages-amp.txt'), encoding='utf-8', errors='replace') as f:
    for ligne in f:
        ligne = ligne.rstrip('\r\n')
        if '=' in ligne and not ligne.startswith('#'):
            k, v = ligne.split('=', 1)
            R[k.strip()] = v

# Joueurs maximum : AMP ne remplace PAS la variable $MaxUsers dans un fichier de type template
# (vu en vrai le 10/10/2026 : la ligne arrivait telle quelle). On lit donc App.MaxUsers
# dans le GenericModule.kvp de l'instance (dossier parent de FullBaseDir), sinon 16.
if not re.fullmatch(r'\d+', R.get('sv_maxclients', '').strip()):
    trouve = ''
    for kvp in (os.path.join(ICI, '..', 'GenericModule.kvp'), os.path.join(ICI, 'GenericModule.kvp')):
        try:
            with io.open(kvp, encoding='utf-8', errors='replace') as f:
                for ligne in f:
                    if ligne.startswith('App.MaxUsers='):
                        trouve = ligne.split('=', 1)[1].strip()
                        break
        except OSError:
            continue
        if trouve:
            break
    R['sv_maxclients'] = trouve if re.fullmatch(r'\d+', trouve) else '16'
    dire('joueurs maximum lus dans les reglages de l\'instance : %s' % R['sv_maxclients'])

# 2. textes : le moteur remplace tout octet > 127 par un point et % par un point chez
#    les joueurs (msg.c) ; " ; et \ sont interdits dans les infostrings (nom du serveur).
REMPLACE = {'\u0153': 'oe', '\u0152': 'OE', '\u00e6': 'ae', '\u00c6': 'AE', '\u00df': 'ss',
            '\u2014': '-', '\u2013': '-', '\u2012': '-', '\u2212': '-', '\u00b7': '-', '\u2022': '-',
            '\u2019': "'", '\u2018': "'", '\u00ab': "'", '\u00bb': "'", '\u201c': "'", '\u201d': "'",
            '\u2026': '...', '\u20ac': ' euros', '\u00a0': ' ', '\u202f': ' ', '\u2009': ' ',
            '"': "'", ';': ',', '\\': '/', '%': ' pour cent'}


def texte_jeu(v):
    # guillemets francais avec leurs espaces : << mot >> devient 'mot'
    s = re.sub(chr(0xab) + r'[ ' + chr(0xa0) + chr(0x202f) + r']*', "'", v)
    s = re.sub(r'[ ' + chr(0xa0) + chr(0x202f) + r']*' + chr(0xbb), "'", s)
    s = ''.join(REMPLACE.get(c, c) for c in s)
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = ''.join(c if 32 <= ord(c) < 127 else '?' for c in s)
    return re.sub(r' {2,}', ' ', s).strip()


def texte(cle, defaut=''):
    brut = R.get(cle, defaut)
    propre = texte_jeu(brut)
    if propre != brut.strip():
        dire('%s : accents et caracteres speciaux remplaces (le jeu ne sait pas les afficher) -> %s' % (cle, propre))
    return propre


def nombre(cle, defaut, mini, maxi):
    v = R.get(cle, '').strip()
    if v == '':
        return defaut
    if not re.fullmatch(r'-?\d+', v) or not (mini <= int(v) <= maxi):
        erreurs.append('%s = %r : un nombre entier entre %d et %d.' % (cle, v, mini, maxi))
        return defaut
    return int(v)


def choix(cle, defaut, permis):
    v = R.get(cle, '').strip() or defaut
    if v not in permis:
        erreurs.append('%s = %r : valeurs possibles %s.' % (cle, v, ', '.join(permis)))
        return defaut
    return v


def mot_de_passe(cle, nom):
    v = R.get(cle, '')
    if v and not re.fullmatch(r'[!#-$&-:<-\[\]-~]{1,64}', v):
        erreurs.append('%s : 64 caracteres au plus, sans espace, accent, guillemet, point-virgule, '
                       'antislash ni %% (le jeu ne les accepte pas dans un mot de passe).' % nom)
        return ''
    return v


nom = texte('sv_hostname') or 'TeamKit - Urban Terror'
bienvenue = texte('sv_joinmessage')
chargement = texte('g_motd')
joueurs = nombre('sv_maxclients', 16, 2, 32)
dedicated = choix('dedicated', '2', ['1', '2'])
entree = mot_de_passe('g_password', 'Mot de passe pour entrer')
rcon = mot_de_passe('rconpassword', 'Mot de passe RCON')
mode = choix('g_gametype', '7', ['0', '1', '3', '4', '5', '6', '7', '8', '9', '10', '11'])
temps = nombre('timelimit', 20, 0, 999)
score = nombre('fraglimit', 0, 0, 9999)
captures = nombre('capturelimit', 0, 0, 999)
manche = nombre('g_roundtime', 2, 1, 60)
tir_allie = choix('g_friendlyfire', '1', ['0', '1', '2'])
votes = choix('g_allowvote', '603981055', ['0', '603981055'])
# case a cocher : AMP ecrit la valeur de EnumValues (1/0) ; True/False acceptes aussi
R['sv_allowdownload'] = {'true': '1', 'false': '0'}.get(R.get('sv_allowdownload', '').strip().lower(),
                                                       R.get('sv_allowdownload', ''))
telechargement = choix('sv_allowdownload', '1', ['0', '1'])

# 3. cartes presentes (fichiers maps/*.bsp des .pk3 de q3ut4, cartes ajoutees comprises)
cartes = set()
for pk3 in sorted(glob.glob(os.path.join(MOD, '*.pk3'))):
    try:
        for n in zipfile.ZipFile(pk3).namelist():
            if n.lower().startswith('maps/') and n.lower().endswith('.bsp') and n.count('/') == 1:
                cartes.add(n[5:-4].lower())
    except (zipfile.BadZipFile, OSError) as e:
        dire('ATTENTION, %s illisible (%s), ignore.' % (os.path.basename(pk3), e))
if not cartes:
    erreurs.append('aucune carte trouvee dans q3ut4/*.pk3 : lance Update.')
with io.open(os.path.join(ICI, 'cartes-disponibles.txt'), 'w', encoding='utf-8', newline='\n') as f:
    f.write('# Cartes trouvees au dernier demarrage (q3ut4/*.pk3), a recopier dans les reglages.\n')
    f.write('\n'.join(sorted(cartes)) + '\n')

NOM_CARTE = re.compile(r'[a-z0-9_.-]{1,64}')
rotation, inconnues = [], []
for c in re.split(r'[\s,;]+', R.get('rotation', '').lower()):
    if not c:
        continue
    if NOM_CARTE.fullmatch(c) and c in cartes:
        if c not in rotation:
            rotation.append(c)
    else:
        inconnues.append(c)
if inconnues:
    dire('ATTENTION, cartes introuvables retirees de la rotation : %s (liste dans cartes-disponibles.txt).'
         % ', '.join(inconnues))
cycle = os.path.join(MOD, 'mapcycle.txt')
if rotation:
    with io.open(cycle, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(rotation) + '\n')
    dire('rotation de %d cartes ecrite dans q3ut4/mapcycle.txt.' % len(rotation))
elif os.path.isfile(cycle):
    dire('rotation vide dans AMP : q3ut4/mapcycle.txt garde tel quel.')
elif os.path.isfile(os.path.join(MOD, 'mapcycle_example.txt')):
    with open(os.path.join(MOD, 'mapcycle_example.txt'), 'rb') as a, open(cycle, 'wb') as b:
        b.write(a.read())
    dire('rotation vide dans AMP : rotation officielle copiee dans q3ut4/mapcycle.txt.')

depart = R.get('map', '').strip().lower()
if depart not in cartes or not NOM_CARTE.fullmatch(depart):
    remplacante = rotation[0] if rotation else ('ut4_turnpike' if 'ut4_turnpike' in cartes else min(cartes, default=''))
    if depart:
        dire('ATTENTION, carte de depart %r introuvable : %s a la place.' % (depart, remplacante))
    depart = remplacante

if erreurs:
    for e in erreurs:
        print('ERREUR : ' + e, flush=True)
    print("Corrige ce reglage dans l'onglet Configuration d'AMP, puis relance.", flush=True)
    sys.exit(1)

# 4. q3ut4/amp-teamkit.cfg, execute au demarrage (les valeurs n'ont plus de " ni de ;)
L = ['// amp-teamkit.cfg - ECRIT PAR lancer-urt.sh a chaque demarrage, a partir des',
     "// reglages d'AMP. Ne le modifie pas : mets tes reglages en plus dans perso.cfg.",
     'set sv_hostname "%s"' % nom,
     'set sv_joinmessage "%s"' % bienvenue,
     'set g_motd "%s"' % chargement,
     'set sv_maxclients "%d"' % joueurs,
     'set g_password "%s"' % entree,
     'set rconpassword "%s"' % rcon,
     'set g_gametype "%s"' % mode,
     'set timelimit "%d"' % temps,
     'set fraglimit "%d"' % score,
     'set capturelimit "%d"' % captures,
     'set g_roundtime "%d"' % manche,
     'set g_friendlyfire "%s"' % tir_allie,
     'set g_allowvote "%s"' % votes,
     'set sv_allowDownload "%s"' % telechargement,
     '// Fixes (valeurs du server_example.cfg officiel de la 4.3). sv_master1 vaut deja',
     '// master.urbanterror.info (valeur du moteur) : on ajoute le second maitre.',
     'set sv_master2 "master2.urbanterror.info"',
     'sets sv_dlURL "urbanterror.info"',
     'sets auth_enable "1"',
     'set g_mapcycle "mapcycle.txt"',
     'set g_log "games.log"',
     'set g_logsync "1"',
     'set filterban "1"',
     'exec perso.cfg',
     'map %s' % depart]
with io.open(os.path.join(MOD, 'amp-teamkit.cfg'), 'w', encoding='ascii', newline='\n') as f:
    f.write('\n'.join(L) + '\n')

# Journal du jeu (g_log) : il grossit sans fin, on garde l'actuel et un ancien.
journal = os.path.join(MOD, 'games.log')
if os.path.isfile(journal) and os.path.getsize(journal) > 50 * 1024 * 1024:
    os.replace(journal, journal + '.ancien')
    dire('q3ut4/games.log depassait 50 Mo : renomme en games.log.ancien.')

perso = os.path.join(MOD, 'perso.cfg')
if not os.path.isfile(perso):
    with io.open(perso, 'w', encoding='ascii', newline='\n') as f:
        f.write('// perso.cfg - tes reglages Urban Terror en plus, un par ligne (voir server_example.cfg).\n'
                '// Lu a chaque demarrage APRES les reglages d\'AMP : il peut donc les remplacer.\n'
                '// Le template ne l\'ecrase jamais. Exemples :\n'
                '// set g_gear "0"\n// set g_respawndelay "3"\n')

dire('%s, %s, carte %s, %d joueurs max, %s, RCON %s.' % (
    {'1': 'non liste (LAN)', '2': 'annonce sur la liste publique'}[dedicated],
    'mode ' + mode, depart, joueurs,
    'mot de passe pour entrer' if entree else 'ouvert a tous',
    'actif' if rcon else 'desactive (mot de passe vide)'))
with io.open(SORTIE, 'w', encoding='ascii', newline='\n') as f:
    f.write(dedicated + '\n')
PY
[ $? = 0 ] && [ -s "$ARGS_FICHIER" ] || exit 1
DEDICATED=$(head -n 1 "$ARGS_FICHIER")
rm -f "$ARGS_FICHIER"

# Lignes d'arrivee et de depart pour la liste des joueurs d'AMP. Le jeu ecrit le nom
# NETTOYE a l'arrivee ("Kevin^7 connected") mais le nom BRUT, codes couleur compris,
# au depart ("^1Ke^4vin^7 disconnected") : impossible a faire correspondre avec une
# regex. Ce filtre suit les emplacements (ClientUserinfoChanged: N n\Nom\..., ClientBegin: N,
# ClientDisconnect: N) et ajoute ses propres lignes, toujours avec le meme nom. Toutes
# les lignes du jeu passent telles quelles.
FILTRE='
import re, sys
COULEUR = re.compile(r"\^[0-9A-Za-z]")
INFO = re.compile(r"^ClientUserinfoChanged: (\d+) n\\([^\\]*)\\")
DEBUT = re.compile(r"^ClientBegin: (\d+)$")
FIN = re.compile(r"^ClientDisconnect: (\d+)$")
noms, presents = {}, {}
def dire(texte):
    sys.stdout.write("TeamKit : " + texte + "\n")
def arrive(n):
    nom = noms.get(n)
    if nom and n not in presents:
        presents[n] = nom
        dire("%s a rejoint la partie (emplacement %s)." % (nom, n))
def part(n):
    nom = presents.pop(n, None)
    if nom:
        dire("%s a quitte la partie (emplacement %s)." % (nom, n))
for brut in sys.stdin.buffer:
    ligne = brut.decode("utf-8", "replace").rstrip("\r\n")
    sys.stdout.write(ligne + "\n")
    m = INFO.match(ligne)
    if m:
        n, nom = m.group(1), COULEUR.sub("", m.group(2)).strip() or "sans_nom"
        noms[n] = nom
        if n in presents and presents[n] != nom:
            part(n)
            arrive(n)
    elif DEBUT.match(ligne):
        arrive(DEBUT.match(ligne).group(1))
    elif FIN.match(ligne):
        n = FIN.match(ligne).group(1)
        part(n)
        noms.pop(n, None)
    elif ligne.startswith("----- Server Shutdown"):
        noms.clear()
        presents.clear()
    sys.stdout.flush()
'

# Utilise seulement par verifier.py : s'arrete avant de lancer le jeu.
[ -n "$TK_ESSAI" ] && { echo "TK_ESSAI dedicated=$DEDICATED"; exit 0; }

# exec : le serveur remplace ce script, garde l'entree d'AMP (console) et recoit le
# "quit" d'arret. Le moteur ecrit sa console sur stderr (Sys_Print, unix_main.c) et
# quelques lignes sur stdout : les deux passent par le filtre, ligne par ligne.
exec stdbuf -oL -eL "$BIN" +set fs_game "$MOD" +set fs_basepath "$PWD" +set fs_homepath "$PWD" \
  +set dedicated "$DEDICATED" +set net_port "$PORT" +set ttycon 0 +exec amp-teamkit.cfg \
  > >(exec python3 -I -u -c "$FILTRE") 2>&1
