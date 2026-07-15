from app.extensions import mongo
from .client import Client
from .client_user import ClientUser
from .api_log import ApiLog

# Module-level aliases to maintain compatibility with existing call sites
find_by_api_key = Client.find_by_api_key
find_user = ClientUser.find_user
insert_log = ApiLog.insert_log
run_aggregation = ApiLog.run_aggregation
count_logs = ApiLog.count_logs
