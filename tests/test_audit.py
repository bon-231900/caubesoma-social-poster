import base64
import json
import tempfile
import unittest
from pathlib import Path

from app import database, config
from app.config import UPLOAD_DIR
from app.database import (
    init_db, create_post, get_post_by_id, claim_post_for_publish,
    create_media_item, get_media_items, cleanup_dead_media_records,
    restore_media_file_if_missing
)

class AuditAndOptimizationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db = database.DB_PATH
        database.DB_PATH = Path(self.temp_dir.name) / 'test_audit.db'
        database._PG_FALLBACK_TO_SQLITE = True
        init_db()

    def tearDown(self):
        database.DB_PATH = self.original_db
        self.temp_dir.cleanup()

    def test_get_media_items_excludes_file_data(self):
        fake_b64 = base64.b64encode(b'FAKE_IMAGE_DATA_VERY_LONG').decode('utf-8')
        create_media_item(
            filename='test_opt_img.jpg',
            original_name='Original Name',
            file_hash='hash123',
            file_data=fake_b64
        )
        items = get_media_items()
        self.assertTrue(len(items) >= 1)
        found = next((x for x in items if x['filename'] == 'test_opt_img.jpg'), None)
        self.assertIsNotNone(found)
        self.assertNotIn('file_data', found)
        self.assertEqual(found['original_name'], 'Original Name')

    def test_cleanup_dead_media_records(self):
        create_media_item(
            filename='ghost_dead_img.jpg',
            original_name='Ghost Image',
            file_hash='ghosthash',
            file_data=''
        )
        fake_b64 = base64.b64encode(b'REAL_IMAGE_BYTES').decode('utf-8')
        create_media_item(
            filename='healthy_img.jpg',
            original_name='Healthy Image',
            file_hash='healthyhash',
            file_data=fake_b64
        )
        deleted = cleanup_dead_media_records()
        self.assertEqual(deleted, 1)

        items = get_media_items()
        filenames = [x['filename'] for x in items]
        self.assertNotIn('ghost_dead_img.jpg', filenames)
        self.assertIn('healthy_img.jpg', filenames)

    def test_restore_media_file_if_missing(self):
        test_filename = 'to_be_restored.jpg'
        test_bytes = b'IMAGE_CONTENT_RESTORE_TEST_XYZ'
        b64 = base64.b64encode(test_bytes).decode('utf-8')
        create_media_item(
            filename=test_filename,
            original_name='Restore Test',
            file_hash='restorehash',
            file_data=b64
        )

        disk_path = UPLOAD_DIR / test_filename
        if disk_path.exists():
            disk_path.unlink()

        self.assertFalse(disk_path.exists())
        success = restore_media_file_if_missing(test_filename)
        self.assertTrue(success)
        self.assertTrue(disk_path.exists())
        self.assertEqual(disk_path.read_bytes(), test_bytes)

        if disk_path.exists():
            disk_path.unlink()

    def test_claim_post_allows_retrying_failed_and_partial_failed(self):
        pid_failed = create_post(status='failed')
        self.assertTrue(claim_post_for_publish(pid_failed))
        
        pid_partial = create_post(status='partial_failed')
        self.assertTrue(claim_post_for_publish(pid_partial))

    def test_threads_topics_search_and_seed(self):
        from app.database import get_threads_topics
        all_topics = get_threads_topics()
        self.assertGreaterEqual(len(all_topics), 50)
        
        # Test exact & unaccented search for ATVNCG 2026
        atv_results = get_threads_topics("atvncg 2026")
        self.assertTrue(any(t['name'] == 'ATVNCG 2026' for t in atv_results))
        
        # Test unaccented search for "anh trai"
        anh_trai_results = get_threads_topics("anh trai")
        self.assertTrue(any("Anh Trai" in t['name'] for t in anh_trai_results))
        
        # Test ROOTS core topic
        organic_results = get_threads_topics("thuc pham huu co")
        self.assertTrue(any(t['name'] == 'Thực Phẩm Hữu Cơ' for t in organic_results))

if __name__ == '__main__':
    unittest.main()
