// async function main() {
//   const [deployer] = await ethers.getSigners();
//   console.log("Deployer:", deployer.address);

//   const EventLog = await ethers.getContractFactory("EventLog");
//   const c = await EventLog.deploy(deployer.address);
//   await c.waitForDeployment();

//   console.log("EventLog deployed to:", await c.getAddress());
// }
// main().catch((e) => {
//   console.error(e);
//   process.exit(1);
// });

const fs = require("fs");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deployer:", deployer.address);

  const EventLog = await ethers.getContractFactory("EventLog");
  const c = await EventLog.deploy(deployer.address);
  await c.waitForDeployment();

  const addr = await c.getAddress();
  console.log("EventLog deployed to:", addr);

  // Write to artifacts/deployed.json (this folder is shared to API via volume)
  const out = {
    chainId: (await ethers.provider.getNetwork()).chainId.toString(),
    deployedAt: new Date().toISOString(),
    deployer: deployer.address,
    contracts: {
      EventLog: addr,
    },
  };

  fs.mkdirSync("artifacts", { recursive: true });
  fs.writeFileSync("artifacts/deployed.json", JSON.stringify(out, null, 2));
  console.log("Wrote artifacts/deployed.json");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
