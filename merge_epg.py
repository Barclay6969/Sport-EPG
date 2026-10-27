"""Merge public XMLTV feeds. No IPTV streams or credentials are used."""
import argparse
import concurrent.futures
import datetime as dt
import gzip
import hashlib
import json
import lzma
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET

UTC = dt.timezone.utc

def timestamp(value):
    value = value.strip()
    if len(value) == 14:
        value += ' +0000'
    return dt.datetime.strptime(value, '%Y%m%d%H%M%S %z').astimezone(UTC)

def unpack(data, name):
    if data.startswith(b'\xfd7zXZ\x00'):
        return lzma.decompress(data)
    if data.startswith(b'\x1f\x8b'):
        return gzip.decompress(data)
    return data

def download(source, directory, cache=None):
    name = source['name']
    if Path(name).name != name:
        raise ValueError('Invalid source name')
    if cache:
        data = (cache / name).read_bytes()
    else:
        for attempt in range(3):
            try:
                request = urllib.request.Request(source['url'], headers={'User-Agent': 'Sport-EPG/1.0'})
                with urllib.request.urlopen(request, timeout=90) as response:
                    data = response.read()
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
    raw = unpack(data, name)
    path = directory / (name + '.xml')
    path.write_bytes(raw)
    return source, path, hashlib.sha256(data).hexdigest()

def channel_ids(value, source_name):
    # Keep original IDs. Legacy Sport.xml used dotted Spanish IDs as well.
    values = [value]
    if source_name.startswith('spain'):
        alias = '.'.join(value.split())
        if alias not in values:
            values.append(alias)
    return values

