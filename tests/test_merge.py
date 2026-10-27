import datetime as dt
import gzip
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from merge_epg import merge, timestamp, UTC

class MergeTests(unittest.TestCase):
    def test_timezone(self):
        self.assertEqual(timestamp('20261027120000 +0100'), timestamp('20261027110000 +0000'))

    def test_merge_priority_alias_and_gzip(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); cache = root/'cache'; cache.mkdir(); work = root/'work'; work.mkdir()
            feed = '<tv><channel id="Sport ES.es"><display-name>Sport</display-name></channel><programme channel="Sport ES.es" start="20261027120000 +0100" stop="20261027140000 +0100"><title>{}</title></programme></tv>'
            sources = []
            for i,title in enumerate(['first','second']):
                name = f'spain{i}.xml'; (cache/name).write_text(feed.format(title)); sources.append({'name':name,'url':'unused'})
            report = merge(sources, work, root/'out', dt.datetime(2026,10,27,tzinfo=UTC), cache)
            xml=(root/'out/Sport.xml').read_bytes(); tree=ET.fromstring(xml)
            self.assertEqual(report['programmes'],2)
            self.assertEqual({x.get('id') for x in tree.findall('channel')},{'Sport ES.es','Sport.ES.es'})
            self.assertEqual({x.findtext('title') for x in tree.findall('programme')},{'first'})
            self.assertEqual(gzip.decompress((root/'out/Sport.xml.gz').read_bytes()),xml)

    def test_outdated_feed_keeps_previous_output(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); cache=root/'cache'; cache.mkdir(); work=root/'work'; work.mkdir(); out=root/'out'; out.mkdir()
            (out/'Sport.xml').write_text('previous')
            (cache/'old.xml').write_text('<tv><channel id="a"/><programme channel="a" start="20200101000000 +0000" stop="20200101010000 +0000"/></tv>')
            with self.assertRaises(ValueError):merge([{'name':'old.xml','url':'unused'}],work,out,dt.datetime.now(UTC),cache)
            self.assertEqual((out/'Sport.xml').read_text(),'previous')

    def test_all_spanish_sources_outdated_aborts(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); cache=root/'cache'; cache.mkdir(); work=root/'work'; work.mkdir()
            (cache/'spain1.xml').write_text('<tv><channel id="a"/><programme channel="a" start="20200101000000 +0000" stop="20200101010000 +0000"/></tv>')
            with self.assertRaisesRegex(ValueError, 'All Spanish'):
                merge([{'name':'spain1.xml','url':'unused'}],work,root/'out',dt.datetime.now(UTC),cache)
            self.assertFalse((root/'out/Sport.xml').exists())

if __name__=='__main__':unittest.main()

