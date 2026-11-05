import tempfile, unittest
from pathlib import Path
from science_factory.jobs import JobStore,cache_key,sha256_file
from science_factory.quality import QualityReport,ReviewStatus

class JobTests(unittest.TestCase):
 def test_atomic_state_and_monotonic_stages(self):
  with tempfile.TemporaryDirectory() as d:
   s=JobStore(Path(d)); s.create("a","hash",{}); s.complete_stage("validated")
   self.assertEqual(s.load()["stage"],"validated")
   with self.assertRaises(ValueError): s.complete_stage("created")
 def test_rejects_other_input(self):
  with tempfile.TemporaryDirectory() as d:
   s=JobStore(Path(d)); s.create("a","hash",{})
   with self.assertRaises(ValueError): s.create("b","other",{})
 def test_output_cache_verifies_recorded_hash(self):
  with tempfile.TemporaryDirectory() as d:
   s=JobStore(Path(d)); s.create("a","hash",{})
   p=Path(d)/"render.bin"; p.write_bytes(b"render")
   from science_factory.jobs import sha256_file
   digest=sha256_file(p); s.complete_stage("audio",{"render.bin":digest})
   self.assertTrue(s.is_complete("audio"))
   self.assertFalse(s.is_complete("audio",{"render.bin":"wrong"}))
 def test_failure_persisted(self):
  with tempfile.TemporaryDirectory() as d:
   s=JobStore(Path(d)); s.create("a","hash",{})
   self.assertEqual(s.fail("error")["status"],"failed")
 def test_hashes(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"x"; p.write_bytes(b"science"); self.assertEqual(len(sha256_file(p)),64)
  self.assertNotEqual(cache_key("a","b"),cache_key("b","a"))
class QualityTests(unittest.TestCase):
 def test_technical_is_not_approval(self):
  self.assertEqual(QualityReport(technical_passed=True).status,ReviewStatus.CONTENT_REVIEW_REQUIRED)
 def test_all_gates_needed(self):
  self.assertEqual(QualityReport(True,True,True,True).status,ReviewStatus.APPROVED)
 def test_failed_gate_rejects(self):
  self.assertEqual(QualityReport(True,True,False,True).status,ReviewStatus.REJECTED)
if __name__=="__main__": unittest.main()
