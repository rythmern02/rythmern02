"""Checks the data boundary and the committed live-data snapshot."""
from pathlib import Path
import importlib.util,json,unittest,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('activity',ROOT/'scripts/refresh_activity.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ActivityChecks(unittest.TestCase):
 def test_calendar_counts_not_color_levels(self):
  p=m.Calendar()
  p.feed('<td id="a" data-date="2026-01-01" data-level="4"></td><tool-tip for="a">1,234 contributions on January 1st.</tool-tip><td id="b" data-date="2026-01-02" data-level="0"></td><tool-tip for="b">No contributions on January 2nd.</tool-tip>')
  self.assertEqual(p.counts,{'a':1234,'b':0})
  self.assertEqual(p.cells['a']['level'],4)
 def test_changed_upstream_tooltip_fails(self):
  p=m.Calendar()
  with self.assertRaises(ValueError):
   p.feed('<tool-tip for="a">upstream format changed</tool-tip>')
 def test_snapshot_matches_daily_sum(self):
  d=json.loads((ROOT/'assets/v2/activity.json').read_text())
  self.assertEqual(d['contributions'],sum(x['count'] for x in d['days']))
  self.assertEqual(len({x['date'] for x in d['days']}),len(d['days']))
  self.assertEqual(d['npm']['package'],'gpu402')
  for day in d['days']:self.assertLessEqual(day['date'],d['as_of'])
 def test_both_renderers_preserve_values_and_parse(self):
  d=json.loads((ROOT/'assets/v2/activity.json').read_text())
  for render in [m.render,m.render_mobile]:
   svg=render(d);ET.fromstring(svg)
   for value in [d['contributions'],d['public_repos'],d['own_repo_stars'],d['npm']['downloads']]:
    self.assertIn(f'>{value:,}</text>',svg)

if __name__=='__main__':unittest.main()
