# -*- coding: utf-8 -*-
"""
Contrôle du template avant de le pousser (même rôle que ceux de Wesnoth et de Dominions 6).

    python verifier.py

1. tous les JSON se parsent ;
2. le .kvp : fichiers inclus, Ref du port, bloc Console.* / Limits.* complet, console d'AMP
   sur l'entrée du serveur (STDIO), arrêt par « quit », conteneur + libxml2-utils ;
3. chaque réglage exposé dans AMP est écrit dans scripts/AMP_reglages.txt (rendu par AMP en
   reglages-amp.txt) et lu par le lanceur, et inversement ;
4. les choix, bornes et valeurs par défaut d'AMP sont ceux du lanceur ;
5. les fichiers téléchargés à l'Update existent dans scripts/, à l'URL du dépôt du manifest,
   et l'étape d'installation lance bien le lanceur ;
6. le lanceur : LF, ASCII, sans {{, `bash -n` si bash est là ;
7. aller-retour : on rend AMP_reglages.txt comme AMP (remplacement brut) avec les valeurs par
   défaut puis des valeurs piégées (accents, guillemets, point-virgule, %, antislash, vide),
   on passe le tout dans la vraie partie Python du lanceur (fausses cartes .pk3), puis on relit
   amp-teamkit.cfg comme le moteur Quake 3 (découpage sur ; hors guillemets, jetons) : chaque
   valeur doit arriver entière, en ASCII, sans " ; \\ ni % ;
8. le filtre de console du lanceur sur les vraies lignes d'Urban Terror 4.3.4 (relevées le
   10 oct. 2026 dans un conteneur jetable avec deux vrais clients : arrivée, renommage,
   exclusion, changement de carte) ;
9. les regex de console sur ces lignes, avec et sans le FilterMatchRegex appliqué avant.
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ICI = os.path.dirname(os.path.abspath(__file__))
NOM = 'urbanterror'
MODELE = 'scripts/AMP_reglages.txt'
LANCEUR = 'scripts/lancer-urt.sh'
soucis = []


def lire(nom, binaire=False):
    with open(os.path.join(ICI, nom), 'rb') as f:
        brut = f.read()
    return brut if binaire else brut.decode('utf-8')


def ok(quoi, detail):
    print('ok   %-26s %s' % (quoi, detail))


def py(motif):
    # AMP est en C# : (?<nom>...) ; Python veut (?P<nom>...)
    return re.compile(motif.replace('(?<', '(?P<'))


# ── 1. JSON ──────────────────────────────────────────────────────────────────
data = {}
for nom in ('manifest.json', NOM + 'config.json', NOM + 'metaconfig.json', NOM + 'ports.json', NOM + 'updates.json'):
    try:
        data[nom] = json.loads(lire(nom))
        ok(nom, 'JSON valide')
    except Exception as e:
        soucis.append('%s : JSON invalide (%s)' % (nom, e))
if soucis:
    print('\n'.join('NON  ' + s for s in soucis))
    sys.exit(1)
config = data[NOM + 'config.json']
updates = data[NOM + 'updates.json']
ports = data[NOM + 'ports.json']
lanceur = lire(LANCEUR)
modele = lire(MODELE)

# ── 2. kvp ───────────────────────────────────────────────────────────────────
kvp = lire(NOM + '.kvp')
cles = dict(l.split('=', 1) for l in kvp.splitlines() if '=' in l)
for ref in re.findall(r'@IncludeJson\[([^\]]+)\]', kvp):
    if not os.path.isfile(os.path.join(ICI, ref)):
        soucis.append('@IncludeJson[%s] : fichier absent' % ref)
for cle in ('Meta.ConfigManifest', 'Meta.MetaConfigManifest'):
    if not os.path.isfile(os.path.join(ICI, cles.get(cle, '?'))):
        soucis.append('%s pointe sur un fichier absent' % cle)
refs = {p['Ref'] for p in ports}
if cles.get('App.PrimaryApplicationPortRef') not in refs:
    soucis.append('PrimaryApplicationPortRef ne correspond à aucun port')
cmd = cles.get('App.CommandLineArgs', '')
for r in re.findall(r'\{\{\$(\w+)\}\}', cmd):
    if r not in refs and r != 'FullBaseDir':
        soucis.append('{{$%s}} : aucun port ne porte ce Ref' % r)
if cmd != '"{{$FullBaseDir}}lancer-urt.sh" lancer {{$%s}}' % cles.get('App.PrimaryApplicationPortRef'):
    soucis.append('ligne de commande inattendue : %s' % cmd)
if [(p['Port'], p['Protocol']) for p in ports] != [(27960, 'UDP')]:
    soucis.append('Urban Terror n’utilise qu’un port, 27960 en UDP')
ok('ports', ', '.join('%s %s/%s' % (p['Ref'], p['Port'], p['Protocol']) for p in ports))
ATTENDUES = ['App.SupportsUniversalSleep', 'App.WakeupMode', 'App.ApplicationReadyMode', 'Console.FilterMatchRegex',
             'Console.FilterMatchReplacement', 'Console.ThrowawayMessageRegex', 'Console.AppReadyRegex',
             'Console.UserJoinRegex', 'Console.UserLeaveRegex', 'Console.UserChatRegex', 'Console.UpdateAvailableRegex',
             'Console.PreConnectRegex', 'Console.ConnectIPRegex', 'Console.MetricsRegex', 'Console.HideFromConsoleRegex',
             'Console.SuppressLogAtStart', 'Console.UserActions', 'Limits.SleepMode', 'Limits.SleepOnStart',
             'Limits.SleepDelayMinutes', 'Limits.DozeDelay', 'Limits.AutoRetryCount', 'Limits.SleepStartThresholdSeconds']
absentes = [c for c in ATTENDUES if c not in cles]
if absentes:
    soucis.append('clés absentes du .kvp : ' + ', '.join(absentes))
else:
    ok('kvp complet', 'les %d clés Console/Limits sont là' % len(ATTENDUES))
ATTENDU_KVP = {
    'App.ApplicationReadyMode': 'RegexMatch',
    'App.HasWriteableConsole': 'True',        # la console d'AMP va sur l'entrée du serveur (exec)
    'App.AdminMethod': 'STDIO',
    'App.ExitMethod': 'String',               # « quit » sur l'entrée : arrêt propre, code 0 (essai)
    'App.ExitString': 'quit',
    'App.ExecutableLinux': '/bin/bash',
    'Meta.ContainerPolicy': 'Required',
    'Meta.SpecificDockerImage': 'cubecoders/ampbase:debian',
    'Meta.NoCommercialUsage': 'True',         # licence du SDK de Quake III Arena
}
for cle, val in ATTENDU_KVP.items():
    if cles.get(cle) != val:
        soucis.append('%s devrait valoir %s (vaut %r)' % (cle, val, cles.get(cle)))
if not cles.get('Console.AppReadyRegex'):
    soucis.append('RegexMatch sans AppReadyRegex : l’instance ne serait jamais déclarée prête')
if json.loads(cles.get('Meta.ExtraContainerPackages', '[]')) != ['libxml2-utils']:
    soucis.append('ExtraContainerPackages doit être ["libxml2-utils"] (xmllint pour l’updater de FrozenSand)')
if cles.get('Meta.URL') != data['manifest.json']['url']:
    soucis.append('Meta.URL et manifest.json ne désignent pas le même dépôt')
ok('kvp', 'STDIO, arrêt par quit, conteneur + libxml2-utils')

# ── 3. réglages <-> modèle <-> lanceur ───────────────────────────────────────
par_param = {}
for c in config:
    p = c['ParamFieldName']
    if p in par_param:
        soucis.append('réglage en double : %s' % p)
    par_param[p] = c
    attendu = 'sv_maxclients' if c['FieldName'] == '$MaxUsers' else c['FieldName']
    if p != attendu:
        soucis.append('%s : ParamFieldName %s inattendu' % (c['FieldName'], p))
lignes_modele = [l for l in modele.splitlines() if l and not l.startswith('#')]
dans_modele = {}
for l in lignes_modele:
    m = re.fullmatch(r'([a-z_]+)=\{\{(\$?\w+)\}\}', l)
    if not m:
        soucis.append('ligne du modèle inattendue : %s' % l)
        continue
    dans_modele[m.group(1)] = m.group(2)
for p, c in par_param.items():
    if dans_modele.get(p) != c['FieldName']:
        soucis.append('%s : attendu « %s={{%s}} » dans %s' % (p, p, c['FieldName'], MODELE))
for p in set(dans_modele) - set(par_param):
    soucis.append('%s dans %s mais aucun réglage AMP' % (p, MODELE))
LU = re.compile(r"""(?:R\.get|texte|nombre|choix|mot_de_passe)\('([a-z_]+)'""")
lus = set(LU.findall(lanceur))
if lus != set(dans_modele):
    soucis.append('clés du modèle %s ≠ clés lues par le lanceur %s' % (sorted(dans_modele), sorted(lus)))
else:
    ok('correspondance', '%d réglages : AMP -> AMP_reglages.txt -> lanceur' % len(par_param))
meta = data[NOM + 'metaconfig.json'][0]
racine = cles['App.RootDir'].strip('./').strip('/')
if meta.get('ConfigType') != 'template' or meta.get('ConfigFileTemplate') != racine + '/AMP_reglages.txt':
    soucis.append('metaconfig : ConfigFileTemplate devrait être %s/AMP_reglages.txt' % racine)
if meta.get('ConfigFile') != 'reglages-amp.txt' or "'reglages-amp.txt'" not in lanceur:
    soucis.append('le fichier rendu par AMP (ConfigFile) n’est pas celui que lit le lanceur')
mu = par_param['sv_maxclients']
if mu['FieldName'] != '$MaxUsers' or mu['DefaultValue'] != cles.get('App.MaxUsers'):
    soucis.append('Joueurs maximum : $MaxUsers, défaut égal à App.MaxUsers')
for p in ('sv_joinmessage', 'g_motd'):
    d = par_param[p]['DefaultValue']
    if 'TeamKit.fr' not in d or 'discord.gg/EuAjGMYPHY' not in d:
        soucis.append('%s par défaut doit citer TeamKit.fr et le Discord' % p)
    if any(ord(ch) > 127 for ch in d):
        soucis.append('%s par défaut : pas d’accent (le jeu affiche un point) : %r' % (p, d))
if 'TeamKit' not in par_param['sv_hostname']['DefaultValue']:
    soucis.append('le nom du serveur par défaut doit contenir TeamKit')
for p in ('g_password', 'rconpassword'):
    if par_param[p]['InputType'] != 'password' or par_param[p]['DefaultValue'] != '':
        soucis.append('%s : champ masqué (password), vide par défaut' % p)

# ── 4. choix, bornes, défauts : AMP == lanceur ───────────────────────────────
for m in re.finditer(r"choix\('(\w+)', '([^']*)', \[([^\]]*)\]\)", lanceur):
    p, defaut, permis = m.group(1), m.group(2), set(re.findall(r"'([^']*)'", m.group(3)))
    c = par_param[p]
    proposes = set(c['EnumValues'].values()) if c['InputType'] == 'checkbox' else set(c['EnumValues'])
    if proposes != permis:
        soucis.append('%s : AMP propose %s, le lanceur accepte %s' % (p, sorted(proposes), sorted(permis)))
    if c['DefaultValue'] != defaut:
        soucis.append('%s : défaut AMP %r, défaut du lanceur %r' % (p, c['DefaultValue'], defaut))
for m in re.finditer(r"nombre\('(\w+)', (-?\d+), (-?\d+), (-?\d+)\)", lanceur):
    p, defaut, mini, maxi = m.groups()
    c = par_param[p]
    if (c['DefaultValue'], c.get('MinValue'), c.get('MaxValue')) != (defaut, mini, maxi):
        soucis.append('%s : AMP (%s, %s-%s) ≠ lanceur (%s, %s-%s)' % (
            p, c['DefaultValue'], c.get('MinValue'), c.get('MaxValue'), defaut, mini, maxi))
ok('choix et bornes', 'énumérations, cases, nombres et défauts identiques')

# ── 5. Update ────────────────────────────────────────────────────────────────
depot = data['manifest.json']['url'].replace('https://github.com/', '')
fetch = [e for e in updates if e['UpdateSource'] == 'FetchURL']
nos_fichiers = set()
for e in fetch:
    if e['UpdateSourceData'].startswith('https://raw.githubusercontent.com/FrozenSand/'):
        if e['UpdateSourceData'] != 'https://raw.githubusercontent.com/FrozenSand/UrTUpdater/master/ded/UrTUpdater_Ded.sh' \
                or e['UpdateSourceArgs'] != 'UrTUpdater_Ded.sh':
            soucis.append('updater de FrozenSand : URL ou nom inattendu')
        continue
    attendu = 'https://raw.githubusercontent.com/%s/main/scripts/%s' % (depot, e['UpdateSourceArgs'])
    if e['UpdateSourceData'] != attendu:
        soucis.append('URL inattendue pour %s : %s' % (e['UpdateSourceArgs'], e['UpdateSourceData']))
    elif not os.path.isfile(os.path.join(ICI, 'scripts', e['UpdateSourceArgs'])):
        soucis.append('scripts/%s absent du dépôt' % e['UpdateSourceArgs'])
    nos_fichiers.add(e['UpdateSourceArgs'])
    if e.get('UpdateSourceTarget') != '{{$FullBaseDir}}' or e.get('OverwriteExistingFiles') is not True:
        soucis.append('%s : doit être réécrit dans {{$FullBaseDir}} à chaque Update' % e['UpdateSourceArgs'])
if nos_fichiers != {'AMP_reglages.txt', 'lancer-urt.sh'}:
    soucis.append('l’Update doit déposer AMP_reglages.txt et lancer-urt.sh')
dernier = updates[-1]
if (dernier['UpdateSource'], dernier['UpdateSourceData'], dernier['UpdateSourceArgs']) != \
        ('Executable', '/bin/bash', '"{{$FullBaseDir}}lancer-urt.sh" installer') or dernier.get('SkipOnFailure'):
    soucis.append('dernière étape : /bin/bash "{{$FullBaseDir}}lancer-urt.sh" installer, sans SkipOnFailure')
for besoin in ('CURRENTVERSION=1', 'DOWNLOADSERVER=2', 'GAMEENGINE=1', 'ASKBEFOREUPDATING=0',
               'bash ./UrTUpdater_Ded.sh -q'):
    if besoin not in lanceur:
        soucis.append('installation : %s absent du lanceur' % besoin)
ok('Update', 'updater FrozenSand + %s, puis « lancer-urt.sh installer »' % ', '.join(sorted(nos_fichiers)))

# ── 6. lanceur ───────────────────────────────────────────────────────────────
for nom in (LANCEUR, MODELE):
    brut = lire(nom, binaire=True)
    if b'\r' in brut:
        soucis.append('%s : fins de ligne Windows (CRLF)' % nom)
    if any(o > 127 for o in brut):
        soucis.append('%s : caractères non ASCII' % nom)
if '{{' in lanceur:
    soucis.append('le lanceur contient {{ : AMP pourrait le remplacer')
for besoin, pourquoi in [
    ('exec stdbuf -oL -eL "$BIN"', 'le serveur doit remplacer le lanceur (console et quit d’AMP)'),
    ('> >(exec python3 -I -u -c "$FILTRE") 2>&1', 'stdout ET stderr (la console du moteur) dans le filtre'),
    ('+set fs_basepath "$PWD" +set fs_homepath "$PWD"', 'tout dans le dossier de l’instance'),
    ('+exec amp-teamkit.cfg', 'config écrite par le lanceur'),
]:
    if besoin not in lanceur:
        soucis.append('lanceur : %s (%s)' % (besoin, pourquoi))
bash = None
for c in (r'C:\Program Files\Git\bin\bash.exe', '/bin/bash', shutil.which('bash')):
    if c and os.path.isfile(c) and 'system32' not in c.lower():
        bash = c
        break
if bash:
    r = subprocess.run([bash, '-n', os.path.join(ICI, LANCEUR)], capture_output=True, text=True)
    if r.returncode:
        soucis.append('bash -n %s : %s' % (LANCEUR, r.stderr.strip()))
    else:
        ok('bash -n', LANCEUR)
else:
    print('--   bash -n                    pas de bash ici, syntaxe non vérifiée')

# ── 7. aller-retour AMP -> lanceur (partie Python) -> moteur ─────────────────
m = re.search(r"^python3 -I - \"\$PWD\" \"\$ARGS_FICHIER\" <<'PY'\n(.*?)^PY$", lanceur, re.S | re.M)
PREPARER = m.group(1) if m else None
if not PREPARER:
    soucis.append('partie Python du lanceur introuvable')
CARTES = ['ut4_turnpike', 'ut4_casa', 'ut4_abbey', 'ut4_uptown', 'ut4_jumpents']


def rendre(valeurs):
    t = modele
    for c in config:
        t = t.replace('{{%s}}' % c['FieldName'], valeurs.get(c['ParamFieldName'], c['DefaultValue']))
    return t


def lire_cfg_comme_le_moteur(texte):
    """Cbuf_Execute (coupe sur ; hors guillemets et fin de ligne) puis Cmd_TokenizeString."""
    commandes = []
    for ligne in texte.split('\n'):
        guillemets, debut = 0, 0
        for i, ch in enumerate(ligne + ';'):
            if ch == '"':
                guillemets += 1
            if (ch == ';' and not guillemets % 2) or i == len(ligne):
                commandes.append(ligne[debut:i])
                debut = i + 1
    vals = {}
    for c in commandes:
        jetons, i = [], 0
        while i < len(c):
            if c[i] <= ' ':
                i += 1
            elif c.startswith('//', i):
                break
            elif c[i] == '"':
                j = c.find('"', i + 1)
                j = len(c) if j < 0 else j
                jetons.append(c[i + 1:j])
                i = j + 1
            else:
                j = i
                while j < len(c) and c[j] > ' ':
                    j += 1
                jetons.append(c[i:j])
                i = j
        if len(jetons) >= 3 and jetons[0] in ('set', 'sets'):
            vals[jetons[1].lower()] = jetons[2] if len(jetons) == 3 else None   # None = valeur coupée
        elif jetons[:1] in (['map'], ['exec']):
            vals[jetons[0]] = jetons[1:]
    return vals


def preparer(valeurs, avant=None):
    """Lance la vraie partie Python du lanceur dans un faux dossier d'instance."""
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, 'q3ut4'))
        with zipfile.ZipFile(os.path.join(tmp, 'q3ut4', 'zUrT43_001.pk3'), 'w') as z:
            for c in CARTES:
                z.writestr('maps/%s.bsp' % c, b'IBSP')
            z.writestr('maps/sous/dossier.bsp', b'IBSP')
        with open(os.path.join(tmp, 'q3ut4', 'mapcycle_example.txt'), 'w') as f:
            f.write('ut4_casa\n')
        if avant:
            avant(tmp)
        with io.open(os.path.join(tmp, 'reglages-amp.txt'), 'w', encoding='utf-8', newline='\n') as f:
            f.write(rendre(valeurs))
        sortie = os.path.join(tmp, 'args')
        p = subprocess.run([sys.executable, '-I', '-', tmp, sortie], input=PREPARER.encode('utf-8'),
                           capture_output=True, timeout=60)
        texte = p.stdout.decode('utf-8', 'replace') + p.stderr.decode('utf-8', 'replace')
        res = {'code': p.returncode, 'texte': texte}
        cfg = os.path.join(tmp, 'q3ut4', 'amp-teamkit.cfg')
        if os.path.isfile(cfg):
            res['cfg_brut'] = open(cfg, 'rb').read()
            res['cfg'] = lire_cfg_comme_le_moteur(res['cfg_brut'].decode('ascii'))
        for nom in ('mapcycle.txt', 'perso.cfg'):
            chemin = os.path.join(tmp, 'q3ut4', nom)
            if os.path.isfile(chemin):
                res[nom] = open(chemin, encoding='utf-8').read()
        if os.path.isfile(sortie):
            res['dedicated'] = open(sortie).read().strip()
        return res


