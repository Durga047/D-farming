
import os
import tempfile
import unittest

TEST_DIRECTORY = tempfile.TemporaryDirectory(prefix="dfarming-test-")

os.environ["SECRET_KEY"] = "test-only-secret-key"
os.environ["DATABASE_PATH"] = os.path.join(
    TEST_DIRECTORY.name, "test_database.db"
)
os.environ["UPLOAD_FOLDER"] = os.path.join(
    TEST_DIRECTORY.name, "uploads"
)

import app as application_module

application_module.app.config["TESTING"] = True


class DFarmingSmokeTests(unittest.TestCase):

    def setUp(self):
        self.client = application_module.app.test_client()

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["application"], "D-Farming")
        self.assertEqual(data["database"], "connected")

    def test_plants_schema(self):
        conn = application_module.get_db_connection()
        try:
            conn.execute("""
                SELECT id, plant_name, description, image, price
                FROM plants LIMIT 1
            """)
        finally:
            conn.close()

    def test_home_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No plants have been added yet.", response.data)


    def test_home_page_displays_added_plant(self):
        conn = application_module.get_db_connection()
        try:
            conn.execute("""
                INSERT INTO plants
                    (plant_name, description, image, price)
                VALUES (?, ?, ?, ?)
            """, (
                "Test Mango",
                "Test plant description",
                "mango.jpg",
                25.0
            ))
            conn.commit()
        finally:
            conn.close()

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test Mango", response.data)
        self.assertIn(b"Test plant description", response.data)

    def test_registration_page(self):
        response = self.client.get("/register")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
