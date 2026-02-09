from pyngrok import ngrok
import time
import sys

def start_tunnel():
    # Set authtoken if not set (optional for public free tier, but recommended)
    # ngrok.set_auth_token("<TOKEN>") 

    # Opening a tunnel to port 8000
    try:
        public_url = ngrok.connect("127.0.0.1:8000").public_url
        print(f"Ngrok Tunnel Started: {public_url}")
        
        # Keep process alive
        while True:
            time.sleep(1)
            
    except Exception as e:
        print(f"Error starting tunnel: {e}")
        sys.exit(1)

if __name__ == "__main__":
    start_tunnel()