if PREPARER:
    defauts = {c['ParamFieldName']: c['DefaultValue'] for c in config}
    n = 0
    r = preparer({})
    n += 1
    if r['code'] != 0 or 'cfg' not in r:
        soucis.append('valeurs par défaut : le lanceur refuse\n%s' % r['texte'])
    else:
        v = r['cfg']
        for p in ('sv_hostname', 'sv_joinmessage', 'g_motd'):
            if v.get(p) != defauts[p]:
                soucis.append('défaut %s : écrit %r, relu %r' % (p, defauts[p], v.get(p)))
        for p in ('timelimit', 'fraglimit', 'capturelimit', 'g_roundtime', 'g_gametype', 'g_friendlyfire',
                  'g_allowvote', 'sv_maxclients'):
            if v.get(p) != defauts[p]:
                soucis.append('défaut %s : %r au lieu de %r' % (p, v.get(p), defauts[p]))
        if v.get('sv_allowdownload') != '1' or v.get('g_password') != '' or v.get('rconpassword') != '':
            soucis.append('défauts téléchargement / mots de passe inattendus')
        if v.get('map') != ['ut4_turnpike'] or v.get('exec') != ['perso.cfg'] or r.get('dedicated') != '2':
            soucis.append('défaut : carte %r, exec %r, dedicated %r' % (v.get('map'), v.get('exec'), r.get('dedicated')))
        if r.get('mapcycle.txt') != 'ut4_turnpike\nut4_abbey\nut4_uptown\nut4_casa\n':
            soucis.append('rotation par défaut (cartes présentes seulement) : %r' % r.get('mapcycle.txt'))
        if 'perso.cfg' not in r:
            soucis.append('perso.cfg pas créé')
        if 'accents' in r['texte']:
            soucis.append('les textes par défaut ne devraient pas déclencher le remplacement des accents')
        lignes = [l for l in r['cfg_brut'].decode('ascii').splitlines() if l and not l.startswith('//')]
        if lignes[-2:] != ['exec perso.cfg', 'map ut4_turnpike']:
            soucis.append('amp-teamkit.cfg doit finir par exec perso.cfg puis map')
    # textes piégés : chaque valeur doit arriver entière, ASCII, sans " ; \ %
    PIEGES = {
        'Serveur francophone hébergé gratuitement par TeamKit.fr — teamkit.fr · Discord : discord.gg/EuAjGMYPHY':
            'Serveur francophone heberge gratuitement par TeamKit.fr - teamkit.fr - Discord : discord.gg/EuAjGMYPHY',
        'Dites "bonjour" ; règles : 100 % fair-play // pas de triche \\o/':
            "Dites 'bonjour' , regles : 100 pour cent fair-play // pas de triche /o/",
        '^1Ça ^2c\'est l\'été « Œuvre »':
            "^1Ca ^2c'est l'ete 'OEuvre'",
        '': '',
        '   espaces   autour   ': 'espaces autour',
    }
    for brut, attendu in PIEGES.items():
        for p in ('sv_hostname', 'sv_joinmessage', 'g_motd'):
            r = preparer({p: brut})
            n += 1
            lu = r.get('cfg', {}).get(p)
            voulu = 'TeamKit - Urban Terror' if (p == 'sv_hostname' and attendu == '') else attendu
            if r['code'] != 0 or lu != voulu:
                soucis.append('aller-retour %s %r : relu %r au lieu de %r\n%s' % (p, brut, lu, voulu, r['texte']))
            elif any(ch in (lu or '') for ch in '";\\%') or any(ord(ch) > 127 for ch in lu or ''):
                soucis.append('aller-retour %s : caractère interdit dans %r' % (p, lu))
    # mots de passe : acceptés tels quels, ou refus net (code 1, message, pas de cfg)
    for mdp, accepte in [('Secret_rcon-42', True), ('a!b#c$d&e(f)g*h+i,j.k/l:m<n=o>p?q@r[s]t^u_v`w{x|y}z~', True),
                         ('mon secret', False), ('été', False), ('a"b', False), ('a;b', False), ('a\\b', False),
                         ('100%', False), ('x' * 65, False)]:
        for p in ('g_password', 'rconpassword'):
            r = preparer({p: mdp})
            n += 1
            if accepte and (r['code'] != 0 or r['cfg'].get(p) != mdp):
                soucis.append('mot de passe %r refusé ou abîmé pour %s' % (mdp, p))
            if not accepte and (r['code'] != 1 or 'ERREUR' not in r['texte'] or 'cfg' in r):
                soucis.append('mot de passe %r pour %s : il fallait un refus net' % (mdp, p))
            if mdp in r['texte'] and len(mdp) > 3:
                soucis.append('le mot de passe %r apparaît dans la console' % mdp)
    # nombres et choix invalides : refus net
    for p, v in [('timelimit', 'abc'), ('timelimit', '1000'), ('sv_maxclients', '1'), ('sv_maxclients', '33'),
                 ('g_gametype', '2'), ('dedicated', '0'), ('g_friendlyfire', 'oui')]:
        r = preparer({p: v})
        n += 1
        if r['code'] != 1 or 'ERREUR' not in r['texte']:
            soucis.append('%s = %r : il fallait un refus net' % (p, v))
    for p, v, attendu in [('timelimit', '', '20'), ('sv_allowdownload', 'False', '0'), ('sv_allowdownload', 'True', '1'),
                          ('dedicated', '1', None)]:
        r = preparer({p: v})
        n += 1
        if r['code'] != 0:
            soucis.append('%s = %r refusé à tort' % (p, v))
        elif attendu is not None and r['cfg'].get(p.lower() if p != 'sv_allowdownload' else 'sv_allowdownload') != attendu:
            soucis.append('%s = %r : relu %r' % (p, v, r['cfg'].get(p)))
        elif attendu is None and r.get('dedicated') != '1':
            soucis.append('dedicated = 1 non transmis au lanceur')
    # cartes
    r = preparer({'rotation': 'UT4_Casa, ut4_inexistante;ut4_abbey ut4_casa ../x', 'map': 'ut4_nulle'})
    n += 1
    if r['code'] != 0 or r.get('mapcycle.txt') != 'ut4_casa\nut4_abbey\n' or r['cfg'].get('map') != ['ut4_casa'] \
            or 'ut4_inexistante' not in r['texte'] or 'ut4_nulle' not in r['texte']:
        soucis.append('cartes inconnues : rotation %r, carte %r\n%s' % (r.get('mapcycle.txt'), r.get('cfg', {}).get('map'), r['texte']))

    def cycle_perso(tmp):
        with open(os.path.join(tmp, 'q3ut4', 'mapcycle.txt'), 'w') as f:
            f.write('ut4_abbey\n{\n g_gametype 4\n}\n')
    r = preparer({'rotation': ''}, avant=cycle_perso)
    n += 1
    if r['code'] != 0 or r.get('mapcycle.txt') != 'ut4_abbey\n{\n g_gametype 4\n}\n':
        soucis.append('rotation vide : mapcycle.txt du joueur modifié')
    r = preparer({'rotation': ''})
    n += 1
    if r.get('mapcycle.txt') != 'ut4_casa\n':
        soucis.append('rotation vide sans mapcycle.txt : copie de mapcycle_example.txt attendue')
    ok('aller-retour', '%d rendus AMP -> lanceur -> lecture façon moteur' % n)

