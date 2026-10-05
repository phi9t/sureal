import io
import unittest
from contextlib import contextmanager
from pipeline.training_box_sender import send_training_box_sources

class SenderTests(unittest.TestCase):
    def test_lease_held_until_consumed_ack_and_footer_after_release(self):
        events=[]
        source={'scene':'s','bytes':3,'native_rows':0,'sha256':'a'*64,'md5_base64':'x'}
        @contextmanager
        def stage(record):
            events.append('enter')
            yield io.BytesIO(b'abc')
            events.append('release')
        class Ack(io.StringIO):
            def readline(self, *args):
                self.assertion()
                return super().readline(*args)
        ack=Ack('{"scene":"s","sha256":"'+ 'a'*64 +'","native_rows":0,"status":"consumed"}\n')
        ack.assertion=lambda:self.assertEqual(events,['enter'])
        output=io.BytesIO()
        result=send_training_box_sources([source],stage=stage,worker_input=output,worker_ack=ack)
        self.assertEqual(events,['enter','release'])
        self.assertEqual(len(result),1)
        self.assertTrue(output.getvalue().endswith(b'{"kind": "end", "sources": 1}\n'))
    def test_wrong_ack_refuses_completion(self):
        source={'scene':'s','bytes':3,'native_rows':0,'sha256':'a'*64,'md5_base64':'x'}
        @contextmanager
        def stage(record): yield io.BytesIO(b'abc')
        output=io.BytesIO()
        with self.assertRaises(ValueError):
            send_training_box_sources([source],stage=stage,worker_input=output,worker_ack=io.StringIO('{}\n'))
        self.assertNotIn(b'"kind": "end"',output.getvalue())

    def test_real_worker_pipes_consume_before_staging_release(self):
        import json
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        from test_training_box_wire import NativeBoxWireTests
        inventory,payloads=NativeBoxWireTests().fixture()
        with tempfile.TemporaryDirectory() as tmp:
            manifest=Path(tmp)/'inventory.json';manifest.write_text(json.dumps(inventory))
            code="""import json,sys
from pipeline.training_box_wire import stream_training_box_sources
inventory=json.load(open(sys.argv[1]))
def ack(event):
 print(json.dumps(event),flush=True)
for source in stream_training_box_sources(sys.stdin.buffer,inventory=inventory,acknowledge=ack):
 list(source['rows'])
"""
            worker=subprocess.Popen([sys.executable,'-c',code,str(manifest)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=False)
            import io
            acknowledgements=io.TextIOWrapper(worker.stdout,encoding='utf-8')
            active=[];released=[]
            @contextmanager
            def stage(source):
                self.assertEqual(active,[])
                active.append(source['scene'])
                try:yield io.BytesIO(payloads[[s['scene'] for s in inventory].index(source['scene'])])
                finally:
                    released.append(active.pop())
            try:
                result=send_training_box_sources(inventory,stage=stage,worker_input=worker.stdin,worker_ack=acknowledgements,ack_timeout_seconds=10,write_timeout_seconds=10)
                worker.stdin.close()
                self.assertEqual(worker.wait(timeout=10),0,worker.stderr.read().decode())
                self.assertEqual(released,['a','b'])
                self.assertEqual([r['scene'] for r in result],released)
            finally:
                if worker.poll() is None:worker.kill();worker.wait()
                acknowledgements.close();worker.stderr.close()

    def test_stalled_worker_ack_times_out_and_releases_stage(self):
        import os
        import time
        read_fd,write_fd=os.pipe()
        os.write(write_fd,b'{')
        released=[]
        @contextmanager
        def stage(source):
            try:yield io.BytesIO(b'abc')
            finally:released.append(True)
        source={'scene':'s','bytes':3,'native_rows':0,'sha256':'a'*64,'md5_base64':'x'}
        try:
            with os.fdopen(read_fd,'r') as ack:
                start=time.monotonic()
                with self.assertRaises(TimeoutError):
                    send_training_box_sources([source],stage=stage,worker_input=io.BytesIO(),worker_ack=ack,ack_timeout_seconds=.05)
                self.assertLess(time.monotonic()-start,1)
            self.assertEqual(released,[True])
        finally:os.close(write_fd)

    def test_worker_not_reading_payload_times_out_and_releases_stage(self):
        import os
        read_fd,write_fd=os.pipe()
        released=[]
        @contextmanager
        def stage(source):
            try:yield io.BytesIO(b'x'*1048576)
            finally:released.append(True)
        source={'scene':'s','bytes':1048576,'native_rows':0,'sha256':'a'*64,'md5_base64':'x'}
        try:
            with os.fdopen(write_fd,'wb',buffering=0) as output:
                with self.assertRaises(TimeoutError):
                    send_training_box_sources([source],stage=stage,worker_input=output,worker_ack=io.StringIO(),write_timeout_seconds=.05)
                self.assertTrue(os.get_blocking(output.fileno()))
            self.assertEqual(released,[True])
        finally:os.close(read_fd)

    def test_process_runner_rejects_failed_exit_and_unexpected_stdout(self):
        import sys
        import tempfile
        from pathlib import Path
        from pipeline.training_box_process import run_source_worker
        with tempfile.TemporaryDirectory() as tmp:
            for name,script in [('failed',"import sys;sys.stdin.buffer.read();sys.exit(7)"),
                                ('extra',"import sys;sys.stdin.buffer.read();print('unexpected')")]:
                with self.subTest(name=name),self.assertRaises(ValueError):
                    run_source_worker([sys.executable,'-c',script],[],stage=None,
                                      stderr_path=Path(tmp)/(name+'.log'),
                                      ack_timeout_seconds=1,write_timeout_seconds=1,
                                      exit_timeout_seconds=1)
