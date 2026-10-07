import copy,tempfile,unittest
from pathlib import Path


class ResourceCommandTests(unittest.TestCase):
    def api(self):
        try:
            from resources.command import wrap_command
        except ImportError:
            self.fail('actual stage command must bind its resource wrapper')
        return wrap_command

    def test_actual_command_changes_in_place_with_literal_worker_arguments(self):
        wrap=self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);code=root/'code';(code/'resources').mkdir(parents=True);(code/'evidence').mkdir();output=root/'resources';output.mkdir()
            (code/'resources/execute_worker.py').write_text('wrapper');(code/'evidence/source_snapshot.py').write_text('helper')
            command=['bwrap','--unshare-all','--die-with-parent','--ro-bind','/native-code','/experiment','--bind','/native-output','/outputs','--','python','/experiment/cohort/worker.py','literal$(touch bad)']
            original=copy.deepcopy(command);argv=wrap(command,code,output)
            self.assertEqual(argv,['/experiment/cohort/worker.py','literal$(touch bad)'])
            self.assertEqual(command[-5:],['python','/tmp/resource-layer/resources/execute_worker.py','/tmp/resource-output','/experiment/cohort/worker.py','literal$(touch bad)'])
            self.assertEqual(command[:command.index('--')],original[:original.index('--')]+['--ro-bind',str(code),'/tmp/resource-layer','--ro-bind',str(code/'resources'),'/experiment/resources','--ro-bind',str(code/'evidence'),'/experiment/evidence','--bind',str(output),'/tmp/resource-output'])
            self.assertFalse((root/'bad').exists())

    def test_missing_namespace_wrong_interpreter_or_conflicting_resource_mount_refused(self):
        wrap=self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);code=root/'code';(code/'resources').mkdir(parents=True);(code/'evidence').mkdir();out=root/'out';out.mkdir()
            (code/'resources/execute_worker.py').write_text('wrapper');(code/'evidence/source_snapshot.py').write_text('helper')
            base=['bwrap','--unshare-all','--die-with-parent','--','python','/experiment/worker.py']
            for fault in ['namespace','interpreter','collision','double-separator','not-script']:
                command=copy.deepcopy(base)
                if fault=='namespace':command.remove('--unshare-all')
                elif fault=='interpreter':command[command.index('python')]='bash'
                elif fault=='collision':command[command.index('--'):command.index('--')]=['--bind','/other','/experiment/evidence']
                elif fault=='double-separator':command.append('--')
                else:command[-1]='relative.py'
                before=command.copy()
                with self.subTest(fault=fault),self.assertRaises(ValueError):wrap(command,code,out)
                self.assertEqual(command,before)

if __name__=='__main__':unittest.main()