def merge(sources, directory, output, now, cache=None):
    database = sqlite3.connect(directory / 'epg.sqlite')
    database.execute('CREATE TABLE channels (id TEXT PRIMARY KEY, xml BLOB)')
    database.execute('CREATE TABLE programmes (channel TEXT, start TEXT, stop TEXT, xml BLOB, PRIMARY KEY(channel,start))')
    report = {'generated_at': now.isoformat(), 'sources': [], 'conflicts': 0}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        # Consume in configured priority order, regardless of download order.
        jobs = [pool.submit(download, source, directory, cache) for source in sources]
        for job in jobs:
            source, path, digest = job.result()
            stats = {'name': source['name'], 'sha256': digest, 'channels': 0, 'programmes': 0, 'future_programmes': 0, 'invalid_programmes': 0}
            if source['name'].startswith('spain'):
                fresh = False
                for _, entry in ET.iterparse(path):
                    if entry.tag == 'programme':
                        try:
                            fresh = fresh or timestamp(entry.get('stop', '')) > now
                        except ValueError:
                            pass
                    entry.clear()
                if not fresh:
                    stats['outdated'] = True
                    stats['skipped'] = True
                    report['sources'].append(stats)
                    print(f"{source['name']}: skipped (outdated)", flush=True)
                    continue
            root = None
            declared = set()
            referenced = set()
            for event, element in ET.iterparse(path, events=('start', 'end')):
                if root is None:
                    root = element
                    if root.tag != 'tv':
                        raise ValueError(f"{source['name']}: not XMLTV")
                if event != 'end':
                    continue
                if element.tag == 'channel':
                    original = element.get('id', '')
                    if not original:
                        raise ValueError('Missing channel id')
                    declared.add(original)
                    stats['channels'] += 1
                    for cid in channel_ids(original, source['name']):
                        element.set('id', cid)
                        if not element.findall('display-name'):
                            ET.SubElement(element, 'display-name').text = original
                        database.execute('INSERT OR IGNORE INTO channels VALUES (?,?)', (cid, ET.tostring(element, encoding='utf-8')))
                    root.remove(element)
                elif element.tag == 'programme':
                    original = element.get('channel', '')
                    try:
                        start = timestamp(element.get('start', ''))
                        stop = timestamp(element.get('stop', ''))
                        if not original or stop <= start:
                            raise ValueError('invalid programme')
                    except ValueError:
                        stats['invalid_programmes'] += 1
                        root.remove(element)
                        continue
                    referenced.add(original)
                    stats['programmes'] += 1
                    stats['future_programmes'] += int(stop > now)
                    for cid in channel_ids(original, source['name']):
                        element.set('channel', cid)
                        element.set('start', start.strftime('%Y%m%d%H%M%S +0000'))
                        element.set('stop', stop.strftime('%Y%m%d%H%M%S +0000'))
                        xml = ET.tostring(element, encoding='utf-8')
                        cursor = database.execute('INSERT OR IGNORE INTO programmes VALUES (?,?,?,?)', (cid, element.get('start'), element.get('stop'), xml))
                        if cursor.rowcount == 0:
                            prior = database.execute('SELECT xml FROM programmes WHERE channel=? AND start=?', (cid, element.get('start'))).fetchone()[0]
                            report['conflicts'] += int(prior != xml)
                    root.remove(element)
            if stats['invalid_programmes'] > max(5, stats['programmes'] * 0.05):
                raise ValueError(f"{source['name']}: too many invalid programmes")
            if not stats['channels'] or not stats['programmes'] or (not stats['future_programmes'] and not source['name'].startswith('spain')):
                raise ValueError(f"{source['name']}: empty or outdated feed; publication aborted")
            # Some feeds omit channel declarations. Supply explicit matching IDs.
            for missing in referenced - declared:
                for cid in channel_ids(missing, source['name']):
                    element = ET.Element('channel', id=cid)
                    ET.SubElement(element, 'display-name').text = missing
                    database.execute('INSERT OR IGNORE INTO channels VALUES (?,?)', (cid, ET.tostring(element, encoding='utf-8')))
            database.commit()
            stats['outdated'] = not bool(stats['future_programmes'])
            report['sources'].append(stats)
            print(f"{source['name']}: {stats['channels']} channels, {stats['programmes']} programmes", flush=True)
    spanish = [s for s in report['sources'] if s['name'].startswith('spain')]
    if spanish and not any(s['future_programmes'] for s in spanish):
        raise ValueError('All Spanish feeds are outdated; publication aborted')
    output.mkdir(parents=True, exist_ok=True)
    pending = output / 'Sport.xml.pending'
    with pending.open('wb') as stream:
        stream.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<tv generator-info-name="Sport-EPG">\n')
        for table, order in [('channels', 'id'), ('programmes', 'channel,start')]:
            for (xml,) in database.execute(f'SELECT xml FROM {table} ORDER BY {order}'):
                stream.write(xml.strip() + b'\n')
        stream.write(b'</tv>\n')
    report['channels'] = database.execute('SELECT COUNT(*) FROM channels').fetchone()[0]
    report['programmes'] = database.execute('SELECT COUNT(*) FROM programmes').fetchone()[0]
    database.close()
    # Parse the finished document before publishing any output.
    for _, element in ET.iterparse(pending):
        element.clear()
    compressed = output / 'Sport.xml.gz.pending'
    with pending.open('rb') as src, compressed.open('wb') as dst:
        with gzip.GzipFile(filename='', fileobj=dst, mode='wb', mtime=0) as gz:
            while chunk := src.read(1024 * 1024):
                gz.write(chunk)
    report['xml_sha256'] = hashlib.sha256(pending.read_bytes()).hexdigest()
    os.replace(pending, output / 'Sport.xml')
    os.replace(compressed, output / 'Sport.xml.gz')
    (output / 'status.json').write_text(json.dumps(report, indent=2) + '\n')
    return report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sources', type=Path, default=Path('sources.json'))
    parser.add_argument('--output', type=Path, default=Path('dist'))
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--now', help='ISO timestamp; for reproducible local verification')
    args = parser.parse_args()
    now = dt.datetime.fromisoformat(args.now) if args.now else dt.datetime.now(UTC)
    with tempfile.TemporaryDirectory() as work:
        report = merge(json.loads(args.sources.read_text()), Path(work), args.output, now, args.cache)
    print(json.dumps({k: v for k, v in report.items() if k != 'sources'}, indent=2))

if __name__ == '__main__':
    main()
