# PoC Blockchain v1

Proof-of-concept blockchain event logging service built with Hardhat, Solidity, Flask, Web3.py, and Docker Compose.

The project starts a local Hardhat blockchain, deploys an `EventLog` smart contract, and exposes a Flask API for writing and reading event logs. Each submitted record stores a hash of the event details on-chain, while the original details can remain off-chain and be referenced by URI.

## Project Structure

```text
.
├── api/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── flask_server.py
│   └── requirements.txt
├── hardhat/
│   ├── contracts/EventLog.sol
│   ├── scripts/deploy.js
│   ├── hardhat.config.js
│   ├── package.json
│   └── artifacts/
├── docker-compose.yml
└── .env
```

## Main Components

- `hardhat`: runs a local Ethereum-compatible blockchain on port `8545`.
- `deployer`: compiles and deploys the `EventLog` smart contract after the Hardhat RPC is ready.
- `api`: starts the Flask API on port `8000` and connects to the deployed contract.

## Smart Contract

The contract is located at `hardhat/contracts/EventLog.sol`.

`EventLog` provides:

- Role-based access control through OpenZeppelin `AccessControl`.
- `LOGGER_ROLE` permission for accounts allowed to write logs.
- `commitLog(recordId, action, detailsHash, uri)` to emit an immutable event.
- Per-record sequence numbering through `lastSeq`.

The emitted event contains:

- `recordId`: indexed hash of the record ID.
- `action`: readable action name.
- `detailsHash`: hash of the event details.
- `uri`: optional pointer to off-chain data.
- `actor`: wallet address that wrote the log.
- `seq`: sequence number for the record.
- `timestamp`: block timestamp.

## Requirements

- Docker
- Docker Compose

For local development without Docker:

- Node.js 20+
- Python 3.11+

## Environment Variables

Do not commit your real `.env` file to GitHub. Create a local `.env` file in the project root by copying `.env.example`:

```bash
cp .env.example .env
```

Then update `PRIVATE_KEY` in `.env`.

```env
PRIVATE_KEY=your_hardhat_account_private_key
# Optional when running outside Docker:
# RPC_URL=http://127.0.0.1:8545
```

`PRIVATE_KEY` must belong to an account that has `LOGGER_ROLE`. In the default local Hardhat setup, the deployer account is granted this role during deployment.

### Getting a Local Hardhat Private Key

Hardhat creates local test accounts when the node starts. These accounts are for local development only and must not be used on a real network.

To get a private key:

1. Start the Hardhat node:

```bash
docker compose up hardhat
```

2. Look at the Hardhat node logs. Hardhat prints a list of test accounts and private keys when it starts.

3. Copy the private key for the first account, which is also the deployer account in this project.

4. Paste it into `.env`:

```env
PRIVATE_KEY=paste_the_hardhat_private_key_here
```

If running Hardhat locally without Docker, you can also get the same list by running this from the `hardhat/` folder:

```bash
npx hardhat node
```

When using Docker Compose, `CONTRACT_ADDRESS` is usually not required because the deployer writes the deployed address to `hardhat/artifacts/deployed.json`, which is mounted into the API container.

## Running with Docker Compose

From the project root:

```bash
docker compose up --build
```

This will:

1. Build the Hardhat and API containers.
2. Start the local Hardhat blockchain.
3. Compile and deploy the `EventLog` smart contract.
4. Write the deployed contract address to `hardhat/artifacts/deployed.json`.
5. Start the Flask API at `http://localhost:8000`.

To stop the services:

```bash
docker compose down
```

## API Endpoints

### Health Check

```http
GET /health
```

Example:

```bash
curl http://localhost:8000/health
```

Example response:

```json
{
  "ok": true,
  "rpc": "http://hardhat:8545",
  "connected": true,
  "contract": "0x...",
  "signer": "0x...",
  "artifact": "/artifacts/contracts/EventLog.sol/EventLog.json"
}
```

### Commit a Log

```http
POST /log
```

Request body:

```json
{
  "recordId": "ORDER_1",
  "action": "crawl_check",
  "details": {
    "status": "ok",
    "source": "crawler"
  },
  "uri": "local://ORDER_1/1"
}
```

Example:

```bash
curl -X POST http://localhost:8000/log \
  -H "Content-Type: application/json" \
  -d '{
    "recordId": "ORDER_1",
    "action": "crawl_check",
    "details": {
      "status": "ok",
      "source": "crawler"
    },
    "uri": "local://ORDER_1/1"
  }'
```

Example response:

```json
{
  "ok": true,
  "txHash": "0x...",
  "detailsHash": "0x..."
}
```

### Get Logs for a Record

```http
GET /logs/<record_id>
```

Example:

```bash
curl http://localhost:8000/logs/ORDER_1
```

Example response:

```json
{
  "ok": true,
  "count": 1,
  "events": [
    {
      "blockNumber": 2,
      "txHash": "0x...",
      "recordIdHash": "0x...",
      "action": "crawl_check",
      "detailsHash": "0x...",
      "uri": "local://ORDER_1/1",
      "actor": "0x...",
      "seq": 1,
      "timestamp": 1730000000,
      "timestampIso": "2024-10-27T00:00:00Z"
    }
  ]
}
```

## Local Hardhat Commands

Run these from the `hardhat/` folder.

Install dependencies:

```bash
npm install
```

Compile contracts:

```bash
npx hardhat compile
```

Start a local node:

```bash
npx hardhat node --hostname 0.0.0.0 --port 8545
```

Deploy the contract:

```bash
npx hardhat run scripts/deploy.js --network localhost
```

## Notes

- The API hashes `recordId` with `keccak256` before querying or writing to the contract.
- The API hashes `details` as canonical JSON using sorted keys and compact separators before writing to the contract.
- The full `details` payload is not stored on-chain. Only its hash is stored.
- `uri` can be used to point to an off-chain file, database record, IPFS object, or local proof artifact.
- This setup is intended as a local proof of concept, not a production deployment.

## Troubleshooting

If the API returns `503` from `/health`, the Flask server is running but cannot connect to the Hardhat RPC.

If the API fails with a missing contract address error, check that:

- The deployer container completed successfully.
- `hardhat/artifacts/deployed.json` exists.
- The API container can read `/artifacts/deployed.json`.

If `/log` fails with an access control error, check that the private key in `.env` belongs to the deployer account or another account with `LOGGER_ROLE`.
