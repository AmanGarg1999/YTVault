import requests
import sys

def check_health():
    try:
        r = requests.get("http://localhost:8501", timeout=5)
        print(f"Status: {r.status_code}")
        if "Streamlit" in r.text:
            print("Streamlit detected in HTML.")
        else:
            print("Streamlit NOT detected in HTML.")
            print(r.text[:500])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_health()
