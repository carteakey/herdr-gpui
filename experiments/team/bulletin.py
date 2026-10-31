"""Shared posts and durable per-recipient mention notifications."""

import re

MENTION = re.compile(r'(?<![\w@])@([A-Za-z0-9_-]+)')

SCHEMA = """
CREATE TABLE IF NOT EXISTS bulletin_posts (
  id INTEGER PRIMARY KEY, author TEXT NOT NULL REFERENCES agents(name),
  body TEXT NOT NULL, task_id INTEGER REFERENCES tasks(id),
  reply_to INTEGER REFERENCES bulletin_posts(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS bulletin_mentions (
  post_id INTEGER NOT NULL REFERENCES bulletin_posts(id),
  recipient TEXT NOT NULL REFERENCES agents(name), acknowledged_at TEXT,
  PRIMARY KEY (post_id, recipient)
);
CREATE INDEX IF NOT EXISTS bulletin_inbox_idx
  ON bulletin_mentions(recipient, acknowledged_at, post_id);
"""


def post(db, author, body, task_id=None, reply_to=None):
    if not db.execute('SELECT 1 FROM agents WHERE name = ?', (author,)).fetchone():
        raise ValueError(f'unknown agent: {author}')
    if not body.strip() or len(body.encode('utf-8')) > 4096:
        raise ValueError('post must contain 1 to 4096 UTF-8 bytes')
    recipients = set()
    for mention in set(MENTION.findall(body)):
        if mention == 'team':
            recipients.update(row['name'] for row in db.execute('SELECT name FROM agents'))
        elif mention == 'supervisor':
            supervisors = [row['name'] for row in db.execute(
                "SELECT name FROM agents WHERE role = 'supervisor'")]
            if not supervisors:
                raise ValueError('no supervisor registered')
            recipients.update(supervisors)
        else:
            if not db.execute('SELECT 1 FROM agents WHERE name = ?', (mention,)).fetchone():
                raise ValueError(f'unknown mention: {mention}')
            recipients.add(mention)
    recipients.discard(author)
    cur = db.execute('INSERT INTO bulletin_posts(author, body, task_id, reply_to) VALUES (?, ?, ?, ?)',
                     (author, body, task_id, reply_to))
    post_id = cur.lastrowid
    db.executemany('INSERT INTO bulletin_mentions(post_id, recipient) VALUES (?, ?)',
                   ((post_id, recipient) for recipient in sorted(recipients)))
    return {'post_id': post_id, 'notified': sorted(recipients)}


def feed(db):
    return [dict(row) for row in db.execute('SELECT * FROM (SELECT * FROM bulletin_posts ORDER BY id DESC LIMIT 200) ORDER BY id')]


def inbox(db, agent, include_acknowledged=False):
    if not db.execute('SELECT 1 FROM agents WHERE name = ?', (agent,)).fetchone():
        raise ValueError(f'unknown agent: {agent}')
    query = '''SELECT p.*, m.acknowledged_at FROM bulletin_mentions m
               JOIN bulletin_posts p ON p.id = m.post_id WHERE m.recipient = ?'''
    if not include_acknowledged:
        query += ' AND m.acknowledged_at IS NULL'
    return [dict(row) for row in db.execute(query + ' ORDER BY p.id LIMIT 200', (agent,))]


def acknowledge(db, agent, post_id):
    cur = db.execute('''UPDATE bulletin_mentions
                        SET acknowledged_at = COALESCE(acknowledged_at, CURRENT_TIMESTAMP)
                        WHERE post_id = ? AND recipient = ?''', (post_id, agent))
    if cur.rowcount != 1:
        raise ValueError('mention not found for this recipient')
    return {'post_id': post_id, 'status': 'acknowledged'}
