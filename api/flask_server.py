import os
import json
from typing import Any, Union, List, Dict, Optional
from datetime import datetime, timezone

from flask import Flask, request, jsonify
from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account

# Load env (.env in current working directory by default)
load_dotenv()

# ----------------------------
# Config
# ----------------------------
RPC_URL = os.getenv("RPC_URL", "http://127.0.0.1:8545")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
ARTIFACT_PATH = os.getenv("ARTIFACT_PATH", "./artifacts/contracts/EventLog.sol/EventLog.json")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")  # optional override
DEPLOYED_JSON_PATH = os.getenv("DEPLOYED_JSON_PATH", "/artifacts/deployed.json")

def load_contract_address_from_file(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("contracts", {}).get("EventLog")
    except Exception:
        return None

if not CONTRACT_ADDRESS:
    CONTRACT_ADDRESS = load_contract_address_from_file(DEPLOYED_JSON_PATH)


print("DEBUG CONTRACT_ADDRESS:", CONTRACT_ADDRESS)
print("DEBUG PRIVATE_KEY starts:", (PRIVATE_KEY[:10] + "...") if PRIVATE_KEY else None)

if not CONTRACT_ADDRESS:
    raise RuntimeError("Missing CONTRACT_ADDRESS and could not read it from deployed.json at "
        f"{DEPLOYED_JSON_PATH}")
if not PRIVATE_KEY:
    raise RuntimeError("Missing PRIVATE_KEY env var")

# w3 = Web3(Web3.HTTPProvider(RPC_URL))
# if not w3.is_connected():
#     raise RuntimeError(f"Cannot connect to RPC at {RPC_URL}")
w3 = Web3(Web3.HTTPProvider(RPC_URL))

def is_rpc_up() -> bool:
    try:
        return w3.is_connected()
    except Exception:
        return False


acct = Account.from_key(PRIVATE_KEY)

if not os.path.exists(ARTIFACT_PATH):
    raise RuntimeError(
        f"ABI artifact not found at {ARTIFACT_PATH}. "
        f"Run: npm install && npm run compile"
    )

with open(ARTIFACT_PATH, "r", encoding="utf-8") as f:
    artifact = json.load(f)

ABI = artifact.get("abi")
if not ABI:
    raise RuntimeError("ABI missing in artifact JSON")

contract = w3.eth.contract(
    address=Web3.to_checksum_address(CONTRACT_ADDRESS),
    abi=ABI
)

# ----------------------------
# Helpers
# ----------------------------
def b32_from_text(text: str) -> bytes:
    return Web3.keccak(text=text)

def keccak_json(details: Union[dict, list, str]) -> bytes:
    if isinstance(details, (dict, list)):
        payload = json.dumps(details, sort_keys=True, separators=(",", ":"))
    else:
        payload = str(details)
    return Web3.keccak(text=payload)

def safe_int(x: Any) -> int:
    try:
        return int(x)
    except Exception:
        return 0

def iso_utc_from_unix(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")

# ----------------------------
# Flask app
# ----------------------------
app = Flask(__name__)

# @app.get("/health")
# def health():
#     return jsonify({
#         "ok": True,
#         "rpc": RPC_URL,
#         "connected": w3.is_connected(),
#         "contract": CONTRACT_ADDRESS,
#         "signer": acct.address,
#         "artifact": ARTIFACT_PATH,
#     }), 200

@app.route("/health", methods=["GET"])
def health():
    connected = is_rpc_up()
    return jsonify({
        "ok": True,
        "rpc": RPC_URL,
        "connected": connected,
        "contract": CONTRACT_ADDRESS,
        "signer": getattr(acct, "address", None),
        "artifact": ARTIFACT_PATH,
    }), (200 if connected else 503)


@app.post("/log")
def commit_log():
    """
    Body:
    {
      "recordId": "ORDER_1",
      "action": "crawl_check",
      "details": {...},
      "uri": "local://ORDER_1/1"
    }
    """
    try:
        body = request.get_json(force=True, silent=False)

        record_id = body.get("recordId")
        action = body.get("action")   # prefer action (matches Solidity)
        details = body.get("details")
        uri = body.get("uri", "") or ""

        if not record_id:
            return jsonify({"ok": False, "error": "Missing required field: recordId"}), 400
        if not action:
            return jsonify({"ok": False, "error": "Missing required field: action"}), 400
        if details is None:
            return jsonify({"ok": False, "error": "Missing required field: details"}), 400

        details_hash = keccak_json(details)

        nonce = w3.eth.get_transaction_count(acct.address)

        tx = contract.functions.commitLog(
            b32_from_text(record_id),
            action,          # string
            details_hash,
            uri
        ).build_transaction({
            "from": acct.address,
            "nonce": nonce,
            "gas": 350_000,
            "gasPrice": w3.eth.gas_price
        })

        signed = acct.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        return jsonify({
            "ok": True,
            "txHash": receipt.transactionHash.hex(),
            "detailsHash": "0x" + details_hash.hex(),
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# @app.get("/logs/<record_id>")
@app.route("/logs/<record_id>", methods=["GET"])
def get_logs(record_id: str):
    """
    Fetch EventLogged events for this recordId by filtering indexed topic.
    """
    try:
        record_id_b32 = b32_from_text(record_id)

        # Must match your Solidity event:
        # EventLogged(bytes32,string,bytes32,string,address,uint256,uint256)
        topic0 = "0x" + w3.keccak(
            text="EventLogged(bytes32,string,bytes32,string,address,uint256,uint256)"
        ).hex()

        topic1 = "0x" + record_id_b32.hex()

        raw_logs = w3.eth.get_logs({
            "fromBlock": 0,
            "toBlock": "latest",
            "address": contract.address,
            "topics": [topic0, topic1],
        })

        out = []
        for log in raw_logs:
            decoded = contract.events.EventLogged().process_log(log)
            args = decoded["args"]

            ts = safe_int(args["timestamp"])
            out.append({
                "blockNumber": log["blockNumber"],
                "txHash": log["transactionHash"].hex(),
                "recordIdHash": "0x" + args["recordId"].hex(),
                "action": args["action"],
                "detailsHash": "0x" + args["detailsHash"].hex(),
                "uri": args["uri"],
                "actor": args["actor"],
                "seq": safe_int(args["seq"]),
                "timestamp": ts,
                "timestampIso": iso_utc_from_unix(ts),
            })

        return jsonify({"ok": True, "count": len(out), "events": out})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    # Dev server (for PoC only)
    app.run(host="0.0.0.0", port=8000, debug=False)
