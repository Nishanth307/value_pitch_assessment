import secrets
import random
import hashlib
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient, ASCENDING, DESCENDING
from app.config import Config

# Helper functions for generating compliance hashes and masks
def mask_id_number(id_num: str) -> str:
    if not id_num:
        return ""
    length = len(id_num)
    if length <= 4:
        return "*" * (length - 1) + id_num[-1:] if length > 0 else ""
    return "*" * (length - 4) + id_num[-4:]

def mask_name(name: str) -> str:
    if not name:
        return ""
    words = name.split()
    return " ".join([w[0] + "*" * (len(w) - 1) if len(w) > 1 else w for w in words])

def hash_value(val: str) -> str:
    if not val:
        return ""
    return hashlib.sha256(val.encode("utf-8")).hexdigest()

def seed_db():
    print("Connecting to MongoDB...")
    client = MongoClient(Config.MONGO_URI)
    db = client[Config.MONGO_DB_NAME]
    
    print(f"Using database: {Config.MONGO_DB_NAME}")
    
    # 1. Drop and recreate clients collection
    print("Seeding 'clients' collection...")
    db.clients.drop()
    
    clients_data = [
        {
            "client_id": "alphabank",
            "name": "Alpha Bank",
            "api_key": secrets.token_hex(24),
            "whitelisted_ips": ["127.0.0.1", "192.168.1.100", "10.0.0.5"],
            "tps_limit": 5,
            "status": "active"
        },
        {
            "client_id": "zetafin",
            "name": "Zeta Financial",
            "api_key": secrets.token_hex(24),
            "whitelisted_ips": ["127.0.0.1", "192.168.1.101", "10.0.0.6"],
            "tps_limit": 8,
            "status": "active"
        },
        {
            "client_id": "novahr",
            "name": "Nova HR Solutions",
            "api_key": secrets.token_hex(24),
            "whitelisted_ips": ["127.0.0.1", "192.168.1.102"],
            "tps_limit": 3,
            "status": "active"
        }
    ]
    
    db.clients.insert_many(clients_data)
    
    # Create indexes for clients
    db.clients.create_index("client_id", unique=True)
    db.clients.create_index("api_key", unique=True)
    
    # 2. Drop and recreate client_users collection
    print("Seeding 'client_users' collection...")
    db.client_users.drop()
    
    client_users_data = [
        # Alpha Bank Users
        {"user_id": "ab_ops_01", "client_id": "alphabank", "name": "AB Ops One", "status": "active"},
        {"user_id": "ab_ops_02", "client_id": "alphabank", "name": "AB Ops Two", "status": "active"},
        # Zeta Financial Users
        {"user_id": "zf_ops_01", "client_id": "zetafin", "name": "ZF Ops One", "status": "active"},
        {"user_id": "zf_ops_02", "client_id": "zetafin", "name": "ZF Ops Two", "status": "active"},
        # Nova HR Users
        {"user_id": "nh_ops_01", "client_id": "novahr", "name": "NH Ops One", "status": "active"},
        {"user_id": "nh_ops_02", "client_id": "novahr", "name": "NH Ops Two", "status": "active"}
    ]
    
    db.client_users.insert_many(client_users_data)
    
    # Create indexes for client_users
    db.client_users.create_index([("client_id", ASCENDING), ("user_id", ASCENDING)], unique=True)
    
    # 3. Create indexes on api_logs
    print("Ensuring indexes exist on 'api_logs' collection...")
    db.api_logs.drop()
    db.api_logs.create_index([("client_id", ASCENDING), ("created_at", DESCENDING)])
    db.api_logs.create_index("error_code")
    
    # 4. Generate ~3000 historical log records spread across the last 15 days
    print("Seeding ~3000 synthetic historical log records across last 15 days...")
    
    clients_list = list(db.clients.find({}))
    users_by_client = {
        "alphabank": ["ab_ops_01", "ab_ops_02"],
        "zetafin": ["zf_ops_01", "zf_ops_02"],
        "novahr": ["nh_ops_01", "nh_ops_02"]
    }
    
    # Simulated names & IDs
    first_names = ["Rahul", "Anjali", "Sanjay", "Preeti", "Amit", "Deepa", "Vikram", "Neha", "Rajesh", "Pooja"]
    last_names = ["Sharma", "Verma", "Patel", "Singh", "Joshi", "Gupta", "Mehta", "Reddy", "Kumar", "Iyer"]
    
    error_pool = [
        ("VP2000", 200, "A", False, False),  # Primary Success
        ("VP2000", 200, "A", False, False),
        ("VP2000", 200, "A", False, False),
        ("VP2001", 200, "B", True, False),   # Fallback Success
        ("VP2002", 200, "A", False, False),  # Not Verified (Primary)
        ("VP2002", 200, "B", True, False),   # Not Verified (Fallback)
        ("VP4003", 403, None, False, False), # IP Blocked
        ("VP4022", 422, None, False, False), # Validation Fail
        ("VP4029", 429, None, False, False), # TPS Limit Exceeded
        ("VP5001", 502, "B", True, False)    # Double Vendor Fail
    ]
    
    log_records = []
    base_time = datetime.now(timezone.utc)
    
    for i in range(3000):
        # Determine timestamp spread over last 15 days
        offset_days = random.randint(0, 15)
        offset_hours = random.randint(0, 23)
        offset_mins = random.randint(0, 59)
        offset_secs = random.randint(0, 59)
        created_at = base_time - timedelta(days=offset_days, hours=offset_hours, minutes=offset_mins, seconds=offset_secs)
        
        # Pick client and user
        client = random.choice(clients_list)
        client_id = client["client_id"]
        user_id = random.choice(users_by_client[client_id])
        
        # Determine IP
        if random.random() < 0.9:
            ip = random.choice(client["whitelisted_ips"])
        else:
            ip = f"103.24.10.{random.randint(1, 254)}"
            
        # Error Code setup
        if ip not in client["whitelisted_ips"]:
            error_code, http_status, vendor_used, fallback_used, circuit_open = "VP4003", 403, None, False, False
        else:
            error_code, http_status, vendor_used, fallback_used, circuit_open = random.choice(error_pool)
            
        # PII preparation
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        id_num = f"ABCDE{random.randint(1000, 9999)}F"
        
        latency_ms = 0
        if vendor_used == "A":
            latency_ms = random.randint(100, 600)
        elif vendor_used == "B":
            latency_ms = random.randint(200, 1200)
            
        record = {
            "request_id": f"req_{secrets.token_hex(4)}",
            "client_id": client_id,
            "user_id": user_id,
            "ip": ip,
            "endpoint": "/api/v1/verify",
            "id_type": random.choice(["PAN", "DL", "VOTER"]),
            "masked_id_number": mask_id_number(id_num),
            "id_number_hash": hash_value(id_num),
            "masked_name": mask_name(name),
            "name_hash": hash_value(name),
            "http_status": http_status,
            "error_code": error_code,
            "vendor_used": vendor_used,
            "fallback_used": fallback_used,
            "circuit_open": circuit_open,
            "latency_ms": latency_ms,
            "created_at": created_at
        }
        log_records.append(record)
        
    db.api_logs.insert_many(log_records)
    print(f"Successfully inserted {len(log_records)} mock transactions into 'api_logs'!")
    
    print("\nDatabase seeded successfully!")
    print("=" * 60)
    print("GENERATED CLIENT API KEYS (Save these for testing):")
    for client_doc in db.clients.find():
        print(f"Client: {client_doc['name']} ({client_doc['client_id']})")
        print(f"  API Key: {client_doc['api_key']}")
        print(f"  TPS Limit: {client_doc['tps_limit']}")
        print(f"  IP Whitelist: {client_doc['whitelisted_ips']}")
        print("-" * 60)

if __name__ == "__main__":
    seed_db()
