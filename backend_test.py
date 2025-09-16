import requests
import sys
import json
import io
import time
from datetime import datetime

class DigitalNativeAnalyzerTester:
    def __init__(self, base_url="https://saas-match-scores.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.batch_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None, response_type='json'):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}" if not endpoint.startswith('http') else endpoint
        headers = {}
        
        if files is None and data is not None:
            headers['Content-Type'] = 'application/json'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files)
                else:
                    response = requests.post(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                
                if response_type == 'json' and response.content:
                    try:
                        response_data = response.json()
                        print(f"   Response: {json.dumps(response_data, indent=2)[:200]}...")
                        return success, response_data
                    except:
                        return success, {}
                else:
                    return success, response.content
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Error: {error_detail}")
                except:
                    print(f"   Error: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def create_test_csv(self):
        """Create a test CSV file with sample companies"""
        csv_content = """name,domain,industry,founded_year,employee_count,location,description
Stripe,stripe.com,Fintech,2010,4000,San Francisco,Online payment processing platform
Shopify,shopify.com,E-commerce,2006,10000,Ottawa,E-commerce platform for online stores
DataDog,datadoghq.com,Monitoring,2010,3000,New York,Cloud monitoring and analytics platform
MongoDB,mongodb.com,Database,2007,3500,New York,Document database platform
Slack,slack.com,Communication,2009,2500,San Francisco,Business communication platform"""
        
        return io.StringIO(csv_content)

    def test_root_endpoint(self):
        """Test the root API endpoint"""
        return self.run_test(
            "Root API Endpoint",
            "GET",
            "",
            200
        )

    def test_csv_upload(self):
        """Test CSV upload and batch creation"""
        csv_file = self.create_test_csv()
        files = {'file': ('test_companies.csv', csv_file.getvalue(), 'text/csv')}
        
        success, response = self.run_test(
            "CSV Upload and Batch Creation",
            "POST",
            "analyze-csv",
            200,
            files=files
        )
        
        if success and 'batch_id' in response:
            self.batch_id = response['batch_id']
            print(f"   Batch ID: {self.batch_id}")
            return True
        return False

    def test_invalid_csv_upload(self):
        """Test invalid CSV upload (missing required columns)"""
        invalid_csv = "company,website\nTest Company,test.com"
        files = {'file': ('invalid.csv', invalid_csv, 'text/csv')}
        
        return self.run_test(
            "Invalid CSV Upload (Missing Required Columns)",
            "POST",
            "analyze-csv",
            400,
            files=files
        )

    def test_non_csv_upload(self):
        """Test non-CSV file upload"""
        files = {'file': ('test.txt', 'This is not a CSV', 'text/plain')}
        
        return self.run_test(
            "Non-CSV File Upload",
            "POST",
            "analyze-csv",
            400,
            files=files
        )

    def test_progress_tracking(self):
        """Test progress tracking for a batch"""
        if not self.batch_id:
            print("❌ No batch ID available for progress testing")
            return False
            
        return self.run_test(
            "Progress Tracking",
            "GET",
            f"progress/{self.batch_id}",
            200
        )

    def test_invalid_batch_progress(self):
        """Test progress tracking for non-existent batch"""
        fake_batch_id = "00000000-0000-0000-0000-000000000000"
        return self.run_test(
            "Invalid Batch Progress",
            "GET",
            f"progress/{fake_batch_id}",
            404
        )

    def test_results_retrieval(self):
        """Test results retrieval for a batch"""
        if not self.batch_id:
            print("❌ No batch ID available for results testing")
            return False
            
        # Wait a bit for analysis to potentially start
        print("   Waiting 5 seconds for analysis to begin...")
        time.sleep(5)
            
        return self.run_test(
            "Results Retrieval",
            "GET",
            f"results/{self.batch_id}",
            200
        )

    def test_invalid_batch_results(self):
        """Test results retrieval for non-existent batch"""
        fake_batch_id = "00000000-0000-0000-0000-000000000000"
        return self.run_test(
            "Invalid Batch Results",
            "GET",
            f"results/{fake_batch_id}",
            404
        )

    def test_export_functionality(self):
        """Test Excel export functionality"""
        if not self.batch_id:
            print("❌ No batch ID available for export testing")
            return False
            
        success, response = self.run_test(
            "Excel Export",
            "GET",
            f"export/{self.batch_id}",
            200,
            response_type='binary'
        )
        
        if success:
            print(f"   Export file size: {len(response)} bytes")
            
        return success

    def test_invalid_batch_export(self):
        """Test export for non-existent batch"""
        fake_batch_id = "00000000-0000-0000-0000-000000000000"
        return self.run_test(
            "Invalid Batch Export",
            "GET",
            f"export/{fake_batch_id}",
            404
        )

    def test_get_all_companies(self):
        """Test getting all companies"""
        return self.run_test(
            "Get All Companies",
            "GET",
            "companies",
            200
        )

    def test_batch_deletion(self):
        """Test batch deletion"""
        if not self.batch_id:
            print("❌ No batch ID available for deletion testing")
            return False
            
        return self.run_test(
            "Batch Deletion",
            "DELETE",
            f"batch/{self.batch_id}",
            200
        )

    def test_invalid_batch_deletion(self):
        """Test deletion of non-existent batch"""
        fake_batch_id = "00000000-0000-0000-0000-000000000000"
        return self.run_test(
            "Invalid Batch Deletion",
            "DELETE",
            f"batch/{fake_batch_id}",
            404
        )

def main():
    print("🚀 Starting Digital Native Analyzer API Tests")
    print("=" * 60)
    
    tester = DigitalNativeAnalyzerTester()
    
    # Test sequence
    test_functions = [
        tester.test_root_endpoint,
        tester.test_csv_upload,
        tester.test_invalid_csv_upload,
        tester.test_non_csv_upload,
        tester.test_progress_tracking,
        tester.test_invalid_batch_progress,
        tester.test_results_retrieval,
        tester.test_invalid_batch_results,
        tester.test_export_functionality,
        tester.test_invalid_batch_export,
        tester.test_get_all_companies,
        tester.test_batch_deletion,
        tester.test_invalid_batch_deletion
    ]
    
    # Run all tests
    for test_func in test_functions:
        try:
            test_func()
        except Exception as e:
            print(f"❌ Test failed with exception: {str(e)}")
            tester.tests_run += 1
    
    # Print final results
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())