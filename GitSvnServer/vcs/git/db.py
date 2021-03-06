import os
import sqlite3


class GitDb(object):
    def __init__(self, git, location):
        self.git = git
        self.map_file = os.path.join(location, 'svnserver', 'db')

    def connect(self):
        conn = sqlite3.connect(self.map_file)
        conn.row_factory = sqlite3.Row
        return conn

    def execute(self, sql, *args):
        conn = self.connect()
        results = conn.execute(sql, args).fetchall()
        conn.close()
        return results


class GitMap(GitDb):
    def get_latest_rev(self):
        conn = self.connect()
        sql = 'SELECT revision FROM transactions ORDER BY revision DESC'
        row = conn.execute(sql).fetchone()
        conn.close()
        if row is None:
            return 0
        return int(row['revision'])

    def find_commit(self, ref, rev=None, tag_sha1=False):
        if rev is None:
            rev = self.get_latest_rev()
        conn = self.connect()
        sql = 'SELECT revision, action, sha1, origin FROM transactions WHERE ' \
              'ref = ? AND revision <= ? ORDER BY revision DESC'
        row = conn.execute(sql, (ref, rev)).fetchone()
        conn.close()

        if row is None:
            return None

        if row['action'] in ['commit', 'branch', 'merge']:
            return row['sha1']

        if row['action'] in ['tag']:
            if tag_sha1:
                return row['sha1']
            return row['origin']

        return None

    def get_commit_by_rev(self, rev, tag_sha1=False):
        conn = self.connect()
        sql = 'SELECT revision, action, sha1, origin FROM transactions WHERE ' \
              'revision = ?'
        row = conn.execute(sql, (rev,)).fetchone()
        conn.close()

        if row is None:
            return None

        if row['action'] in ['commit', 'branch', 'merge']:
            return row['sha1']

        if row['action'] in ['tag']:
            if tag_sha1:
                return row['sha1']
            return row['origin']

        return None

    def get_commit_by_pattern(self, pattern, rev=None, tag_sha1=False):
        conn = self.connect()
        sql = 'SELECT revision, action, sha1, origin FROM transactions WHERE ' \
              'ref like ? AND revision <= ? ORDER BY revision DESC'
        row = conn.execute(sql, (pattern, rev)).fetchone()
        conn.close()

        if row is None:
            return None

        if row['action'] in ['commit', 'branch', 'merge']:
            return row['sha1']

        if row['action'] in ['tag']:
            if tag_sha1:
                return row['sha1']
            return row['origin']

        return None

    def get_commits(self, ref, frm, to, order='ASC'):
        conn = self.connect()
        sql = 'SELECT revision, action, sha1, origin FROM transactions WHERE ' \
              'ref = ? AND revision >= ? AND revision <= ? ORDER BY revision ' \
              '%s' % order
        rows = conn.execute(sql, (ref, frm, to)).fetchall()
        conn.close()

        return rows

    def get_ref_rev(self, sha1):
        conn = self.connect()
        sql = 'SELECT revision, ref FROM transactions WHERE sha1 = ?'
        row = conn.execute(sql, (sha1,)).fetchone()
        conn.close()

        if row is None:
            return None, None

        return row['ref'], int(row['revision'])
