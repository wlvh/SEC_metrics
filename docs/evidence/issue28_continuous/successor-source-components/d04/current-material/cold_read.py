import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1]+"/scripts")
def deny(event,args):
 if event in ("socket.connect","socket.connect_ex","socket.getaddrinfo"): raise RuntimeError("NO_NETWORK_D04_COLD_READ")
sys.addaudithook(deny)
from vnext.going_concern_source import verify_ordinary_going_concern_source
p=json.loads(Path(sys.argv[2]).read_text())
r=verify_ordinary_going_concern_source(packet=p,repo_root=Path(sys.argv[1]),company_id=sys.argv[3])
print(json.dumps({"status":"SOURCE_PACKET_REBUILT_FROM_ORIGINAL_BYTES","packet_id":r["packet_id"],"documents":len(r["components"]),"not_disclosed_confirmed":r["not_disclosed_confirmed"],"native_result_created":r["native_result_created"],"calls":r["calls"]}))