# ── 8. filtre de console sur de vraies lignes (UrT 4.3.4, 10 oct. 2026) ──────
VRAIES = r'''------- Game Initialization -------
Client 0 connecting with 0 challenge ping
Session data initialised for client on slot 0 at 8686
ClientConnect: 0
ClientUserinfo: 0 \ip\127.0.0.1:27961\challenge\1426825727\qport\35\protocol\68\name\^1Ke^4vin\snaps\20\rate\25000
ClientUserinfoChanged: 0 n\Kevin\t\3\r\2\tl\0\f0\\f1\\f2\\a0\255\a1\255\a2\255
broadcast: print "Kevin^7 connected\n"
ClientUserinfoChanged: 0 n\Kevin\t\3\r\0\tl\0\f0\\f1\\f2\\a0\255\a1\255\a2\255
ClientBegin: 0
Client 1 connecting with 50 challenge ping
ClientConnect: 1
ClientUserinfoChanged: 1 n\Marine\t\3\r\2\tl\0\f0\\f1\\f2\\a0\255\a1\255\a2\255
broadcast: print "Marine^7 connected\n"
ClientUserinfoChanged: 1 n\Marine\t\3\r\0\tl\0\f0\\f1\\f2\\a0\255\a1\255\a2\255
ClientBegin: 1
say: 0 Kevin: Bonjour : premier message
Kevin^3: Bonjour : premier message
broadcast: print "Kevin^7 renamed to KevBis\n"
ClientUserinfoChanged: 0 n\KevBis\t\3\r\0\tl\0\f0\\f1\\f2\\a0\255\a1\255\a2\255
say: 0 KevBis: renomme
sayteam: 1 Marine: on attaque
Server: ut4_casa
------- Game Initialization -------
ClientConnect: 0
ClientUserinfoChanged: 0 n\KevBis\t\3\r\0\tl\0\f0\\f1\\f2\\a0\255\a1\255\a2\255
ClientBegin: 0
ClientConnect: 1
ClientUserinfoChanged: 1 n\Marine\t\3\r\0\tl\0\f0\\f1\\f2\\a0\255\a1\255\a2\255
ClientBegin: 1
broadcast: print "KevBis^7 was kicked\n"
ClientDisconnect: 0
broadcast: print "^1Ke^4vin^7 disconnected\n"
Hitch warning: 906 msec frame time
----- Server Shutdown (Server quit) -----
'''
ATTENDU_FILTRE = [
    'TeamKit : Kevin a rejoint la partie (emplacement 0).',
    'TeamKit : Marine a rejoint la partie (emplacement 1).',
    'TeamKit : Kevin a quitte la partie (emplacement 0).',
    'TeamKit : KevBis a rejoint la partie (emplacement 0).',
    'TeamKit : KevBis a quitte la partie (emplacement 0).',
]
m = re.search(r"^FILTRE='\n(.*?)^'$", lanceur, re.S | re.M)
sortie_filtre = []
if not m:
    soucis.append('programme FILTRE introuvable dans le lanceur')
