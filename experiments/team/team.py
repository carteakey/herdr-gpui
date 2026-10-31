#!/usr/bin/env python3
"""Local, durable task board and inbox for a team of Herdr agents."""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

import bulletin

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
  name TEXT PRIMARY KEY, role TEXT NOT NULL, pane TEXT
);
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
  created_by TEXT NOT NULL REFERENCES agents(name),
  assignee TEXT REFERENCES agents(name), status TEXT NOT NULL DEFAULT 'open',
  result TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY, sender TEXT NOT NULL REFERENCES agents(name),
  recipient TEXT NOT NULL REFERENCES agents(name), body TEXT NOT NULL,
  task_id INTEGER REFERENCES tasks(id), read_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS inbox_idx ON messages(recipient, read_at, id);
CREATE TABLE IF NOT EXISTS findings (
  id INTEGER PRIMARY KEY, author TEXT NOT NULL REFERENCES agents(name),
  description TEXT NOT NULL, evidence TEXT NOT NULL, confidence TEXT NOT NULL,
  task_id INTEGER REFERENCES tasks(id), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', default=os.environ.get('HERDR_TEAM_DB', '.herdr-team/team.sqlite3'))
    subs = p.add_subparsers(dest='command', required=True)
    s = subs.add_parser('register', help='Register an agent or update its role and pane')
    s.add_argument('name'); s.add_argument('--role', required=True); s.add_argument('--pane')
    subs.add_parser('agents')
    s = subs.add_parser('send', help='Queue a message for another agent')
    s.add_argument('--from', dest='sender', required=True); s.add_argument('--to', required=True)
    s.add_argument('--task', type=int); s.add_argument('message')
    s = subs.add_parser('inbox', help='Read messages; explicitly acknowledge after processing')
    s.add_argument('agent'); s.add_argument('--all', action='store_true')
    s = subs.add_parser('ack'); s.add_argument('agent'); s.add_argument('message', type=int)
    s = subs.add_parser('create', help='Create a task; optionally assign it')
    s.add_argument('--by', required=True); s.add_argument('--to'); s.add_argument('--description', default='')
    s.add_argument('title')
    s = subs.add_parser('claim'); s.add_argument('agent'); s.add_argument('task', type=int)
    s = subs.add_parser('complete'); s.add_argument('agent'); s.add_argument('task', type=int)
    s.add_argument('--result', required=True)
    subs.add_parser('board')
    s = subs.add_parser('finding', help='Record a finding with its evidence and confidence')
    s.add_argument('--by', required=True); s.add_argument('--evidence', required=True)
    s.add_argument('--confidence', required=True, choices=('low', 'medium', 'high'))
    s.add_argument('--task', type=int); s.add_argument('description')
    subs.add_parser('findings', help='List recorded findings')
    s = subs.add_parser('post', help='Post to the shared bulletin')
    s.add_argument('--by', required=True); s.add_argument('--task', type=int)
    s.add_argument('--reply-to', type=int); s.add_argument('body')
    subs.add_parser('bulletin', help='Read the shared bulletin')
    s = subs.add_parser('mentions', help='Read your bulletin mentions')
    s.add_argument('agent'); s.add_argument('--all', action='store_true')
    s = subs.add_parser('ack-mention', help='Acknowledge a bulletin mention')
    s.add_argument('agent'); s.add_argument('post', type=int)
    return p


def agent_exists(db, name):
    if not db.execute('SELECT 1 FROM agents WHERE name = ?', (name,)).fetchone():
        raise ValueError(f'unknown agent: {name}')


def run(db, args):
    cmd = args.command
    if cmd == 'register':
        if not args.name.strip() or not args.role.strip():
            raise ValueError('name and role must not be empty')
        db.execute('INSERT INTO agents VALUES (?, ?, ?) ON CONFLICT(name) DO UPDATE SET role=excluded.role, pane=excluded.pane',
                   (args.name, args.role, args.pane))
        return {'name': args.name, 'role': args.role, 'pane': args.pane}
    if cmd == 'agents':
        return [dict(row) for row in db.execute('SELECT * FROM agents ORDER BY name')]
    if cmd == 'send':
        agent_exists(db, args.sender); agent_exists(db, args.to)
        if not args.message.strip():
            raise ValueError('message must not be empty')
        cur = db.execute('INSERT INTO messages(sender, recipient, body, task_id) VALUES (?, ?, ?, ?)',
                         (args.sender, args.to, args.message, args.task))
        return {'message_id': cur.lastrowid, 'status': 'queued'}
    if cmd == 'inbox':
        agent_exists(db, args.agent)
        query = 'SELECT * FROM messages WHERE recipient = ?'
        if not args.all:
            query += ' AND read_at IS NULL'
        return [dict(row) for row in db.execute(query + ' ORDER BY id', (args.agent,))]
    if cmd == 'ack':
        cur = db.execute('UPDATE messages SET read_at = COALESCE(read_at, CURRENT_TIMESTAMP) WHERE id = ? AND recipient = ?',
                         (args.message, args.agent))
        if cur.rowcount != 1:
            raise ValueError('message not found for this recipient')
        return {'message_id': args.message, 'status': 'acknowledged'}
    if cmd == 'create':
        agent_exists(db, args.by)
        if args.to:
            agent_exists(db, args.to)
        if not args.title.strip():
            raise ValueError('title must not be empty')
        cur = db.execute('INSERT INTO tasks(title, description, created_by, assignee) VALUES (?, ?, ?, ?)',
                         (args.title, args.description, args.by, args.to))
        return {'task_id': cur.lastrowid, 'status': 'open', 'assignee': args.to}
    if cmd == 'claim':
        agent_exists(db, args.agent)
        cur = db.execute("UPDATE tasks SET assignee=?, status='in_progress' WHERE id=? AND status='open' AND (assignee IS NULL OR assignee=?)",
                         (args.agent, args.task, args.agent))
        if cur.rowcount != 1:
            raise ValueError('task is unavailable or assigned to another agent')
        return {'task_id': args.task, 'status': 'in_progress', 'assignee': args.agent}
    if cmd == 'complete':
        if not args.result.strip():
            raise ValueError('result must not be empty')
        cur = db.execute("UPDATE tasks SET status='done', result=? WHERE id=? AND status='in_progress' AND assignee=?",
                         (args.result, args.task, args.agent))
        if cur.rowcount != 1:
            raise ValueError('task is not in progress for this agent')
        return {'task_id': args.task, 'status': 'done'}
    if cmd == 'post':
        return bulletin.post(db, args.by, args.body, args.task, args.reply_to)
    if cmd == 'bulletin':
        return bulletin.feed(db)
    if cmd == 'mentions':
        return bulletin.inbox(db, args.agent, args.all)
    if cmd == 'ack-mention':
        return bulletin.acknowledge(db, args.agent, args.post)
    if cmd == 'finding':
        agent_exists(db, args.by)
        if not args.description.strip() or not args.evidence.strip():
            raise ValueError('finding description and evidence must not be empty')
        cur = db.execute('INSERT INTO findings(author, description, evidence, confidence, task_id) VALUES (?, ?, ?, ?, ?)',
                         (args.by, args.description, args.evidence, args.confidence, args.task))
        return {'finding_id': cur.lastrowid}
    if cmd == 'findings':
        return [dict(row) for row in db.execute('SELECT * FROM findings ORDER BY id')]
    if cmd == 'board':
        return [dict(row) for row in db.execute('SELECT * FROM tasks ORDER BY id')]
    raise ValueError('unknown command')


def main():
    args = parser().parse_args()
    path = Path(args.db).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path, timeout=10) as db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            db.executescript(SCHEMA + bulletin.SCHEMA)
            result = run(db, args)
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
