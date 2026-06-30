import os
import time
import requests

# Base URL for your Scrutinize backend
BASE_URL = "http://localhost:8000"

# Change these to match your project credentials
PROJECT_NAME = "ammer"
PROJECT_PASSWORD = "ammer@1234"

def main():
    print(f"=== Scrutinize API Integration Example ===")
    print(f"Connecting to {BASE_URL}...\n")

    # 1. Login (or Signup) to get API Keys
    # Standard practice: Authenticate once to exchange your password for secure keys.
    keys = authenticate()
    if not keys:
        return
    
    api_key = keys.get("api_key")
    client_key = keys.get("client_key")
    
    print(f"✅ Successfully Authenticated!")
    print(f"   API Key (Keep Secret! Use for uploads/deletes): {api_key[:8]}...")
    print(f"   Client Key (Safe for frontend chat/search): {client_key[:8]}...\n")

    # 2. Upload a File
    file_id = upload_file(api_key, "sample_document.txt", "This is some test content to upload via the API.")
    
    if not file_id:
        return

    # Wait a few seconds for the background worker to process (embed) the text
    print("⏳ Waiting for backend to process and embed the file (5s)...")
    time.sleep(5)

    # 3. View the Library
    print("\n=== Library Contents ===")
    list_library(api_key)

    # 4. Chat / Search Query
    print("\n=== Chat / Query ===")
    query_data(client_key, "What is the test content about?")

    # 5. Cleanup: Delete the file
    print("\n=== Cleanup ===")
    delete_file(api_key, file_id)


def authenticate():
    """Authenticates the project and returns the API and Client keys."""
    # Try to login first
    response = requests.post(
        f"{BASE_URL}/v2/projects/login",
        json={"name": PROJECT_NAME, "password": PROJECT_PASSWORD}
    )
    
    # If project doesn't exist, sign up
    if response.status_code == 404:
        print("Project not found. Signing up instead...")
        response = requests.post(
            f"{BASE_URL}/v2/projects/signup",
            json={"name": PROJECT_NAME, "password": PROJECT_PASSWORD}
        )
        
    if response.status_code == 200 or response.status_code == 201:
        return response.json()
    else:
        print(f"❌ Auth Failed: {response.status_code} - {response.text}")
        return None


def upload_file(api_key, filename, content):
    """Uploads a file using the administrative API Key."""
    # Write temporary file to upload
    with open(filename, "w") as f:
        f.write(content)
        
    print(f"Uploading '{filename}'...")
    
    # We pass the API Key in the X-Project-Key header
    headers = {"X-Project-Key": api_key}
    
    with open(filename, "rb") as f:
        files = {"file": (filename, f, "text/plain")}
        response = requests.post(f"{BASE_URL}/upload", headers=headers, files=files)
        
    # Cleanup local temp file
    os.remove(filename)
    
    if response.status_code == 200:
        file_id = response.json().get("id")
        print(f"✅ Upload Successful! File ID: {file_id}")
        return file_id
    else:
        print(f"❌ Upload Failed: {response.status_code} - {response.text}")
        return None


def list_library(api_key):
    """Retrieves all files owned by this project."""
    headers = {"X-Project-Key": api_key}
    response = requests.get(f"{BASE_URL}/library", headers=headers)
    
    if response.status_code == 200:
        files = response.json()
        if not files:
            print("   Library is empty.")
        for f in files:
            print(f"   - {f['filename']} (Status: {f['status']}) [ID: {f['id']}]")
    else:
        print(f"❌ Library Fetch Failed: {response.status_code} - {response.text}")


def query_data(client_key, query_text):
    """Queries the data using the read-only Client Key."""
    # We pass the Client Key in the X-Client-Key header
    headers = {"X-Client-Key": client_key}
    payload = {"query": query_text}
    
    print(f"Query: '{query_text}'")
    response = requests.post(f"{BASE_URL}/v2/search", headers=headers, json=payload)
    
    if response.status_code == 200:
        result = response.json()
        print(f"🤖 Answer: {result.get('answer', 'No answer generated')}")
    else:
        print(f"❌ Query Failed: {response.status_code} - {response.text}")


def delete_file(api_key, file_id):
    """Deletes a file from the library."""
    headers = {"X-Project-Key": api_key}
    response = requests.delete(f"{BASE_URL}/library/{file_id}", headers=headers)
    
    if response.status_code == 200:
        print(f"✅ Successfully deleted file: {file_id}")
    else:
        print(f"❌ Delete Failed: {response.status_code} - {response.text}")

if __name__ == "__main__":
    main()