elif "'" in m.group(1):
    soucis.append('FILTRE contient une apostrophe : elle fermerait la chaîne bash')
else:
    p = subprocess.run([sys.executable, '-I', '-u', '-c', m.group(1)], input=VRAIES.encode('utf-8'),
                       capture_output=True, timeout=30)
    sortie_filtre = p.stdout.decode('utf-8').replace('\r\n', '\n').split('\n')[:-1]   # \r\n sous Windows
    ajoutees = [l for l in sortie_filtre if l.startswith('TeamKit : ')]
    if ajoutees != ATTENDU_FILTRE:
        soucis.append('filtre :\n       obtenu  %s\n       attendu %s\n%s' % (ajoutees, ATTENDU_FILTRE, p.stderr.decode()))
    elif [l for l in sortie_filtre if not l.startswith('TeamKit : ')] != VRAIES.split('\n')[:-1]:
        soucis.append('le filtre doit laisser passer toutes les lignes du jeu, inchangées')
    else:
        ok('filtre de console', '%d lignes réelles, %d lignes ajoutées (arrivée, renommage, exclusion, carte)'
           % (len(VRAIES.split('\n')) - 1, len(ajoutees)))

# ── 9. regex de console ──────────────────────────────────────────────────────
filtre_amp = py(cles['Console.FilterMatchRegex'])
ESSAIS = [
    ('Console.AppReadyRegex', '------- Game Initialization -------', {}),
    ('Console.UserJoinRegex', 'TeamKit : Kevin a rejoint la partie (emplacement 0).', {'username': 'Kevin', 'userid': '0'}),
    ('Console.UserJoinRegex', 'TeamKit : [FR]Jean-Luc (2) a rejoint la partie (emplacement 15).',
     {'username': '[FR]Jean-Luc (2)', 'userid': '15'}),
    ('Console.UserLeaveRegex', 'TeamKit : KevBis a quitte la partie (emplacement 0).', {'username': 'KevBis', 'userid': '0'}),
    ('Console.UserChatRegex', 'say: 0 Kevin: Bonjour : premier message', {'username': 'Kevin', 'message': 'Bonjour : premier message'}),
    ('Console.UserChatRegex', 'say: 12 Marine: salut', {'username': 'Marine', 'message': 'salut'}),
    ('Console.ThrowawayMessageRegex', 'Hitch warning: 906 msec frame time', {}),
]
for cle, ligne, attendu in ESSAIS:
    for version in (ligne, filtre_amp.sub(cles['Console.FilterMatchReplacement'], ligne)):
        mm = py(cles.get(cle) or '^$').search(version)
        if not mm or any(mm.group(k) != v for k, v in attendu.items()):
            soucis.append('%s ne reconnaît pas : %r' % (cle, version))
