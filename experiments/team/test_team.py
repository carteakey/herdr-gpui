import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name('team.py')


class TeamTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = str(Path(self.directory.name) / 'team.db')

    def cli(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(SCRIPT), '--db', self.db, *args],
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0 if ok else 1, result.stderr)
        return json.loads(result.stdout if ok else result.stderr)

    def test_delegation_and_direct_messages(self):
        self.cli('register', 'lead', '--role', 'supervisor')
        self.cli('register', 'analyst', '--role', 'worker')
        task = self.cli('create', '--by', 'lead', '--to', 'analyst', 'Inspect parser')['task_id']
        message = self.cli('send', '--from', 'lead', '--to', 'analyst', '--task', str(task), 'Please inspect')['message_id']
        self.assertEqual(self.cli('inbox', 'analyst')[0]['body'], 'Please inspect')
        self.cli('ack', 'lead', str(message), ok=False)
        self.cli('ack', 'analyst', str(message))
        self.assertEqual(self.cli('inbox', 'analyst'), [])
        self.assertEqual(len(self.cli('inbox', 'analyst', '--all')), 1)
        self.cli('claim', 'lead', str(task), ok=False)
        self.cli('claim', 'analyst', str(task))
        self.cli('complete', 'lead', str(task), '--result', 'wrong', ok=False)
        self.cli('complete', 'analyst', str(task), '--result', 'Evidence at 0x1234')
        self.assertEqual(self.cli('board')[0]['result'], 'Evidence at 0x1234')

    def test_findings_persist_with_evidence_and_task(self):
        self.cli('register', 'analyst', '--role', 'worker')
        task = self.cli('create', '--by', 'analyst', 'Inspect parser')['task_id']
        finding = self.cli('finding', '--by', 'analyst', '--task', str(task),
                           '--evidence', 'report.md:42', '--confidence', 'medium',
                           'Parser handles the request')['finding_id']
        recorded = self.cli('findings')
        self.assertEqual(len(recorded), 1)
        self.assertEqual((recorded[0]['id'], recorded[0]['author'], recorded[0]['task_id']),
                         (finding, 'analyst', task))
        self.assertEqual((recorded[0]['evidence'], recorded[0]['confidence']),
                         ('report.md:42', 'medium'))
        self.cli('finding', '--by', 'missing', '--evidence', 'source', '--confidence', 'low',
                 'Unknown author', ok=False)
        self.cli('finding', '--by', 'analyst', '--task', '999', '--evidence', 'source',
                 '--confidence', 'low', 'Unknown task', ok=False)
        self.cli('finding', '--by', 'analyst', '--evidence', ' ', '--confidence', 'low',
                 'Missing evidence', ok=False)
        self.assertEqual(len(self.cli('findings')), 1)

    def test_bulletin_mentions_and_replies_survive_restart(self):
        self.cli('register', 'lead', '--role', 'supervisor')
        self.cli('register', 'analyst', '--role', 'worker')
        self.cli('register', 'protocol', '--role', 'worker')
        post = self.cli('post', '--by', 'analyst', '@protocol @supervisor found a parser')
        self.assertEqual(post['notified'], ['lead', 'protocol'])
        self.assertEqual(self.cli('mentions', 'protocol')[0]['body'],
                         '@protocol @supervisor found a parser')
        self.cli('ack-mention', 'analyst', str(post['post_id']), ok=False)
        self.cli('ack-mention', 'protocol', str(post['post_id']))
        self.assertEqual(self.cli('mentions', 'protocol'), [])
        self.assertEqual(len(self.cli('mentions', 'protocol', '--all')), 1)
        self.assertEqual(len(self.cli('mentions', 'lead')), 1)
        reply = self.cli('post', '--by', 'protocol', '--reply-to', str(post['post_id']),
                         '@team checking length')
        self.assertEqual(reply['notified'], ['analyst', 'lead'])
        feed = self.cli('bulletin')
        self.assertEqual(feed[-1]['reply_to'], post['post_id'])
        self.cli('post', '--by', 'analyst', '@missing unknown', ok=False)
        self.cli('post', '--by', 'analyst', '--reply-to', '999', 'Invalid reply', ok=False)
        self.cli('post', '--by', 'analyst', 'x' * 4097, ok=False)
        self.assertEqual(self.cli('bulletin'), feed)

    def test_claim_is_atomic(self):
        self.cli('register', 'one', '--role', 'worker')
        self.cli('register', 'two', '--role', 'worker')
        task = self.cli('create', '--by', 'one', 'Independent task')['task_id']
        commands = [[sys.executable, str(SCRIPT), '--db', self.db, 'claim', name, str(task)]
                    for name in ('one', 'two')]
        procs = [subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for cmd in commands]
        for proc in procs:
            proc.communicate(timeout=10)
        self.assertEqual(sorted(proc.returncode for proc in procs), [0, 1])

    def test_unknown_recipient_does_not_queue_message(self):
        self.cli('register', 'lead', '--role', 'supervisor')
        self.cli('send', '--from', 'lead', '--to', 'missing', 'hello', ok=False)
        self.assertEqual(self.cli('inbox', 'lead', '--all'), [])


if __name__ == '__main__':
    unittest.main()
