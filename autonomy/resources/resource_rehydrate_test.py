import tempfile,unittest
from pathlib import Path
from resources.resource_archive import create_archive,sha
from resources.resource_rehydrate import rehydrate_archive
class RehydrateTests(unittest.TestCase):
 def test_exact_regular_members_and_existing_destination_rejection(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);source=root/'source';source.mkdir();(source/'nested').mkdir();(source/'nested/checkpoint.pt').write_bytes(b'exact model and adam');archive=root/'archive.tar.gz';manifest=create_archive(source,['nested/checkpoint.pt'],archive);destination=root/'restored'
   result=rehydrate_archive(archive,manifest,destination,max_bytes=100)
   self.assertEqual(sha(destination/'nested/checkpoint.pt'),manifest['members'][0]['sha256']);self.assertEqual(result['payload_bytes'],len(b'exact model and adam'))
   with self.assertRaises(FileExistsError):rehydrate_archive(archive,manifest,destination,max_bytes=100)
 def test_corruption_and_capacity_rejected_before_destination_creation(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);source=root/'source';source.mkdir();(source/'checkpoint.pt').write_bytes(b'original');archive=root/'archive.tar.gz';manifest=create_archive(source,['checkpoint.pt'],archive);destination=root/'restored'
   with self.assertRaises(ValueError):rehydrate_archive(archive,manifest,destination,max_bytes=4)
   self.assertFalse(destination.exists());archive.write_bytes(b'bad')
   with self.assertRaises(ValueError):rehydrate_archive(archive,manifest,destination,max_bytes=100)
   self.assertFalse(destination.exists())
if __name__=='__main__':unittest.main()
