"""Scheduling and verified publication for Sport-EPG (standard library only)."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('Europe/Zurich')
ANCHOR = dt.date(2026, 10, 30)
ASSETS = ('Sport.xml', 'Sport.xml.gz', 'status.json')

def due_date(now):
    local = now.astimezone(ZONE)
    day = local.date()
    if local.time() < dt.time(6, 17):
        day -= dt.timedelta(days=1)
    return day - dt.timedelta(days=(day - ANCHOR).days % 2)

def complete_release(report, release, now):
    try:
        generated = dt.datetime.fromisoformat(report['generated_at'])
        if generated.tzinfo is None or generated > now + dt.timedelta(minutes=5):
            return False
        if generated.astimezone(ZONE).date() < due_date(now):
            return False
        if report['channels'] <= 0 or report['programmes'] <= 0:
            return False
        assets = {a['name']: a for a in release['assets']}
        if any(n not in assets or assets[n]['size'] <= 0 for n in ASSETS):
            return False
        status_time = dt.datetime.fromisoformat(assets['status.json']['updated_at'].replace('Z', '+00:00'))
        for name, field in [('Sport.xml', 'xml_sha256'), ('Sport.xml.gz', 'gz_sha256')]:
            asset = assets[name]
            changed = dt.datetime.fromisoformat(asset['updated_at'].replace('Z', '+00:00'))
            if changed < generated or changed > status_time:
                return False
            expected = 'sha256:' + report[field]
            if asset.get('digest') != expected:
                return False
        return True
    except (KeyError, TypeError, ValueError):
        return False

def gh(*args, capture=True):
    return subprocess.run(['gh', *args], check=True, stdout=subprocess.PIPE if capture else None, stderr=subprocess.PIPE if capture else None).stdout

def release_info(repo):
    return json.loads(gh('api', f'repos/{repo}/releases/tags/epg-latest'))

def check(repo, event, force=False):
    now = dt.datetime.now(dt.timezone.utc)
    run = True
    reason = 'Aktualisierung erforderlich oder Veroeffentlichung nicht verifizierbar'
    if not force:
        try:
            release = release_info(repo)
            with tempfile.TemporaryDirectory() as tmp:
                gh('release', 'download', 'epg-latest', '-R', repo, '--pattern', 'status.json', '--dir', tmp)
                report = json.loads((Path(tmp) / 'status.json').read_text())
            if complete_release(report, release, now):
                run = False
                reason = 'Vollstaendige Ausgabe fuer den letzten faelligen Termin bereits vorhanden'
        except Exception as exc:
            print(f'Pruefung nicht moeglich ({type(exc).__name__}); versuche Aktualisierung.', flush=True)
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        output.write(f'run={str(run).lower()}\n')
    print(f'{now.astimezone(ZONE).isoformat()} | faellig seit {due_date(now)} | {reason}', flush=True)

def retry(action):
    for attempt in range(3):
        try:
            return action()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))

def verify(repo, directory, names):
    assets = {a['name']: a for a in release_info(repo)['assets']}
    for name in names:
        local = directory / name
        asset = assets.get(name)
        if not asset or asset['size'] != local.stat().st_size:
            raise ValueError(f'Unvollstaendiger Upload: {name}')
        expected = hashlib.sha256(local.read_bytes()).hexdigest()
        digest = asset.get('digest')
        if digest:
            if digest != 'sha256:' + expected:
                raise ValueError(f'Pruefsumme stimmt nicht: {name}')
        else:
            with tempfile.TemporaryDirectory() as tmp:
                gh('release', 'download', 'epg-latest', '-R', repo, '--pattern', name, '--dir', tmp)
                if hashlib.sha256((Path(tmp) / name).read_bytes()).hexdigest() != expected:
                    raise ValueError(f'Download-Pruefsumme stimmt nicht: {name}')

def upload(repo, directory, name):
    retry(lambda: gh('release', 'upload', 'epg-latest', str(directory / name), '-R', repo, '--clobber'))

def publish(repo, directory):
    directory = Path(directory)
    for name in ASSETS:
        if not (directory / name).is_file():
            raise ValueError(f'Fehlende Ausgabedatei: {name}')
    with tempfile.TemporaryDirectory() as tmp:
        backup = Path(tmp)
        # An API/auth failure must never be mistaken for an absent release.
        existing = release_info(repo)
        for name in ASSETS:
            if not any(a['name'] == name for a in existing['assets']):
                raise ValueError(f'Vorherige Ausgabe unvollstaendig: {name}; keine Dateien ersetzen')
            retry(lambda n=name: gh('release', 'download', 'epg-latest', '-R', repo, '--pattern', n, '--dir', str(backup), '--clobber'))
        try:
            for name in ASSETS[:2]:
                upload(repo, directory, name)
            retry(lambda: verify(repo, directory, ASSETS[:2]))
            # Publish the success marker only after both XML files are verified.
            upload(repo, directory, 'status.json')
            retry(lambda: verify(repo, directory, ASSETS))
        except Exception:
            print('Veroeffentlichung fehlgeschlagen; letzte Ausgabe wiederherstellen.', flush=True)
            for name in ASSETS:
                upload(repo, backup, name)
            retry(lambda: verify(repo, backup, ASSETS))
            raise
    gh('release', 'edit', 'epg-latest', '-R', repo, '--notes', 'EPG alle zwei Tage. Automatische Nachholpruefungen taeglich um 06:17, 08:17, 10:17, 14:17, 18:17 und 22:17 Uhr Europe/Zurich. Letzte erfolgreiche Erzeugung: ' + json.loads((directory/'status.json').read_text())['generated_at'])
    print('EPG veroeffentlicht und alle drei Dateien per Pruefsumme bestaetigt.', flush=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('check', 'publish'))
    parser.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY'))
    parser.add_argument('--event', default=os.environ.get('GITHUB_EVENT_NAME', 'schedule'))
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--directory', default='dist')
    args = parser.parse_args()
    if not args.repo:
        parser.error('Repository erforderlich')
    if args.action == 'check':
        check(args.repo, args.event, args.force)
    else:
        publish(args.repo, args.directory)

if __name__ == '__main__':
    main()
