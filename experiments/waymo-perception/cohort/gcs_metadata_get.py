"""Read an immutable GCS metadata generation when the HDFS mirror is unavailable."""
import json,subprocess,sys
from pathlib import Path
package=Path(__file__).resolve().parents[1];mode,uri,destination=sys.argv[1:];assert mode=='get';scene=Path(uri).stem;cache=Path.home()/'.cache/waystone/waymo-perception';record=json.loads((cache/'scientific-source-audit'/f'training-lidar_box-{scene}.json').read_text());assert uri==record['hdfs_uri'] and record['official_split']=='training' and record['research_splits']==['train']
command=['bash',str(package/'gcs.sh'),'--','storage','cp',record['source_metadata']['storage_url'],destination];raise SystemExit(subprocess.run(command,timeout=90).returncode)
