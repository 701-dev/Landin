#!/usr/bin/env python3
"""Give each Debian package in tools.lock.json its snapshot.debian.org URL.

deb.debian.org's pool keeps only the versions a suite still names, so a
locked package disappears from it once Debian supersedes it, edge by edge
of its mirror network.  snapshot.debian.org keeps every file the archive
ever held, addressed by its SHA-1 at /file/SHA1, and setup.py fetches a
package from there when the pool no longer serves it (D2489).

Run after changing the lock: it looks up each `deb` entry that has no
`snapshot` URL by its package, version and file name, downloads the file
from that URL, refuses it unless its SHA-256 is the locked one, and writes
the URL into the lock.  --check only verifies that every entry has one,
without the network.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
LOCK = HERE / 'tools.lock.json'
SNAPSHOT = 'https://snapshot.debian.org'
#  The form every `snapshot` URL takes, which test.py holds the lock to.
FILE_URL = re.compile(r'^https://snapshot\.debian\.org/file/[0-9a-f]{40}$')


def get(url, timeout=300):
    request = urllib.request.Request(url, headers={'User-Agent': 'landin-lock-snapshot'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def snapshot_url(item):
    """ITEM's file at snapshot.debian.org, found by name and verified by SHA-256."""
    #  The pool's file name, which drops the version's epoch; the lock's
    #  `file` is only where setup.py stores it.
    name = urllib.parse.unquote(item['url'].rsplit('/', 1)[1])
    package, version, _ = name[:-len('.deb')].split('_')
    quoted = urllib.parse.quote(package, safe='')
    versions = json.loads(get('%s/mr/binary/%s/' % (SNAPSHOT, quoted)))['result']
    full = [entry['binary_version'] for entry in versions
            if entry['binary_version'].split(':', 1)[-1] == version]
    if len(full) != 1:
        raise RuntimeError('%s: snapshot.debian.org has %d versions of %s matching %s'
                           % (item['file'], len(full), package, version))
    info = json.loads(get('%s/mr/binary/%s/%s/binfiles?fileinfo=1'
                          % (SNAPSHOT, quoted, urllib.parse.quote(full[0], safe=''))))
    hashes = [digest for digest, places in info['fileinfo'].items()
              if any(place['name'] == name for place in places)]
    if len(hashes) != 1:
        raise RuntimeError('%s: snapshot.debian.org names %d files called %s'
                           % (item['file'], len(hashes), name))
    url = '%s/file/%s' % (SNAPSHOT, hashes[0])
    data = get(url)
    if hashlib.sha1(data).hexdigest() != hashes[0]:
        raise RuntimeError('%s: %s did not return the file of its SHA-1' % (item['file'], url))
    found = hashlib.sha256(data).hexdigest()
    if found != item['sha256']:
        raise RuntimeError('%s: %s has SHA-256 %s, not the locked %s'
                           % (item['file'], url, found, item['sha256']))
    return url


def missing(lock):
    return [item['file'] for item in lock
            if item['kind'] == 'deb' and not FILE_URL.match(item.get('snapshot', ''))]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true',
                        help='only refuse a deb entry without a snapshot URL; no network')
    args = parser.parse_args()
    lock = json.loads(LOCK.read_text())
    if args.check:
        absent = missing(lock)
        if absent:
            sys.exit('lock_snapshot.py: no snapshot URL for %s; run'
                     ' environments/cortex-m/lock_snapshot.py' % ', '.join(absent))
        return
    for item in lock:
        if item['kind'] == 'deb' and 'snapshot' not in item:
            item['snapshot'] = snapshot_url(item)
            print(item['file'], item['snapshot'], flush=True)
            #  Written after each, so an interrupted run keeps what it verified.
            LOCK.write_text(json.dumps(lock, indent=2) + '\n')


if __name__ == '__main__':
    main()
