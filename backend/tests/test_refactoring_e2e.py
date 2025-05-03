"""
End-to-end tests for validating the backend refactoring.
These tests use the actual development database and real API endpoints.
"""
import unittest
import json
import time
import random
from sqlalchemy.orm import Session
from backend import models
from backend.app import app
from backend.tasks import run_generation, regenerate_line_takes, run_speech_to_speech_line
import base64
import os

class RefactoringEndToEndTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures before running tests."""
        # Configure the Flask app for testing
        app.config['TESTING'] = True
        cls.client = app.test_client()
        
        # Use existing template ID instead of creating a new one
        cls.setup_test_data()

    @classmethod
    def tearDownClass(cls):
        """Tear down test fixtures after running tests."""
        # We can leave the test data in the development DB
        # or optionally clean it up here
        pass

    @classmethod
    def setup_test_data(cls):
        """Set up test data in the database."""
        db = next(models.get_db())
        try:
            # Use an existing template (SMITE 2 Skin - Test)
            template = db.query(models.VoScriptTemplate).filter_by(id=5).first()
            if template:
                # Save template ID for later use
                cls.template_id = template.id
                print(f"Using existing template ID: {cls.template_id} ({template.name})")
                
                # Print info about template categories and lines
                categories = db.query(models.VoScriptTemplateCategory).filter_by(template_id=template.id).all()
                print(f"Template has {len(categories)} categories")
                
                lines = db.query(models.VoScriptTemplateLine).filter_by(template_id=template.id).all()
                print(f"Template has {len(lines)} lines")
            else:
                raise Exception("Template ID 5 not found in database")
            
        except Exception as e:
            print(f"Error setting up test data: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    def test_01_create_vo_script(self):
        """Test creating a new VO script from a template."""
        # Generate a unique script name
        script_name = f"Test Script {random.randint(1000, 9999)}"
        
        # Create a new VO script
        response = self.client.post('/api/vo-scripts', json={
            'name': script_name,
            'template_id': self.template_id,
            'character_description': 'Test character for end-to-end testing'
        })
        
        # Check response
        self.assertEqual(response.status_code, 201, f"Failed to create script: {response.data}")
        data = json.loads(response.data)
        self.assertIn('data', data)
        self.assertIn('id', data['data'])
        
        # Save script ID for subsequent tests
        self.__class__.script_id = data['data']['id']
        print(f"Created test script with ID: {self.__class__.script_id}")
        
        # Verify script exists in database
        db = next(models.get_db())
        try:
            script = db.query(models.VoScript).get(self.__class__.script_id)
            self.assertIsNotNone(script)
            self.assertEqual(script.name, script_name)
            
            # Also verify lines were created
            lines = db.query(models.VoScriptLine).filter_by(vo_script_id=self.__class__.script_id).all()
            self.assertGreater(len(lines), 0)
            print(f"Script has {len(lines)} lines")
            
            # Lines with static_text should have that copied to generated_text
            static_text_lines = 0
            for line in lines:
                if line.template_line and line.template_line.static_text:
                    self.assertEqual(line.generated_text, line.template_line.static_text)
                    static_text_lines += 1
            print(f"Script has {static_text_lines} lines with static text")
        finally:
            db.close()

    def test_02_run_script_agent(self):
        """Test running the script agent on the VO script."""
        # Skip if script_id wasn't set in previous test
        if not hasattr(self.__class__, 'script_id'):
            self.skipTest("Script ID not available")
            
        # Run the script agent
        response = self.client.post(f'/api/vo-scripts/{self.__class__.script_id}/run-agent', json={
            'task_type': 'generate_draft'
        })
        
        # Check response
        self.assertEqual(response.status_code, 202, f"Failed to start script agent: {response.data}")
        data = json.loads(response.data)
        self.assertIn('data', data)
        self.assertIn('job_id', data['data'])
        
        # For templates with categories, we get results with per-category tasks instead of a single task_id
        if 'results' in data['data']:
            self.assertIn('categories', data['data']['results'])
            self.assertGreater(len(data['data']['results']['categories']), 0)
            print(f"Script agent started with {len(data['data']['results']['categories'])} category tasks")
            
            # Save one of the category job IDs for checking later
            job_id = data['data']['results']['categories'][0]['job_id']
        else:
            # For older templates, we might get a single task_id
            self.assertIn('task_id', data['data'])
            job_id = data['data']['job_id']
            print(f"Script agent started with single task")
        
        # Wait briefly and check job status
        time.sleep(2)
        db = next(models.get_db())
        try:
            job = db.query(models.GenerationJob).get(job_id)
            self.assertIsNotNone(job)
            print(f"Script agent job status: {job.status}")
        finally:
            db.close()

    def test_03_generate_voice_takes(self):
        """Test generating voice takes for the script."""
        # Skip if script_id wasn't set in previous test
        if not hasattr(self.__class__, 'script_id'):
            self.skipTest("Script ID not available")
            
        # Use ElevenLabs test voice IDs
        test_voice_ids = ["21m00Tcm4TlvDq8ikWAM"] # Rachel voice
        
        # Start generation
        response = self.client.post('/api/generate', json={
            'vo_script_id': self.__class__.script_id,
            'skin_name': 'test_skin',
            'voice_ids': test_voice_ids,
            'variants_per_line': 1,
            'model_id': 'eleven_monolingual_v1',
            'stability_range': [0.5, 0.6],
            'similarity_boost_range': [0.75, 0.8],
            'style_range': [0.0, 0.1],
            'speed_range': [1.0, 1.0],
            'use_speaker_boost': True
        })
        
        # Check response
        self.assertEqual(response.status_code, 202, f"Failed to start generation: {response.data}")
        data = json.loads(response.data)
        self.assertIn('data', data)
        self.assertIn('job_id', data['data'])
        
        # Save job ID and batch ID for regeneration tests
        job_id = data['data']['job_id']
        self.__class__.generation_job_id = job_id
        
        # Wait for job to complete (or at least start processing)
        time.sleep(5)
        
        # Check job status and get batch ID
        db = next(models.get_db())
        try:
            job = db.query(models.GenerationJob).get(job_id)
            self.assertIsNotNone(job)
            print(f"Generation job status: {job.status}")
            
            # If job completed or has batch IDs, save them
            if job.result_batch_ids_json:
                batch_ids = json.loads(job.result_batch_ids_json)
                if batch_ids and len(batch_ids) > 0:
                    self.__class__.batch_id = batch_ids[0]
                    print(f"Saved batch ID: {self.__class__.batch_id}")
                    
            # Save a line key for regeneration tests
            lines = db.query(models.VoScriptLine).filter_by(vo_script_id=self.__class__.script_id).all()
            if lines:
                self.__class__.test_line_key = lines[0].line_key
                self.__class__.test_line_text = lines[0].generated_text
                print(f"Using line key for tests: {self.__class__.test_line_key}")
                
        finally:
            db.close()

    def test_04_direct_task_call_regenerate(self):
        """Test directly calling the regenerate_line_takes task."""
        # Skip this test as it's trying to call a Celery task directly
        # which doesn't work because it requires Celery context (task_id)
        self.skipTest("Skipping direct task call - requires Celery context")
        
        # Skip if we don't have the necessary data from previous tests
        if not all(hasattr(self.__class__, attr) for attr in ['batch_id', 'test_line_key', 'test_line_text']):
            self.skipTest("Required data from previous tests not available")
        
        # Create a job record for the task
        db = next(models.get_db())
        try:
            job = models.GenerationJob(
                status="PENDING",
                job_type="line_regen",
                target_batch_id=self.__class__.batch_id,
                target_line_key=self.__class__.test_line_key,
                parameters_json=json.dumps({
                    'line_text': self.__class__.test_line_text,
                    'num_new_takes': 1,
                    'replace_existing': False
                })
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            regen_job_id = job.id
        finally:
            db.close()
        
        # Call the regenerate_line_takes task directly
        settings = {
            'stability_range': [0.5, 0.6],
            'similarity_boost_range': [0.75, 0.8],
            'style_range': [0.0, 0.1],
            'speed_range': [1.0, 1.0],
            'use_speaker_boost': True,
            'model_id': 'eleven_monolingual_v1',
            'output_format': 'mp3_44100_128'
        }
        
        # Execute task (note: this runs synchronously, not via Celery)
        result = regenerate_line_takes(
            generation_job_db_id=regen_job_id,
            batch_id=self.__class__.batch_id,
            line_key=self.__class__.test_line_key,
            line_text=self.__class__.test_line_text,
            num_new_takes=1,
            settings_json=json.dumps(settings),
            replace_existing=False,
            update_script=False
        )
        
        print(f"Regeneration task result: {result}")
        
        # Check the job status in the database
        db = next(models.get_db())
        try:
            job = db.query(models.GenerationJob).get(regen_job_id)
            self.assertIsNotNone(job)
            print(f"Regeneration job status: {job.status}")
            print(f"Regeneration job message: {job.result_message}")
        finally:
            db.close()

    def test_05_api_regenerate_line(self):
        """Test line regeneration via API endpoint."""
        # Skip if we don't have batch ID from previous tests
        if not all(hasattr(self.__class__, attr) for attr in ['batch_id', 'test_line_key', 'test_line_text']):
            self.skipTest("Required data from previous tests not available")
            
        # Call the regenerate endpoint
        response = self.client.post(f'/api/batch/{self.__class__.batch_id}/regenerate_line', json={
            'line_key': self.__class__.test_line_key,
            'line_text': self.__class__.test_line_text,
            'num_new_takes': 1,
            'settings': {
                'stability_range': [0.5, 0.6],
                'similarity_boost_range': [0.75, 0.8],
                'style_range': [0.0, 0.1],
                'speed_range': [1.0, 1.0],
                'use_speaker_boost': True
            },
            'replace_existing': False,
            'update_script': False
        })
        
        # Check response
        self.assertEqual(response.status_code, 202, f"Failed to start regeneration: {response.data}")
        data = json.loads(response.data)
        self.assertIn('data', data)
        self.assertIn('job_id', data['data'])
        
        # Check job status after a brief wait
        time.sleep(2)
        job_id = data['data']['job_id']
        db = next(models.get_db())
        try:
            job = db.query(models.GenerationJob).get(job_id)
            self.assertIsNotNone(job)
            print(f"API regeneration job status: {job.status}")
            print(f"API regeneration job message: {job.result_message}")
        finally:
            db.close()

    def test_06_list_batches(self):
        """Test listing batches API endpoint."""
        response = self.client.get('/api/batches')
        
        # Check response
        self.assertEqual(response.status_code, 200, f"Failed to list batches: {response.data}")
        data = json.loads(response.data)
        self.assertIn('data', data)
        
        # We should have at least one batch from our generation test
        self.assertGreater(len(data['data']), 0)
        
        # Print batch info for debugging
        print(f"Found {len(data['data'])} batches:")
        for i, batch in enumerate(data['data']):
            print(f"  {i+1}. Batch: {batch.get('batch_prefix')}")

    def test_07_get_batch_metadata(self):
        """Test getting batch metadata API endpoint."""
        # Skip if batch_id not available
        if not hasattr(self.__class__, 'batch_id'):
            self.skipTest("Batch ID not available from previous tests")
            
        response = self.client.get(f'/api/batch/{self.__class__.batch_id}')
        
        # Check response
        self.assertEqual(response.status_code, 200, f"Failed to get batch metadata: {response.data}")
        data = json.loads(response.data)
        self.assertIn('data', data)
        
        # Verify basic batch metadata structure
        batch_data = data['data']
        self.assertIn('takes', batch_data)
        self.assertIn('batch_id', batch_data)
        self.assertIn('skin_name', batch_data)
        self.assertIn('voice_name', batch_data)
        
        # Print take info for debugging
        print(f"Batch has {len(batch_data['takes'])} takes")
        if batch_data['takes']:
            # Save a take for crop test
            take = batch_data['takes'][0]
            self.__class__.test_take_r2_key = take.get('r2_key')
            print(f"Selected take for crop test: {self.__class__.test_take_r2_key}")

    def test_08_crop_audio_take(self):
        """Test cropping an audio take via API endpoint."""
        # Skip if test_take_r2_key not available
        if not hasattr(self.__class__, 'test_take_r2_key'):
            self.skipTest("Take R2 key not available from previous tests")
            
        # Extract batch_prefix and filename from r2_key
        parts = self.__class__.test_take_r2_key.split('/takes/')
        if len(parts) != 2:
            self.skipTest(f"Invalid R2 key format: {self.__class__.test_take_r2_key}")
            
        batch_prefix = parts[0]
        filename = parts[1]
        
        # Call the crop endpoint
        response = self.client.post(f'/api/batch/{batch_prefix}/takes/{filename}/crop', json={
            'startTime': 0.2,
            'endTime': 1.5
        })
        
        # Check response
        self.assertEqual(response.status_code, 202, f"Failed to start crop: {response.data}")
        data = json.loads(response.data)
        self.assertIn('data', data)
        self.assertIn('task_id', data['data'])
        
        # The crop task ID will be used in the worker (asynchronously)
        print(f"Crop task ID: {data['data']['task_id']}")
        
        # Note: We're not waiting for the crop to complete since it's async and may require worker

    def test_09_update_take_rank(self):
        """Test updating a take's rank via API endpoint."""
        # Skip if test_take_r2_key not available
        if not hasattr(self.__class__, 'test_take_r2_key'):
            self.skipTest("Take R2 key not available from previous tests")
            
        # Extract batch_prefix and filename from r2_key
        parts = self.__class__.test_take_r2_key.split('/takes/')
        if len(parts) != 2:
            self.skipTest(f"Invalid R2 key format: {self.__class__.test_take_r2_key}")
            
        batch_prefix = parts[0]
        filename = parts[1]
        
        # Call the update rank endpoint
        response = self.client.patch(f'/api/batch/{batch_prefix}/take/{filename}', json={
            'rank': 1
        })
        
        # Check response
        self.assertEqual(response.status_code, 200, f"Failed to update rank: {response.data}")
        data = json.loads(response.data)
        self.assertIn('data', data)
        self.assertIn('updated_take', data['data'])
        
        # Verify rank was updated
        updated_take = data['data']['updated_take']
        self.assertEqual(updated_take['rank'], 1)
        print(f"Updated take rank for {filename}")

if __name__ == '__main__':
    unittest.main() 