PIEGES = [
    ('Console.UserJoinRegex', 'broadcast: print "Kevin^7 connected\\n"'),
    ('Console.UserJoinRegex', 'TeamKit : Kevin a quitte la partie (emplacement 0).'),
    ('Console.UserJoinRegex', 'say: 0 Kevin: TeamKit : Bob a rejoint la partie (emplacement 3).'),
    ('Console.UserLeaveRegex', 'TeamKit : Kevin a rejoint la partie (emplacement 0).'),
    ('Console.UserLeaveRegex', 'ClientDisconnect: 0'),
    ('Console.UserChatRegex', 'sayteam: 1 Marine: on attaque'),
    ('Console.UserChatRegex', 'Kevin^3: Bonjour'),
    ('Console.AppReadyRegex', '------------------------------------------------------------'),
    ('Console.AppReadyRegex', 'say: 0 Kevin: ------- Game Initialization -------'),
    ('Console.ThrowawayMessageRegex', 'ClientBegin: 0'),
]
for cle, ligne in PIEGES:
    if py(cles[cle]).search(ligne):
        soucis.append('%s attrape une ligne qui n’est pas pour lui : %r' % (cle, ligne))
if filtre_amp.sub('', 'broadcast: print "^1Ke^4vin^7 disconnected\\n"') != 'broadcast: print "Kevin disconnected\\n"':
    soucis.append('FilterMatchRegex doit retirer les codes couleur ^0 à ^9')
for l in sortie_filtre:
    if l.startswith('TeamKit : ') and not (py(cles['Console.UserJoinRegex']).search(l) or py(cles['Console.UserLeaveRegex']).search(l)):
        soucis.append('ligne du filtre reconnue par aucune regex : %r' % l)
ok('console', '%d lignes réelles (avec et sans FilterMatchRegex), %d pièges' % (len(ESSAIS), len(PIEGES)))

print()
if soucis:
    print('%d problème(s) :' % len(soucis))
    print('\n'.join('  NON  ' + s for s in soucis))
    sys.exit(1)
print('Tout est bon.')
