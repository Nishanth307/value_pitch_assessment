import time
import random
import threading
import requests
from datetime import datetime, timezone
from pymongo import MongoClient
from config import Config

# Target endpoint
TARGET_URL = "http://127.0.0.1:5000/api/v1/verify"

def run_load_test():
    print("Connecting to MongoDB to load clients and users...")
    mongo_client = MongoClient(Config.MONGO_URI)
    db = mongo_client[Config.MONGO_DB_NAME]
    
    clients = list(db.clients.find({}))
    if not clients:
        print("No clients found in the database. Did you run scripts/seed.py?")
        return
        
    client_map = {c["client_id"]: c for c in clients}
    
    # Load users per client
    users_by_client = {}
    for cid in client_map:
        users = list(db.client_users.find({"client_id": cid}))
        users_by_client[cid] = [u["user_id"] for u in users] if users else ["default_user"]
        
    print(f"Loaded {len(clients)} clients from database.")
    
    # Thread-safe metrics tracking
    metrics_lock = threading.Lock()
    # Schema: client_id -> { sent, succeeded, rate_limited, ip_blocked, vendor_failed, other_errors }
    metrics = {
        cid: {
            "sent": 0,
            "succeeded": 0,
            "rate_limited": 0,
            "ip_blocked": 0,
            "vendor_failed": 0,
            "other_errors": 0
        } for cid in client_map
    }
    
    # Test control
    duration_seconds = 10
    end_time = time.time() + duration_seconds
    active = True
    
    def client_worker(client_id, target_rate_tps):
        """Worker targeting a specific client's API traffic rate."""
        nonlocal active
        client_doc = client_map[client_id]
        api_key = client_doc["api_key"]
        whitelisted_ips = client_doc["whitelisted_ips"]
        users = users_by_client[client_id]
        
        interval = 1.0 / target_rate_tps
        
        while active and time.time() < end_time:
            # 1. Prepare Request Data
            user_id = random.choice(users)
            
            # Spoof IP: 80% chance of a whitelisted IP, 20% chance of a blocked IP
            if random.random() < 0.8:
                ip = random.choice(whitelisted_ips)
            else:
                ip = f"192.168.10.{random.randint(10, 200)}"
                
            # Random synthetic payload
            client_ref_id = f"ref_{random.randint(100000, 999999)}"
            id_type = random.choice(["PAN", "DL", "VOTER"])
            
            # 10% chance of name mismatch ID ending in 99
            if random.random() < 0.1:
                id_num = f"ID{random.randint(10000, 99999)}99"
            else:
                id_num = f"ID{random.randint(10000, 99999)}"
                
            name = f"User {random.randint(1, 100)}"
            
            headers = {
                "X-API-Key": api_key,
                "X-User-Id": user_id,
                "X-Forwarded-For": ip,
                "Content-Type": "application/json"
            }
            
            payload = {
                "client_ref_id": client_ref_id,
                "id_type": id_type,
                "id_number": id_num,
                "name": name
            }
            
            # 2. Fire Request
            try:
                # Track request start
                with metrics_lock:
                    metrics[client_id]["sent"] += 1
                    
                res = requests.post(TARGET_URL, headers=headers, json=payload, timeout=2.0)
                
                with metrics_lock:
                    status_code = res.status_code
                    if status_code == 200:
                        metrics[client_id]["succeeded"] += 1
                    elif status_code == 429:
                        metrics[client_id]["rate_limited"] += 1
                    elif status_code == 403:
                        metrics[client_id]["ip_blocked"] += 1
                    elif status_code == 502:
                        metrics[client_id]["vendor_failed"] += 1
                    else:
                        metrics[client_id]["other_errors"] += 1
                        
            except requests.exceptions.RequestException:
                with metrics_lock:
                    metrics[client_id]["other_errors"] += 1
                    
            # 3. Rate Control Delay
            # Add small noise to delay to simulate dynamic real-world requests
            time.sleep(interval * random.uniform(0.8, 1.2))

    print(f"\nStarting load test for {duration_seconds} seconds...")
    print("Ensure the Flask app is running at http://127.0.0.1:5000/")
    
    threads = []
    # 1. Drive alphabank: limit 5 TPS. We target 9 TPS (should trigger rate limit VP4029)
    threads.append(threading.Thread(target=client_worker, args=("alphabank", 9)))
    
    # 2. Drive zetafin: limit 8 TPS. We target 6 TPS (should stay inside limits)
    threads.append(threading.Thread(target=client_worker, args=("zetafin", 6)))
    
    # 3. Drive novahr: limit 3 TPS. We target 4.5 TPS (should trigger rate limit VP4029)
    threads.append(threading.Thread(target=client_worker, args=("novahr", 4.5)))
    
    start_time = time.time()
    for t in threads:
        t.start()
        
    # Wait for completion
    try:
        while time.time() < end_time:
            time.sleep(1)
            elapsed = int(time.time() - start_time)
            if elapsed % 10 == 0:
                print(f"Running... {elapsed}/{duration_seconds} seconds elapsed.")
    except KeyboardInterrupt:
        print("\nLoad test interrupted by user.")
        
    active = False
    for t in threads:
        t.join()
        
    total_duration = time.time() - start_time
    
    print("\n" + "=" * 60)
    print(f"LOAD TEST COMPLETED (Duration: {total_duration:.2f} seconds)")
    print("=" * 60)
    for cid, counts in metrics.items():
        print(f"Client: {cid.upper()}")
        print(f"  Requests Sent:   {counts['sent']}")
        print(f"  Success (200):   {counts['succeeded']}")
        print(f"  Rate Ltd (429):  {counts['rate_limited']}")
        print(f"  IP Blocked (403):{counts['ip_blocked']}")
        print(f"  Vendor Fail(502):{counts['vendor_failed']}")
        print(f"  Other Errors:    {counts['other_errors']}")
        print("-" * 60)
        
    today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print("\nCROSS-CHECK ANALYTICS:")
    print("Ensure you query the MIS blueprints using X-Admin-Key to verify logs match:")
    print(f"GET http://127.0.0.1:5000/api/v1/mis/usage?from={today_iso}T00:00:00Z&to={today_iso}T23:59:59Z&group_by=client")
    print(f"GET http://127.0.0.1:5000/api/v1/mis/ips?client_id=alphabank&from={today_iso}T00:00:00Z&to={today_iso}T23:59:59Z")
    print(f"GET http://127.0.0.1:5000/api/v1/mis/tps?client_id=alphabank&date={today_iso}")
    print("=" * 60)

if __name__ == "__main__":
    run_load_test()
